"""Reverse verification (ACCEPTANCE.md section 7): break things on purpose.

    python tools/reverse_checks.py [--group age|time|all]

Works on a temporary copy of the repository, never on the working tree.
Every check must FAIL the way the acceptance criteria describe; the tool
exits 0 only when all of them did. Outputs go to reports/reverse/.

Groups:
  age   ACCEPTANCE 7.4: each age check commented out makes tests fail
  time  stage 3 gates: required offscreen beats, undo reverting facts, the
        retcon knowledge rule, the settlement order, chapter archiving
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


def main(argv):
    group = "all"
    if "--group" in argv:
        group = argv[argv.index("--group") + 1]
    os.makedirs(OUT, exist_ok=True)
    all_ok = True
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
