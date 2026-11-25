"""Test bootstrap: delegates to helpers.bootstrap so all suites share one setup."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from helpers.bootstrap import E2E_DIR, REPO_ROOT, TESTS_DIR, setup  # noqa: E402, F401

setup()
