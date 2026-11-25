"""CLI adapter: argv and input parsing, dispatch, envelope, exit codes.

stdout carries exactly one JSON envelope, written as UTF-8 bytes whatever the
console code page is. Diagnostics go to the log file under the data dir.

ADULT_TENSION_TRACE=<file> (set by an evaluation harness, never by a player)
appends one JSON line per call: argv, parsed input, exit code, envelope,
duration and the Skill root that ran. End-to-end records read the tool calls
from there, whatever the host's own transcript looks like; a trace that
cannot be written is reported on stderr.
"""

import json
import os
import sys
import time
import traceback

from .. import schema
from ..application import commands
from ..errors import (
    EXIT_INTERNAL,
    INTERNAL_ERROR,
    INVALID_INPUT,
    AppError,
    detail,
    exit_code_for,
)
from ..jsonio import copy, decode_bytes, dumps, loads_strict

MAX_INPUT_BYTES = 32 * 1024 * 1024
GLOBAL_FLAGS = {
    "--json": "bool",
    "--pretty": "bool",
    "--debug": "bool",
    "--input-file": "str",
    "--data-dir": "str",
}


def new_request_id():
    return "r_" + os.urandom(6).hex()


def parse_argv(argv):
    """Return (command, options, command_flags) or raise INVALID_INPUT."""
    if not argv or argv[0].startswith("-"):
        raise AppError(
            INVALID_INPUT,
            "缺少命令",
            [detail("$.argv[0]", "第一个参数必须是命令名", "可用命令：%s" % "、".join(sorted(commands.COMMANDS)))],
        )
    name = argv[0]
    command = commands.get(name)
    if command is None:
        raise AppError(
            INVALID_INPUT,
            "未知命令：%s" % name,
            [detail("$.argv[0]", "未知命令：%s" % name, "可用命令：%s" % "、".join(sorted(commands.COMMANDS)))],
        )
    options = {}
    flags = {}
    problems = []
    bool_flags = {f for f, k in GLOBAL_FLAGS.items() if k == "bool"} | {f for f, (_k, k) in command.flags.items() if k == "bool"} | {"--help", "-h"}
    index = 1
    while index < len(argv):
        item = argv[index]
        value = None
        if item.startswith("--") and "=" in item:
            item, value = item.split("=", 1)
        if item in GLOBAL_FLAGS:
            kind, target, key = GLOBAL_FLAGS[item], options, item[2:].replace("-", "_")
        elif item in command.flags:
            key, kind = command.flags[item]
            target = flags
        else:
            problems.append(detail("$.argv[%d]" % index, "未知参数：%s" % item, "命令 %s 可用参数：%s" % (name, "、".join(list(GLOBAL_FLAGS) + list(command.flags)))))
            index += 1
            continue
        if kind == "bool":
            if value is not None:
                problems.append(detail("$.argv[%d]" % index, "%s 不接受取值" % item, None))
            target[key] = True
            index += 1
            continue
        arg_idx = index
        if value is None:
            if index + 1 >= len(argv):
                problems.append(detail("$.argv[%d]" % index, "%s 缺少取值" % item, None))
                break
            if argv[index + 1] in bool_flags:
                problems.append(detail("$.argv[%d]" % index, "%s 缺少取值" % item, None))
                index += 1
                continue
            value = argv[index + 1]
            index += 2
        else:
            index += 1
        if kind == "int":
            try:
                target[key] = int(value)
            except ValueError:
                problems.append(detail("$.argv[%d]" % arg_idx, "%s 需要整数，收到 %r" % (item, value), None))
        else:
            target[key] = value
    if problems:
        raise AppError(INVALID_INPUT, "命令行参数有误", problems)
    return command, options, flags


def _too_large(path_key, label):
    limit_mb = MAX_INPUT_BYTES // (1024 * 1024)
    return AppError(
        INVALID_INPUT,
        "%s太大（上限 %d MB）" % (label, limit_mb),
        [detail(path_key, "输入超过 %d MB 上限" % limit_mb, None, INVALID_INPUT)],
    )


def _read_bounded(stream, path_key, label):
    chunks = []
    total = 0
    while True:
        chunk = stream.read(min(65536, MAX_INPUT_BYTES + 1 - total))
        if not chunk:
            break
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_INPUT_BYTES:
            raise _too_large(path_key, label)
    return b"".join(chunks)


