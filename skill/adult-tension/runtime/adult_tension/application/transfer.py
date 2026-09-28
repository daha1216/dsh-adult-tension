"""Export and import of a whole game (RUNTIME_PROTOCOL 9.4, DATA_CONTRACTS 9).

An export file is the exchange format: the complete state (facts included),
the content snapshot and the archive, with a sha256 over everything else so
that truncation and damage are found on import. It is data validation for
an exchange file, not a governance lock (DESIGN_DECISIONS D9).

Import validates everything before anything is written: the format, the
version (newer -> UNSUPPORTED_VERSION), the checksum, then the state, the
content snapshot and the archive in full. An older export is copied to
backups/ and upgraded in memory.
"""

import hashlib
import os
import re
import time

from .. import RNG_VERSION, SAVE_FORMAT, SKILL_VERSION, STATE_SCHEMA_VERSION, paths
from ..domain import state_check, worldpack
from ..domain.upgrade import upgrade
from ..errors import CONTENT_ERROR, INVALID_INPUT, UNSUPPORTED_VERSION, AppError, detail, fail
from ..jsonio import canonical, decode_bytes, dumps, loads_strict, plain

MAX_IMPORT_BYTES = 32 * 1024 * 1024
DOC_KEYS = ("format", "schema_version", "content_version", "rng_version", "skill_version", "exported_at", "source", "session", "checksum")
SESSION_KEYS = ("state", "content", "archive")
CONTENT_KEYS = ("world", "tags", "content_version")


def checksum(doc):
    body = {k: v for k, v in doc.items() if k != "checksum"}
    return "sha256:" + hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def build(state, content, archive, source, exported_at):
    """The export document for a complete state (facts as a dict)."""
    doc = {
        "format": SAVE_FORMAT,
        "schema_version": STATE_SCHEMA_VERSION,
        "content_version": content["content_version"],
        "rng_version": state["rng_version"],
        "skill_version": SKILL_VERSION,
        "exported_at": exported_at,
        "source": source,
        "session": {"state": state, "content": content, "archive": archive},
    }
    doc["checksum"] = checksum(doc)
    return doc


# ---------------------------------------------------------------------------
# where an export goes


def _safe_stem(text):
    stem = re.sub(r"[\\/:*?\"<>|\s]+", "-", text).strip("-.") or "export"
    return stem[:40]


def export_target(ctx, path, stem, overwrite):
    """exports/<stem>-<time>.json by default; a path the user gave must be an
    absolute .json path outside the Skill, with no '..' in it."""
    if path is None:
        directory = os.path.join(ctx.data_dir, "exports")
        os.makedirs(directory, exist_ok=True)
        base = os.path.join(directory, "%s-%s" % (_safe_stem(stem), time.strftime("%Y%m%d-%H%M%S")))
        target = base + ".json"
        counter = 1
        while os.path.exists(target):
            counter += 1
            target = "%s-%d.json" % (base, counter)
        return target
    problems = []
    parts = re.split(r"[\\/]+", path)
    if ".." in parts:
        problems.append(detail("$.path", "路径里不能有 ..", "给出完整的绝对路径", INVALID_INPUT))
    if not os.path.isabs(path):
        problems.append(detail("$.path", "导出路径必须是绝对路径", "例如 D:\\\\备份\\\\港口.json；不给路径时写到数据目录的 exports/", INVALID_INPUT))
    if not path.lower().endswith(".json"):
        problems.append(detail("$.path", "导出文件要以 .json 结尾", None, INVALID_INPUT))
    if problems:
        fail(problems)
    target = os.path.normpath(path)
    if paths.is_inside(target, ctx.skill_root):
        fail([detail("$.path", "不能导出到 Skill 目录里", "升级会替换 Skill 目录，文件会丢失", INVALID_INPUT)])
    if not os.path.isdir(os.path.dirname(target)):
        fail([detail("$.path", "目录不存在：%s" % os.path.dirname(target), "先建好目录，或不给路径（写到数据目录的 exports/）", INVALID_INPUT)])
    if os.path.isdir(target):
        fail([detail("$.path", "这是一个目录", None, INVALID_INPUT)])
    if os.path.exists(target) and not overwrite:
        fail([detail("$.path", "文件已存在：%s" % target, "问玩家是否覆盖；确认后带 overwrite: true", INVALID_INPUT)])
    return target


def write_file(target, doc):
    data = dumps(doc).encode("utf-8")
    temp = "%s.tmp-%d" % (target, os.getpid())
    with open(temp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, target)
    return len(data)


# ---------------------------------------------------------------------------
# import


