"""Scaffold a new world pack (CONTENT_BIBLE.md 8.2, step 1).

    python tools/new_world.py <id> --title 标题 --era 时代 --region 地域
                              [--premise ...] [--tone 词,词] [--dir DIR] [--force]

Writes <dir>/<id>.json (default content-src/worlds/) with every field present,
every list empty and status "draft". The skeleton parses and passes the
structural checks; `verify-content --file <path>` then fails it only for what
is still missing, item by item, until the author has written the content.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

DEFAULT_DIR = os.path.join(_runtime.REPO_ROOT, "content-src", "worlds")
LIST_FIELDS = (
    "rules",
    "customs",
    "player_identities",
    "locations",
    "character_templates",
    "background_cast",
    "channels",
    "tension_engines",
    "cast_combos",
    "daily_activities",
    "pressures",
    "hooks",
    "twists",
    "forbidden_terms",
    "content_tags",
)


def skeleton(world_id, title, era, region, premise=None, tone=None):
    pack = {
        "schema_version": 1,
        "id": world_id,
        "title": title,
        "extends": None,
        "era": era,
        "region": region,
        "premise": premise or "%s，%s。" % (era, region),
        "tone": tone or ["日常"],
        "style_hint": "写%s的器物、声音与称呼，句子短，少写心理独白。" % era,
        "clock_start": {"label": None, "minute": 1200},
        "clock_style": "hm",
        "default_person": "second",
        "default_npc_gender_mix": {"female": 0.5, "male": 0.5, "nonbinary": 0.0},
        "stage_labels": None,
        "name_pools": {"family": [], "given_female": [], "given_male": [], "given_neutral": [], "nickname_patterns": []},
        "status": "draft",
        "notes": "由 new-world 生成的骨架；按 CONTENT_BIBLE.md 第 3 节补齐内容。",
    }
    for field in LIST_FIELDS:
        pack[field] = []
    return pack


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--era", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--premise")
    parser.add_argument("--tone", help="逗号分隔的基调词")
    parser.add_argument("--dir", default=DEFAULT_DIR)
    parser.add_argument("--force", action="store_true", help="覆盖已有文件")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", args.id):
        print("世界 ID 只能用小写字母、数字和下划线，以字母开头：%s" % args.id)
        return 2
    path = os.path.join(args.dir, args.id + ".json")
    if os.path.exists(path) and not args.force:
        print("文件已存在：%s（要覆盖请加 --force）" % path)
        return 2
    tone = [t.strip() for t in args.tone.split(",") if t.strip()] if args.tone else None
    pack = skeleton(args.id, args.title, args.era, args.region, args.premise, tone)
    os.makedirs(args.dir, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(pack, ensure_ascii=False, indent=1) + "\n")
    print("已生成骨架：%s" % path)
    print("下一步：python %s verify-content --json --file %s" % (os.path.relpath(_runtime.ENTRY_SCRIPT), path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
