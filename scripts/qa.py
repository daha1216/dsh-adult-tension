"""One maintenance entry point; structural QA never substitutes for playtests."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from data_contract import core_review_errors, dependency_closure, load_manifest, validate_files
from material_inventory import read_yaml

ROOT = Path(__file__).resolve().parents[1]
FINGERPRINT = ROOT / "maintenance/content_fingerprint.txt"


def git(*args):
    process = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if process.returncode:
        raise ValueError(process.stderr.decode("utf-8", errors="replace").strip())
    return process.stdout


def changed_paths(base="origin/main"):
    merge_base = git("merge-base", "HEAD", base).decode().strip()
    # diff against the merge base includes committed, staged and worktree edits.
    tracked = git("diff", "--name-only", "-z", merge_base)
    untracked = git("ls-files", "--others", "--exclude-standard", "-z")
    return sorted({p.decode("utf-8") for p in (tracked + untracked).split(b"\0") if p})


def scope(paths, manifest=None, index=None):
    manifest = manifest or load_manifest()
    index = index or read_yaml(ROOT / "authoring/framework_index.yaml")
    names = {row["id"]: row["name"] for row in index["frameworks"]}
    authored = any(p.startswith(("authoring/frameworks/", "maintenance/framework_reviews/"))
                   and Path(p).stem in names for p in paths)
    frameworks, files, tests = set(), set(), set()
    full = False
    for path in paths:
        p = Path(path)
        if path.startswith(("authoring/frameworks/", "maintenance/framework_reviews/")) and p.stem in names:
            frameworks.add(names[p.stem])
        elif authored and path in {"scripts/data/world_frameworks.yaml", "references/material_registry.yaml", "maintenance/content_fingerprint.txt"}:
            # Aggregate equality is checked before scoped samples run.
            continue
        elif path.startswith("scripts/data/"):
            files.add(p.name)
        elif path.startswith("tests/test_") and p.suffix == ".py" and (ROOT / path).exists():
            tests.add(path)
        elif p.suffix == ".md" and p.name not in {"SKILL.md", "AGENTS.md"}:
            tests.add("tests/test_doc_consistency.py")
        elif path.startswith(("scripts/", "authoring/", "maintenance/", "references/", ".github/", "tests/")) or p.name in {"SKILL.md", "commands.yaml", "requirements-dev.txt"}:
            full = True
    dependencies = dependency_closure(files, manifest) if files else []
    if dependencies:
        full = True
    return {"paths": sorted(paths), "data_dependencies": dependencies,
            "frameworks": [] if full else sorted(frameworks),
            "tests": [] if full or frameworks else sorted(tests), "full": full}


def frozen_errors(root=ROOT):
    baseline = read_yaml(root / "maintenance/baseline.yaml")["frozen_section"]
    raw = (root / baseline["file"]).read_bytes()
    start = raw.find(baseline["heading"].encode("utf-8"))
    if start < 0:
        return ["FROZEN_SECTION_MISSING"]
    end = raw.find(b"\n## ", start)
    value = raw[start:end if end >= 0 else len(raw)]
    return [] if hashlib.sha256(value).hexdigest() == baseline["sha256"] else ["FROZEN_SECTION_CHANGED"]


def release_errors():
    from material_registry import audit, load_registry, units
    report = audit(load_registry(), units())
    errors = list(report["errors"]) + core_review_errors()
    if report["summary"]["core_pool_dispositions"].get("NOT_REVIEWED", 0):
        errors.append("CORE_REVIEW_GATE: pending core dispositions")
    bridges = report["summary"]["core_pool_dispositions"].get("BRIDGE_REQUIRED", 0)
    if bridges:
        errors.append(f"CORE_BRIDGE_GATE: {bridges} core materials still require semantic closure")
    from build_frameworks import aggregate
    compiled = aggregate()
    if set(compiled["frameworks"]) != set(compiled["reviewed_frameworks"]):
        errors.append("FRAMEWORK_REVIEW_GATE: missing or stale reviews")
    from check_duplicates import audit as duplicate_audit
    if duplicate_audit()["unresolved_candidates"]:
        errors.append("DUPLICATE_REVIEW_GATE: unresolved candidates")
    from playtest_report import audit as audit_playtests
    errors.extend(audit_playtests()["errors"])
    return errors


def run(command):
    print("+ " + subprocess.list2cmdline(command), flush=True)
    return subprocess.run(command, cwd=ROOT).returncode


def write_fingerprint(value):
    fd, temporary = tempfile.mkstemp(dir=FINGERPRINT.parent, prefix="fingerprint-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as stream:
            stream.write(value + "\n")
        os.replace(temporary, FINGERPRINT)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selectors = parser.add_mutually_exclusive_group(required=True)
    selectors.add_argument("--changed", action="store_true")
    selectors.add_argument("--full", action="store_true")
    selectors.add_argument("--framework")
    selectors.add_argument("--material")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--release", action="store_true", help="Also require current semantic and real-model evidence")
    parser.add_argument("--update-fingerprint", action="store_true", help="After full checks succeed, update the data digest")
    parser.add_argument("--plan", action="store_true", help="Print scope and commands without running checks or writes")
    args = parser.parse_args(argv)
    if (args.release or args.update_fingerprint) and not args.full:
        parser.error("--release and --update-fingerprint require --full")
    index = read_yaml(ROOT / "authoring/framework_index.yaml")
    names = {r["name"] for r in index["frameworks"]}
    selected = {"full": True, "frameworks": [], "tests": [], "paths": [], "data_dependencies": []}
    if args.changed:
        selected = scope(changed_paths(args.base))
    elif args.framework:
        if args.framework not in names:
            parser.error(f"Unknown framework: {args.framework}")
        selected.update(full=False, frameworks=[args.framework])
    elif args.material:
        from material_registry import load_registry
        row = load_registry()["entries"].get(args.material)
        if not row:
            parser.error(f"Unknown material ID: {args.material}")
        if row["kind"] == "framework" and row["source"]["label"] in names:
            selected.update(full=False, frameworks=[row["source"]["label"]])
        else:
            selected = scope(["scripts/data/" + row["source"]["file"]])
    python = [sys.executable, "-X", "utf8"]
    commands = [python + ["scripts/build_frameworks.py"], python + ["scripts/check_content.py"],
                python + ["scripts/material_registry.py", "--summary"]]
    if selected["full"]:
        commands.extend(python + ["scripts/" + script, *flags] for script, flags in (
            ("material_inventory.py", ["--summary"]), ("check_material_compatibility.py", ["--summary"]),
            ("material_quality.py", ["--summary"]), ("check_duplicates.py", []), ("analyze_content.py", ["--samples", "1000"]),
            ("framework_coverage.py", ["--summary"])))
    sample = python + ["scripts/sample_materials.py", "--summary"]
    for name in selected["frameworks"]:
        sample.extend(["--framework", name])
    if selected["full"] or selected["frameworks"]:
        commands.append(sample)
    tests = selected["tests"] or (["tests/test_framework_build.py"]
                                 if selected["frameworks"] else [])
    test_command = python + ["-m", "pytest", "-q", *tests]
    if args.update_fingerprint:
        test_command.extend(["-k", "not test_content_fingerprint"])
    commands.extend([test_command, python + ["-m", "compileall", "-q", "scripts", "tests"],
                     ["git", "diff", "--check"]])
    print(json.dumps({"scope": selected, "commands": commands, "release": args.release}, ensure_ascii=False, indent=2))
    if args.plan:
        return 0
    errors = validate_files() + frozen_errors() + core_review_errors()
    if errors:
        print("\n".join(errors))
        return 1
    if args.changed and not selected["paths"]:
        print("No changed paths since merge base")
        return 0
    from check_content import content_fingerprint as fingerprint
    before = fingerprint()
    for command in commands:
        if run(command):
            return 1
    if args.release:
        errors = release_errors()
        if errors:
            print("\n".join(errors))
            return 1
    if args.update_fingerprint:
        if fingerprint() != before:
            print("ERROR: data changed during validation; fingerprint not updated")
            return 1
        write_fingerprint(before)
        return run(python + ["-m", "pytest", "-q", "tests/test_content_integrity.py", "-k", "test_content_fingerprint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
