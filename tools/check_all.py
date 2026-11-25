"""Every local gate in one run, with a summary at the end.

    python tools/check_all.py [--quick] [--fuzz] [--only NAME[,NAME...]]

Runs, in order: the four test suites (core, content, integration, e2e
harness), the three generated-file and package checks (validate_skill,
gen_references --check, compile_content --check), the benchmark and the
reverse checks. --quick leaves out the benchmark and the reverse checks;
--fuzz adds tools/fuzz.py. Each step runs in its own process; its output is
kept in reports/check_all/<step>.log and only failing steps are echoed.
Exits 1 when any step failed.
"""

import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

REPO = _runtime.REPO_ROOT
OUT = os.path.join(REPO, "reports", "check_all")
PY = sys.executable

STEPS = [
    ("core", [PY, "-m", "unittest", "discover", "-s", "tests/core"], False),
    ("content", [PY, "-m", "unittest", "discover", "-s", "tests/content"], False),
    ("integration", [PY, "-m", "unittest", "discover", "-s", "tests/integration"], False),
    ("e2e", [PY, "-m", "unittest", "discover", "-s", "tests/e2e"], False),
    ("validate_skill", [PY, "tools/validate_skill.py"], False),
    ("gen_references", [PY, "tools/gen_references.py", "--check"], False),
    ("compile_content", [PY, "tools/compile_content.py", "--check"], False),
    ("benchmark", [PY, "tools/benchmark.py"], True),
    ("reverse_checks", [PY, "tools/reverse_checks.py", "--group", "all"], True),
]
FUZZ = ("fuzz", [PY, "tools/fuzz.py", "all"], False)


def headline(name, text):
    """One line worth reading from a step's output."""
    if name in ("core", "content", "integration", "e2e"):
        ran = re.findall(r"Ran (\d+) tests? in ([\d.]+s)", text)
        verdict = re.findall(r"^(OK.*|FAILED.*)$", text, re.M)
        return "%s tests, %s, %s" % (ran[-1][0], ran[-1][1], verdict[-1]) if ran and verdict else ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1][:120] if lines else ""


def main(argv):
    quick = "--quick" in argv
    steps = [s for s in STEPS if not (quick and s[2])]
    if "--fuzz" in argv:
        steps.append(FUZZ)
    if "--only" in argv:
        wanted = set(_runtime.opt_value(argv, "--only").split(","))
        steps = [s for s in STEPS + [FUZZ] if s[0] in wanted]
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPYCACHEPREFIX=os.path.join(REPO, ".pycache"))
    rows = []
    for name, cmd, _slow in steps:
        start = time.time()
        proc = subprocess.run(cmd, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        took = time.time() - start
        text = proc.stdout.decode("utf-8", "replace")
        with open(os.path.join(OUT, name + ".log"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        ok = proc.returncode == 0
        rows.append((name, ok, took, headline(name, text)))
        print("%-16s %-4s %6.1fs  %s" % (name, "ok" if ok else "FAIL", took, rows[-1][3]), flush=True)
        if not ok:
            sys.stdout.write("\n".join(text.splitlines()[-40:]) + "\n")
    failed = [r[0] for r in rows if not r[1]]
    print("\ncheck_all: %d step(s), %s, %.0fs; logs in %s" % (
        len(rows), "all passed" if not failed else "FAILED: " + ", ".join(failed), sum(r[2] for r in rows), os.path.relpath(OUT, REPO)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
