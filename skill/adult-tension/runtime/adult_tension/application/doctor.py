"""`doctor`: first-run initialisation plus a full environment diagnosis.

Idempotent. After a successful run the data directory holds a version marker;
the next doctor for the same Skill version, Skill root, Python and content
files takes a fast path with lightweight checks only.
"""

import json
import os
import platform
import sys

from .. import DB_SCHEMA_VERSION, MIN_PYTHON, MIN_SQLITE, SKILL_VERSION, paths
from ..errors import (
    CONTENT_ERROR,
    DATA_DIR_UNAVAILABLE,
    INTERNAL_ERROR,
    RUNTIME_UNSUPPORTED,
    AppError,
    detail,
)

REQUIRED_SKILL_FILES = ("SKILL.md", "scripts/adult_tension.py", "references", "content/index.json")

# The failure that matters most decides the envelope's error code.
FAIL_ORDER = ("python", "sqlite", "data_dir", "migrations", "skill_files", "content")


def _check(check_id, status, message, hint=None, code=None, details=None):
    item = {"id": check_id, "status": status, "message": message, "hint": hint}
    if code:
        item["code"] = code
    if details:
        item["details"] = details
    return item


def _python_check():
    version = platform.python_version()
    if tuple(sys.version_info[:2]) < MIN_PYTHON:
        return _check("python", "fail", "Python %s 低于 %d.%d" % ((version,) + MIN_PYTHON), "换用 Python 3.10+", RUNTIME_UNSUPPORTED)
    return _check("python", "ok", "Python %s（%s）" % (version, sys.executable))


def _skill_files_check(skill_root):
    missing = [rel for rel in REQUIRED_SKILL_FILES if not os.path.exists(os.path.join(skill_root, rel))]
    if missing:
        return _check(
            "skill_files",
            "fail",
            "Skill 目录不完整，缺少：%s" % "、".join(missing),
            "重新安装完整的 Skill 目录",
            CONTENT_ERROR,
            [detail(rel, "缺失", "重新安装完整的 Skill 目录") for rel in missing],
        )
    return _check("skill_files", "ok", "Skill 根目录：%s" % skill_root)


def _sqlite_check():
    try:
        import sqlite3
    except ImportError as exc:
        return _check("sqlite", "fail", "Python 缺少 sqlite3 模块：%s" % exc, "换用带 sqlite3 的 Python 3.10+", RUNTIME_UNSUPPORTED)
    if tuple(sqlite3.sqlite_version_info) < MIN_SQLITE:
        return _check(
            "sqlite",
            "fail",
            "SQLite %s 低于 %s" % (sqlite3.sqlite_version, ".".join(map(str, MIN_SQLITE))),
            "换用自带较新 SQLite 的 Python",
            RUNTIME_UNSUPPORTED,
        )
    return _check("sqlite", "ok", "SQLite %s" % sqlite3.sqlite_version)


def _content_check(ctx):
    from ..content.verify import verify_installed

    problems, summary = verify_installed(ctx.content())
    if problems:
        return _check(
            "content",
            "fail",
            "内容编译产物校验失败（%d 处）" % len(problems),
            "重新安装 Skill 目录；已有会话使用自己的内容快照，仍可续玩",
            CONTENT_ERROR,
            problems,
        )
    # what new-game offers: the released worlds, or every world under the development switch
    openable = summary["worlds"] if ctx.drafts_switch() else summary["released_worlds"]
    if openable == 0:
        return _check("content", "warn", "内容版本 %s，还没有可开局的世界" % summary["content_version"], "等待世界包发布")
    return _check(
        "content",
        "ok",
        "内容版本 %s，%d 个世界可开局" % (summary["content_version"], openable),
    )


