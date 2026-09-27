"""File-system helpers for tests (temporary directories only)."""

import contextlib
import getpass
import os
import shutil
import stat
import subprocess
import sys
import tempfile

from .cli import SKILL_ROOT


@contextlib.contextmanager
def temp_dir(prefix="at-test-"):
    path = tempfile.mkdtemp(prefix=prefix)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@contextlib.contextmanager
def unwritable_dir(parent):
    """A directory the current user cannot write into (icacls on Windows, chmod elsewhere)."""
    target = os.path.join(parent, "locked")
    os.makedirs(target)
    if sys.platform.startswith("win"):
        user = getpass.getuser()
        subprocess.run(["icacls", target, "/deny", "%s:(OI)(CI)(W,AD,WD)" % user], check=True, capture_output=True)
        try:
            yield target
        finally:
            subprocess.run(["icacls", target, "/remove:d", user], check=True, capture_output=True)
    else:
        os.chmod(target, stat.S_IRUSR | stat.S_IXUSR)
        try:
            yield target
        finally:
            os.chmod(target, stat.S_IRWXU)


def copy_skill(dest_parent, name="adult-tension"):
    """Copy the Skill directory (without caches) for tamper tests."""
    dest = os.path.join(dest_parent, name)
    shutil.copytree(SKILL_ROOT, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dest