def read_payload(command, options, stdin):
    """Read the JSON input object for a command, or {} when there is none."""
    source = options.get("input_file")
    raw = None
    label = "输入"
    if source == "-":
        raw = _read_bounded(stdin, "$.input_file", "stdin ")
        label = "stdin"
    elif source:
        label = "输入文件 %s" % source
        try:
            if os.path.isfile(source) and os.path.getsize(source) > MAX_INPUT_BYTES:
                raise _too_large("$.input_file", label + " ")
            with open(source, "rb") as handle:
                raw = _read_bounded(handle, "$.input_file", label + " ")
        except OSError as exc:
            raise AppError(
                INVALID_INPUT,
                "读不到输入文件：%s" % source,
                [detail("$.input_file", str(exc.strerror or exc), "确认文件路径存在且可读")],
            )
    elif command.input == "required":
        isatty = getattr(stdin, "isatty", None)
        if isatty is not None and not isatty():
            raw = _read_bounded(stdin, "$", "stdin ")
            label = "stdin"
    if raw is None or not raw.strip():
        if command.input == "required":
            raise AppError(
                INVALID_INPUT,
                "命令 %s 需要 JSON 输入" % command.name,
                [detail("$", "没有收到输入", "把 JSON 写进 UTF-8 文件并用 --input-file 传入")],
            )
        return {}
    text = decode_bytes(raw, label)
    payload = loads_strict(text, label)
    if not isinstance(payload, dict):
        raise AppError(INVALID_INPUT, "输入必须是 JSON 对象", [detail("$", "顶层应为对象", None)])
    _check_encoding(payload)
    return payload


ENCODING_CHECK = "汉字"


def _check_encoding(payload):
    """Any input may carry "encoding_check": "汉字". A terminal that mangles
    Chinese on the way in (PowerShell 5.1 pipes turn it into "??") still
    yields valid JSON, so without this the player's words would be saved
    broken. The field is removed before the command sees the input."""
    if "encoding_check" not in payload:
        return
    got = payload.pop("encoding_check")
    if got != ENCODING_CHECK:
        raise AppError(
            INVALID_INPUT,
            "传入的中文编码已损坏",
            [detail("$.encoding_check", "应为“%s”，收到 %s" % (ENCODING_CHECK, json.dumps(got, ensure_ascii=False)), "当前终端管道破坏了中文字符，请将 JSON 保存为 UTF-8 文件后用 --input-file 传入", INVALID_INPUT)],
        )


def merge_flags(payload, flags):
    problems = []
    for key, value in flags.items():
        if key in payload and payload[key] != value:
            problems.append(detail("$.%s" % key, "命令行参数与输入 JSON 的取值不一致", "只在一处给出"))
        payload[key] = value
    if problems:
        raise AppError(INVALID_INPUT, "参数冲突", problems)
    return payload


def _log_path(data_dir):
    return os.path.join(data_dir, "logs", "runtime.log")