def _read_marker(data_dir):
    try:
        with open(paths.marker_path(data_dir), "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def _write_marker(data_dir, marker):
    target = paths.marker_path(data_dir)
    temp = target + ".tmp-%d" % os.getpid()
    with open(temp, "wb") as handle:
        handle.write(json.dumps(marker, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, target)


def _expected_marker(ctx):
    return {
        "skill_version": SKILL_VERSION,
        "db_schema_version": DB_SCHEMA_VERSION,
        "skill_root": ctx.skill_root,
        "python": "%d.%d" % tuple(sys.version_info[:2]),
        "content_stamp": ctx.content().stamp(),
        # the content check counts unreleased worlds only under the switch
        "drafts_switch": ctx.drafts_switch(),
    }


def run(ctx, payload):
    checks = [_python_check()]
    data_dir_error = None
    try:
        ctx.prepare_data_dir()
        checks.append(_check("data_dir", "ok", "数据目录可写：%s（来源：%s）" % (ctx.data_dir, ctx.data_dir_source)))
    except AppError as err:
        data_dir_error = err
        checks.append(
            _check("data_dir", "fail", err.message, err.extra.get("suggestions", [None])[0], DATA_DIR_UNAVAILABLE, err.details)
        )

    fast_path = False
    content_version = None
    try:
        content_version = ctx.content().index().get("content_version")
    except AppError:
        pass

    if data_dir_error is None:
        expected = _expected_marker(ctx)
        marker = _read_marker(ctx.data_dir)
        if marker is not None and {k: marker.get(k) for k in expected} == expected:
            fast_path = _fast_checks(ctx, checks, marker)
        if not fast_path:
            _full_checks(ctx, checks)
    else:
        checks.append(_sqlite_check())
        checks.append(_skill_files_check(ctx.skill_root))

    failed = [c for c in checks if c["status"] == "fail"]
    if not failed and data_dir_error is None and not fast_path:
        marker = _expected_marker(ctx)
        content = next(c for c in checks if c["id"] == "content")
        marker["content_check"] = {"status": content["status"], "message": content["message"], "hint": content["hint"]}
        _write_marker(ctx.data_dir, marker)

    result = {
        "status": "fail" if failed else ("warn" if any(c["status"] == "warn" for c in checks) else "ok"),
        "fast_path": fast_path,
        "skill_version": SKILL_VERSION,
        "content_version": content_version,
        "skill_root": ctx.skill_root,
        "data_dir": ctx.data_dir,
        "data_dir_source": ctx.data_dir_source,
        "checks": checks,
    }
    if failed:
        failed.sort(key=lambda c: FAIL_ORDER.index(c["id"]) if c["id"] in FAIL_ORDER else len(FAIL_ORDER))
        first = failed[0]
        details = []
        for check in failed:
            details.extend(check.get("details") or [detail("$.checks.%s" % check["id"], check["message"], check["hint"])])
        raise AppError(first.get("code", INTERNAL_ERROR), first["message"], details, doctor=result)
    return result


def _fast_checks(ctx, checks, marker):
    """Lightweight checks; return False to fall back to the full path."""
    try:
        conn = ctx.db()
        conn.execute("SELECT 1").fetchone()
    except AppError:
        return False
    if ctx.schema_report and ctx.schema_report.get("migrated"):
        return False
    checks.append(_check("sqlite", "ok", "SQLite 可用（快速检查）"))
    checks.append(_check("migrations", "ok", "数据库 schema %d（快速检查）" % DB_SCHEMA_VERSION))
    checks.append(_check("skill_files", "ok", "Skill 根目录：%s（快速检查）" % ctx.skill_root))
    content = marker.get("content_check") or {}
    checks.append(_check("content", content.get("status", "ok"), "%s（快速检查：内容文件未变化）" % content.get("message", "内容可用"), content.get("hint")))
    return True


def _full_checks(ctx, checks):
    sqlite_check = _sqlite_check()
    checks.append(sqlite_check)
    if sqlite_check["status"] == "ok":
        try:
            ctx.db()
            report = ctx.schema_report or {}
            if report.get("migrated"):
                message = "数据库已从 schema %d 迁移到 %d" % (report["from"], report["to"])
                if report.get("backup"):
                    message += "（迁移前备份：%s）" % report["backup"]
            else:
                message = "数据库 schema %d，无需迁移" % DB_SCHEMA_VERSION
            checks.append(_check("migrations", "ok", message))
        except AppError as err:
            checks.append(_check("migrations", "fail", err.message, err.details[0]["hint"] if err.details else None, err.code, err.details))
    checks.append(_skill_files_check(ctx.skill_root))
    try:
        checks.append(_content_check(ctx))
    except AppError as err:
        checks.append(_check("content", "fail", err.message, "重新安装 Skill 目录", CONTENT_ERROR, err.details))
