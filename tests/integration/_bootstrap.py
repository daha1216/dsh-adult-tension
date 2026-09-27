"""Test bootstrap: runtime and helpers on sys.path; caches outside the Skill."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.pycache_prefix = os.path.join(REPO_ROOT, ".pycache")
for path in (
    os.path.join(REPO_ROOT, "skill", "adult-tension", "runtime"),
    os.path.join(REPO_ROOT, "tools"),
    TESTS_DIR,
):
    if path not in sys.path:
        sys.path.insert(0, path)