def log_internal_error(data_dir, error_id, text):
    """Append to logs/runtime.log (rotated by size). Returns the log path or None."""
    try:
        path = _log_path(data_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > 1024 * 1024:
            for index in (2, 1):
                older = "%s.%d" % (path, index)
                if os.path.exists(older):
                    os.replace(older, "%s.%d" % (path, index + 1))
            os.replace(path, path + ".1")
        with open(path, "ab") as handle:
            stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            handle.write(("[%s] %s\n%s\n" % (stamp, error_id, text)).encode("utf-8", "backslashreplace"))
        return path
    except OSError:
        return None


def write_text(stream, text):
    # Input with a lone surrogate is refused, but a path from the file system
    # can still carry one; written as a \u escape it keeps the JSON valid.
    stream.write(text.encode("utf-8", "backslashreplace"))
    stream.flush()


def _internal_error(ctx):
    error_id = "E" + time.strftime("%Y%m%d%H%M%S") + os.urandom(3).hex()
    log_file = None
    if ctx is not None:
        log_file = log_internal_error(ctx.data_dir, error_id, traceback.format_exc())
    hint = "状态没有改变；查看日志 %s，必要时导出存档" % log_file if log_file else "状态没有改变；必要时导出存档"
    body = {
        "code": INTERNAL_ERROR,
        "message": "内部运行异常（编号 %s）" % error_id,
        "details": [detail("$", "内部运行异常", hint)],
        "error_id": error_id,
        "log": log_file,
        "next_request_id": new_request_id(),
    }
    return {"ok": False, "data": None, "error": body}


def execute(argv, skill_root, stdin=None, environ=None, keep_input=True):
    """Run one command; return (envelope, exit code, options, text, payload). Never raises.

    The envelope is serialized here, inside the error handling: a result that
    cannot be written as JSON is an INTERNAL_ERROR envelope, never a crash
    with nothing on stdout.
    """
    from ..application.context import Context

    stdin = stdin if stdin is not None else getattr(sys.stdin, "buffer", sys.stdin)
    environ = os.environ if environ is None else environ
    ctx = None
    options = {}
    payload = None
    try:
        command, options, flags = parse_argv(argv)
        payload = merge_flags(read_payload(command, options, stdin), flags)
        if command.input == "none":
            _normalized, errors = schema.validate(schema.EMPTY, payload)
            if errors:
                raise AppError(INVALID_INPUT, "命令 %s 不接受这些输入" % command.name, errors)
        ctx = Context(skill_root, options.get("data_dir"), environ, flags, options.get("debug", False))
        if environ.get("ADULT_TENSION_FAULT") == "internal_error":
            raise RuntimeError("injected internal error")  # test hook: exercises the INTERNAL_ERROR path
        module = __import__(command.module, fromlist=[command.func])
        # Direct callers and evaluation traces keep an untouched snapshot of payload.
        call_input = copy(payload) if (keep_input or environ.get("ADULT_TENSION_TRACE")) else payload
        data = getattr(module, command.func)(ctx, call_input)
        if environ.get("ADULT_TENSION_FAULT") == "unserializable_result":
            data["probe"] = object()  # test hook: a result that cannot become JSON
        if "next_request_id" not in data:
            data["next_request_id"] = new_request_id()
        envelope = {"ok": True, "data": data, "error": None}
        return envelope, 0, options, dumps(envelope, pretty=bool(options.get("pretty"))), payload
    except AppError as err:
        body = err.to_dict()
        body.setdefault("next_request_id", new_request_id())
        envelope = {"ok": False, "data": None, "error": body}
        try:
            return envelope, exit_code_for(err.code), options, dumps(envelope, pretty=bool(options.get("pretty"))), payload
        except Exception:
            envelope = _internal_error(ctx)
            return envelope, EXIT_INTERNAL, options, dumps(envelope), payload
    except Exception:
        envelope = _internal_error(ctx)
        return envelope, EXIT_INTERNAL, options, dumps(envelope), payload
    finally:
        if ctx is not None:
            ctx.close()


def trace(path, argv, payload, code, envelope, started, skill_root):
    """Append one call to the evaluation trace. A trace that cannot be written
    does not fail the command (its answer is already on stdout); it is reported
    on stderr, so an evaluation sees the gap instead of counting fewer calls."""
    try:
        parsed_envelope = json.loads(envelope) if isinstance(envelope, (str, bytes)) else envelope
        line = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "pid": os.getpid(),
            "skill_root": skill_root,
            "argv": list(argv),
            "input": payload,
            "exit": code,
            "envelope": parsed_envelope,
        }
        with open(path, "ab") as handle:
            handle.write((json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        sys.stderr.write("adult-tension: ADULT_TENSION_TRACE not written: %s\n" % exc)


def run(argv, skill_root, stdin=None, stdout=None, environ=None):
    environ = os.environ if environ is None else environ
    started = time.perf_counter()
    tracing = bool(environ.get("ADULT_TENSION_TRACE"))
    envelope, code, _options, text, payload = execute(argv, skill_root, stdin, environ, keep_input=tracing)
    stdout = stdout if stdout is not None else getattr(sys.stdout, "buffer", sys.stdout)
    write_text(stdout, text)
    if tracing:
        trace(environ["ADULT_TENSION_TRACE"], argv, payload, code, envelope, started, skill_root)
    return code
