"""Shared test path bootstrap: runtime, tools, helpers and e2e harness."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(TESTS_DIR)
E2E_DIR = os.path.join(TESTS_DIR, "e2e")


def setup():
    sys.pycache_prefix = os.path.join(REPO_ROOT, ".pycache")
    for path in (
        os.path.join(REPO_ROOT, "skill", "adult-tension", "runtime"),
        os.path.join(REPO_ROOT, "tools"),
        TESTS_DIR,
    ):
        if path not in sys.path:
            sys.path.insert(0, path)
    for extra in (
        os.path.join(E2E_DIR, "harness"),
        os.path.join(E2E_DIR, "calibration"),
    ):
        if extra not in sys.path:
            sys.path.append(extra)


setup()