def read_source(payload):
    """(document, original bytes or None) from `path` or inline `data`."""
    if payload["path"] is not None:
        path = payload["path"]
        if not os.path.isfile(path):
            fail([detail("$.path", "文件不存在：%s" % path, "确认路径；或让玩家直接粘贴导出的 JSON", INVALID_INPUT)])
        if os.path.getsize(path) > MAX_IMPORT_BYTES:
            fail([detail("$.path", "文件太大（上限 %d MB）" % (MAX_IMPORT_BYTES // 1024 // 1024), None, INVALID_INPUT)])
        with open(path, "rb") as handle:
            raw = handle.read()
        try:
            return plain(loads_strict(decode_bytes(raw, "导入文件"), "导入文件")), raw
        except AppError as err:
            fail([dict(d, hint=d.get("hint") or "文件不完整或已损坏：请重新导出") for d in err.details] or [detail("$", err.message, "文件不完整或已损坏", INVALID_INPUT)])
    return payload["data"], None


def _keys(obj, expected, path, problems):
    if not isinstance(obj, dict):
        problems.append(detail(path, "应为对象", None, INVALID_INPUT))
        return False
    ok = True
    for key in expected:
        if key not in obj:
            problems.append(detail("%s.%s" % (path, key), "缺少字段", None, INVALID_INPUT))
            ok = False
    for key in obj:
        if key not in expected:
            problems.append(detail("%s.%s" % (path, key), "未知字段", None, INVALID_INPUT))
            ok = False
    return ok


def check(doc):
    """Validate an export document. Returns (state, content, archive, upgraded)
    or raises AppError with every problem found."""
    problems = []
    if not _keys(doc, DOC_KEYS, "$", problems):
        fail(problems, "导入文件缺少必要的部分或带了未知字段")
    if doc["format"] != SAVE_FORMAT:
        fail([detail("$.format", "不是 Adult Tension 的导出文件", None, INVALID_INPUT)])
    version = doc["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        fail([detail("$.schema_version", "版本号非法", None, INVALID_INPUT)])
    if version > STATE_SCHEMA_VERSION:
        raise AppError(
            UNSUPPORTED_VERSION,
            "这个导出文件来自更新版本的 Skill（格式 %d > %d）" % (version, STATE_SCHEMA_VERSION),
            [detail("$.schema_version", "格式 %d 比当前支持的 %d 新" % (version, STATE_SCHEMA_VERSION), "升级 Skill 后再导入；没有写入任何数据", UNSUPPORTED_VERSION)],
        )
    if doc["rng_version"] != RNG_VERSION:
        raise AppError(
            UNSUPPORTED_VERSION,
            "随机算法版本不同（%s，本版本 %d），导入后无法复现同样的结果" % (doc["rng_version"], RNG_VERSION),
            [detail("$.rng_version", "随机算法版本不受支持", "用相同版本的 Skill 导入", UNSUPPORTED_VERSION)],
        )
    if doc["checksum"] != checksum(doc):
        fail([detail("$.checksum", "校验值不符：文件被改动过或已损坏", "请重新导出；没有写入任何数据", INVALID_INPUT)])
    session = doc["session"]
    if not _keys(session, SESSION_KEYS, "$.session", problems):
        fail(problems)
    state, content, archive = session["state"], session["content"], session["archive"]
    if not _keys(content, CONTENT_KEYS, "$.session.content", problems):
        fail(problems)
    upgraded = False
    if isinstance(state, dict) and isinstance(state.get("schema_version"), int) and state["schema_version"] < STATE_SCHEMA_VERSION:
        upgrade(state)
        upgraded = True
    world = content["world"] if isinstance(content["world"], dict) else None
    problems.extend(_prefix(state_check.check_state(state, world), "$.session.state"))
    problems.extend(_prefix(state_check.check_archive(archive), "$.session"))
    tags = content["tags"]
    if not isinstance(tags, list) or not all(isinstance(t, dict) and isinstance(t.get("id"), str) for t in tags):
        problems.append(detail("$.session.content.tags", "标签表格式不对", None, CONTENT_ERROR))
        tag_ids = None
    else:
        tag_ids = [t["id"] for t in tags]
    if world is None:
        problems.append(detail("$.session.content.world", "缺少世界包", None, CONTENT_ERROR))
    else:
        _pack, world_problems = worldpack.validate_world(world, custom=world.get("custom"), tag_ids=tag_ids)
        problems.extend(_prefix(world_problems, "$.session.content.world"))
    if isinstance(state, dict) and world is not None and state.get("world_id") != world.get("id"):
        problems.append(detail("$.session.state.world_id", "与内容快照的世界不一致", None, INVALID_INPUT))
    if problems:
        fail(problems, "导入文件有 %d 处问题，没有写入任何数据" % len(problems) if len(problems) > 1 else None)
    return state, content, archive, upgraded


def _prefix(problems, prefix):
    out = []
    for problem in problems:
        path = problem.get("path") or "$"
        out.append(dict(problem, path=prefix + path[1:] if path.startswith("$") else "%s %s" % (prefix, path)))
    return out


def backup_import(ctx, doc, raw):
    """Keep the original of an older export before it is upgraded."""
    directory = os.path.join(ctx.data_dir, "backups")
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, "import-format%s-%s.json" % (doc["schema_version"], time.strftime("%Y%m%dT%H%M%S")))
    with open(target, "wb") as handle:
        handle.write(raw if raw is not None else dumps(doc).encode("utf-8"))
    return target
