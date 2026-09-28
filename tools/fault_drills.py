"""Fault drills (SKILL_PACKAGING.md 10), through the real entry script.

    python tools/fault_drills.py [--out reports/stage4/fault-drills.json]

Every drill runs in its own temporary directory with a game that has been
saved first. Each must fail recognisably, with an actionable hint, and leave
the existing save intact (checked after the drill with a normal process).
Exit 1 when any drill does not behave as expected.
"""

import argparse
import getpass
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

ENTRY = _runtime.ENTRY_SCRIPT
FIXTURE_V2 = os.path.join(_runtime.REPO_ROOT, "tests", "fixtures", "db_v2", "adult_tension.db")
SLOT = "演练前的存档"


def env_for(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION") and k != "PYTHONPYCACHEPREFIX"}
    env["ADULT_TENSION_INCLUDE_DRAFTS"] = "1"
    env.update(extra)
    return env


def call(args, data_dir, payload=None, env=None, entry=ENTRY, python_code=None):
    """(exit code, envelope or None, stderr tail) for one fresh process."""
    temp = None
    argv = [sys.executable, entry] + list(args) + ["--json", "--data-dir", data_dir]
    if payload is not None:
        handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False)
        handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        handle.close()
        temp = handle.name
        argv += ["--input-file", temp]
    if python_code is not None:
        argv = [sys.executable, "-c", python_code % {"entry": entry, "argv": argv[2:]}]
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env or env_for(), timeout=120)
    finally:
        if temp:
            os.remove(temp)
    try:
        envelope = json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else None
    except ValueError:
        envelope = None
    return proc.returncode, envelope, proc.stderr.decode("utf-8", "replace")[-400:]


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def logical(path):
    """Digest of every table's schema and rows (the backup API restores
    content, not header bytes)."""
    conn = sqlite3.connect(path)
    try:
        return hashlib.sha256("\n".join(conn.iterdump()).encode("utf-8")).hexdigest()
    finally:
        conn.close()


def prepared(root, entry=ENTRY):
    """A data dir with a game of three turns saved to SLOT. Returns (dir, session)."""
    data_dir = os.path.join(root, "data")
    code, opened, err = call(["new-game"], data_dir, {"request_id": "drill_new_0001", "mode": "pressure", "seed": 31}, entry=entry)
    assert code == 0, (opened, err)
    session = opened["data"]
    npc = next(c for c in session["context"]["scene"]["present"] if c != "player")
    revision = session["revision"]
    for index in range(3):
        code, env, err = call(["commit-turn"], data_dir, commit(session["session_id"], "drill_turn_%04d" % index, revision, npc), entry=entry)
        assert code == 0, (env, err)
        revision = env["data"]["revision"]
    code, env, err = call(["save-slot"], data_dir, {"session_id": session["session_id"], "request_id": "drill_save_0001", "expected_revision": revision, "name": SLOT}, entry=entry)
    assert code == 0, (env, err)
    session["revision"] = revision
    session["npc"] = npc
    return data_dir, session


def commit(sid, rid, revision, npc):
    return {
        "session_id": sid,
        "request_id": rid,
        "expected_revision": revision,
        "action_mode": "continue",
        "player_input": "继续",
        "operations": [{"op": "npc_action", "npc_id": npc, "action": "看了一眼门口"}],
        "content_tags": [],
        "summary": "有人看了一眼门口。",
        "open_action": "门口没有动静",
    }


def save_intact(data_dir, entry=ENTRY):
    """The saved game still loads and plays, through a normal process."""
    code, env, _err = call(["list-slots"], data_dir, entry=entry)
    if code != 0 or SLOT not in [s["name"] for s in env["data"]["slots"]]:
        return False
    code, env, _err = call(["load-slot"], data_dir, {"request_id": "drill_check_%s" % os.urandom(3).hex(), "name": SLOT}, entry=entry)
    return code == 0 and env["data"]["turn"] == 4


def summary(code, env):
    error = (env or {}).get("error") or {}
    return {
        "exit_code": code,
        "envelope": env is not None,
        "code": error.get("code"),
        "message": error.get("message"),
        "hints": [d.get("hint") for d in error.get("details", []) if d.get("hint")][:3],
        "paths": [d.get("path") for d in error.get("details", [])][:5],
    }


# ---------------------------------------------------------------------------


