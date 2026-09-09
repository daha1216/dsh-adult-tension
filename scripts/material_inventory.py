"""Inventory every YAML field; classification is not semantic approval.

Read-only maintenance tool, never imported by the opening/turn pipeline.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scripts/data"
INDEX = ROOT / "references/material_architecture.yaml"


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_yaml(path):
    return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)


def leaves(value, prefix=()):
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from leaves(child, prefix + (str(key),))
    elif isinstance(value, list) and value:
        for i, child in enumerate(value):
            yield from leaves(child, prefix + (str(i),))
    else:
        yield prefix, value


def resolve(value, path, prefix=()):
    if not path:
        return [(prefix, value)]
    key, *tail = path
    if key == "*":
        if not isinstance(value, (dict, list)) or not value:
            raise ValueError(f"Empty/invalid wildcard at {prefix}")
        items = value.items() if isinstance(value, dict) else enumerate(value)
        return [row for k, child in items for row in resolve(child, tail, prefix + (str(k),))]
    if not isinstance(value, dict) or key not in value:
        raise ValueError(f"Missing indexed key: {prefix + (key,)}")
    return resolve(value[key], tail, prefix + (key,))


def pointer(path):
    return "/" + "/".join(str(k).replace("~", "~0").replace("/", "~1") for k in path)


def build_inventory(data_dir=DATA, index_path=INDEX):
    documents = {p.name: read_yaml(p) for p in sorted(data_dir.glob("*.yaml"))}
    index = read_yaml(index_path)
    records = {}
    for name, value in documents.items():
        for path, leaf in leaves(value):
            raw = json.dumps(leaf, ensure_ascii=False, sort_keys=True).encode("utf-8")
            records[(name, path)] = {
                "id": name + "#" + pointer(path), "file": name, "path": list(path),
                "value": leaf, "content_hash": hashlib.sha256(raw).hexdigest(),
                "layers": [], "declared_modes": [], "compatibility_metadata": False,
            }
    errors = []
    if Path(data_dir).resolve() == DATA.resolve():
        import sys
        if str(ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(ROOT / "scripts"))
        from data_contract import validate_files
        errors.extend(validate_files(data_dir))
    groups = list(index["layers"].items()) + [("compatibility", {"sources": index.get("compatibility", [])})]
    for layer, group in groups:
        for source in group["sources"]:
            name = source["file"]
            try:
                if name not in documents:
                    raise ValueError(f"Missing data file: {name}")
                for path, value in resolve(documents[name], source["path"]):
                    for leaf_path, _ in leaves(value, path):
                        row = records[(name, leaf_path)]
                        if layer == "compatibility":
                            row["compatibility_metadata"] = True
                            continue
                        if layer not in row["layers"]:
                            row["layers"].append(layer)
                        for mode in source.get("modes", group.get("modes", [])):
                            if mode not in row["declared_modes"]:
                                row["declared_modes"].append(mode)
            except ValueError as exc:
                errors.append(f"{layer}/{name}: {exc}")
    # Fallback is classification only; never add mode permissions here.
    for row in records.values():
        row["classification_evidence"] = "selector" if row["layers"] else "none"
        if not row["layers"]:
            layer = index.get("classification_defaults", {}).get(row["file"])
            for rule in index.get("classification_overrides", []):
                if rule["file"] == row["file"] and row["path"][:len(rule["path"])] == rule["path"]:
                    layer = rule["layer"]
            if layer:
                row["layers"] = [layer]
                row["classification_evidence"] = "file_or_path_contract"
        row["classification"] = "CLASSIFIED" if row["layers"] or row["compatibility_metadata"] else "UNMAPPED"
        row["semantic_review"] = "NOT_REVIEWED"
    counts = Counter(row["classification"] for row in records.values())
    indexed_files = sorted({r["file"] for r in records.values() if r["classification"] == "CLASSIFIED"})
    return {
        "version": 2, "count_unit": "scalar_or_empty_container_at_source_path",
        "id_contract": "source address; list insertion changes subsequent IDs; content_hash detects value changes",
        "mode_contract": "architecture declarations only; not a runtime eligibility guarantee",
        "files": sorted(documents), "indexed_files": indexed_files,
        "unindexed_files": sorted(set(documents) - set(indexed_files)),
        "record_count": len(records), "status_counts": dict(counts),
        "layer_counts": dict(Counter(layer for row in records.values() for layer in row["layers"])),
        "errors": errors, "records": list(records.values()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    report = build_inventory()
    if args.summary:
        report.pop("records")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
