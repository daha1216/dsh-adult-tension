"""Maintenance data ownership and dependency contract, not runtime state."""
from __future__ import annotations

from pathlib import Path
import hashlib

from material_inventory import read_yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "maintenance/data_manifest.yaml"


def load_manifest(path=MANIFEST):
    manifest = read_yaml(path)
    if manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Invalid data manifest")
    for name, row in manifest["files"].items():
        if Path(name).name != name or not name.endswith(".yaml"):
            raise ValueError(f"Invalid data filename: {name}")
        if row.get("layer") not in manifest["layers"]:
            raise ValueError(f"Unknown architecture layer: {name}")
        if set(row.get("depends_on", [])) - manifest["files"].keys():
            raise ValueError(f"Unknown dependency: {name}")
    return manifest


def validate_files(data_dir=ROOT / "scripts/data", manifest=None):
    manifest = manifest or load_manifest()
    actual = {p.name for p in data_dir.iterdir() if p.is_file() and p.suffix in (".yaml", ".yml")}
    expected = set(manifest["files"])
    return ([f"UNREGISTERED_DATA_FILE: {name}" for name in sorted(actual - expected)]
            + [f"MISSING_DATA_FILE: {name}" for name in sorted(expected - actual)])


def dependency_closure(names, manifest=None):
    """Include forward requirements and reverse consumers until stable."""
    manifest = manifest or load_manifest()
    result = set(names)
    unknown = result - manifest["files"].keys()
    if unknown:
        raise ValueError(f"Unknown data files: {sorted(unknown)}")
    while True:
        expanded = set(result)
        for name, row in manifest["files"].items():
            dependencies = set(row.get("depends_on", []))
            if name in result or dependencies & result:
                expanded.add(name)
                expanded.update(dependencies)
        if expanded == result:
            return sorted(result)
        result = expanded


def core_review_errors(root=ROOT):
    """Invalidate pool-label reviews when their inspected consumers change."""
    if not (root / "maintenance/core_review_decisions.yaml").exists():
        return []
    path = root / "maintenance/core_review_dependencies.yaml"
    if not path.exists():
        return ["CORE_REVIEW_DEPENDENCIES_MISSING"]
    document = read_yaml(path)
    if document.get("version") != 1 or not isinstance(document.get("files"), dict) or not document["files"]:
        return ["CORE_REVIEW_DEPENDENCIES_INVALID"]
    errors = []
    for source, expected in document["files"].items():
        target = (root / source).resolve()
        if root.resolve() not in target.parents or not target.is_file():
            errors.append(f"CORE_REVIEW_DEPENDENCY_MISSING_OR_OUTSIDE: {source}")
        elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            errors.append(f"CORE_REVIEW_DEPENDENCY_STALE: {source}")
    return errors


DATA_FILES = tuple(load_manifest()["files"])
