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
CONTRACT = INVENTORY.read_yaml(ROOT / "maintenance/data_manifest.yaml")
STATUSES = set(CONTRACT["review_statuses"])
LAYERS = set(CONTRACT["layers"]) | {"maintenance"}
REVIEW_FIELDS = ("status", "modes", "compatibility", "owners", "canonical_id", "cleanup",
                 "review", "quality", "chemistry", "activity_functions", "restrictions")
ROW_DEFAULTS = {
    "status": "NOT_REVIEWED", "modes": [], "owners": [], "canonical_id": None,
    "compatibility": {"eras": [], "places": [], "themes": [], "technology_boundary": "未审查"},
    "cleanup": {"stage": "keep"}, "review": None,
    "restrictions": {"frozen": False, "restricted": None, "reason": "未审查"},
}
HISTORY_DEFAULTS = {**ROW_DEFAULTS, "quality": None, "chemistry": None, "activity_functions": None}


def _expand_defaults(value, defaults):
    result = copy.deepcopy(value)
    for key, default in defaults.items():
        if key not in result:
            result[key] = copy.deepcopy(default)
        elif isinstance(default, dict) and isinstance(result[key], dict):
            result[key] = _expand_defaults(result[key], default)
    return result


def _compact_defaults(value, defaults):
    result = copy.deepcopy(value)
    for key, default in defaults.items():
        if key not in result:
            continue
        if _same_value(result[key], default):
            del result[key]
        elif isinstance(default, dict) and isinstance(result[key], dict):
            result[key] = _compact_defaults(result[key], default)
    return result


