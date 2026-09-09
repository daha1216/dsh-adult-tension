from __future__ import annotations

import importlib.util
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("material_registry", ROOT / "scripts/material_registry.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class MaterialRegistryTests(unittest.TestCase):
    def fixture(self):
        units = []
        MODULE._add(units, "pools.yaml", ["example"], "one", "one", "world", "pool")
        return units, MODULE.sync({}, units)

    def decision(self, unit, **updates):
        return {"id": unit["id"], "source_hash": unit["source_hash"], "status": "KEEP_LEGACY",
                "modes": ["pressure"], "owners": ["legacy"],
                "compatibility": {"eras": [], "places": [], "themes": ["example"],
                                  "technology_boundary": "Existing legacy constraints apply"},
                "review": {"scope": "unit", "reason": "Fixture semantic review", "release": "governance-1"},
                **updates}

    def test_duplicate_pool_occurrences_have_distinct_stable_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "pools.yaml"
            path.write_text(json.dumps({"example": ["one", "one"]}), encoding="utf-8")
            old = MODULE.units(root)
            self.assertEqual(2, len({u["id"] for u in old}))
            path.write_text(json.dumps({"example": ["new", "one", "one"]}), encoding="utf-8")
            self.assertEqual([u["id"] for u in old], [u["id"] for u in MODULE.units(root)[1:]])

    def test_decisions_are_atomic_and_require_current_source(self):
        units, registry = self.fixture()
        before = copy.deepcopy(registry)
        decision = self.decision(units[0])
        accepted = MODULE.apply_decisions(registry, [decision], units)
        self.assertEqual(before, registry)
        self.assertEqual("KEEP_LEGACY", accepted["entries"][decision["id"]]["status"])
        self.assertEqual("review_decision", accepted["entries"][decision["id"]]["history"][0]["event"])
        for bad in ({**decision, "source_hash": "stale"}, {**decision, "modes": ["legacy"]},
                    {**decision, "unexpected": True}, {**decision, "owners": []}):
            with self.assertRaises(ValueError):
                MODULE.apply_decisions(registry, [bad], units)
            self.assertEqual(before, registry)
        with self.assertRaises(ValueError):
            MODULE.apply_decisions(registry, [decision, decision], units)
        with self.assertRaises(ValueError):
            MODULE.apply_decisions(registry, [decision], [{**units[0], "source_hash": "changed"}])

    def test_content_change_clears_approvals_but_keeps_history(self):
        units, registry = self.fixture()
        decision = self.decision(units[0], quality={"grade": "A"}, activity_functions=["inspect"])
        accepted = MODULE.apply_decisions(registry, [decision], units)
        changed = MODULE.sync(accepted, [{**units[0], "source_hash": "new"}])
        row = changed["entries"][units[0]["id"]]
        self.assertEqual("NOT_REVIEWED", row["status"])
        self.assertEqual([], row["owners"])
        self.assertEqual([], row["modes"])
        self.assertNotIn("quality", row)
        self.assertNotIn("activity_functions", row)
        self.assertEqual("KEEP_LEGACY", row["history"][-1]["status"])
        self.assertEqual("A", accepted["entries"][units[0]["id"]]["quality"]["grade"])

    def test_frozen_content_cannot_be_changed_or_removed(self):
        units, registry = self.fixture()
        decision = self.decision(units[0], status="FROZEN_RESTRICTED",
                                 restrictions={"frozen": True, "restricted": True, "reason": "Frozen fixture"})
        accepted = MODULE.apply_decisions(registry, [decision], units)
        with self.assertRaisesRegex(ValueError, "FROZEN_CONTENT_CHANGED"):
            MODULE.sync(accepted, [{**units[0], "source_hash": "new"}])
        accepted["entries"][units[0]["id"]]["cleanup"] = {"stage": "removed"}
        self.assertTrue(any("FROZEN_REMOVAL" in error for error in MODULE.audit(accepted, [])["errors"]))

    def test_removal_requires_prior_release_and_regression_evidence(self):
        units, registry = self.fixture()
        row = registry["entries"][units[0]["id"]]
        row.update(status="DEPRECATED", cleanup={"stage": "removed", "marked_release": "governance-1"})
        self.assertTrue(MODULE.audit(registry, [])["errors"])
        registry.update(release="governance-2", release_history=["governance-1", "governance-2"])
        self.assertTrue(any("UNVERIFIED_REMOVAL" in error for error in MODULE.audit(registry, [])["errors"]))
        row["cleanup"]["regression_evidence"] = "tests, references and save compatibility reviewed"
        self.assertEqual([], MODULE.audit(registry, [])["errors"])
        row["cleanup"]["marked_release"] = "invented-release"
        self.assertTrue(any("PREMATURE_REMOVAL" in error for error in MODULE.audit(registry, [])["errors"]))

    def test_duplicate_canonical_must_be_live(self):
        units, registry = self.fixture()
        unit = copy.deepcopy(units[0])
        unit["id"] = "removed-canonical"
        registry["entries"][unit["id"]] = {**unit, "status": "DEPRECATED", "cleanup": {"stage": "removed"}}
        decision = self.decision(units[0], status="DUPLICATE", canonical_id=unit["id"])
        with self.assertRaisesRegex(ValueError, "INVALID_CANONICAL"):
            MODULE.apply_decisions(registry, [decision], units)

    def test_failed_atomic_replace_preserves_previous_file_and_cleans_temp(self):
        _, registry = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.yaml"
            path.write_text("previous", encoding="utf-8")
            with patch.object(MODULE.os, "replace", side_effect=OSError("failure")):
                with self.assertRaises(OSError):
                    MODULE.write_registry(registry, path)
            self.assertEqual("previous", path.read_text(encoding="utf-8"))
            self.assertEqual([path], list(path.parent.iterdir()))

    def test_registry_is_maintenance_only_and_conservative(self) -> None:
        units = MODULE.units()
        self.assertGreater(len(units), 2000)
        registry = MODULE.sync({}, units)
        self.assertEqual(2, registry["version"])
        self.assertTrue(all("status" in row and "source_hash" in row for row in registry["entries"].values()))

    def test_sync_preserves_conservative_default_and_framework_reviews(self) -> None:
        registry = MODULE.sync({}, MODULE.units())
        self.assertTrue(any(row["status"] == "NOT_REVIEWED" for row in registry["entries"].values()))
        self.assertTrue(all(row["status"] == "NOT_REVIEWED" for row in registry["entries"].values()
                            if row["kind"] != "framework"))

    def test_changed_content_invalidates_review(self):
        unit = MODULE.units()[0]
        registry = MODULE.sync({}, [unit])
        row = registry["entries"][unit["id"]]
        row.update(status="KEEP_LEGACY", review={"scope":"unit","reason":"reviewed","release":"one"})
        same = MODULE.sync(registry, [unit])
        self.assertEqual("KEEP_LEGACY", same["entries"][unit["id"]]["status"])
        changed = MODULE.sync(registry, [{**unit,"source_hash":"changed"}])
        self.assertEqual("NOT_REVIEWED", changed["entries"][unit["id"]]["status"])

    def test_cycle_unknown_mode_and_unexplained_removal_fail(self):
        unit = MODULE.units()[0]
        registry = MODULE.sync({}, [unit])
        row = registry["entries"][unit["id"]]
        row.update(status="DUPLICATE", canonical_id=unit["id"], modes=["unknown"])
        errors = MODULE.audit(registry, [unit])["errors"]
        self.assertTrue(any("CANONICAL" in e for e in errors))
        self.assertTrue(any("INVALID_MODES" in e for e in errors))
        self.assertTrue(MODULE.audit(registry, [])["errors"])

    def test_release_gate_rejects_pending_reviews(self):
        unit = MODULE.units()[0]
        registry = MODULE.sync({}, [unit])
        self.assertFalse(MODULE.audit(registry, [unit])["errors"])
        self.assertTrue(MODULE.audit(registry, [unit], require_reviewed=True)["errors"])


if __name__ == "__main__":
    unittest.main()
