from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import playtest_report as report
import run_playtest as runner


class PlaytestReportTests(unittest.TestCase):
    def setUp(self):
        self.context_patch = patch.object(runner, "context", return_value={"fixture": "runtime brief"})
        self.context_patch.start()
        self.addCleanup(self.context_patch.stop)
        self.pools_patch = patch.object(runner.roll, "load_pools", return_value={})
        self.pools_patch.start()
        self.addCleanup(self.pools_patch.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.key = "test-framework"
        self.material = {"rule": "fixture"}
        self.config = {"host": "DeepSeek Harness", "modes": ["daily"], "seed": 11,
                       "continuation_turns": 3, "minimum_model_responses": 4, "minimum_score": 8,
                       "dimensions": ["a", "b", "c", "d", "e"]}
        self.write("maintenance/baseline.yaml", {"playtest": self.config})
        self.write("authoring/framework_index.yaml", {"frameworks": [{"id": self.key, "name": "Fixture"}]})
        self.write(f"authoring/frameworks/{self.key}.yaml", {"material": self.material})
        self.path = self.root / f"maintenance/playtests/{self.key}-daily.json"

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value), encoding="utf-8")

    def record(self):
        record = {"framework_id": self.key, "name": "Fixture", "mode": "daily", "seed": 11,
                  "source_hash": report.digest(self.material), "scope": "non_explicit_narrative", "protocol": runner.PROTOCOL,
                  "host": "DeepSeek Harness", "host_version": "test", "generator": "fixture-generator",
                  "turns": [{"turn": i, "request": runner.request_for_turn(i), "response": "actual fixture reply", "recorded_at": "test", "returncode": 0, "prompt_sha256": "a" * 64} for i in range(4)]}
        for i, turn in enumerate(record["turns"]):
            prompt = runner.render_prompt({"fixture": "runtime brief"}, record["turns"][:i], turn["request"])
            turn["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(record), encoding="utf-8")
        return record

    def review(self, **changes):
        turn_reviews = [{"turn": i, "scores": dict.fromkeys(self.config["dimensions"], 2),
                         "evidence": dict.fromkeys(self.config["dimensions"], "actual fixture reply"),
                         "blocking_findings": []} for i in range(4)]
        review = {"reviewer": "independent-fixture-reviewer", "transcript_sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
                  "scores": dict.fromkeys(self.config["dimensions"], 2),
                  "evidence": dict.fromkeys(self.config["dimensions"], "actual fixture reply"),
                  "turn_reviews": turn_reviews, "blocking_findings": []}
        review.update(changes)
        self.write(f"maintenance/playtests/{self.key}-daily.review.yaml", review)

    def test_missing_or_unscored_is_not_a_pass(self):
        self.assertFalse(report.audit(self.root)["passed"])
        self.record()
        result = report.audit(self.root)
        self.assertEqual(4, result["responses"])
        self.assertFalse(result["passed"])

    def test_independent_traceable_evidence_can_pass(self):
        self.record()
        self.review()
        self.assertTrue(report.audit(self.root)["passed"])

    def test_zero_dimension_or_self_review_fails(self):
        self.record()
        self.review(reviewer="fixture-generator")
        self.assertFalse(report.audit(self.root)["passed"])
        self.review(scores={"a": 0, "b": 2, "c": 2, "d": 2, "e": 2})
        self.assertFalse(report.audit(self.root)["passed"])

    def test_transcript_or_material_change_invalidates_review(self):
        self.record()
        self.review()
        self.path.write_text(self.path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertFalse(report.audit(self.root)["passed"])
        self.review()
        self.write(f"authoring/frameworks/{self.key}.yaml", {"material": {"rule": "changed"}})
        self.assertFalse(report.audit(self.root)["passed"])

    def test_missing_turn_is_not_counted_as_four_replies(self):
        record = self.record()
        record["turns"].pop()
        self.path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(0, report.audit(self.root)["responses"])

    def test_good_opening_cannot_hide_unreviewed_or_failed_continuation(self):
        self.record()
        self.review(turn_reviews=[])
        self.assertFalse(report.audit(self.root)["passed"])
        turns = [{"turn": i, "scores": dict.fromkeys(self.config["dimensions"], 2),
                  "evidence": dict.fromkeys(self.config["dimensions"], "actual fixture reply"),
                  "blocking_findings": []} for i in range(4)]
        turns[3]["scores"]["a"] = 0
        self.review(turn_reviews=turns)
        self.assertFalse(report.audit(self.root)["passed"])
        self.review(turn_reviews=turns, scores=turns[3]["scores"])
        self.assertFalse(report.audit(self.root)["passed"])

    def test_turn_evidence_must_come_from_that_turn(self):
        record = self.record()
        record["turns"][3]["response"] = "different final reply"
        self.path.write_text(json.dumps(record), encoding="utf-8")
        self.review()
        result = report.audit(self.root)
        self.assertIn("untraceable scoring evidence", result["errors"][0])

    def test_equal_total_cannot_hide_different_or_zero_summary_dimension(self):
        self.record()
        scores = dict(zip(self.config["dimensions"], [1, 1, 2, 2, 2]))
        turns = [{"turn": i, "scores": scores,
                  "evidence": dict.fromkeys(self.config["dimensions"], "actual fixture reply"),
                  "blocking_findings": []} for i in range(4)]
        self.review(turn_reviews=turns, scores=dict(zip(self.config["dimensions"], [0, 2, 2, 2, 2])))
        self.assertFalse(report.audit(self.root)["passed"])
        self.review(turn_reviews=turns, scores=scores)
        self.assertTrue(report.audit(self.root)["passed"])

    def test_runtime_brief_change_invalidates_unchanged_framework_evidence(self):
        self.record()
        self.review()
        with patch.object(runner, "context", return_value={"fixture": "changed runtime brief"}):
            result = report.audit(self.root)
        self.assertEqual(4, result["responses"])
        self.assertEqual(0, result["current_responses"])
        self.assertIn("stale runtime input", result["errors"][0])

    def test_self_consistent_prompt_hash_does_not_override_current_protocol(self):
        record = self.record()
        record["turns"][3]["request"] = "obsolete follow-up"
        prompt = runner.render_prompt({"fixture": "runtime brief"}, record["turns"][:3], "obsolete follow-up")
        record["turns"][3]["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self.path.write_text(json.dumps(record), encoding="utf-8")
        self.review()
        result = report.audit(self.root)
        self.assertFalse(result["passed"])
        self.assertIn("stale continuation request protocol", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