def _same_value(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_value(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_value(a, b) for a, b in zip(left, right))
    return left == right


def _expand_registry(registry):
    if not isinstance(registry, dict) or not isinstance(registry.get("entries", {}), dict):
        raise ValueError("Registry and entries must be mappings")
    result = copy.deepcopy(registry)
    for key, row in result.get("entries", {}).items():
        if not isinstance(row, dict):
            raise ValueError(f"Invalid registry row: {key}")
        row = _expand_defaults(row, ROW_DEFAULTS)
        row.setdefault("id", key)
        if isinstance(row.get("source"), dict) and "kind" in row["source"]:
            row.setdefault("kind", row["source"]["kind"])
        if "history" in row:
            if not isinstance(row["history"], list) or any(not isinstance(h, dict) for h in row["history"]):
                raise ValueError(f"Invalid history: {key}")
            row["history"] = [_expand_defaults(h, HISTORY_DEFAULTS)
                              if h.get("event") in ("source_changed", "review_decision") else h
                              for h in row["history"]]
        result["entries"][key] = row
    return result


def load_registry(path=REGISTRY):
    """Read v1 or compact v2 with conservative row/history defaults expanded."""
    registry = INVENTORY.read_yaml(Path(path))
    if not isinstance(registry, dict) or registry.get("version") not in (1, 2):
        raise ValueError("INVALID_VERSION")
    return _expand_registry(registry)


def _bound_units(registry, current):
    # Aliases are explicit generated-source-ID -> existing stable-ID bindings.
    aliases = registry.get("source_aliases", {})
    entries = registry.get("entries", {})
    if not isinstance(aliases, dict):
        raise ValueError("INVALID_SOURCE_ALIASES: expected a mapping")
    for source_id, stable_id in aliases.items():
        if (not isinstance(source_id, str) or not isinstance(stable_id, str) or
                stable_id not in entries or source_id == stable_id or
                source_id in entries or stable_id in aliases):
            raise ValueError(f"INVALID_SOURCE_ALIAS: {source_id}")
    live = {}
    for unit in current:
        key = aliases.get(unit["id"], unit["id"])
        if key in live:
            raise ValueError(f"AMBIGUOUS_SOURCE_BINDING: {key}")
        live[key] = {**copy.deepcopy(unit), "id": key}
    return live


def _snapshot(row, event):
    return {"event": event, "source_hash": row.get("source_hash"),
            **{field: copy.deepcopy(row.get(field)) for field in REVIEW_FIELDS}}


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
    """Expand defaults and refresh sources, preserving IDs through explicit aliases."""
    existing = _expand_registry(existing)
    if existing.get("version", 2) not in (1, 2):
        raise ValueError("INVALID_VERSION")
    old = existing.get("entries", {})
    entries = {}
    for key, unit in _bound_units(existing, current).items():
        prior = copy.deepcopy(old.get(key, {}))
        row = {**copy.deepcopy(ROW_DEFAULTS), **prior}
        row.update(unit)
        if prior and (prior.get("source_hash") != unit["source_hash"] or prior.get("source") != unit["source"]):
            if (prior.get("restrictions") or {}).get("frozen"):
                raise ValueError(f"FROZEN_CONTENT_CHANGED: {key}")
            snapshot = _snapshot(prior, "source_changed")
            snapshot["source"] = copy.deepcopy(prior.get("source"))
            row["history"] = prior.get("history", []) + [snapshot]
            row.update(copy.deepcopy(ROW_DEFAULTS))
            # Content edits cannot silently lift an existing restriction.
            if (prior.get("restrictions") or {}).get("restricted"):
                row["restrictions"] = copy.deepcopy(prior["restrictions"])
            for field in ("quality", "chemistry", "activity_functions"):
                row.pop(field, None)
        entries[key] = row
    for key, prior in old.items():
        if key not in entries:
            entries[key] = copy.deepcopy(prior)
    return {**existing, "version": 2, "release": existing.get("release", "governance-1"),
            "release_history": existing.get("release_history", [existing.get("release", "governance-1")]),
            "purpose": "maintenance-only; never loaded by runtime", "entries": entries}


def audit(registry, current, require_reviewed=False):
    errors, warnings = [], []
    try:
        registry = _expand_registry(registry)
        live = _bound_units(registry, current)
    except ValueError as exc:
        return {"summary": {"errors": 1, "warnings": 0}, "errors": [str(exc)], "warnings": []}
    entries = registry.get("entries", {})
    if registry.get("version") not in (1, 2):
        errors.append("INVALID_VERSION")
    releases = registry.get("release_history", [registry.get("release")])
    if (not isinstance(releases, list) or not releases or
            any(not isinstance(r, str) or not r for r in releases) or
            len(set(releases)) != len(releases) or releases[-1] != registry.get("release")):
        errors.append("INVALID_RELEASE_HISTORY")
        releases = []
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
        if not isinstance(modes, list) or any(mode not in CONTRACT["modes"] for mode in modes):
            errors.append(f"INVALID_MODES: {key}")
        restrictions = row.get("restrictions", {})
        if (not isinstance(restrictions, dict) or type(restrictions.get("frozen")) is not bool or
                (restrictions.get("restricted") is not None and type(restrictions.get("restricted")) is not bool)):
            errors.append(f"INVALID_RESTRICTIONS: {key}")
            restrictions = {}
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
        cleanup = row.get("cleanup") or {}
        if not isinstance(cleanup, dict):
            errors.append(f"INVALID_LIVE_CLEANUP: {key}")
            cleanup = {}
        if cleanup.get("stage") not in ("keep", "candidate"):
            errors.append(f"INVALID_LIVE_CLEANUP: {key}")
        required = ("reason",) if cleanup.get("policy") == "verified_direct" else ("marked_release", "reason")
        if row.get("status") == "DEPRECATED" and not all(cleanup.get(k) for k in required):
            errors.append(f"MISSING_DEPRECATION: {key}")
    for key, row in entries.items():
        seen, cursor = {key}, row.get("canonical_id")
        while isinstance(cursor, str) and cursor in entries:
            if cursor in seen:
                errors.append(f"CANONICAL_CYCLE: {key}")
                break
            seen.add(cursor)
            cursor = entries[cursor].get("canonical_id")
        if key in live:
            continue
        restrictions = row.get("restrictions")
        if not isinstance(restrictions, dict):
            errors.append(f"INVALID_RESTRICTIONS: {key}")
        elif restrictions.get("frozen"):
            errors.append(f"FROZEN_REMOVAL: {key}")
        cleanup = row.get("cleanup") or {}
        if not isinstance(cleanup, dict) or cleanup.get("stage") != "removed":
            errors.append(f"UNEXPLAINED_REMOVAL: {key}")
            continue
        marked = cleanup.get("marked_release")
        if cleanup.get("policy") != "verified_direct" and (not releases or marked not in releases[:-1]):
            errors.append(f"PREMATURE_REMOVAL: {key}")
        if row.get("status") not in ("DEPRECATED", "DUPLICATE") or not cleanup.get("regression_evidence"):
            errors.append(f"UNVERIFIED_REMOVAL: {key}")
    pending = sum(entries.get(key, {}).get("status") not in STATUSES - {"NOT_REVIEWED"} for key in live)
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
                                                           for key, row in entries.items() if key in live and row.get("kind") == "framework"))},
            "errors": errors, "warnings": warnings}


