"""Shared bootstrap for development tools.

Puts the Skill runtime on sys.path and keeps bytecode caches out of the Skill
directory (they go to <repo>/.pycache, which is ignored by git).
"""

import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_ROOT = os.path.join(REPO_ROOT, "skill", "adult-tension")
RUNTIME_DIR = os.path.join(SKILL_ROOT, "runtime")
ENTRY_SCRIPT = os.path.join(SKILL_ROOT, "scripts", "adult_tension.py")

sys.pycache_prefix = os.path.join(REPO_ROOT, ".pycache")


def use_runtime(skill_root=None):
    runtime = os.path.join(os.path.abspath(skill_root), "runtime") if skill_root else RUNTIME_DIR
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    return runtime


def opt_value(argv, flag):
    idx = argv.index(flag)
    if idx + 1 >= len(argv) or argv[idx + 1].startswith("--"):
        raise SystemExit("error: %s requires a value" % flag)
    return argv[idx + 1]


def opt_int(argv, flag):
    raw = opt_value(argv, flag)
    try:
        return int(raw)
    except ValueError:
        raise SystemExit("error: %s expects an integer, got %r" % (flag, raw))


def clean_tool_env(extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION") and k != "PYTHONPYCACHEPREFIX"}
    if extra:
        env.update(extra)
    return env


def run_entry(args, data_dir=None, payload=None, env=None, entry=None, timeout=120):
    argv = [sys.executable, entry or ENTRY_SCRIPT] + list(args)
    if "--json" not in argv:
        argv.append("--json")
    if data_dir is not None:
        argv += ["--data-dir", data_dir]
    temp = None
    if payload is not None:
        handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False)
        handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        handle.close()
        temp = handle.name
        argv += ["--input-file", temp]
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            env=env if env is not None else clean_tool_env(),
            timeout=timeout,
        )
    finally:
        if temp:
            os.remove(temp)
    envelope = json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else None
    return proc.returncode, envelope, proc
