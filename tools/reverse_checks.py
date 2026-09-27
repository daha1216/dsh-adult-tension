"""Reverse verification (ACCEPTANCE.md section 7): break things on purpose.

    python tools/reverse_checks.py [--json]

Works on a temporary copy of the repository, never on the working tree.
Every check must FAIL the way the acceptance criteria describe; the tool
exits 0 only when all of them did. Outputs go to reports/reverse/.
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


def age_checks():
    results = []
    root = tempfile.mkdtemp(prefix="at-reverse-")
    try:
        copy_repo(root)
        code, _failing, summary = run_suite(root, "core")
        results.append({"check": "baseline (no patch)", "exit_code": code, "summary": summary, "expected": "exit 0"})
        for label, rel, old, new in AGE_PATCHES:
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
    os.makedirs(OUT, exist_ok=True)
    results = age_checks()
    ok = results and results[0]["exit_code"] == 0 and all(r.get("exit_code", 0) != 0 and r.get("failing_tests") for r in results[1:])
    report = {"ok": bool(ok), "age_checks": results}
    with open(os.path.join(OUT, "age-checks.json"), "wb") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    for item in results:
        sys.stdout.buffer.write(("%-45s exit=%s failing=%d\n" % (item["check"], item.get("exit_code"), len(item.get("failing_tests", [])))).encode("utf-8"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
