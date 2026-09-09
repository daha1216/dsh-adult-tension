"""Maintain a conservative, non-runtime material catalog."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("material_inventory", ROOT / "scripts/material_inventory.py")
INVENTORY = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(INVENTORY)
DATA = INVENTORY.DATA
REGISTRY = ROOT / "references/material_registry.yaml"
STATUSES = {"KEEP_FRAMEWORK", "KEEP_SHARED", "KEEP_LEGACY", "BRIDGE_REQUIRED",
            "DUPLICATE", "DEPRECATED", "FROZEN_RESTRICTED", "NOT_REVIEWED"}
LAYERS = {"world", "space", "character", "relationship", "activity", "opening",
          "development", "expression", "maintenance"}
REVIEW_FIELDS = ("status", "modes", "compatibility", "owners", "canonical_id", "cleanup",
                 "review", "quality", "chemistry", "activity_functions", "restrictions")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _add(result, file, path, label, value, layer, kind, occurrence=0):
    address = f"{file}#{INVENTORY.pointer(path)}:{kind}:{label}"
    if occurrence:
        address += f":occurrence={occurrence}"
    result.append({"id": "mat-" + uuid.uuid5(uuid.NAMESPACE_URL, address).hex,
                   "source": {"file": file, "path": list(path), "label": str(label), "kind": kind},
                   "source_hash": digest(value), "layer": layer, "kind": kind})


def units(data_dir=DATA):
    docs = {p.name: INVENTORY.read_yaml(p) for p in sorted(data_dir.glob("*.yaml"))}
    result = []
    pool_layers = {"时代与地点": "world", "美学基调": "world", "核心规则": "world", "社会规则": "world",
                   "权力结构": "world", "张力引擎": "opening", "压力来源": "opening", "处境侧": "opening",
                   "场景动作": "activity", "身份侧": "character", "玩家化身轴": "character", "反差轴": "character"}
    pools = docs["pools.yaml"]
    for key, value in pools.items():
        if key == "meta":
            for name, child in value.items():
                _add(result, "pools.yaml", [key], name, child, "maintenance", "contract")
        elif isinstance(value, list):
            occurrences = Counter()
            for item in value:
                _add(result, "pools.yaml", [key], item, item, pool_layers.get(key, "maintenance"), "pool", occurrences[str(item)])
                occurrences[str(item)] += 1
        elif isinstance(value, dict):
            for group, items in value.items():
                if isinstance(items, list):
                    occurrences = Counter()
                    for item in items:
                        _add(result, "pools.yaml", [key, group], item, item,
                             "space" if group == "地点" else pool_layers.get(key, "maintenance"), "pool", occurrences[str(item)])
                        occurrences[str(item)] += 1
    layers = {"templates.yaml": "expression", "locations.yaml": "space", "location_profiles.yaml": "space",
              "twists.yaml": "development", "twist_profiles.yaml": "development",
              "action_categories.yaml": "activity", "action_metadata.yaml": "activity",
              "identity_profiles.yaml": "character", "names.yaml": "character"}
    for file, doc in docs.items():
        if file == "pools.yaml":
            continue
        if file == "world_frameworks.yaml":
            for name, frame in doc.get("frameworks", {}).items():
                _add(result, file, ["frameworks"], name, frame, "world", "framework")
            for name, value in doc.items():
                if name != "frameworks":
                    _add(result, file, [], name, value, "maintenance", "contract")
            continue
        layer = layers.get(file, "character")
        for key, value in doc.items():
            if isinstance(value, dict):
                for label, child in value.items():
                    _add(result, file, [key], label, child, layer, "entry")
            else:
                _add(result, file, [], key, value, layer, "group")
    if len({row["id"] for row in result}) != len(result):
        raise ValueError("Duplicate semantic source address")
    return result


def sync(existing, current):
    old = existing.get("entries", {})
    entries = {}
    for unit in current:
        key = unit["id"]
        prior = copy.deepcopy(old.get(key, {}))
        row = {**unit, "status": "NOT_REVIEWED", "modes": [],
               "compatibility": {"eras": [], "places": [], "themes": [], "technology_boundary": "未审查"},
               "owners": [], "canonical_id": None, "cleanup": {"stage": "keep"}, "review": None,
               "restrictions": {"frozen": False, "restricted": None, "reason": "未审查"}, **prior}
        row.update(unit)
        if prior and prior.get("source_hash") != unit["source_hash"]:
            if prior.get("restrictions", {}).get("frozen"):
                raise ValueError(f"FROZEN_CONTENT_CHANGED: {key}")
            row["history"] = prior.get("history", []) + [{
                "event": "source_changed", "source_hash": prior.get("source_hash"),
                **{field: prior.get(field) for field in REVIEW_FIELDS}}]
            row.update(status="NOT_REVIEWED", review=None, modes=[], owners=[], canonical_id=None,
                       cleanup={"stage": "keep"},
                       compatibility={"eras": [], "places": [], "themes": [], "technology_boundary": "未审查"})
            for field in ("quality", "chemistry", "activity_functions"):
                row.pop(field, None)
        entries[key] = row
    for key, prior in old.items():
        if key not in entries:
            entries[key] = copy.deepcopy(prior)
    return {**existing, "version": 1, "release": existing.get("release", "governance-1"),
            "release_history": existing.get("release_history", [existing.get("release", "governance-1")]),
            "purpose": "maintenance-only; never loaded by runtime", "entries": entries}


def audit(registry, current, require_reviewed=False):
    errors, warnings = [], []
    entries = registry.get("entries", {})
    if registry.get("version") != 1:
        errors.append("INVALID_VERSION")
    releases = registry.get("release_history", [registry.get("release")])
    if (not isinstance(releases, list) or not releases or
            any(not isinstance(r, str) or not r for r in releases) or
            len(set(releases)) != len(releases) or releases[-1] != registry.get("release")):
        errors.append("INVALID_RELEASE_HISTORY")
        releases = []
    live = {row["id"]: row for row in current}
    for key, unit in live.items():
        row = entries.get(key)
        if not row:
            errors.append(f"UNREGISTERED: {key}")
            continue
        if row.get("id") != key or row.get("source_hash") != unit["source_hash"] or row.get("source") != unit["source"]:
            errors.append(f"STALE_SOURCE: {key}")
        if row.get("status") not in STATUSES or row.get("layer") not in LAYERS:
            errors.append(f"INVALID_CLASSIFICATION: {key}")
        reviewed = row.get("status") != "NOT_REVIEWED"
        review = row.get("review") or {}
        if reviewed and (not isinstance(review, dict) or not all(review.get(k) for k in ("scope", "reason", "release"))):
            errors.append(f"MISSING_REVIEW_EVIDENCE: {key}")
        modes = row.get("modes")
        if not isinstance(modes, list) or any(mode not in ("daily", "pressure") for mode in modes):
            errors.append(f"INVALID_MODES: {key}")
        restrictions = row.get("restrictions", {})
        if (not isinstance(restrictions, dict) or type(restrictions.get("frozen")) is not bool or
                restrictions.get("restricted") not in (True, False, None)):
            errors.append(f"INVALID_RESTRICTIONS: {key}")
        if row.get("status") == "FROZEN_RESTRICTED" and not (restrictions.get("frozen") or restrictions.get("restricted")):
            errors.append(f"MISSING_RESTRICTION: {key}")
        if row.get("status") in ("KEEP_FRAMEWORK", "KEEP_SHARED", "KEEP_LEGACY"):
            compatibility = row.get("compatibility") or {}
            if (not row.get("owners") or not modes or not isinstance(compatibility, dict) or
                    not compatibility.get("themes") or compatibility.get("technology_boundary") in (None, "", "未审查")):
                errors.append(f"MISSING_OWNERSHIP_EVIDENCE: {key}")
        canonical = row.get("canonical_id")
        if canonical and (canonical == key or canonical not in live):
            errors.append(f"INVALID_CANONICAL: {key}")
        if row.get("status") == "DUPLICATE" and not canonical:
            errors.append(f"INVALID_CANONICAL: {key}")
        seen, cursor = {key}, canonical
        while cursor in entries:
            if cursor in seen:
                errors.append(f"CANONICAL_CYCLE: {key}")
                break
            seen.add(cursor)
            cursor = entries[cursor].get("canonical_id")
        cleanup = row.get("cleanup") or {}
        if cleanup.get("stage") not in ("keep", "candidate"):
            errors.append(f"INVALID_LIVE_CLEANUP: {key}")
        if row.get("status") == "DEPRECATED" and not all(cleanup.get(k) for k in ("marked_release", "reason")):
            errors.append(f"MISSING_DEPRECATION: {key}")
    for key, row in entries.items():
        if key in live:
            continue
        cleanup = row.get("cleanup") or {}
        if cleanup.get("stage") != "removed":
            errors.append(f"UNEXPLAINED_REMOVAL: {key}")
            continue
        marked = cleanup.get("marked_release")
        if not releases or marked not in releases[:-1]:
            errors.append(f"PREMATURE_REMOVAL: {key}")
        if row.get("status") not in ("DEPRECATED", "DUPLICATE") or not cleanup.get("regression_evidence"):
            errors.append(f"UNVERIFIED_REMOVAL: {key}")
        if (row.get("restrictions") or {}).get("frozen"):
            errors.append(f"FROZEN_REMOVAL: {key}")
    pending = sum(entries.get(key, {}).get("status") == "NOT_REVIEWED" for key in live)
    if pending:
        warnings.append(f"{pending} units remain NOT_REVIEWED")
    if require_reviewed and pending:
        errors.append("REVIEW_GATE: pending semantic reviews")
    core_paths = {(name,) for name in ("美学基调", "核心规则", "社会规则", "张力引擎", "压力来源", "处境侧", "身份侧")}
    core_paths.update(("时代与地点", name) for name in ("时代", "地点"))
    core_paths.update(("场景动作", name) for name in ("非交易靠近", "交易摊牌"))
    core_paths.update(("玩家化身轴", name) for name in ("社会位置", "称谓"))
    core_rows = [entries[key] for key, unit in live.items() if key in entries and
                 unit["source"]["file"] == "pools.yaml" and tuple(unit["source"]["path"]) in core_paths]
    return {"summary": {"units": len(live), "entries": len(entries), "errors": len(errors), "warnings": len(warnings),
                         "status_counts": dict(Counter(row.get("status") for row in entries.values())),
                         "core_pool_units": len(core_rows),
                         "core_pool_dispositions": dict(Counter(row.get("status") for row in core_rows)),
                         "framework_quality": dict(Counter((row.get("quality") or {}).get("grade", "NOT_REVIEWED")
                                                           for row in entries.values() if row.get("kind") == "framework"))},
            "errors": errors, "warnings": warnings}


def write_registry(registry, path=REGISTRY):
    """Replace a validated catalog atomically; never truncate the last good copy."""
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            yaml.safe_dump(registry, stream, allow_unicode=True, sort_keys=False, width=110)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--require-reviewed", action="store_true")
    parser.add_argument("--release", help="Record a new actual release in the ordered maintenance history")
    parser.add_argument("--decisions", type=Path, help="Apply explicit reviewed decisions with matching source hashes")
    args = parser.parse_args()
    current = units()
    registry = INVENTORY.read_yaml(REGISTRY) if REGISTRY.exists() else {}
    if args.sync:
        registry = sync(registry, current)
    if args.release and args.release != registry.get("release"):
        history = registry.get("release_history", [registry.get("release")])
        if not registry or args.release in history:
            raise ValueError("Initialize the catalog first; release history cannot move backwards")
        registry = {**registry, "release": args.release, "release_history": [*history, args.release]}
    if args.decisions:
        registry = apply_decisions(registry, INVENTORY.read_yaml(args.decisions), current)
    result = audit(registry, current, args.require_reviewed)
    if (args.sync or args.decisions or args.release) and not result["errors"]:
        write_registry(registry)
    print(json.dumps(result["summary"] if args.summary else result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


def apply_decisions(registry, decisions, current):
    """Reject stale reviews before mutating the registry on disk."""
    result = copy.deepcopy(registry)
    if not isinstance(decisions, list):
        raise ValueError("Decisions must be a list")
    live = {unit["id"]: unit for unit in current}
    seen = set()
    for decision in decisions:
        if not isinstance(decision, dict) or not all(k in decision for k in ("id", "source_hash", "status")):
            raise ValueError("A decision requires id, source_hash and status")
        key = decision["id"]
        if key in seen:
            raise ValueError(f"Duplicate decision: {key}")
        seen.add(key)
        row = result["entries"].get(key)
        if (not row or row["source_hash"] != decision["source_hash"] or
                (key in live and live[key]["source_hash"] != decision["source_hash"])):
            raise ValueError(f"Stale or unknown decision: {key}")
        allowed = {"id", "source_hash", *REVIEW_FIELDS}
        if set(decision) - allowed:
            raise ValueError(f"Unknown decision fields: {set(decision)-allowed}")
        if all(row.get(field) == value for field, value in decision.items()):
            continue
        row.setdefault("history", []).append({"event": "review_decision", "source_hash": row["source_hash"],
                                             **{field: copy.deepcopy(row.get(field)) for field in REVIEW_FIELDS}})
        row.update(copy.deepcopy(decision))
    report = audit(result, current)
    if report["errors"]:
        raise ValueError("; ".join(report["errors"]))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
