"""CLI adapter: argv and input parsing, dispatch, envelope, exit codes.

stdout carries exactly one JSON envelope, written as UTF-8 bytes whatever the
console code page is. Diagnostics go to the log file under the data dir.

ADULT_TENSION_TRACE=<file> (set by an evaluation harness, never by a player)
appends one JSON line per call: argv, parsed input, exit code, envelope and
duration. End-to-end records read the tool calls from there, whatever the
host's own transcript looks like.
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
from ..jsonio import decode_bytes, dumps, loads_strict, plain

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
        if value is None:
            if index + 1 >= len(argv):
                problems.append(detail("$.argv[%d]" % index, "%s 缺少取值" % item, None))
                break
            value = argv[index + 1]
            index += 2
        else:
            index += 1
        if kind == "int":
            try:
                target[key] = int(value)
            except ValueError:
                problems.append(detail("$.argv[%d]" % index, "%s 需要整数，收到 %r" % (item, value), None))
        else:
            target[key] = value
    if problems:
        raise AppError(INVALID_INPUT, "命令行参数有误", problems)
    return command, options, flags


def read_payload(command, options, stdin):
    """Read the JSON input object for a command, or {} when there is none."""
    source = options.get("input_file")
    raw = None
    label = "输入"
    if source == "-":
        raw = stdin.read()
        label = "stdin"
    elif source:
        label = "输入文件 %s" % source
        try:
            with open(source, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            raise AppError(
                INVALID_INPUT,
                "读不到输入文件：%s" % source,
                [detail("$.input_file", str(exc.strerror or exc), "确认文件路径存在且可读")],
            )
    elif command.input == "required":
        isatty = getattr(stdin, "isatty", None)
        if isatty is not None and not isatty():
            raw = stdin.read()
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
    return payload


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
            handle.write(("[%s] %s\n%s\n" % (stamp, error_id, text)).encode("utf-8"))
        return path
    except OSError:
        return None


def write_text(stream, text):
    stream.write(text.encode("utf-8"))
    stream.flush()


def _internal_error(ctx):
    error_id = "E" + time.strftime("%Y%m%d%H%M%S") + os.urandom(3).hex()
    log_file = None
    if ctx is not None:
        log_file = log_internal_error(ctx.data_dir, error_id, traceback.format_exc())
    hint = "状态没有改变；查看日志 %s，必要时导出存档" % log_file if log_file else "状态没有改变；必要时导出存档"
    body = {
        "code": INTERNAL_ERROR,
        "message": "未预期错误（编号 %s）" % error_id,
        "details": [detail("$", "未预期错误", hint)],
        "error_id": error_id,
        "log": log_file,
        "next_request_id": new_request_id(),
    }
    return {"ok": False, "data": None, "error": body}


def execute(argv, skill_root, stdin=None, environ=None):
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
        data = getattr(module, command.func)(ctx, plain(payload))
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


def trace(path, argv, payload, code, text, started):
    """Append one call to the evaluation trace. Never fails the command."""
    try:
        line = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "pid": os.getpid(),
            "argv": list(argv),
            "input": payload,
            "exit": code,
            "envelope": json.loads(text),
        }
        with open(path, "ab") as handle:
            handle.write((json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8"))
    except Exception:
        pass


def run(argv, skill_root, stdin=None, stdout=None, environ=None):
    environ = os.environ if environ is None else environ
    started = time.perf_counter()
    _envelope, code, _options, text, payload = execute(argv, skill_root, stdin, environ)
    stdout = stdout if stdout is not None else getattr(sys.stdout, "buffer", sys.stdout)
    write_text(stdout, text)
    if environ.get("ADULT_TENSION_TRACE"):
        trace(environ["ADULT_TENSION_TRACE"], argv, payload, code, text, started)
    return code
