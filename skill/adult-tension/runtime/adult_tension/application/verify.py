"""`verify-content`: the machine gate for content (CONTENT_BIBLE.md section 6).

Checks the compiled content in the Skill directory: every pack's structure,
semantics, era and boundary rules; cross-pack checks; fixed-seed openings;
and the anti-collapse diversity gate. Output is meant for people: every
problem names the world, the JSON path, the reason and a hint.
"""

from .. import schema as S
from ..domain import opening_checks, worldpack
from ..domain import structure as ST
from ..errors import CONTENT_ERROR, AppError, detail
from . import specs

F = S.Field
TAG_TABLE = S.Obj(
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
GATE_BASES = (1, 2, 3)


def run(ctx, payload):
    from .service import validate

    payload = validate(specs.VERIFY_CONTENT, payload)
    store = ctx.content()
    problems = []
    index = store.index()
    tags, errs = S.validate(TAG_TABLE, store.tags())
    problems.extend(dict(e, code=CONTENT_ERROR, world="tags.json") for e in errs)
    tag_ids = {t["id"] for t in (tags or {"tags": []})["tags"]}
    if payload["file"]:
        return _verify_file(payload, tag_ids, problems)
    entries = index["worlds"]
    if payload["world"]:
        entries = [w for w in entries if w["id"] == payload["world"]]
        if not entries:
            raise AppError(CONTENT_ERROR, "没有这个世界：%s" % payload["world"], [detail("$.world", "世界不存在", None, CONTENT_ERROR)])
    packs = {}
    report = {"content_version": index["content_version"], "worlds": []}
    for entry in entries:
        world_report = {"id": entry["id"], "status": entry["status"], "problems": 0}
        try:
            raw = store.world_raw(entry["id"])
        except AppError as err:
            problems.extend(dict(d, code=CONTENT_ERROR, world=entry["id"]) for d in err.details)
            report["worlds"].append(world_report)
            continue
        pack, errs = worldpack.validate_world(raw, tag_ids=tag_ids)
        errs = [dict(e, world=entry["id"]) for e in errs]
        if pack is not None:
            for key, value in (("title", pack["title"]), ("status", pack["status"])):
                if entry.get(key) != value:
                    errs.append(dict(detail("content/index.json", "索引里的 %s 与世界包不一致" % key, "重新编译内容", CONTENT_ERROR), world=entry["id"]))
            packs[pack["id"]] = pack
            count, failures = opening_checks.fixed_seed_openings(pack)
            world_report["fixed_seed_openings"] = {"count": count, "failures": failures}
            for failure in failures:
                errs.append(
                    dict(
                        detail("opening:%s:%d" % (failure["mode"], failure["seed"]), "；".join(failure["problems"][:3]), "修内容或开局规则", CONTENT_ERROR),
                        world=entry["id"],
                    )
                )
            if not payload["skip_diversity"]:
                runs = []
                for mode in ("daily", "pressure"):
                    for base in GATE_BASES:
                        runs.append(opening_checks.diversity(pack, mode, base))
                world_report["diversity"] = runs
                if pack["status"] in ("review", "released"):
                    for item in runs:
                        if not item["pass"]:
                            failed = [k for k, c in item["checks"].items() if not c["pass"]]
                            errs.append(
                                dict(
                                    detail(
                                        "diversity:%s:base%d" % (item["mode"], item["base"]),
                                        "防坍缩指标不达标：%s" % "、".join("%s=%s" % (k, item["checks"][k]["value"]) for k in failed),
                                        "增加对应的内容（组合、活动/压力、钩子、身份），而不是调门槛",
                                        CONTENT_ERROR,
                                    ),
                                    world=entry["id"],
                                )
                            )
            if payload["stats"]:
                world_report["stats"] = worldpack.world_stats(pack)
        world_report["problems"] = len(errs)
        problems.extend(errs)
        report["worlds"].append(world_report)
    cross = worldpack.cross_checks(packs, ST.generic_strings() + [t["label"] for t in (tags or {"tags": []})["tags"]])
    problems.extend(cross)
    report["near_duplicate_threshold"] = worldpack.NEAR_DUP_THRESHOLD
    report["problems"] = len(problems)
    if problems:
        raise AppError(CONTENT_ERROR, "内容校验发现 %d 处问题" % len(problems), problems, report=report)
    report["ok"] = True
    return report


def _verify_file(payload, tag_ids, problems):
    """One world pack file on its own (a source being written, a new-world skeleton)."""
    import os

    from ..jsonio import decode_bytes, loads_strict, plain

    path = payload["file"]
    if not os.path.isfile(path):
        raise AppError(CONTENT_ERROR, "文件不存在：%s" % path, [detail("$.file", "文件不存在", None, CONTENT_ERROR)])
    with open(path, "rb") as handle:
        raw = plain(loads_strict(decode_bytes(handle.read(), path), path))
    label = raw.get("id") if isinstance(raw, dict) and isinstance(raw.get("id"), str) else os.path.basename(path)
    if isinstance(raw, dict) and raw.get("extends"):
        problems.append(dict(detail("$.extends", "带 extends 的源文件要先编译（tools/compile_content.py）再校验", None, CONTENT_ERROR), world=label))
    else:
        custom = raw.get("custom") if isinstance(raw, dict) else None
        pack, errs = worldpack.validate_world(raw, custom=custom, tag_ids=tag_ids)
        problems.extend(dict(e, world=label) for e in errs)
        report = {"file": path, "world": label, "problems": 0}
        if pack is not None:
            count, failures = opening_checks.fixed_seed_openings(pack)
            report["fixed_seed_openings"] = {"count": count, "failures": failures}
            for failure in failures:
                problems.append(dict(detail("opening:%s:%d" % (failure["mode"], failure["seed"]), "；".join(failure["problems"][:3]), "修内容或开局规则", CONTENT_ERROR), world=label))
            if payload["stats"]:
                report["stats"] = worldpack.world_stats(pack)
        report["problems"] = len(problems)
        if not problems:
            report["ok"] = True
            return report
        raise AppError(CONTENT_ERROR, "世界包有 %d 处问题" % len(problems), problems, report=report)
    raise AppError(CONTENT_ERROR, "世界包有 %d 处问题" % len(problems), problems)
