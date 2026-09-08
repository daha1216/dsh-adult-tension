from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("material_inventory_test", ROOT / "scripts/material_inventory.py")
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)


class MaterialInventoryTests(unittest.TestCase):
    def test_every_field_in_known_file_is_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.yaml").write_text("known: ok\nhidden: []\nempty: null\nzero: 0\n", encoding="utf-8")
            index = root / "index.txt"
            index.write_text("layers:\n  world:\n    sources:\n    - {file: one.yaml, path: [known]}\n", encoding="utf-8")
            report = I.build_inventory(root, index)
            self.assertEqual(4, report["record_count"])
            self.assertEqual(3, report["status_counts"]["UNMAPPED"])
            self.assertEqual([], report["errors"])

    def test_duplicate_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.yaml"
            path.write_text("meta:\n  rules: [a]\n  rules: [b]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate YAML key"):
                I.read_yaml(path)

    def test_missing_wildcard_child_is_not_silently_skipped(self):
        with self.assertRaises(ValueError):
            I.resolve({"a": {"x": 1}, "b": {}}, ["*", "x"])

    def test_repository_has_unique_ids_and_full_field_accounting(self):
        report = I.build_inventory()
        expected = sum(len(list(I.leaves(I.read_yaml(p)))) for p in I.DATA.glob("*.yaml"))
        self.assertEqual([], report["errors"])
        self.assertEqual(expected, report["record_count"])
        self.assertEqual(expected, len({row["id"] for row in report["records"]}))
        self.assertEqual(0, report["status_counts"].get("UNMAPPED", 0))
        self.assertTrue(all(row["semantic_review"] == "NOT_REVIEWED" for row in report["records"]))

    def test_duplicate_compatibility_blocks_are_preserved_as_one_mapping(self):
        pools = I.read_yaml(I.DATA / "pools.yaml")
        self.assertTrue({"压力来源", "场景动作", "身份族", "玩家社会位置"} <= set(pools["meta"]["material_compatibility"]))


if __name__ == "__main__":
    unittest.main()
