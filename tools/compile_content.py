"""Compile content-src/ into skill/adult-tension/content/.

    python tools/compile_content.py           # validate and write
    python tools/compile_content.py --check   # exit 1 if the compiled files are stale

Sources are JSON. Era base packs (content-src/bases/) are merged into the
worlds that `extends` them at compile time; the runtime only sees complete
packs. Output is deterministic (sorted keys, LF, trailing newline), so the
same sources always produce byte-identical files.

The same content version and seed must give the same opening (DESIGN_DECISIONS
D10). content-src/content.lock.json pairs the version with a fingerprint of
the compiled content and of a fixed sample of openings, so a change to either
the content or the opening algorithm stops the compile until content.json
gets a new content_version.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

_runtime.use_runtime()

from adult_tension import schema as S  # noqa: E402
from adult_tension.content.verify import TAG_TABLE as TAGS_SPEC  # noqa: E402
from adult_tension.domain import structure as ST  # noqa: E402
from adult_tension.domain import opening, worldpack  # noqa: E402
from adult_tension.errors import AppError  # noqa: E402
from adult_tension.jsonio import decode_bytes, loads_strict  # noqa: E402

SRC = os.path.join(_runtime.REPO_ROOT, "content-src")
LOCK = os.path.join(SRC, "content.lock.json")
OUT = os.path.join(_runtime.SKILL_ROOT, "content")

F = S.Field
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


_COMPILED_PACK_CACHE = {}


def dump(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


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


def fingerprint(files):
    """The compiled content, without its version, and the openings it gives
    for a fixed seed in each mode for each player gender."""
    digest = hashlib.sha256()
    for rel in sorted(files):
        data = files[rel]
        if rel == "index.json":
            index = json.loads(data.decode("utf-8"))
            index.pop("content_version")
            data = dump(index)
        digest.update(rel.encode("utf-8") + b"\0" + data + b"\0")
    for rel in sorted(files):
        if not rel.startswith("worlds/"):
            continue
        raw_bytes = files[rel]
        cached = _COMPILED_PACK_CACHE.get(rel)
        if cached is not None and cached[0] is raw_bytes:
            pack = cached[1]
        else:
            pack = json.loads(raw_bytes.decode("utf-8"))
        for mode in ("daily", "pressure"):
            for gender in (None, "male", "female"):
                conditions = opening.normalize_conditions({"mode": mode, "player": {"gender": gender}})
                try:
                    _state, payload = opening.build(pack, 7, conditions, "")
                except AppError as err:
                    payload = {"error": err.code}
                digest.update(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\0")
    return digest.hexdigest()


def _next_version(version):
    head, _, last = version.rpartition(".")
    return "%s.%d" % (head, int(last) + 1) if head and last.isdigit() else version + ".1"


def version_check(version, files):
    """(lock to write or None, problem or None)."""
    current = fingerprint(files)
    lock = read_json(LOCK) if os.path.exists(LOCK) else None
    if lock and lock["content_version"] == version:
        if lock["fingerprint"] == current:
            return None, None
        return None, {
            "world": "content.json",
            "path": "$.content_version",
            "reason": "内容或开局算法变了，同一种子会开出不同的局，但内容版本还是 %s" % version,
            "hint": "在 content-src/content.json 把 content_version 改成新的版本号（例如 %s → %s）再编译" % (version, _next_version(version)),
        }
    return {"content_version": version, "fingerprint": current}, None


def load_sources():
    problems = []
    meta = read_json(os.path.join(SRC, "content.json"))
    tags_raw = read_json(os.path.join(SRC, "tags.json"))
    tags, errs = S.validate(TAGS_SPEC, tags_raw)
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
                raw = read_json(os.path.join(base_dir, name))
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
        raw = read_json(os.path.join(world_dir, name))
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
        ordered_packs = sorted(packs.values(), key=lambda p: p["id"])
        dumped_worlds = {pack["id"]: dump(pack) for pack in ordered_packs}
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
                    # doctor checks only the worlds whose bytes differ from what was validated here
                    "sha256": hashlib.sha256(dumped_worlds[pack["id"]]).hexdigest(),
                }
                for pack in ordered_packs
            ],
        }
        files["index.json"] = dump(index)
        files["tags.json"] = dump(tags)
        _COMPILED_PACK_CACHE.clear()
        for pack in ordered_packs:
            rel = "worlds/%s.json" % pack["id"]
            raw_bytes = dumped_worlds[pack["id"]]
            files[rel] = raw_bytes
            _COMPILED_PACK_CACHE[rel] = (raw_bytes, pack)
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
    lock, problem = version_check(json.loads(files["index.json"].decode("utf-8"))["content_version"], files)
    if problem:
        sys.stdout.buffer.write(("[%s] %s: %s —— %s\nnothing written\n" % (problem["world"], problem["path"], problem["reason"], problem["hint"])).encode("utf-8"))
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
    if lock:
        # a new content_version: pair it with what it now gives
        stale.append("content-src/content.lock.json")
        if "--check" not in argv:
            with open(LOCK, "wb") as handle:
                handle.write(dump(lock))
    if "--check" in argv:
        print("stale: " + ", ".join(stale) if stale else "up to date")
        return 1 if stale else 0
    print(("compiled: " + ", ".join(stale)) if stale else "up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
