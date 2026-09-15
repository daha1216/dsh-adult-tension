"""One-shot release orchestration for adult-tension playtest evidence.

Daily maintenance never runs this file: ordinary iteration stops at static and
fingerprint checks (`qa.py --full --update-fingerprint`, zero model calls) and
deliberately tolerates stale playtest evidence for frameworks whose source hash
changed since the last release. That staleness is the expected state between
releases, not a defect to repair.

Release mode is triggered only when the user explicitly asks to publish, and it
closes the evidence gap in one command by orchestrating the existing scripts --
it adds no new gate logic and modifies nothing it calls:

  1. static precheck   qa.py --full                     (abort before any model call)
  2. mismatch scan     reuses playtest_report's source_hash comparison
  3. archive           move stale transcripts + reviews into a dated subdirectory
  4. regenerate        run_playtest.py --framework <name> for each stale framework
  5. review            review_playtest.py run --batch maintenance/playtests
  6. final gate        qa.py --full --release, then --update-fingerprint

Only frameworks whose recorded `source_hash` no longer matches `digest(material)`
-- or that have no transcript at all -- are rerun; frameworks whose hash is
unchanged keep their existing evidence.

Usage
-----
Dry run first -- this is the primary acceptance check and touches no model and
moves no file:

    python -X utf8 scripts/release_playtest.py --dry-run

Actual release, when the user has explicitly asked to publish:

    python -X utf8 scripts/release_playtest.py

On Windows the npm `dsh` shim routes arguments through cmd.exe and shreds the
JSON quotes in the material payload, so the default launcher is the real Node
entry point rather than the shim. `--dsh-entry` overrides it if the checkout
moves. Both run_playtest.py and review_playtest.py take the same value.

Timing and recovery: each step prints progress with elapsed seconds. A failure
stops the run and prints what to re-issue. run_playtest.py persists each turn
with `atomic_json`, so re-running the same command resumes from the recorded
turns instead of restarting the case; already-archived transcripts stay
archived, and the rerun regenerates them into the top-level batch directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_frameworks import digest  # noqa: E402
from material_inventory import read_yaml  # noqa: E402

EVIDENCE = ROOT / "maintenance/playtests"
DEFAULT_DSH_ENTRY = Path(r"C:\dsh\deepseek-harness\apps\cli\lib\bin.js")
# Mirrors run_playtest.CALL_TIMEOUT: one probe call may legitimately take minutes
# under parallel load, so a single timeout must not kill a whole framework lane.
CALL_TIMEOUT = 300
REVIEW_TIMEOUT = 900
REVIEW_JOBS = 4
REVIEW_RETRIES = 3


def python_command(*args: str) -> list[str]:
    return [sys.executable, "-X", "utf8", *args]


def run_step(label: str, command: list[str]) -> int:
    """Run one orchestrated command, printing progress and elapsed time."""
    started = time.monotonic()
    print(f"\n=== {label} ===", flush=True)
    print("+ " + subprocess.list2cmdline(command), flush=True)
    code = subprocess.run(command, cwd=ROOT).returncode
    print(f"--- {label}: exit {code} in {time.monotonic() - started:.1f}s", flush=True)
    return code


def load_config(root: Path = ROOT) -> dict:
    return read_yaml(root / "maintenance/baseline.yaml")["playtest"]


def stale_cases(root: Path = ROOT) -> tuple[list[dict], list[str]]:
    """Identify frameworks whose recorded evidence no longer matches its source.

    Reuses the exact judgement `playtest_report.audit` applies at the release
    gate -- recorded `source_hash` versus `digest(material)` -- without importing
    the audit itself (which rebuilds prompts and needs model pools). Returns the
    stale rows plus notes. A framework with no transcript at all is exactly as
    blocking for the release gate as a hash mismatch, so it enters the rows too
    (with `recorded_hash` None) while its PLAYTEST_MISSING note stays behind as
    an audit trail; both plan() and the run loop in main() consume the same rows.
    """
    config = load_config(root)
    index = read_yaml(root / "authoring/framework_index.yaml")
    evidence = root / "maintenance/playtests"
    rows, notes = [], []
    for row in index["frameworks"]:
        material = read_yaml(root / "authoring/frameworks" / f"{row['id']}.yaml")["material"]
        expected = digest(material)
        for mode in config["modes"]:
            stem = f"{row['id']}-{mode}"
            path = evidence / f"{stem}.json"
            review_path = evidence / f"{stem}.review.yaml"
            if not path.exists():
                notes.append(f"PLAYTEST_MISSING: {stem}")
                rows.append({"id": row["id"], "name": row["name"], "mode": mode, "stem": stem,
                             "transcript": path, "review": review_path,
                             "recorded_hash": None, "expected_hash": expected})
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                notes.append(f"PLAYTEST_UNREADABLE: {stem}: {exc}")
                continue
            if record.get("source_hash") == expected:
                continue
            rows.append({"id": row["id"], "name": row["name"], "mode": mode, "stem": stem,
                         "transcript": path, "review": review_path,
                         "recorded_hash": record.get("source_hash"), "expected_hash": expected})
    return rows, notes


def plan(rows: list[dict], config: dict, stamp: str) -> dict:
    """Pure description of what a release run would do; performs no I/O."""
    frameworks = sorted({row["name"] for row in rows})
    turns = config["continuation_turns"] + 1
    # Missing-evidence rows name files that do not exist yet; archiving only
    # moves what is on disk, so the plan lists only existing files.
    archive_files = [row["transcript"].name for row in rows if row["transcript"].exists()]
    archive_files += [row["review"].name for row in rows if row["review"].exists()]
    return {
        "stale_frameworks": frameworks,
        "framework_count": len(frameworks),
        "stale_cases": len(rows),
        "modes": list(config["modes"]),
        "generation_model_calls": len(rows) * turns,
        "review_model_calls": len(rows),
        "total_model_calls": len(rows) * (turns + 1),
        "turns_per_case": turns,
        "archive_dir": f"maintenance/playtests/release-{stamp}/",
        "archive_files": archive_files,
        "steps": [
            "python -X utf8 scripts/qa.py --full",
            f"archive {len(archive_files)} transcript(s) + review(s) into release-{stamp}/",
            "python -X utf8 scripts/run_playtest.py --framework <name> (per stale framework)",
            "python -X utf8 scripts/review_playtest.py run --batch maintenance/playtests",
            "python -X utf8 scripts/qa.py --full --release",
            "python -X utf8 scripts/qa.py --full --update-fingerprint",
        ],
    }


def archive(rows: list[dict], stamp: str, root: Path = ROOT) -> Path:
    """Move stale evidence into a dated subdirectory; never delete anything."""
    target = root / "maintenance/playtests" / f"release-{stamp}"
    target.mkdir(parents=True, exist_ok=True)
    for row in rows:
        for path in (row["transcript"], row["review"]):
            if path.exists():
                shutil.move(str(path), str(target / path.name))
                print(f"archived {path.name} -> {target.relative_to(root)}", flush=True)
    return target


def print_plan(payload: dict, notes: list[str], dsh_entry: Path) -> None:
    print(json.dumps({"plan": payload, "notes": notes, "dsh_entry": str(dsh_entry)},
                     ensure_ascii=False, indent=2))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the stale frameworks, case counts and archive plan; run no model and move no file")
    parser.add_argument("--dsh-entry", type=Path, default=DEFAULT_DSH_ENTRY,
                        help=f"DSH bin.js used by run_playtest/review_playtest (default: {DEFAULT_DSH_ENTRY})")
    parser.add_argument("--stamp", help="Override the archive directory timestamp (YYYYMMDD-HHMM)")
    parser.add_argument("--skip-precheck", action="store_true",
                        help="Skip the qa.py --full precheck (only for resuming a partially completed release)")
    args = parser.parse_args(argv)

    config = load_config()
    rows, notes = stale_cases()
    stamp = args.stamp or datetime.now().strftime("%Y%m%d-%H%M")
    payload = plan(rows, config, stamp)

    if not rows:
        payload["archive_files"] = []
        print("No stale playtest evidence: every framework matches its current source hash.")
        print_plan(payload, notes, args.dsh_entry)
        return 0

    if args.dry_run:
        print_plan(payload, notes, args.dsh_entry)
        return 0

    if not args.dsh_entry.exists():
        print(f"ERROR: DSH entry not found: {args.dsh_entry}\n"
              f"Pass --dsh-entry <path to apps/cli/lib/bin.js>.")
        return 1

    if not args.skip_precheck:
        if run_step("1/6 static precheck", python_command("scripts/qa.py", "--full")):
            print("ERROR: static precheck failed; no model call was made and no file was moved.\n"
                  "Fix the structural errors first, then re-run this script.")
            return 1

    frameworks = sorted({row["name"] for row in rows})
    print(f"\nstale: {len(frameworks)} framework(s) / {len(rows)} case(s) -> {', '.join(frameworks)}", flush=True)
    target = archive(rows, stamp)

    step = python_command("scripts/run_playtest.py", "--dsh-entry", str(args.dsh_entry))
    for name in frameworks:
        if run_step(f"3/6 regenerate {name}", [*step, "--framework", name]):
            print(f"ERROR: generation failed for {name}.\n"
                  f"Archived evidence is in {target.relative_to(ROOT)}; run_playtest.py records each turn "
                  f"atomically, so re-running the same command resumes instead of restarting.\n"
                  f"Re-issue: python -X utf8 scripts/release_playtest.py --skip-precheck")
            return 1

    review_command = python_command("scripts/review_playtest.py", "run", "--batch", "maintenance/playtests",
                                    "--dsh-entry", str(args.dsh_entry),
                                    "--jobs", str(REVIEW_JOBS), "--timeout", str(REVIEW_TIMEOUT),
                                    "--retries", str(REVIEW_RETRIES))
    if run_step("4/6 independent review", review_command):
        print("ERROR: review step failed.\n"
              "Existing review files are kept; re-running the same review command only scores the "
              "cases still missing a review file.")
        return 1

    if run_step("5/6 release gate", python_command("scripts/qa.py", "--full", "--release")):
        print("ERROR: release gate failed; the fingerprint was not updated.\n"
              "Report the gate errors as-is instead of relaxing the acceptance criteria.")
        return 1

    if run_step("6/6 fingerprint", python_command("scripts/qa.py", "--full", "--update-fingerprint")):
        print("ERROR: fingerprint update failed after the release gate passed.")
        return 1
    print("\nRelease complete: playtest evidence now matches the current source hashes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
