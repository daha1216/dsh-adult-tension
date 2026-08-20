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
        manifest = self.store.init_slot("main", self.source, session_id="session-a")
        state, loaded = self.store.load_slot("main")
        self.assertEqual(3, state["save_version"])
        self.assertEqual(0, manifest["revision"])
        self.assertEqual(manifest["state_sha256"], loaded["state_sha256"])
        self.assertEqual(["main"], [item["slot"] for item in self.store.list_slots()])

    def test_cas_rejects_stale_writer(self) -> None:
        self.store.init_slot("main", self.source)
        candidate = copy.deepcopy(valid_save())
        candidate["meta"]["turn"] = 6
        candidate_source = Path(self.temp.name) / "candidate.yaml"
        candidate_source.write_text(MANAGE.yaml_text(candidate), encoding="utf-8")
        self.store.save_slot("main", candidate_source, expected_revision=0)
        with self.assertRaisesRegex(MANAGE.SaveError, "write conflict"):
            self.store.save_slot("main", candidate_source, expected_revision=0)

    def test_two_concurrent_writers_only_one_commits(self) -> None:
        self.store.init_slot("main", self.source)
        candidate = copy.deepcopy(valid_save())
        candidate["meta"]["turn"] = 6
        candidate_source = Path(self.temp.name) / "candidate.yaml"
        candidate_source.write_text(MANAGE.yaml_text(candidate), encoding="utf-8")
        results: list[str] = []
        barrier = threading.Barrier(2)

        def write_once() -> None:
            barrier.wait()
            try:
                self.store.save_slot("main", candidate_source, expected_revision=0)
                results.append("ok")
            except MANAGE.SaveError:
                results.append("conflict")

        threads = [threading.Thread(target=write_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(["conflict", "ok"], sorted(results))
        _, manifest = self.store.load_slot("main")
        self.assertEqual(1, manifest["revision"])

    def test_branch_starts_from_exact_parent_revision(self) -> None:
        parent = self.store.init_slot("main", self.source)
        branch = self.store.branch("main", "alternate")
        self.assertEqual(parent["archive_id"], branch["parent_archive"])
        self.assertEqual(parent["revision"], branch["parent_revision"])
        state, loaded = self.store.load_slot("alternate")
        self.assertEqual(valid_save(), state)
        self.assertEqual(branch["state_sha256"], loaded["state_sha256"])

    def test_access_mode_can_be_changed_without_active_lease(self) -> None:
        self.store.init_slot("main", self.source)
        manifest = self.store.set_access_mode("main", "shared")
        self.assertEqual("shared", manifest["access_mode"])
        self.store.acquire("main", "session-a")
        with self.assertRaisesRegex(MANAGE.SaveError, "active"):
            self.store.set_access_mode("main", "isolated")
        self.store.release("main", "session-a")
        manifest = self.store.set_access_mode("main", "isolated")
        self.assertEqual("isolated", manifest["access_mode"])

    def test_shared_slot_requires_and_honors_lease(self) -> None:
        self.store.init_slot("shared", self.source, access_mode="shared")
        candidate = copy.deepcopy(valid_save())
        candidate["meta"]["turn"] = 6
        candidate_source = Path(self.temp.name) / "candidate.yaml"
        candidate_source.write_text(MANAGE.yaml_text(candidate), encoding="utf-8")
        with self.assertRaisesRegex(MANAGE.SaveError, "leased"):
            self.store.save_slot("shared", candidate_source, expected_revision=0, session_id="session-a")
        self.store.acquire("shared", "session-a")
        self.store.save_slot("shared", candidate_source, expected_revision=0, session_id="session-a")
        with self.assertRaisesRegex(MANAGE.SaveError, "leased"):
            self.store.save_slot("shared", candidate_source, expected_revision=1, session_id="session-b")
        self.store.release("shared", "session-a")


if __name__ == "__main__":
    unittest.main()