def drill_old_python(root):
    data_dir, _session = prepared(root)
    before = sha(os.path.join(data_dir, "adult_tension.db"))
    code_text = "import sys, runpy; sys.version_info = (3, 9, 18, 'final', 0); sys.argv = [%(entry)r] + %(argv)r; runpy.run_path(%(entry)r, run_name='__main__')"
    code, env, _err = call(["doctor"], data_dir, python_code=code_text)
    observed = summary(code, env)
    ok = code == 20 and observed["code"] == "RUNTIME_UNSUPPORTED" and (env["error"].get("required") == "3.10")
    return "Python 版本过低（模拟 3.9.18 运行入口脚本）", "RUNTIME_UNSUPPORTED，说明需要的版本", observed, ok and sha(os.path.join(data_dir, "adult_tension.db")) == before and save_intact(data_dir)


def drill_unwritable(root):
    data_dir, _session = prepared(root)
    before = sha(os.path.join(data_dir, "adult_tension.db"))
    user = getpass.getuser()
    if sys.platform.startswith("win"):
        subprocess.run(["icacls", data_dir, "/deny", "%s:(OI)(CI)(W,AD,WD)" % user], check=True, capture_output=True)
    else:
        os.chmod(data_dir, 0o500)
    try:
        code, env, _err = call(["doctor"], data_dir)
    finally:
        if sys.platform.startswith("win"):
            subprocess.run(["icacls", data_dir, "/remove:d", user], check=True, capture_output=True)
        else:
            os.chmod(data_dir, 0o700)
    observed = summary(code, env)
    ok = code == 20 and observed["code"] == "DATA_DIR_UNAVAILABLE" and bool(observed["hints"]) and bool((env["error"].get("tried") or env["error"].get("paths") or observed["paths"]))
    return "数据目录不可写（拒绝写入已有存档的数据目录）", "DATA_DIR_UNAVAILABLE，附尝试过的路径与建议", observed, ok and sha(os.path.join(data_dir, "adult_tension.db")) == before and save_intact(data_dir)


def drill_content_tampered(root):
    skill = os.path.join(root, "adult-tension")
    shutil.copytree(_runtime.SKILL_ROOT, skill, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    entry = os.path.join(skill, "scripts", "adult_tension.py")
    data_dir, session = prepared(root, entry)
    world_path = os.path.join(skill, "content", "worlds", "harbor_night_shift.json")
    with open(world_path, encoding="utf-8") as handle:
        world = json.load(handle)
    here = session["context"]["scene"]["location_id"]
    removed = next(loc["id"] for loc in world["locations"] if loc["id"] != here and any(loc["id"] in other["exits"] for other in world["locations"]))
    world["locations"] = [loc for loc in world["locations"] if loc["id"] != removed]
    with open(world_path, "w", encoding="utf-8") as handle:
        json.dump(world, handle, ensure_ascii=False)
    code, env, _err = call(["doctor"], data_dir, entry=entry)
    observed = summary(code, env)
    observed["removed_location"] = removed
    located = any(removed in (d.get("reason", "") + d.get("path", "")) for d in (env or {}).get("error", {}).get("details", []))
    code2, env2, _err = call(["commit-turn"], data_dir, commit(session["session_id"], "drill_after_tamper", session["revision"], session["npc"]), entry=entry)
    observed["existing_game_commit_exit"] = code2
    ok = code == 10 and observed["code"] == "CONTENT_ERROR" and located and code2 == 0
    return "编译后的内容被篡改（删掉一个被引用的地点）", "doctor 报 CONTENT_ERROR 并指出位置；已有会话仍然可以续玩", observed, ok and save_intact(data_dir, entry)


def drill_newer_database(root):
    data_dir, _session = prepared(root)
    db = os.path.join(data_dir, "adult_tension.db")
    conn = sqlite3.connect(db)
    conn.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    before = sha(db)
    code, env, _err = call(["doctor"], data_dir)
    observed = summary(code, env)
    unchanged = sha(db) == before
    observed["database_unchanged"] = unchanged
    conn = sqlite3.connect(db)
    conn.execute("UPDATE meta SET value=(SELECT value FROM meta WHERE key='schema_version') WHERE 0")
    conn.execute("UPDATE meta SET value=? WHERE key='schema_version'", (str(_db_version()),))
    conn.commit()
    conn.close()
    ok = code == 20 and observed["code"] == "UNSUPPORTED_VERSION" and unchanged
    return "数据库 schema 比 Skill 新", "UNSUPPORTED_VERSION，数据库不被修改", observed, ok and save_intact(data_dir)


def _db_version():
    _runtime.use_runtime()
    from adult_tension import DB_SCHEMA_VERSION

    return DB_SCHEMA_VERSION


def drill_migration_fails(root):
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir)
    db = os.path.join(data_dir, "adult_tension.db")
    shutil.copyfile(FIXTURE_V2, db)
    before = logical(db)
    code, env, _err = call(["list-slots"], data_dir, env=env_for(ADULT_TENSION_FAULT="migration_fail"))
    observed = summary(code, env)
    restored = logical(db) == before
    observed["restored"] = (env or {}).get("error", {}).get("restored")
    observed["database_content_restored"] = restored
    code2, env2, _err = call(["load-slot"], data_dir, {"request_id": "drill_load_after_fix", "name": "旧版本的存档"})
    observed["next_normal_run_exit"] = code2
    ok = code == 20 and observed["code"] == "MIGRATION_FAILED" and observed["restored"] is True and restored and code2 == 0
    return "迁移中途失败（测试钩子注入，真实 schema 2 旧库）", "自动恢复备份，错误说明清楚，下一次正常版本可以继续", observed, ok


