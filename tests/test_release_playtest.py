from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_playtest as release
from build_frameworks import digest

# v1.4.0 release completion: every case in the tree that the release gate reads now
# has fresh evidence (matching source_hash + review), so the stale set is empty and
# the dry-run plan has nothing to run. These numbers pin the dry-run plan to it.
STALE_FRAMEWORKS = 0
STALE_CASES = 0
TURNS_PER_CASE = 4
TOTAL_MODEL_CALLS = 0

# The tree has no never-played frameworks left, so the dry-run emits no audit notes.
MISSING_NOTES = []


class ReleaseFixtureTests(unittest.TestCase):
    """Pure-static coverage of the dry-run plan against a synthetic tree."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = {"host": "DeepSeek Harness", "modes": ["daily", "pressure"], "seed": 11,
                       "continuation_turns": 3, "minimum_model_responses": 4, "minimum_score": 9}
        self.write("maintenance/baseline.yaml", {"playtest": self.config})
        self.frameworks = [{"id": "fx-fresh", "name": "Fresh"}, {"id": "fx-stale", "name": "Stale"}]
        self.write("authoring/framework_index.yaml", {"frameworks": self.frameworks})
        self.write("authoring/frameworks/fx-fresh.yaml", {"material": {"rule": "fresh"}})
        self.write("authoring/frameworks/fx-stale.yaml", {"material": {"rule": "current"}})
        self.record("fx-fresh", "daily", {"rule": "fresh"})
        self.record("fx-fresh", "pressure", {"rule": "fresh"})
        self.record("fx-stale", "daily", {"rule": "outdated material"})
        self.record("fx-stale", "pressure", {"rule": "current"})

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value), encoding="utf-8")

    def path(self, key, mode):
        return self.root / f"maintenance/playtests/{key}-{mode}.json"

    def review_path(self, key, mode):
        return self.root / f"maintenance/playtests/{key}-{mode}.review.yaml"

    def record(self, key, mode, material):
        """Write a transcript whose recorded source_hash may already be outdated.

        Transcripts are JSON on disk (`json.loads` in `stale_cases`), so they must
        be dumped as JSON rather than through the YAML helper.
        """
        path = self.path(key, mode)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"source_hash": digest(material),
                                    "turns": [{"turn": i} for i in range(TURNS_PER_CASE)]}),
                        encoding="utf-8")
        return path

    def test_only_hash_mismatched_cases_are_stale(self):
        rows, notes = release.stale_cases(self.root)
        self.assertEqual([], notes)
        self.assertEqual(["fx-stale-daily"], [row["stem"] for row in rows])
        self.assertEqual(digest({"rule": "current"}), rows[0]["expected_hash"])
        self.assertEqual(digest({"rule": "outdated material"}), rows[0]["recorded_hash"])

    def test_plan_counts_model_calls_without_touching_anything(self):
        rows, _ = release.stale_cases(self.root)
        before = sorted(p.name for p in (self.root / "maintenance/playtests").iterdir())
        payload = release.plan(rows, self.config, "20260101-0000")
        self.assertEqual(1, payload["framework_count"])
        self.assertEqual(["Stale"], payload["stale_frameworks"])
        self.assertEqual(1, payload["stale_cases"])
        self.assertEqual(TURNS_PER_CASE, payload["turns_per_case"])
        self.assertEqual(4, payload["generation_model_calls"])
        self.assertEqual(1, payload["review_model_calls"])
        self.assertEqual(5, payload["total_model_calls"])
        self.assertEqual("maintenance/playtests/release-20260101-0000/", payload["archive_dir"])
        self.assertEqual(before, sorted(p.name for p in (self.root / "maintenance/playtests").iterdir()))

    def test_missing_evidence_is_reported_not_silently_skipped(self):
        stale = self.path("fx-stale", "pressure")
        stale.unlink()
        rows, notes = release.stale_cases(self.root)
        self.assertEqual(["PLAYTEST_MISSING: fx-stale-pressure"], notes)
        self.assertEqual(["fx-stale-daily", "fx-stale-pressure"], [row["stem"] for row in rows])
        self.assertIsNone(rows[1]["recorded_hash"])
        self.assertEqual(digest({"rule": "current"}), rows[1]["expected_hash"])

    def test_unreadable_evidence_is_reported_not_raised(self):
        self.path("fx-stale", "pressure").write_text("{not json", encoding="utf-8")
        rows, notes = release.stale_cases(self.root)
        self.assertEqual(1, len(notes))
        self.assertIn("PLAYTEST_UNREADABLE: fx-stale-pressure", notes[0])
        self.assertEqual(["fx-stale-daily"], [row["stem"] for row in rows])

    def test_archive_moves_only_stale_evidence_and_deletes_nothing(self):
        rows, _ = release.stale_cases(self.root)
        self.review_path("fx-stale", "daily").write_text("reviewer: fixture\n", encoding="utf-8")
        target = release.archive(rows, "20260101-0000", self.root)
        moved = sorted(p.name for p in target.iterdir())
        self.assertEqual(["fx-stale-daily.json", "fx-stale-daily.review.yaml"], moved)
        self.assertFalse(self.path("fx-stale", "daily").exists())
        self.assertTrue(self.path("fx-stale", "pressure").exists())
        self.assertTrue(self.path("fx-fresh", "daily").exists())

    def test_dry_run_makes_no_model_call_and_moves_no_file(self):
        before = sorted(p.name for p in (self.root / "maintenance/playtests").iterdir())
        with patch.object(release, "ROOT", self.root), \
                patch.object(release, "load_config", return_value=self.config), \
                patch.object(release.subprocess, "run") as runner:
            code = release.main(["--dry-run", "--stamp", "20260101-0000"])
        self.assertEqual(0, code)
        self.assertEqual([], runner.call_args_list)
        self.assertEqual(before, sorted(p.name for p in (self.root / "maintenance/playtests").iterdir()))


class ReleaseDryRunOnTreeTests(unittest.TestCase):
    """Pin the dry-run plan to the real tree: pure static, zero model calls."""

    def test_dry_run_plan_matches_the_known_stale_set(self):
        rows, notes = release.stale_cases()
        payload = release.plan(rows, release.load_config(), "20260101-0000")
        self.assertEqual(MISSING_NOTES, notes)
        self.assertEqual(STALE_FRAMEWORKS, payload["framework_count"])
        self.assertEqual(STALE_FRAMEWORKS, len(payload["stale_frameworks"]))
        self.assertEqual(STALE_CASES, payload["stale_cases"])
        self.assertEqual(STALE_FRAMEWORKS * len(payload["modes"]), payload["stale_cases"])
        self.assertEqual(payload["stale_cases"] * TURNS_PER_CASE, payload["generation_model_calls"])
        self.assertEqual(payload["stale_cases"], payload["review_model_calls"])
        self.assertEqual(TOTAL_MODEL_CALLS, payload["total_model_calls"])

    def test_dry_run_exits_zero_without_running_a_command(self):
        with patch.object(release.subprocess, "run") as runner:
            self.assertEqual(0, release.main(["--dry-run", "--stamp", "20260101-0000"]))
        self.assertEqual([], runner.call_args_list)
        self.assertEqual(0, len(list(Path(ROOT / "maintenance/playtests").glob("release-20260101-0000"))))


if __name__ == "__main__":
    unittest.main()
