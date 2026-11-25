"""Locating the user data directory (SKILL_PACKAGING.md section 6).

Order: --data-dir, then ADULT_TENSION_HOME, then the platform default.
The data directory never lives inside the Skill directory.
"""

import os
import sys
import time

APP_DIR_NAME = "adult-tension"
ENV_VAR = "ADULT_TENSION_HOME"
DB_FILE = "adult_tension.db"
MARKER_FILE = "version.json"
SUBDIRS = ("backups", "exports", "inputs", "logs")
RESERVED_NAMES = frozenset({"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)})
KNOWN_BOOL_FLAGS = frozenset({"--json", "--pretty", "--debug", "--help", "-h", "--include-drafts", "--skip-diversity", "--stats"})


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
    """Find the last value of --data-dir in raw argv without full parsing."""
    found = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--data-dir" and index + 1 < len(argv):
            if argv[index + 1] in KNOWN_BOOL_FLAGS:
                index += 1
                continue
            found = argv[index + 1]
            index += 2
            continue
        if item.startswith("--data-dir="):
            found = item.split("=", 1)[1]
        index += 1
    return found


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


INPUT_KEEP_SECONDS = 24 * 3600
_PRUNE_CACHE = {}


def prune_inputs(data_dir, now=None):
    """Delete input files (*.json) older than a day: they hold what the
    player said and nothing reads them after the call they were written for.
    Only that folder, only regular files; failures are ignored."""
    folder = inputs_dir(data_dir)
    try:
        stat_before = os.stat(folder)
    except OSError:
        return 0
    ts = time.time() if now is None else now
    if now is None:
        cached = _PRUNE_CACHE.get(folder)
        if cached is not None and cached[0] == stat_before.st_mtime_ns and 0.0 <= ts - cached[1] < 60.0:
            return 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0
    cutoff = ts - INPUT_KEEP_SECONDS
    removed = 0
    for name in names:
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path) and not os.path.islink(path) and os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    if now is None:
        try:
            _PRUNE_CACHE[folder] = (os.stat(folder).st_mtime_ns, ts)
        except OSError:
            _PRUNE_CACHE.pop(folder, None)
    return removed


def marker_path(data_dir):
    return os.path.join(data_dir, MARKER_FILE)


def pycache_dir(data_dir):
    return os.path.join(data_dir, "cache", "pycache")