def write_registry(registry, path=REGISTRY):
    """Atomically write compact v2 without changing IDs, evidence or the input.

    Defaults are fixed by this module, never inferred semantic approvals. Call
    audit first when writing externally supplied decisions or changed sources.
    """
    registry = _expand_registry(registry)
    if registry.get("version") not in (1, 2):
        raise ValueError("INVALID_VERSION")
    registry["version"] = 2
    for key, row in registry.get("entries", {}).items():
        compact = _compact_defaults(row, ROW_DEFAULTS)
        if compact.get("id") == key:
            compact.pop("id")
        if isinstance(compact.get("source"), dict) and compact.get("kind") == compact["source"].get("kind"):
            compact.pop("kind", None)
        if "history" in compact:
            compact["history"] = [_compact_defaults(h, HISTORY_DEFAULTS)
                                  if h.get("event") in ("source_changed", "review_decision") else h
                                  for h in compact["history"]]
        registry["entries"][key] = compact
    path = Path(path)
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
    registry = load_registry() if REGISTRY.exists() else {}
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
    """Apply explicit reviews in memory; reject stale sources and frozen edits.

    After a source rename/move, decisions must also supply the exact current
    source mapping, so an old decision cannot be replayed against equal content.
    """
    result = _expand_registry(registry)
    if not isinstance(decisions, list):
        raise ValueError("Decisions must be a list")
    live = _bound_units(result, current)
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
                (key in live and (live[key]["source_hash"] != decision["source_hash"] or
                                 live[key]["source"] != row.get("source")))):
            raise ValueError(f"Stale or unknown decision: {key}")
        moved = any(h.get("event") == "source_changed" and "source" in h and
                    h["source"] != row.get("source") for h in row.get("history", []))
        if (moved or "source" in decision) and decision.get("source") != row.get("source"):
            raise ValueError(f"Stale or missing decision source binding: {key}")
        allowed = {"id", "source_hash", "source", *REVIEW_FIELDS}
        if set(decision) - allowed:
            raise ValueError(f"Unknown decision fields: {set(decision)-allowed}")
        decision = copy.deepcopy(decision)
        for field, value in decision.items():
            if isinstance(value, dict) and isinstance(ROW_DEFAULTS.get(field), dict):
                decision[field] = _expand_defaults(value, ROW_DEFAULTS[field])
        if all(_same_value(row.get(field), value) for field, value in decision.items()):
            continue
        if (row.get("restrictions") or {}).get("frozen"):
            raise ValueError(f"FROZEN_DECISION: {key}")
        row.setdefault("history", []).append(_snapshot(row, "review_decision"))
        row.update(copy.deepcopy(decision))
    report = audit(result, current)
    if report["errors"]:
        raise ValueError("; ".join(report["errors"]))
    return _expand_registry(result)


if __name__ == "__main__":
    raise SystemExit(main())
