"""Print opening structures for a few seeds (CONTENT_BIBLE.md 8.2, step 5).

    python tools/preview_openings.py --world <id> --mode daily|pressure
                                     [--seeds 5] [--start 1] [--file PATH] [--json]

No model, no database: the same planning and instantiation as `new-game`
with that seed, that mode and the world locked, so an author sees at once
whether the combinations hold together. --file previews a source pack that
is not compiled yet.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

_runtime.use_runtime()

from adult_tension.content.store import ContentStore  # noqa: E402
from adult_tension.domain import opening, worldpack  # noqa: E402
from adult_tension.errors import AppError  # noqa: E402
from adult_tension.jsonio import decode_bytes, loads_strict, plain  # noqa: E402


def load_pack(world_id, path):
    store = ContentStore(os.path.join(_runtime.SKILL_ROOT, "content"))
    if path is None:
        return store.world(world_id), store.index()["content_version"]
    with open(path, "rb") as handle:
        raw = plain(loads_strict(decode_bytes(handle.read(), path), path))
    pack, problems = worldpack.validate_world(raw, custom=raw.get("custom"), tag_ids=[t["id"] for t in store.tags()["tags"]])
    if pack is None:
        raise AppError("CONTENT_ERROR", "世界包有 %d 处问题；先用 verify-content --file 修好" % len(problems), problems)
    return pack, store.index()["content_version"]


def preview(pack, content_version, mode, seed):
    # new-game locks a pack world by id; a custom world comes alone, with no lock.
    locks = {} if pack.get("custom") else {"world_id": pack["id"]}
    conditions = opening.normalize_conditions({"mode": mode, "locks": locks})
    _state, payload = opening.build(pack, seed, conditions, content_version)
    out = {
        "seed": seed,
        "signature": payload["signature"],
        "location": payload["scene"]["location"],
        "player": "%s（%s，%d 岁，%s）" % (payload["player"]["name"], payload["player"]["role"], payload["player"]["age"], payload["player"]["social_position"]),
        "npcs": ["%s（%s，%d 岁，%s）" % (n["name"], n["role"], n["age"], n["gender"]) for n in payload["npcs"]],
        "chemistry": payload["tension"]["chemistry"],
        "hook": "%s：%s" % (payload["hook"]["kind"], payload["hook"]["text"]),
    }
    if mode == "daily":
        out["activity"] = payload["activity"]["title"]
    else:
        out["pressure"] = "%s（%s；%s）" % (payload["pressure"]["title"], payload["pressure"]["immediate"], payload["pressure"]["near"]["text"])
    return out


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--world", required=True)
    parser.add_argument("--mode", required=True, choices=("daily", "pressure"))
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        pack, version = load_pack(args.world, args.file)
        rows = [preview(pack, version, args.mode, seed) for seed in range(args.start, args.start + args.seeds)]
    except AppError as err:
        print("%s：%s" % (err.code, err.message))
        for d in err.details[:20]:
            print("  %s：%s" % (d.get("path"), d.get("reason")))
        return 1
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    for row in rows:
        print("种子 %d  %s" % (row["seed"], row["signature"]))
        print("  地点：%s" % row["location"])
        print("  玩家：%s" % row["player"])
        print("  人物：%s" % "；".join(row["npcs"]))
        print("  %s：%s" % ("活动" if args.mode == "daily" else "压力", row.get("activity") or row.get("pressure")))
        print("  关系：%s" % row["chemistry"])
        print("  钩子：%s" % row["hook"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