def drill_killed_in_write(root):
    data_dir, session = prepared(root)
    payload = commit(session["session_id"], "drill_killed_0001", session["revision"], session["npc"])
    code, env, _err = call(["commit-turn"], data_dir, payload, env=env_for(ADULT_TENSION_FAULT="kill_in_commit"))
    observed = {"exit_code": code, "envelope": env is not None}
    code2, env2, _err = call(["status"], data_dir, {"session_id": session["session_id"], "level": "debug"})
    observed["revision_after"] = env2["data"]["revision"] if code2 == 0 else None
    code3, env3, _err = call(["commit-turn"], data_dir, payload)
    observed["same_request_after_exit"] = code3
    observed["revision_after_retry"] = env3["data"]["revision"] if code3 == 0 else None
    ok = code == 137 and observed["revision_after"] == session["revision"] and code3 == 0 and observed["revision_after_retry"] == session["revision"] + 1
    return "写事务期间进程被杀", "下一次打开时状态停在上一个 revision，没有半写入", observed, ok and save_intact(data_dir)


def drill_two_processes(root):
    data_dir, session = prepared(root)
    procs = []
    files = []
    for tag in ("a", "b"):
        payload = commit(session["session_id"], "drill_race_%s_0001" % tag, session["revision"], session["npc"])
        handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False)
        handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        handle.close()
        files.append(handle.name)
        procs.append(subprocess.Popen([sys.executable, ENTRY, "commit-turn", "--json", "--data-dir", data_dir, "--input-file", handle.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_for()))
    results = []
    for proc in procs:
        out, _err = proc.communicate(timeout=120)
        envelope = json.loads(out.decode("utf-8"))
        results.append((proc.returncode, envelope["ok"], (envelope.get("error") or {}).get("code")))
    for name in files:
        os.remove(name)
    code, env, _err = call(["status"], data_dir, {"session_id": session["session_id"], "level": "debug"})
    observed = {"results": results, "revision_after": env["data"]["revision"]}
    successes = sum(1 for r in results if r[1])
    losers = [r[2] for r in results if not r[1]]
    ok = successes == 1 and all(c in ("STALE_REVISION", "STORAGE_BUSY") for c in losers) and observed["revision_after"] == session["revision"] + 1
    return "两个进程同时提交同一会话", "一个成功，另一个得到 STALE_REVISION 或 STORAGE_BUSY，没有重复推进", observed, ok and save_intact(data_dir)


DRILLS = (drill_old_python, drill_unwritable, drill_content_tampered, drill_newer_database, drill_migration_fails, drill_killed_in_write, drill_two_processes)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=os.path.join(_runtime.REPO_ROOT, "reports", "stage4", "fault-drills.json"))
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = {"drills": []}
    for drill in DRILLS:
        root = tempfile.mkdtemp(prefix="at-drill-")
        try:
            name, expected, observed, ok = drill(root)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        report["drills"].append({"drill": name, "expected": expected, "observed": observed, "pass": bool(ok)})
        print("[%s] %s" % ("OK" if ok else "FAIL", name))
    report["pass"] = all(d["pass"] for d in report["drills"])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("PASS" if report["pass"] else "FAIL")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
