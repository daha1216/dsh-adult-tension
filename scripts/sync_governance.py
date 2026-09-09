"""Apply authored review evidence and the exact user-approved cleanup selection."""
from __future__ import annotations

import argparse
import json

from build_frameworks import ROOT, REVIEWS, aggregate, digest
from material_inventory import read_yaml
import material_registry as catalog
from data_contract import core_review_errors

ORPHANS = {"天平两端真名典当夜", "妖狐内丹子时反噬"}


def decisions(registry, current):
    dependency_errors = core_review_errors()
    if dependency_errors:
        raise ValueError("; ".join(dependency_errors))
    baseline = read_yaml(ROOT / "maintenance/baseline.yaml")
    removed = set(baseline["framework_selection"]["removed"])
    live = {row["id"] for row in current}
    result = []
    compiled = aggregate()
    for key, row in registry["entries"].items():
        source, label = row["source"], row["source"]["label"]
        is_framework = row["kind"] == "framework" and label in removed
        is_orphan = source["file"] == "templates.yaml" and source["path"] == ["situation_beats"] and label in ORPHANS
        if key not in live and (is_framework or is_orphan):
            reason = "用户按原序号37-42、47-53排除该框架；不删除跨框架共享池或旧存档快照。" if is_framework else "处境池与框架没有该模板入口；仅删除不可达模板，不回填旧池。"
            result.append({"id": key, "source_hash": row["source_hash"], "status": "DEPRECATED",
                           "cleanup": {"stage": "removed", "policy": "verified_direct", "reason": reason,
                                       "regression_evidence": ["tests/test_governance_cleanup.py", "tests/test_framework_build.py"]},
                           "review": {"scope": "explicit selection or unreachable template", "reason": reason,
                                      "release": registry["release"]}})
    for name, material_hash in compiled["reviewed_frameworks"].items():
        row = next(r for r in current if r["kind"] == "framework" and r["source"]["label"] == name)
        key = row["id"]
        review = read_yaml(REVIEWS / f"{key}.yaml")
        frame = compiled["frameworks"][name]
        result.append({"id": key, "source_hash": material_hash, "status": "KEEP_FRAMEWORK",
                       "modes": ["daily", "pressure"], "owners": [name],
                       "compatibility": {"eras": frame["eras"], "places": list(frame["places"]),
                                         "themes": frame["themes"], "technology_boundary": frame["technology_boundary"],
                                         "bridge_status": frame["bridge_status"]},
                       "restrictions": {"frozen": False, "restricted": False, "reason": "非露骨框架语义审查；不扩展冻结章节。"},
                       "review": {"scope": "framework source and explicit bindings; not model playtest",
                                  "reason": review["reason"], "release": registry["release"]},
                       "quality": review["quality"], "chemistry": review["chemistry"],
                       "activity_functions": review["activity_functions"]})
    path = ROOT / "maintenance/core_review_decisions.yaml"
    if path.exists():
        result.extend(read_yaml(path))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Atomically save compact registry after validation")
    args = parser.parse_args()
    current = catalog.units()
    registry = catalog.sync(catalog.load_registry(), current)
    registry = catalog.apply_decisions(registry, decisions(registry, current), current)
    report = catalog.audit(registry, current)
    if args.write and not report["errors"]:
        catalog.write_registry(registry)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
