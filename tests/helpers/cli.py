"""Run the real entry script in a fresh process, as a host would."""

import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL_ROOT = os.path.join(REPO_ROOT, "skill", "adult-tension")
ENTRY = os.path.join(SKILL_ROOT, "scripts", "adult_tension.py")

_SCRUB = ("ADULT_TENSION_HOME", "ADULT_TENSION_FAULT", "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONPATH", "PYTHONPYCACHEPREFIX")


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in _SCRUB}
    env.update({k: v for k, v in extra.items() if v is not None})
    return env


def run_cli(args, data_dir=None, payload=None, stdin_bytes=None, env=None, entry=ENTRY, python=None, timeout=60):
    """Return (exit_code, envelope, raw_stdout). payload goes through --input-file."""
    argv = [python or sys.executable, entry] + list(args)
    if "--json" not in argv:
        argv.append("--json")
    if data_dir is not None:
        argv += ["--data-dir", data_dir]
    temp_path = None
    if payload is not None:
        handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False)
        handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        handle.close()
        temp_path = handle.name
        argv += ["--input-file", temp_path]
    try:
        proc = subprocess.run(
            argv,
            input=stdin_bytes,
            stdin=None if stdin_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env if env is not None else clean_env(),
            timeout=timeout,
        )
    finally:
        if temp_path:
            os.remove(temp_path)
    raw = proc.stdout
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise AssertionError("stdout is not one JSON envelope: %r / stderr %r" % (raw[:300], proc.stderr[:500]))
    return proc.returncode, envelope, raw
