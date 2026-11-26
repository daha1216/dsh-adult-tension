"""Copy the Skill directory to an install location (host tests, release drills).

    python tools/install_skill.py <dest_dir> [--from <skill_dir>] [--replace]

Copies only the files a published Skill may contain (the same rule as
tools/validate_skill.py), so caches and stray files never travel along.
If <dest_dir> is a parent skills folder rather than a directory named
`adult-tension`, the Skill is placed in `<dest_dir>/adult-tension` so an
upgrade with --replace never wipes sibling plugins and directory-name
validation passes.
"""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402
import validate_skill  # noqa: E402

SKILL_DIR_NAME = "adult-tension"


def resolve_dest(dest, skill_name=SKILL_DIR_NAME):
    dest = os.path.abspath(dest)
    if os.path.basename(os.path.normpath(dest)) == skill_name:
        return dest
    if os.path.isfile(os.path.join(dest, "SKILL.md")):
        return dest
    return os.path.join(dest, skill_name)


def _check_disjoint(source, target):
    real_src = os.path.normcase(os.path.realpath(source))
    real_dst = os.path.normcase(os.path.realpath(target))
    try:
        common = os.path.commonpath([real_src, real_dst])
    except ValueError:
        return
    if common in (real_src, real_dst):
        raise SystemExit("源目录与目标目录不能相同或互为父子目录：%s -> %s" % (source, target))


def install(source, dest, replace=False):
    source = os.path.abspath(source)
    if not os.path.isdir(source):
        raise SystemExit("源 Skill 目录不存在：%s" % source)
    target_root = resolve_dest(dest)
    _check_disjoint(source, target_root)
    if os.path.exists(target_root):
        if not replace:
            raise SystemExit("目标目录已存在（覆盖请加 --replace）：%s" % target_root)
        if not os.path.isdir(target_root):
            raise SystemExit("目标路径已存在且不是目录：%s" % target_root)
        if os.listdir(target_root) and not os.path.isfile(os.path.join(target_root, "SKILL.md")):
            raise SystemExit("拒绝清空非 Skill 目录（缺少 SKILL.md）：%s" % target_root)
        shutil.rmtree(target_root)
    copied = 0
    for base, dirs, names in os.walk(source):
        dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
        for name in names:
            src = os.path.join(base, name)
            rel = os.path.relpath(src, source).replace(os.sep, "/")
            if not validate_skill._allowed(rel):
                continue
            target = os.path.join(target_root, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(src, target)
            copied += 1
    return copied


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python tools/install_skill.py",
        description="将发布版 Skill 目录复制安装到目标位置（自动过滤缓存与开发杂物）。",
    )
    parser.add_argument("dest", metavar="<dest_dir>", help="安装目标目录（若非 adult-tension 目录则自动安装到其下的 adult-tension 子目录）")
    parser.add_argument("--from", dest="source", default=_runtime.SKILL_ROOT, metavar="<skill_dir>", help="指定源 Skill 目录（默认使用仓库内 skill/adult-tension）")
    parser.add_argument("--replace", action="store_true", help="目标 adult-tension 目录已存在时先清空再覆盖升级")
    return parser


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    parser = build_parser()
    opts = parser.parse_args(argv)
    final_dest = resolve_dest(opts.dest)
    count = install(opts.source, final_dest, replace=opts.replace)
    print("已安装 %d 个文件到 %s" % (count, final_dest))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
