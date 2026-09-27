"""Stage 0 exit evidence (DELIVERY_PLAN.md stage 0).

    python tools/evidence_stage0.py

Writes to reports/stage0/:
  doctor-fresh.json        doctor on a brand-new data directory
  doctor-unwritable.json   doctor on a directory the user cannot write
  doctor-initialized.json  doctor again on the initialized directory (fast path)
  old-python.json          the entry script under a faked Python 3.9
Each file records the command, exit code and the exact stdout envelope.
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

sys.path.insert(0, os.path.join(_runtime.REPO_ROOT, "tests"))
from helpers.fs import unwritable_dir  # noqa: E402

OUT = os.path.join(_runtime.REPO_ROOT, "reports", "stage0")


def call(argv, env=None):
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


def save(name, argv, code, envelope):
    record = {"argv": argv, "exit_code": code, "stdout": envelope}
    with open(os.path.join(OUT, name), "wb") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    print("%-26s exit=%s ok=%s %s" % (name, code, envelope["ok"], (envelope.get("error") or {}).get("code", "")))


def main():
    os.makedirs(OUT, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION")}
    tmp = tempfile.mkdtemp(prefix="at-evidence-")
    fresh = os.path.join(tmp, "data")
    argv = [sys.executable, _runtime.ENTRY_SCRIPT, "doctor", "--json", "--data-dir", fresh]
    save("doctor-fresh.json", argv, *call(argv, env))
    save("doctor-initialized.json", argv, *call(argv, env))
    with unwritable_dir(tmp) as locked:
        target = os.path.join(locked, "data")
        argv = [sys.executable, _runtime.ENTRY_SCRIPT, "doctor", "--json", "--data-dir", target]
        save("doctor-unwritable.json", argv, *call(argv, env))
    fake = (
        "import sys, runpy; sys.version_info = (3, 9, 18, 'final', 0); "
        "sys.argv = [%r, 'doctor', '--json']; runpy.run_path(%r, run_name='__main__')" % (_runtime.ENTRY_SCRIPT, _runtime.ENTRY_SCRIPT)
    )
    argv = [sys.executable, "-c", fake]
    save("old-python.json", argv, *call(argv, env))


if __name__ == "__main__":
    main()
