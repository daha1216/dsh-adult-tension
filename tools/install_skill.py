"""Copy the Skill directory to an install location (host tests, release drills).

    python tools/install_skill.py <dest_dir> [--from <skill_dir>] [--replace]

Copies only the files a published Skill may contain (the same rule as
tools/validate_skill.py), so caches and stray files never travel along.
With --replace an existing destination is removed first (upgrade = replace
the Skill directory; the data directory is never inside it).
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402
import validate_skill  # noqa: E402


def install(source, dest, replace=False):
    source = os.path.abspath(source)
    dest = os.path.abspath(dest)
    if os.path.exists(dest):
        if not replace:
            raise SystemExit("destination exists (use --replace): %s" % dest)
        shutil.rmtree(dest)
    copied = 0
    for base, dirs, names in os.walk(source):
        dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
        for name in names:
            src = os.path.join(base, name)
            rel = os.path.relpath(src, source).replace(os.sep, "/")
            if not validate_skill._allowed(rel):
                continue
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(src, target)
            copied += 1
    return copied


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    source = _runtime.SKILL_ROOT
    if "--from" in argv:
        source = argv[argv.index("--from") + 1]
        args = [a for a in args if a != source]
    count = install(source, args[0], replace="--replace" in argv)
    print("installed %d files into %s" % (count, os.path.abspath(args[0])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
