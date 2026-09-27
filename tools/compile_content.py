"""Compile content-src/ into skill/adult-tension/content/.

    python tools/compile_content.py           # validate and write
    python tools/compile_content.py --check   # exit 1 if the compiled files are stale

Sources are JSON. Era base packs (content-src/bases/) are merged into the
worlds that `extends` them at compile time; the runtime only sees complete
packs. Output is deterministic (sorted keys, LF, trailing newline), so the
same sources always produce byte-identical files.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

_runtime.use_runtime()

from adult_tension import schema as S  # noqa: E402
from adult_tension.domain import structure as ST  # noqa: E402
from adult_tension.domain import worldpack  # noqa: E402
from adult_tension.errors import AppError  # noqa: E402
from adult_tension.jsonio import decode_bytes, loads_strict, plain  # noqa: E402

SRC = os.path.join(_runtime.REPO_ROOT, "content-src")
OUT = os.path.join(_runtime.SKILL_ROOT, "content")

F = S.Field
TAGS_SPEC = S.Obj(
    {
        "schema_version": F(S.Int(1, 1)),
        "tags": F(
            S.List(
                S.Obj(
                    {
                        "id": F(S.Id()),
                        "label": F(S.Str(1, 20)),
                        "kind": F(S.Enum("intimacy", "conflict", "theme", "setting", "custom")),
                        "description": F(S.Str(1, 120)),
                    }
                ),
                min_items=1,
            )
        ),
    }
)
BASE_SPEC = S.Obj(
    {
        "schema_version": F(S.Int(1, 1)),
        "id": F(S.Id()),
        "base": F(S.Bool()),
        "era": F(S.Str(1, 40), required=False),
        "name_pools": F(S.Any(), required=False),
        "customs": F(S.List(S.Str(1, 200)), required=False),
        "rules": F(S.List(S.Any()), required=False),
        "forbidden_terms": F(S.List(S.Str(1, 20), unique=True), required=False),
        "notes": F(S.Str(0, 2000), required=False),
    }
)
REQUIRED_TAGS = set(ST.INTIMACY_TAGS) | set(ST.CONFLICT_TAGS) | {"substance", "pregnancy", "death", "workplace_power", "infidelity", "custom"}


def read_json(path):
    with open(path, "rb") as handle:
        return loads_strict(decode_bytes(handle.read(), path), path)


def dump(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode("utf-8")


def merge(base, world):
    out = dict(base)
    for key, value in world.items():
        if key in out and isinstance(out[key], list) and isinstance(value, list):
            merged = list(out[key])
            for item in value:
                if item not in merged:
                    merged.append(item)
            out[key] = merged
        elif key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


def load_sources():
    problems = []
    meta = read_json(os.path.join(SRC, "content.json"))
    tags_raw = read_json(os.path.join(SRC, "tags.json"))
    tags, errs = S.validate(TAGS_SPEC, plain(tags_raw))
    for e in errs:
        problems.append(dict(e, world="tags.json"))
    tag_ids = {t["id"] for t in (tags or {"tags": []})["tags"]}
    missing = REQUIRED_TAGS - tag_ids
    if missing:
        problems.append({"world": "tags.json", "path": "$.tags", "reason": "缺少必须的标签：%s" % "、".join(sorted(missing)), "hint": None})
    bases = {}
    base_dir = os.path.join(SRC, "bases")
    if os.path.isdir(base_dir):
        for name in sorted(os.listdir(base_dir)):
            if name.endswith(".json"):
                raw = plain(read_json(os.path.join(base_dir, name)))
                base, errs = S.validate(BASE_SPEC, raw)
                for e in errs:
                    problems.append(dict(e, world="bases/" + name))
                if base:
                    for term in base.get("forbidden_terms", []):
                        for text in base.get("customs", []):
                            if term in text:
                                problems.append({"world": "bases/" + name, "path": "$.customs", "reason": "底包文本含自己的禁用词：%s" % term, "hint": None})
                    bases[base["id"]] = raw
    worlds = {}
    world_dir = os.path.join(SRC, "worlds")
    for name in sorted(os.listdir(world_dir)):
        if not name.endswith(".json"):
            continue
        raw = plain(read_json(os.path.join(world_dir, name)))
        if raw.get("extends"):
            base = bases.get(raw["extends"])
            if base is None:
                problems.append({"world": name, "path": "$.extends", "reason": "底包不存在：%s" % raw["extends"], "hint": None})
                continue
            clean = {k: v for k, v in base.items() if k not in ("id", "base", "schema_version", "notes")}
            raw = merge(clean, raw)
            raw["extends"] = None
        worlds[name] = raw
    return meta, tags, tag_ids, worlds, problems


def compile_all():
    meta, tags, tag_ids, sources, problems = load_sources()
    packs = {}
    for name, raw in sources.items():
        pack, errs = worldpack.validate_world(raw, tag_ids=tag_ids)
        for e in errs:
            problems.append(dict(e, world=raw.get("id", name)))
        if pack is not None:
            if pack["id"] + ".json" != name:
                problems.append({"world": pack["id"], "path": "$.id", "reason": "文件名应为 %s.json" % pack["id"], "hint": None})
            packs[pack["id"]] = pack
    problems.extend(worldpack.cross_checks(packs, ST.generic_strings() + [t["label"] for t in (tags or {"tags": []})["tags"]]))
    files = {}
    if not problems:
        index = {
            "schema_version": 1,
            "content_version": meta["content_version"],
            "worlds": [
                {
                    "id": pack["id"],
                    "title": pack["title"],
                    "era": pack["era"],
                    "region": pack["region"],
                    "summary": pack["premise"],
                    "modes": [m for m, key in (("daily", "daily_activities"), ("pressure", "pressures")) if pack[key]],
                    "status": pack["status"],
                    "default_person": pack["default_person"],
                    "content_tags": pack["content_tags"],
                }
                for pack in sorted(packs.values(), key=lambda p: p["id"])
            ],
        }
        files["index.json"] = dump(index)
        files["tags.json"] = dump(tags)
        for world_id, pack in packs.items():
            files["worlds/%s.json" % world_id] = dump(pack)
    return files, problems


def main(argv):
    try:
        files, problems = compile_all()
    except AppError as err:
        print("source error: %s" % err.message)
        for d in err.details:
            print("  %s: %s" % (d["path"], d["reason"]))
        return 1
    if problems:
        for p in problems:
            line = "[%s] %s: %s" % (p.get("world", "?"), p["path"], p["reason"])
            if p.get("hint"):
                line += " —— %s" % p["hint"]
            sys.stdout.buffer.write((line + "\n").encode("utf-8"))
        sys.stdout.buffer.write(("%d problem(s); nothing written\n" % len(problems)).encode("utf-8"))
        return 1
    stale = []
    existing = set()
    for base, _dirs, names in os.walk(OUT):
        for name in names:
            existing.add(os.path.relpath(os.path.join(base, name), OUT).replace(os.sep, "/"))
    for rel, data in files.items():
        path = os.path.join(OUT, rel)
        current = open(path, "rb").read() if os.path.exists(path) else None
        if current != data:
            stale.append(rel)
            if "--check" not in argv:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as handle:
                    handle.write(data)
    extra = sorted(existing - set(files))
    for rel in extra:
        stale.append(rel + " (stale)")
        if "--check" not in argv:
            os.remove(os.path.join(OUT, rel))
    if "--check" in argv:
        print("stale: " + ", ".join(stale) if stale else "up to date")
        return 1 if stale else 0
    print(("compiled: " + ", ".join(stale)) if stale else "up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
