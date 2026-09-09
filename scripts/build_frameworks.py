"""Build the runtime aggregate from ordered, individually authored frameworks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from material_inventory import read_yaml

ROOT = Path(__file__).resolve().parents[1]
AUTHORING = ROOT / "authoring" / "frameworks"
INDEX = ROOT / "authoring" / "framework_index.yaml"
OUTPUT = ROOT / "scripts" / "data" / "world_frameworks.yaml"
REVIEWS = ROOT / "maintenance" / "framework_reviews"
REVIEW_CHECKS = {"era_and_theme", "space", "people", "daily", "pressure_bindings", "distinct_functions"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def aggregate(index_path=INDEX, authoring=AUTHORING, reviews=REVIEWS):
    index = read_yaml(index_path)
    frames, approved, seen = {}, {}, set()
    for row in index["frameworks"]:
        key = row["id"]
        if not key.startswith("mat-") or not all(c in "0123456789abcdef" for c in key[4:]) or len(key) != 36:
            raise ValueError(f"Invalid framework ID: {key}")
        source = read_yaml(authoring / f"{key}.yaml")
        if key in seen or source["id"] != key or source["name"] in frames:
            raise ValueError(f"Duplicate or inconsistent framework identity: {key}")
        if source["name"] != row["name"]:
            raise ValueError(f"Framework index/name mismatch: {key}")
        seen.add(key)
        material = source["material"]
        frames[source["name"]] = material
        path = reviews / f"{key}.yaml"
        if path.exists():
            review = read_yaml(path)
            if (review.get("id") == key and review.get("name") == source["name"]
                    and review.get("source_hash") == digest(material)
                    and review.get("semantic_status") == "REVIEWED"
                    and isinstance(review.get("quality"), dict)
                    and review["quality"].get("grade") in {"A", "B", "C"}
                    and review.get("reason") and review.get("checks")
                    and isinstance(review["checks"], dict)
                    and REVIEW_CHECKS <= review["checks"].keys()
                    and all(value is True for value in review["checks"].values())):
                approved[source["name"]] = digest(material)
    actual = {path.stem for path in authoring.glob("*.yaml")}
    if actual != seen:
        raise ValueError(f"Unindexed/missing authoring files: {actual ^ seen}")
    return {"version": 1, "legacy_weight": 0, "reviewed_frameworks": approved, "frameworks": frames}


def bootstrap():
    """One-time lossless split and user-approved framework selection."""
    import yaml

    if INDEX.exists():
        raise ValueError("Authoring index already exists; bootstrap would overwrite author work")
    original = read_yaml(OUTPUT)
    selection = read_yaml(ROOT / "maintenance" / "baseline.yaml")["framework_selection"]
    removed = set(selection["removed"])
    if len(original["frameworks"]) != selection["original_count"] or not removed <= set(original["frameworks"]):
        raise ValueError("The selection does not match the audited source")
    from material_registry import load_registry
    registry = load_registry(ROOT / "references" / "material_registry.yaml")
    ids = {row["source"]["label"]: key for key, row in registry["entries"].items() if row["kind"] == "framework"}
    AUTHORING.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, material in original["frameworks"].items():
        if name in removed:
            continue
        key = ids[name]
        source = {"id": key, "name": name, "material": material}
        (AUTHORING / f"{key}.yaml").write_text(yaml.safe_dump(source, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8", newline="\n")
        rows.append({"id": key, "name": name})
    if len(rows) != selection["retained_count"]:
        raise ValueError("Retained count does not match user selection")
    INDEX.write_text(yaml.safe_dump({"version": 1, "frameworks": rows}, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")


def main():
    import yaml

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true", help="One-time lossless authoring split from the audited baseline")
    parser.add_argument("--write", action="store_true", help="Rebuild the generated runtime aggregate")
    args = parser.parse_args()
    if args.bootstrap:
        bootstrap()
    expected = aggregate()
    if args.write:
        fd, temporary = tempfile.mkstemp(dir=OUTPUT.parent, prefix="frameworks-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                yaml.safe_dump(expected, stream, allow_unicode=True, sort_keys=False, width=100)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, OUTPUT)
        finally:
            Path(temporary).unlink(missing_ok=True)
    elif read_yaml(OUTPUT) != expected:
        print("ERROR: runtime framework aggregate is stale; run build_frameworks.py --write")
        return 1
    print(f"OK: {len(expected['frameworks'])} frameworks, {len(expected['reviewed_frameworks'])} reviewed for default selection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
