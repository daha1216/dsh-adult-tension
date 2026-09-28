"""Reverse verification (ACCEPTANCE.md section 7): break things on purpose.

    python tools/reverse_checks.py [--group age|time|all]

Works on a temporary copy of the repository, never on the working tree.
Every check must FAIL the way the acceptance criteria describe; the tool
exits 0 only when all of them did. Outputs go to reports/reverse/.

Groups:
  age   ACCEPTANCE 7.4: each age check commented out makes tests fail
  time  stage 3 gates: required offscreen beats, undo reverting facts, the
        retcon knowledge rule, the settlement order, chapter archiving
  cli   ACCEPTANCE 7.1, 7.2, 7.3, 7.5 through the real entry script: a deleted
        referenced location, a stale revision, one changed byte in an export,
        an anachronistic word in a location name
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

REPO = _runtime.REPO_ROOT
OUT = os.path.join(REPO, "reports", "reverse")
RUNTIME = "skill/adult-tension/runtime/adult_tension/"

# (label, file, exact text, replacement) — each disables one age check.
AGE_PATCHES = [
    (
        "invariants: every character >= 18",
        RUNTIME + "domain/invariants.py",
        '        elif age < 18:\n            bad(base + ".age", "角色 %s 年龄 %d 小于 18" % (cid, age), SAFETY_BLOCK)\n',
        "        elif False:  # age check disabled on purpose\n            pass\n",
    ),
    (
        "introduce_character: new characters >= 18",
        RUNTIME + "domain/ops_people.py",
        '    if op["age"] < 18:\n        errs.append(detail(path + ".age", "年龄 %d 小于 18，不能登场" % op["age"], "所有角色都必须是明确的成年人", SAFETY_BLOCK))\n',
        "    pass  # age check disabled on purpose\n",
    ),
    (
        "opening: player character >= 18",
        RUNTIME + "domain/opening.py",
        "    if age < 18:\n",
        "    if False:  # age check disabled on purpose\n",
    ),
    (
        "intimacy: participants >= 18",
        RUNTIME + "domain/turn.py",
        '        elif char["age"] < 18:\n',
        "        elif False:  # age check disabled on purpose\n",
    ),
    (
        "content validator: age ranges >= 18",
        RUNTIME + "domain/worldpack.py",
        "                if lo < 18:\n",
        "                if False:  # age check disabled on purpose\n",
    ),
]


# Stage 3 gates, each disabled on purpose.
TIME_PATCHES = [
    (
        "required offscreen beats",
        RUNTIME + "domain/turn.py",
        "    missing = [npc for npc in ctx.required_beats if npc not in ctx.beats_after_time]\n",
        "    missing = []  # required beats disabled on purpose\n",
    ),
    (
        "undo reverts the turn's facts",
        RUNTIME + "application/service.py",
        "        repo.revert_turn_facts(conn, sid, undone)\n",
        "        pass  # fact revert disabled on purpose\n",
    ),
    (
        "retcon adds no NPC knowledge",
        RUNTIME + "domain/ops.py",
        '        if not op["truth"] or op["believed_by"] or op["spread"] or op["visibility"] != "private" or op["known_by"] != [state["player_id"]]:\n',
        "        if False:  # retcon knowledge rule disabled on purpose\n",
    ),
    (
        "settlement order: events before status",
        RUNTIME + "domain/settlement.py",
        '    report["resolved_events"] = settle_events(state, state["clock"], turn)\n    report["steps"].append("events")\n    report["expired_conditions"] = expire_conditions(state, state["clock"])\n    report["steps"].append("status")\n',
        '    report["expired_conditions"] = expire_conditions(state, state["clock"])\n    report["steps"].append("status")\n    report["resolved_events"] = settle_events(state, state["clock"], turn)\n    report["steps"].append("events")\n',
    ),
    (
        "chapter archives its turns",
        RUNTIME + "domain/turn.py",
        '        if entry["turn"] < turn:\n',
        "        if False:  # chapter archiving disabled on purpose\n",
    ),
]
GROUPS = {"age": ("age-checks.json", AGE_PATCHES), "time": ("time-checks.json", TIME_PATCHES)}


def copy_repo(dest):
    for name in ("skill", "tests", "tools", "content-src"):
        shutil.copytree(os.path.join(REPO, name), os.path.join(dest, name), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def run_suite(root, suite):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION")}
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/%s" % suite],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        timeout=600,
    )
    text = proc.stdout.decode("utf-8", "replace")
    failing = [line.split(" ", 1)[1] for line in text.splitlines() if line.startswith(("FAIL: ", "ERROR: "))]
    summary = [line for line in text.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    return proc.returncode, failing, summary


def patch_checks(patches):
    results = []
    root = tempfile.mkdtemp(prefix="at-reverse-")
    try:
        copy_repo(root)
        code, _failing, summary = run_suite(root, "core")
        results.append({"check": "baseline (no patch)", "exit_code": code, "summary": summary, "expected": "exit 0"})
        for label, rel, old, new in patches:
            path = os.path.join(root, rel)
            with open(path, encoding="utf-8") as handle:
                original = handle.read()
            if old not in original:
                results.append({"check": label, "error": "patch target not found"})
                continue
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(original.replace(old, new, 1))
            suite = "content" if "worldpack" in rel else "core"
            code, failing, summary = run_suite(root, suite)
            results.append({"check": label, "suite": suite, "exit_code": code, "failing_tests": failing, "summary": summary, "expected": "tests fail"})
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(original)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return results


def _cli(args, data_dir, payload=None, entry=None):
    argv = [sys.executable, entry or _runtime.ENTRY_SCRIPT] + list(args) + ["--json", "--data-dir", data_dir]
    temp = None
    if payload is not None:
        handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False)
        handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        handle.close()
        temp = handle.name
        argv += ["--input-file", temp]
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION") and k != "PYTHONPYCACHEPREFIX"}
    env["ADULT_TENSION_INCLUDE_DRAFTS"] = "1"
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env, timeout=300)
    finally:
        if temp:
            os.remove(temp)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


def _outcome(label, code, envelope, expected_code, located):
    error = envelope.get("error") or {}
    return {
        "check": label,
        "exit_code": code,
        "code": error.get("code"),
        "message": error.get("message"),
        "details": error.get("details", [])[:5],
        "expected": "exit 10, %s%s" % (expected_code, "，并指出位置" if located else ""),
        "as_expected": code == 10 and error.get("code") == expected_code and bool(located),
    }


def _tampered_skill(root, mutate):
    skill = os.path.join(root, "adult-tension")
    shutil.copytree(os.path.join(REPO, "skill", "adult-tension"), skill, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    path = os.path.join(skill, "content", "worlds", "harbor_night_shift.json")
    with open(path, encoding="utf-8") as handle:
        pack = json.load(handle)
    mutate(pack)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(pack, handle, ensure_ascii=False)
    return os.path.join(skill, "scripts", "adult_tension.py")


def cli_checks():
    results = []
    root = tempfile.mkdtemp(prefix="at-reverse-cli-")
    try:
        # 7.1 a referenced location deleted from the compiled content
        entry = _tampered_skill(os.path.join(root, "one"), lambda p: p.update(locations=[loc for loc in p["locations"] if loc["id"] != "tool_shed"]))
        code, env = _cli(["verify-content", "--skip-diversity"], os.path.join(root, "d1"), entry=entry)
        located = [d for d in (env.get("error") or {}).get("details", []) if "tool_shed" in d.get("reason", "") and d.get("world") == "harbor_night_shift"]
        results.append(_outcome("7.1 删掉内容里一个被引用的地点 → verify-content 失败并指出位置", code, env, "CONTENT_ERROR", located))
        # 7.2 a stale revision
        data = os.path.join(root, "d2")
        _code, opened = _cli(["new-game"], data, {"request_id": "rev_new_000001", "mode": "daily", "seed": 3})
        session = opened["data"]
        npc = next(c for c in session["context"]["scene"]["present"] if c != "player")
        commit = {
            "session_id": session["session_id"], "request_id": "rev_turn_00001", "expected_revision": session["revision"],
            "action_mode": "continue", "player_input": "继续", "operations": [{"op": "npc_action", "npc_id": npc, "action": "看了看表"}],
            "content_tags": [], "summary": "有人看表。", "open_action": "表针在走",
        }
        _cli(["commit-turn"], data, commit)
        code, env = _cli(["commit-turn"], data, dict(commit, request_id="rev_turn_00002"))
        results.append(_outcome("7.2 用过期 revision 提交 → STALE_REVISION", code, env, "STALE_REVISION", env.get("error", {}).get("current_revision") == session["revision"] + 1))
        # 7.3 one byte of an export changed
        _code, exported = _cli(["export-save"], data, {"session_id": session["session_id"]})
        path = exported["data"]["path"]
        with open(path, "rb") as handle:
            raw = bytearray(handle.read())
        position = raw.index(b'"turn":') + len(b'"turn":')
        raw[position] = ord("9") if raw[position] != ord("9") else ord("8")
        with open(path, "wb") as handle:
            handle.write(bytes(raw))
        code, env = _cli(["import-save"], data, {"request_id": "rev_import_001", "path": path})
        located = [d for d in (env.get("error") or {}).get("details", []) if d.get("path") == "$.checksum"]
        results.append(_outcome("7.3 篡改导出文件的一个字节 → 导入失败", code, env, "INVALID_INPUT", located))
        # 7.5 an anachronistic word in a location name
        entry = _tampered_skill(os.path.join(root, "five"), lambda p: p["locations"][0].update(name="扫码取件点"))
        code, env = _cli(["verify-content", "--skip-diversity"], os.path.join(root, "d5"), entry=entry)
        located = [d for d in (env.get("error") or {}).get("details", []) if d.get("path") == "$.locations[0].name"]
        results.append(_outcome("7.5 把地点名换成另一个时代的词 → 跨世界扫描失败", code, env, "CONTENT_ERROR", located))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return results


def main(argv):
    group = "all"
    if "--group" in argv:
        group = argv[argv.index("--group") + 1]
    os.makedirs(OUT, exist_ok=True)
    all_ok = True
    if group in ("all", "cli"):
        results = cli_checks()
        ok = all(r["as_expected"] for r in results)
        all_ok = all_ok and ok
        with open(os.path.join(OUT, "cli-checks.json"), "wb") as handle:
            handle.write(json.dumps({"ok": ok, "group": "cli", "checks": results}, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
        for item in results:
            sys.stdout.buffer.write(("cli   %-60s exit=%s code=%s %s\n" % (item["check"], item["exit_code"], item["code"], "OK" if item["as_expected"] else "UNEXPECTED")).encode("utf-8"))
        if group == "cli":
            return 0 if all_ok else 1
    for name in (sorted(GROUPS) if group == "all" else [group]):
        filename, patches = GROUPS[name]
        results = patch_checks(patches)
        ok = results and results[0]["exit_code"] == 0 and all(r.get("exit_code", 0) != 0 and r.get("failing_tests") for r in results[1:])
        all_ok = all_ok and bool(ok)
        report = {"ok": bool(ok), "group": name, "checks": results}
        with open(os.path.join(OUT, filename), "wb") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
        for item in results:
            sys.stdout.buffer.write(("%-5s %-45s exit=%s failing=%d\n" % (name, item["check"], item.get("exit_code"), len(item.get("failing_tests", [])))).encode("utf-8"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
