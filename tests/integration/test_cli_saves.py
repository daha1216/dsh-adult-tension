"""Sessions, export, import and the debug view through the real entry script."""

import json
import os
import unittest

import _bootstrap  # noqa: F401
from helpers.cli import clean_env, run_cli
from helpers.fs import temp_dir

ENV = clean_env(ADULT_TENSION_INCLUDE_DRAFTS="1")


def new_game(data_dir, seed, rid):
    code, env, _raw = run_cli(["new-game"], data_dir, payload={"request_id": rid, "mode": "pressure", "seed": seed}, env=ENV)
    assert code == 0, env
    return env["data"]


class SavesThroughCliTest(unittest.TestCase):
    def test_list_export_import_and_debug(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "数据")
            opened = new_game(data_dir, 21, "req_cli_new_0001")
            sid = opened["session_id"]
            code, env, _raw = run_cli(["list-sessions"], data_dir, env=ENV)
            self.assertEqual(code, 0, env)
            self.assertEqual([s["session_id"] for s in env["data"]["sessions"]], [sid])
            target = os.path.join(tmp, "导出 目录", "港口的局.json")
            os.makedirs(os.path.dirname(target))
            code, env, _raw = run_cli(["export-save"], data_dir, payload={"session_id": sid, "path": target}, env=ENV)
            self.assertEqual(code, 0, env)
            self.assertEqual(env["data"]["path"], os.path.normpath(target))
            with open(target, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["checksum"], env["data"]["checksum"])
            code, env, _raw = run_cli(["import-save"], data_dir, payload={"request_id": "req_cli_imp_0001", "path": target, "slot": "从文件来的"}, env=ENV)
            self.assertEqual(code, 0, env)
            imported = env["data"]["session_id"]
            self.assertNotEqual(imported, sid)
            code, again, _raw = run_cli(["import-save"], data_dir, payload={"request_id": "req_cli_imp_0001", "path": target, "slot": "从文件来的"}, env=ENV)
            self.assertTrue(again["data"]["replayed"])  # a retried import does not create a second session
            self.assertEqual(again["data"]["session_id"], imported)
            code, env, _raw = run_cli(["list-sessions"], data_dir, env=ENV)
            self.assertEqual(len(env["data"]["sessions"]), 2)
            code, env, _raw = run_cli(["status"], data_dir, payload={"session_id": imported, "level": "debug"}, env=ENV)
            self.assertEqual(code, 0, env)
            debug = env["data"]["debug"]
            self.assertEqual(debug["state_problems"], [])
            self.assertEqual(debug["storage"]["save"]["current_slot"], "从文件来的")
            self.assertEqual(debug["storage"]["undo"], {"floor": 1, "points": 0})

    def test_an_unwritable_result_is_still_an_envelope(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            code, env, raw = run_cli(["version"], data_dir, env=clean_env(ADULT_TENSION_FAULT="unserializable_result"))
            self.assertEqual(code, 30)
            self.assertEqual(env["error"]["code"], "INTERNAL_ERROR")
            self.assertTrue(os.path.isfile(env["error"]["log"]))
            self.assertEqual(raw.count(b"\n") <= 1, True)


if __name__ == "__main__":
    unittest.main()
