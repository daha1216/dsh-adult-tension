"""Locating the user data directory (SKILL_PACKAGING.md section 6).

Order: --data-dir, then ADULT_TENSION_HOME, then the platform default.
The data directory never lives inside the Skill directory.
"""

import os
import sys

APP_DIR_NAME = "adult-tension"
ENV_VAR = "ADULT_TENSION_HOME"
DB_FILE = "adult_tension.db"
MARKER_FILE = "version.json"
SUBDIRS = ("backups", "exports", "inputs", "logs")


def platform_default(platform=None, environ=None, home=None):
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    home = os.path.expanduser("~") if home is None else home
    if platform.startswith("win"):
        base = environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return os.path.join(base, APP_DIR_NAME)
    if platform == "darwin":
        return os.path.join(home, "Library", "Application Support", APP_DIR_NAME)
    base = environ.get("XDG_DATA_HOME")
    if not base or not os.path.isabs(base):
        base = os.path.join(home, ".local", "share")
    return os.path.join(base, APP_DIR_NAME)


def resolve(arg_value=None, environ=None, platform=None, home=None):
    """Return (absolute path, source) where source is arg, env or default."""
    environ = os.environ if environ is None else environ
    if arg_value:
        return os.path.abspath(os.path.expanduser(arg_value)), "arg"
    env_value = environ.get(ENV_VAR)
    if env_value:
        return os.path.abspath(os.path.expanduser(env_value)), "env"
    return os.path.abspath(platform_default(platform, environ, home)), "default"


def data_dir_arg(argv):
    """Find the value of --data-dir in raw argv without full parsing."""
    for index, item in enumerate(argv):
        if item == "--data-dir" and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith("--data-dir="):
            return item.split("=", 1)[1]
    return None


def is_inside(path, root):
    try:
        path = os.path.normcase(os.path.realpath(path))
        root = os.path.normcase(os.path.realpath(root))
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def db_path(data_dir):
    return os.path.join(data_dir, DB_FILE)


def inputs_dir(data_dir):
    """Where the host writes the runtime's input files (SKILL.md). They carry
    what the player said, so they are user data: in the data directory,
    never in the Skill directory (SKILL_PACKAGING.md 1)."""
    return os.path.join(data_dir, "inputs")


def marker_path(data_dir):
    return os.path.join(data_dir, MARKER_FILE)


def pycache_dir(data_dir):
    return os.path.join(data_dir, "cache", "pycache")
