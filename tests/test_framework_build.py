from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_frameworks as compiler
import qa
import world_frameworks as frameworks


class FrameworkBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.authoring = self.root / "authoring"
        self.reviews = self.root / "reviews"
        self.authoring.mkdir()
        self.reviews.mkdir()
        self.index = self.root / "index.yaml"
        self.key = "mat-" + "a" * 32
        self.source = {"id": self.key, "name": "Demo", "material": {"rule": "A test setting"}}
        self.write(self.index, {"frameworks": [{"id": self.key, "name": "Demo"}]})
        self.write(self.authoring / f"{self.key}.yaml", self.source)

    def write(self, path, value):
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    def review(self):
        return {"id": self.key, "name": "Demo", "semantic_status": "REVIEWED", "reason": "Source inspected",
                "quality": {"grade": "B"},
                "source_hash": compiler.digest(self.source["material"]),
                "checks": dict.fromkeys(compiler.REVIEW_CHECKS, True)}

    def build(self):
        return compiler.aggregate(self.index, self.authoring, self.reviews)

    def test_unreviewed_is_authored_but_not_in_default_pool(self):
        built = self.build()
        self.assertEqual(["Demo"], list(built["frameworks"]))
        self.assertEqual({}, built["reviewed_frameworks"])
        self.assertEqual(0, built["legacy_weight"])

    def test_approval_requires_exact_identity_hash_and_all_checks(self):
        self.write(self.reviews / f"{self.key}.yaml", self.review())
        self.assertIn("Demo", self.build()["reviewed_frameworks"])
        for field, value in (("name", "Other"), ("id", "other"), ("source_hash", "stale"),
                             ("checks", {"unchecked_shortcut": True})):
            with self.subTest(field=field):
                review = self.review()
                review[field] = value
                self.write(self.reviews / f"{self.key}.yaml", review)
                self.assertEqual({}, self.build()["reviewed_frameworks"])

    def test_pending_quality_review_is_not_default_approved(self):
        for quality in ({"grade": "REVIEW_REQUIRED"}, {"grade": "unknown"}, None):
            review = self.review()
            review["quality"] = quality
            self.write(self.reviews / f"{self.key}.yaml", review)
            self.assertEqual({}, self.build()["reviewed_frameworks"])

    def test_unindexed_or_mismatched_source_is_rejected(self):
        self.write(self.authoring / "extra.yaml", self.source)
        with self.assertRaisesRegex(ValueError, "Unindexed"):
            self.build()
        (self.authoring / "extra.yaml").unlink()
        self.source["name"] = "Renamed without index migration"
        self.write(self.authoring / f"{self.key}.yaml", self.source)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.build()

    def test_yaml_duplicate_keys_are_not_silently_overwritten(self):
        self.index.write_text("frameworks: []\nframeworks: []\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate YAML key"):
            self.build()

    def test_state_text_validation_rejects_duplicate_keys(self):
        import validate_state
        errors = validate_state.validate_text("save_version: 3\nsave_version: 3\n")
        self.assertEqual(1, len(errors))
        self.assertIn("duplicate key", errors[0])

    def test_auto_has_no_implicit_legacy_fallback(self):
        def legacy(*args):
            self.fail("auto called legacy")
        with self.assertRaises(frameworks.FrameworkError):
            frameworks.build(legacy, {"世界框架": {}}, 11, "all_random", {}, {}, {}, "daily", "auto")

    def test_pressure_binding_is_exact_not_cartesian(self):
        pressure = {"bindings": [{"activity": "repair", "place": "shop", "pair": 0}]}
        self.assertTrue(frameworks.pressure_allows(pressure, "repair", "shop", 0))
        self.assertFalse(frameworks.pressure_allows(pressure, "repair", "lobby", 0))
        self.assertFalse(frameworks.pressure_allows(pressure, "talk", "shop", 0))
        self.assertFalse(frameworks.pressure_allows(pressure, "repair", "shop", 1))

    def test_frozen_section_matches_audited_bytes(self):
        self.assertEqual([], qa.frozen_errors())

    def test_selection_keeps_exact_user_approved_count(self):
        index = compiler.read_yaml(compiler.INDEX)
        baseline = compiler.read_yaml(ROOT / "maintenance/baseline.yaml")["framework_selection"]
        self.assertEqual(baseline["retained_count"], len(index["frameworks"]))
        self.assertFalse(set(baseline["removed"]) & {r["name"] for r in index["frameworks"]})

    def test_brief_preserves_committed_ages_and_framework_boundary(self):
        import build_opening
        import fill_opening
        import live_slice
        import roll_opening
        pools = roll_opening.load_pools()
        name = "幕末町屋与道场"
        drawn = roll_opening.build_roll(pools, 11, recent={}, opening_mode="daily", framework=name)
        state = fill_opening.fill_opening(build_opening.build_skeleton(drawn), drawn, fill_opening.load_tables())
        brief = live_slice.opening_brief(state)
        self.assertEqual(state["player"]["age"], brief["player"]["age"])
        self.assertEqual(state["npcs"][0]["age"], brief["npc"]["age"])
        frame = pools["世界框架"][name]
        self.assertIn(frame["technology_boundary"], brief["world"]["constants"])
        self.assertIn(frame["bridge_explanation"], brief["world"]["constants"])


if __name__ == "__main__":
    unittest.main()
