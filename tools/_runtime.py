"""Shared bootstrap for development tools.

Puts the Skill runtime on sys.path and keeps bytecode caches out of the Skill
directory (they go to <repo>/.pycache, which is ignored by git).
"""

import os
import sys

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
