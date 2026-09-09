from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("material_registry", ROOT / "scripts/material_registry.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def unit(label="one", file="pools.yaml", path=("example",), value="payload", kind="pool"):
    rows = []
    MODULE._add(rows, file, path, label, value, "maintenance", kind)
    return rows[0]


def decision(row, **updates):
    return {"id": row["id"], "source_hash": row["source_hash"], "status": "BRIDGE_REQUIRED",
            "review": {"scope": "unit", "reason": "Explicit fixture review", "release": "governance-1"},
            **updates}


class RegistryCompactionTests(unittest.TestCase):
    def round_trip(self, registry):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.yaml"
            MODULE.write_registry(registry, path)
            raw = MODULE.INVENTORY.read_yaml(path)
            loaded = MODULE.load_registry(path)
            first = path.read_bytes()
            MODULE.write_registry(loaded, path)
            self.assertEqual(first, path.read_bytes())
            return raw, loaded

    def test_v1_migrates_losslessly_and_compacts_defaults_and_history(self):
        current = [unit(str(i)) for i in range(60)]
        registry = MODULE.sync({}, current)
        registry = MODULE.apply_decisions(registry, [decision(current[0])], current)
        registry = MODULE.sync(registry, [{**current[0], "source_hash": "changed"}, *current[1:]])
        registry["version"] = 1
        registry["external_note"] = "Preserve integration metadata"
        before = copy.deepcopy(registry)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v1.yaml"
            path.write_text(yaml.safe_dump(registry), encoding="utf-8")
            self.assertEqual(registry, MODULE.load_registry(path))
        raw, loaded = self.round_trip(registry)
        self.assertEqual(before, registry)
        self.assertEqual({**registry, "version": 2}, loaded)
        row = raw["entries"][current[1]["id"]]
        self.assertEqual({"source", "source_hash", "layer"}, set(row))
        history = raw["entries"][current[0]["id"]]["history"]
        self.assertEqual({"event", "source_hash"}, set(history[0]))
        self.assertEqual("Explicit fixture review", history[1]["review"]["reason"])
        self.assertEqual(current[0]["source"], history[1]["source"])
        self.assertLess(len(yaml.safe_dump(raw)), len(yaml.safe_dump(registry)) * 0.60)

    def test_compact_governance_rows_expand_before_audit_and_apply(self):
        current = [unit(kind="contract")]
        raw, expanded = self.round_trip(MODULE.sync({}, current))
        self.assertEqual([], MODULE.audit(raw, current)["errors"])
        self.assertEqual(MODULE.audit(expanded, current), MODULE.audit(raw, current))
        self.assertTrue(MODULE.audit(raw, current, require_reviewed=True)["errors"])
        accepted = MODULE.apply_decisions(raw, [decision(current[0])], current)
        row = accepted["entries"][current[0]["id"]]
        self.assertEqual({"stage": "keep"}, row["cleanup"])
        self.assertEqual([], row["compatibility"]["eras"])
        self.assertEqual([], MODULE.audit(accepted, current, require_reviewed=True)["errors"])
        self.assertEqual(accepted, MODULE.apply_decisions(accepted, [decision(current[0])], current))

    def test_unknown_or_missing_rows_never_pass_strict_gate(self):
        current = [unit()]
        raw, _ = self.round_trip(MODULE.sync({}, current))
        for status in ("UNKNOWN", None, "NOT_REVIEWED"):
            with self.subTest(status=status):
                candidate = copy.deepcopy(raw)
                candidate["entries"][current[0]["id"]]["status"] = status
                self.assertTrue(MODULE.audit(candidate, current, require_reviewed=True)["errors"])
        raw["entries"].clear()
        errors = MODULE.audit(raw, current, require_reviewed=True)["errors"]
        self.assertTrue(any("UNREGISTERED" in e for e in errors))
        self.assertTrue(any("REVIEW_GATE" in e for e in errors))

    def test_review_evidence_is_not_inferred_from_classification(self):
        current = [unit()]
        raw, _ = self.round_trip(MODULE.sync({}, current))
        raw["entries"][current[0]["id"]]["status"] = "BRIDGE_REQUIRED"
        self.assertTrue(any("MISSING_REVIEW_EVIDENCE" in e
                            for e in MODULE.audit(raw, current, require_reviewed=True)["errors"]))

    def test_same_content_rename_and_move_preserve_id_but_invalidate_review(self):
        old = unit()
        moved = unit("renamed", "other.yaml", ("moved",))
        inserted = unit("inserted")
        registry = MODULE.apply_decisions(MODULE.sync({}, [old]), [decision(old)], [old])
        registry["source_aliases"] = {moved["id"]: old["id"]}
        with self.assertRaisesRegex(ValueError, "Stale or unknown decision"):
            MODULE.apply_decisions(registry, [decision(old)], [moved])
        synced = MODULE.sync(registry, [inserted, moved])
        row = synced["entries"][old["id"]]
        self.assertEqual({inserted["id"], old["id"]}, set(synced["entries"]))
        self.assertEqual(old["id"], row["id"])
        self.assertEqual(moved["source"], row["source"])
        self.assertEqual("NOT_REVIEWED", row["status"])
        self.assertIsNone(row["review"])
        self.assertEqual("BRIDGE_REQUIRED", row["history"][-1]["status"])
        with self.assertRaisesRegex(ValueError, "decision source binding"):
            MODULE.apply_decisions(synced, [decision(old)], [inserted, moved])
        reviewed = MODULE.apply_decisions(synced, [decision(row, source=moved["source"])], [inserted, moved])
        raw, loaded = self.round_trip(reviewed)
        self.assertEqual(registry["source_aliases"], raw["source_aliases"])
        self.assertEqual(loaded, MODULE.sync(loaded, [inserted, moved]))
        self.assertEqual([], MODULE.audit(raw, [inserted, moved])["errors"])

    def test_rename_without_alias_is_not_guessed_from_equal_content(self):
        old, moved = unit(), unit("renamed")
        registry = MODULE.sync(MODULE.sync({}, [old]), [moved])
        self.assertEqual({old["id"], moved["id"]}, set(registry["entries"]))
        self.assertTrue(any("UNEXPLAINED_REMOVAL" in e for e in MODULE.audit(registry, [moved])["errors"]))

    def test_alias_conflicts_and_unknown_targets_fail_closed(self):
        old, other, moved = unit(), unit("other"), unit("moved")
        registry = MODULE.sync({}, [old, other])
        for aliases, current in (({moved["id"]: "missing"}, [moved]),
                                 ({other["id"]: old["id"]}, [other]),
                                 ({moved["id"]: old["id"]}, [old, moved]),
                                 ({moved["id"]: old["id"], old["id"]: moved["id"]}, [moved])):
            with self.subTest(aliases=aliases):
                registry["source_aliases"] = aliases
                with self.assertRaises(ValueError):
                    MODULE.sync(registry, current)
                self.assertTrue(MODULE.audit(registry, current, require_reviewed=True)["errors"])

    def test_alias_content_change_rejects_old_hash_and_clears_all_review_fields(self):
        old, moved = unit(), unit("moved", value="new content")
        approved = decision(old, quality={"grade": "A"}, chemistry={"evidence": "fixture"},
                            activity_functions=["inspect"])
        registry = MODULE.apply_decisions(MODULE.sync({}, [old]), [approved], [old])
        registry["source_aliases"] = {moved["id"]: old["id"]}
        raw, _ = self.round_trip(registry)
        synced = MODULE.sync(raw, [moved])
        row = synced["entries"][old["id"]]
        self.assertEqual(moved["source_hash"], row["source_hash"])
        self.assertEqual("NOT_REVIEWED", row["status"])
        for field in ("quality", "chemistry", "activity_functions"):
            self.assertNotIn(field, row)
            self.assertEqual(approved[field], row["history"][-1][field])
        with self.assertRaisesRegex(ValueError, "Stale or unknown decision"):
            MODULE.apply_decisions(synced, [approved], [moved])

    def test_verified_direct_removal_needs_no_invented_release(self):
        old = unit()
        registry = MODULE.sync({}, [old])
        removal = decision(old, status="DEPRECATED", cleanup={"stage": "removed", "policy": "verified_direct",
                           "regression_evidence": "Focused regression passed"})
        removed = MODULE.apply_decisions(registry, [removal], [])
        raw, _ = self.round_trip(removed)
        self.assertEqual("governance-1", raw["release"])
        self.assertEqual(["governance-1"], raw["release_history"])
        self.assertEqual([], MODULE.audit(raw, [], require_reviewed=True)["errors"])
        self.assertTrue(any("INVALID_LIVE_CLEANUP" in e for e in MODULE.audit(raw, [old])["errors"]))
        for change, error in (({"regression_evidence": ""}, "UNVERIFIED_REMOVAL"),
                              ({"policy": "legacy"}, "PREMATURE_REMOVAL"),
                              ({"policy": "verified_direct_typo"}, "PREMATURE_REMOVAL")):
            candidate = copy.deepcopy(raw)
            candidate["entries"][old["id"]]["cleanup"].update(change)
            self.assertTrue(any(error in e for e in MODULE.audit(candidate, [])["errors"]))

    def test_frozen_rows_block_decisions_changes_moves_and_all_removal_stages(self):
        old, moved = unit(), unit("moved")
        frozen = decision(old, status="FROZEN_RESTRICTED", restrictions={"frozen": True, "restricted": True})
        registry = MODULE.apply_decisions(MODULE.sync({}, [old]), [frozen], [old])
        raw, _ = self.round_trip(registry)
        self.assertEqual(registry, MODULE.apply_decisions(raw, [frozen], [old]))
        with self.assertRaisesRegex(ValueError, "FROZEN_DECISION"):
            MODULE.apply_decisions(raw, [decision(old, restrictions={"frozen": False})], [old])
        with self.assertRaisesRegex(ValueError, "FROZEN_CONTENT_CHANGED"):
            MODULE.sync(raw, [{**old, "source_hash": "changed"}])
        raw["source_aliases"] = {moved["id"]: old["id"]}
        with self.assertRaisesRegex(ValueError, "FROZEN_CONTENT_CHANGED"):
            MODULE.sync(raw, [moved])
        for stage in ("keep", "candidate", "removed"):
            raw["entries"][old["id"]]["cleanup"] = {
                "stage": stage, "policy": "verified_direct", "regression_evidence": "tests passed"}
            self.assertTrue(any("FROZEN_REMOVAL" in e for e in MODULE.audit(raw, [])["errors"]))

    def test_canonical_cycles_survive_compaction_and_are_rejected(self):
        current = [unit(), unit("two")]
        registry = MODULE.sync({}, current)
        for index, row in enumerate(current):
            registry["entries"][row["id"]].update(decision(row, status="DUPLICATE",
                                                              canonical_id=current[1-index]["id"]))
        raw, _ = self.round_trip(registry)
        self.assertTrue(any("CANONICAL_CYCLE" in e for e in MODULE.audit(raw, current)["errors"]))
        for row in raw["entries"].values():
            row["cleanup"] = {"stage": "removed", "policy": "verified_direct", "regression_evidence": "tests"}
        self.assertTrue(any("CANONICAL_CYCLE" in e for e in MODULE.audit(raw, [])["errors"]))

    def test_compaction_does_not_convert_invalid_false_values_into_defaults(self):
        current = [unit()]
        registry = MODULE.sync({}, current)
        registry["entries"][current[0]["id"]]["restrictions"]["frozen"] = 0
        raw, loaded = self.round_trip(registry)
        self.assertIs(type(raw["entries"][current[0]["id"]]["restrictions"]["frozen"]), int)
        self.assertTrue(any("INVALID_RESTRICTIONS" in e for e in MODULE.audit(loaded, current)["errors"]))

    def test_cli_sync_decisions_and_review_gate_write_only_on_success(self):
        current = [unit()]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.yaml"
            MODULE.write_registry(MODULE.sync({}, current), path)
            before = path.read_bytes()
            original_load, original_write = MODULE.load_registry, MODULE.write_registry
            with patch.object(MODULE, "REGISTRY", path), \
                    patch.object(MODULE, "load_registry", side_effect=lambda: original_load(path)), \
                    patch.object(MODULE, "units", return_value=current), \
                    patch.object(MODULE, "write_registry", wraps=lambda registry: original_write(registry, path)) as write:
                with contextlib.redirect_stdout(io.StringIO()), \
                        patch("sys.argv", ["material_registry", "--sync", "--require-reviewed"]):
                    self.assertEqual(1, MODULE.main())
                write.assert_not_called()
                self.assertEqual(before, path.read_bytes())
                decisions_path = Path(directory) / "decisions.yaml"
                decisions_path.write_text(yaml.safe_dump([decision(current[0])]), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()), patch("sys.argv", ["material_registry", "--sync",
                        "--decisions", str(decisions_path), "--require-reviewed"]):
                    self.assertEqual(0, MODULE.main())
                write.assert_called_once()
                self.assertEqual(2, MODULE.INVENTORY.read_yaml(path)["version"])


if __name__ == "__main__":
    unittest.main()
