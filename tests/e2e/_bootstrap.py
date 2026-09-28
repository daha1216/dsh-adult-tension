"""Test bootstrap: runtime, helpers and the e2e harness on sys.path; caches outside the Skill."""

import os
import sys

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(E2E_DIR)
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.pycache_prefix = os.path.join(REPO_ROOT, ".pycache")
for path in (
    os.path.join(REPO_ROOT, "skill", "adult-tension", "runtime"),
    os.path.join(REPO_ROOT, "tools"),
    TESTS_DIR,
    os.path.join(E2E_DIR, "harness"),
    os.path.join(E2E_DIR, "calibration"),
):
    if path not in sys.path:
        sys.path.insert(0, path)
