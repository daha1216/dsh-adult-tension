from __future__ import annotations

import copy
import importlib.util
import tempfile
import threading
import unittest
from pathlib import Path

from test_validate_state import valid_save


SCRIPT = Path(__file__).parents[1] / "scripts" / "manage_saves.py"
SPEC = importlib.util.spec_from_file_location("manage_saves", SCRIPT)
assert SPEC and SPEC.loader
MANAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MANAGE)


class ManageSavesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "saves"
        self.store = MANAGE.SaveStore(self.root)
        self.source = Path(self.temp.name) / "source.yaml"
        self.source.write_text(MANAGE.yaml_text(valid_save()), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_init_and_load_preserve_v3_state(self) -> None:
        manifest = self.store.init_slot("main", self.source)
        state, loaded = self.store.load_slot("main")
        self.assertEqual(3, state["save_version"])
        self.assertEqual("main", loaded["slot"])
        self.assertEqual(manifest["updated_at"], loaded["updated_at"])
        self.assertEqual(["main"], [item["slot"] for item in self.store.list_slots()])

    def test_save_rejects_stale_updated_at(self) -> None:
        manifest = self.store.init_slot("main", self.source)
        candidate = copy.deepcopy(valid_save())
        candidate["meta"]["turn"] = 6
        candidate_source = Path(self.temp.name) / "candidate.yaml"
        candidate_source.write_text(MANAGE.yaml_text(candidate), encoding="utf-8")
        self.store.save_slot("main", candidate_source, expected_updated_at=manifest["updated_at"])
        with self.assertRaisesRegex(MANAGE.SaveError, "write conflict"):
            self.store.save_slot("main", candidate_source, expected_updated_at=manifest["updated_at"])

    def test_two_concurrent_writers_only_one_commits(self) -> None:
        manifest = self.store.init_slot("main", self.source)
        candidate = copy.deepcopy(valid_save())
        candidate["meta"]["turn"] = 6
        candidate_source = Path(self.temp.name) / "candidate.yaml"
        candidate_source.write_text(MANAGE.yaml_text(candidate), encoding="utf-8")
        results: list[str] = []
        barrier = threading.Barrier(2)

        def write_once() -> None:
            barrier.wait()
            try:
                self.store.save_slot("main", candidate_source, expected_updated_at=manifest["updated_at"])
                results.append("ok")
            except MANAGE.SaveError:
                results.append("conflict")

        threads = [threading.Thread(target=write_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(["conflict", "ok"], sorted(results))
        _, loaded = self.store.load_slot("main")
        self.assertNotEqual(manifest["updated_at"], loaded["updated_at"])

    def test_duplicate_init_is_rejected(self) -> None:
        self.store.init_slot("main", self.source)
        with self.assertRaisesRegex(MANAGE.SaveError, "already exists"):
            self.store.init_slot("main", self.source)

    def test_list_returns_all_manifests(self) -> None:
        self.store.init_slot("main", self.source)
        second = Path(self.temp.name) / "second.yaml"
        state = copy.deepcopy(valid_save())
        state["meta"]["turn"] = 7
        second.write_text(MANAGE.yaml_text(state), encoding="utf-8")
        self.store.init_slot("branch-b", second)
        slots = {item["slot"] for item in self.store.list_slots()}
        self.assertEqual({"main", "branch-b"}, slots)

    def test_chinese_slot_name_and_list_summary(self) -> None:
        manifest = self.store.init_slot("实验槽", self.source)
        self.assertEqual("实验槽", manifest["slot"])
        listed = {item["slot"]: item for item in self.store.list_slots()}
        self.assertIn("实验槽", listed)
        self.assertEqual(5, listed["实验槽"].get("turn"))
        self.assertTrue(listed["实验槽"].get("summary"))


if __name__ == "__main__":
    unittest.main()
