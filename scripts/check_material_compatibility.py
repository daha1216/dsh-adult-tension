"""Read-only pairing audit. Missing evidence is UNMAPPED, not compatible."""
from __future__ import annotations

import argparse
from collections import Counter
import json

from material_inventory import DATA, INDEX, build_inventory, leaves, pointer, read_yaml


def audit(data_dir=DATA, index_path=INDEX):
    inventory = build_inventory(data_dir, index_path)
    data = {p.name: read_yaml(p) for p in sorted(data_dir.glob("*.yaml"))}
    pools = data["pools.yaml"]
    frames = data["world_frameworks.yaml"]["frameworks"]
    errors, warnings, edges, forbidden = list(inventory["errors"]), [], [], []
    eras = set(pools["时代与地点"]["时代"])
    places = set(pools["时代与地点"]["地点"])
    meta = pools["meta"]
    for table, allowed in (("location_eras", places), ("aesthetic_eras", set(pools["美学基调"]))):
        for name, allowed_eras in meta.get(table, {}).items():
            if name not in allowed or not set(allowed_eras) <= eras:
                errors.append(f"{table}/{name}: unknown material or era")
            forbidden.append({"source": table, "material": name, "excluded_eras": sorted(eras - set(allowed_eras))})
    for frame, row in frames.items():
        for place in row["places"]:
            allowed = meta.get("location_eras", {}).get(place)
            if allowed and not set(row["eras"]) <= set(allowed):
                warnings.append({"code": "BRIDGE", "framework": frame, "material": place,
                                 "reason": "framework bypasses a legacy location-era restriction"})
        for activity, entry in row["activities"].items():
            for place in entry["places"]:
                if place not in row["places"]:
                    errors.append(f"{frame}/{activity}: missing place {place}")
                    continue
                if activity not in row["places"][place]["profile"]["affordances"]:
                    warnings.append({"code": "WARNING", "framework": frame, "material": activity,
                                     "reason": "activity not explicitly listed in place affordances"})
                for pair in entry["pairs"]:
                    if type(pair) is not int or not 0 <= pair < len(row["pairs"]):
                        errors.append(f"{frame}/{activity}: invalid pair {pair}")
                        continue
                    edges.append({"framework": frame, "place": place, "activity": activity, "pair": pair,
                                  "daily": True, "pressure_options": [name for name, pressure in row["pressures"].items()
                                      if {"activity": activity, "place": place, "pair": pair} in pressure.get("bindings", [])],
                                  "evidence": "declared references; not semantic certification"})
        for axis, values in row.get("legacy_sources", {}).items():
            actual = row.get(axis, {})
            for value in values:
                if value not in actual:
                    errors.append(f"{frame}/legacy_sources/{axis}: {value} is not used by package")
    # Index literal field reuse, with a type-aware boundary. A matching era or
    # place name does not certify reuse of that item's profile or behavior.
    owners = {}
    axes = {"时代": "eras", "地点": "places", "美学基调": "aesthetics",
            "核心规则": "rule", "社会规则": "social_rule", "压力来源": "source",
            "张力引擎": "engines", "身份侧": "family"}
    def record(kind, value, frame):
        if isinstance(value, str):
            owners.setdefault((kind, value), set()).add(frame)
    for name, row in frames.items():
        for key in ("eras", "places", "aesthetics"):
            for value in row[key]:
                record(key, value, name)
        for key in ("rule", "social_rule"):
            record(key, row[key], name)
        for pair in row["pairs"]:
            record("family", pair["family"], name)
            record("position", pair["position"], name)
            for value in pair["appellations"]:
                record("appellation", value, name)
        for activity in row["activities"]:
            record("action", activity, name)
        for situation, entry in row["pressures"].items():
            record("situation", situation, name)
            record("source", entry["source"], name)
            for value in entry["engines"]:
                record("engines", value, name)
    materials = []
    for path, value in leaves(pools):
        kind = None
        if len(path) == 2:
            kind = axes.get(path[0])
        if path[:1] == ("时代与地点",) and len(path) == 3:
            kind = axes.get(path[1])
        if path[:1] == ("场景动作",) and len(path) == 3:
            kind = "action"
        if path[:1] == ("处境侧",):
            kind = "situation"
        if path[:1] == ("玩家化身轴",) and len(path) == 3:
            kind = {"社会位置": "position", "称谓": "appellation"}.get(path[1])
        if kind and isinstance(value, str):
            matches = sorted(owners.get((kind, value), set()))
            materials.append({"id": "pools.yaml#" + pointer(path), "type": kind,
                              "value": value, "frameworks": matches,
                              "status": "REFERENCED" if matches else "UNMAPPED",
                              "semantic_review": "NOT_REVIEWED"})
    summary = {"field_count": inventory["record_count"], "classification": inventory["status_counts"],
               "frameworks": len(frames), "declared_pairings": len(edges),
               "legacy_pool_items": len(materials), "legacy_pool_status": dict(Counter(x["status"] for x in materials)),
               "errors": len(errors), "warnings": len(warnings)}
    return {"summary": summary, "errors": errors, "warnings": warnings,
            "pairings": edges, "forbidden_by_existing_rule": forbidden,
            "legacy_pool_items": materials,
            "limitations": ["Field classification is not semantic review.",
                "REFERENCED counts names, not full profile reuse.",
                "Unrestricted or unmatched items are not automatically approved.",
                "No runtime allowlist or new bridge permission is introduced."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = audit()
    print(json.dumps(result["summary"] if args.summary else result, ensure_ascii=False, indent=2))
    return bool(result["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
