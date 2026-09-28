"""doctor / version through the real entry script in fresh processes."""

import json
import os
import sqlite3
import unittest

import _bootstrap  # noqa: F401
from adult_tension import DB_SCHEMA_VERSION
from helpers.cli import SKILL_ROOT, clean_env, run_cli
from helpers.fs import copy_skill, temp_dir, unwritable_dir


def schema_version(data_dir):
    conn = sqlite3.connect(os.path.join(data_dir, "adult_tension.db"))
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


class DoctorTest(unittest.TestCase):
    def test_fresh_then_initialized_data_dir(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            code, env, raw = run_cli(["doctor"], data_dir)
            self.assertEqual(code, 0, env)
            self.assertTrue(env["ok"])
            data = env["data"]
            self.assertFalse(data["fast_path"])
            self.assertIn(data["status"], ("ok", "warn"))
            self.assertEqual(os.path.normcase(data["data_dir"]), os.path.normcase(data_dir))
            ids = [c["id"] for c in data["checks"]]
            for expected in ("python", "data_dir", "sqlite", "migrations", "skill_files", "content"):
                self.assertIn(expected, ids)
            for sub in ("backups", "exports", "logs"):
                self.assertTrue(os.path.isdir(os.path.join(data_dir, sub)))
            self.assertEqual(schema_version(data_dir), DB_SCHEMA_VERSION)
            self.assertTrue(os.path.isfile(os.path.join(data_dir, "version.json")))
            self.assertTrue(data["next_request_id"].startswith("r_"))
            # stdout is UTF-8 bytes regardless of the console code page
            self.assertIn("数据目录".encode("utf-8"), raw)

            code, env, _raw = run_cli(["doctor"], data_dir)
            self.assertEqual(code, 0, env)
            self.assertTrue(env["data"]["fast_path"])

    def test_unwritable_data_dir(self):
        with temp_dir() as tmp, unwritable_dir(tmp) as locked:
            data_dir = os.path.join(locked, "data")
            code, env, _raw = run_cli(["doctor"], data_dir)
            self.assertEqual(code, 20)
            self.assertEqual(env["error"]["code"], "DATA_DIR_UNAVAILABLE")
            tried = env["error"]["doctor"]["checks"]
            self.assertTrue(any(c["id"] == "data_dir" and c["status"] == "fail" for c in tried))
            self.assertEqual(os.path.normcase(env["error"]["details"][0]["path"]), "$.data_dir")
            self.assertTrue(env["error"]["details"][0]["hint"])

    def test_data_dir_blocked_by_a_file(self):
        with temp_dir() as tmp:
            blocker = os.path.join(tmp, "blocker")
            open(blocker, "w").close()
            code, env, _raw = run_cli(["version"], None)
            self.assertEqual(code, 0)
            code, env, _raw = run_cli(["doctor"], os.path.join(blocker, "data"))
            self.assertEqual(code, 20)
            self.assertEqual(env["error"]["code"], "DATA_DIR_UNAVAILABLE")

    def test_data_dir_inside_skill_is_refused_without_touching_it(self):
        inside = os.path.join(SKILL_ROOT, "user-data")
        code, env, _raw = run_cli(["doctor"], inside)
        self.assertEqual(code, 20)
        self.assertEqual(env["error"]["code"], "DATA_DIR_UNAVAILABLE")
        self.assertFalse(os.path.exists(inside))

    def test_data_dir_from_environment(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "from-env")
            code, env, _raw = run_cli(["doctor"], None, env=clean_env(ADULT_TENSION_HOME=data_dir))
            self.assertEqual(code, 0, env)
            self.assertEqual(env["data"]["data_dir_source"], "env")
            self.assertTrue(os.path.isfile(os.path.join(data_dir, "adult_tension.db")))

    def test_tampered_content_is_reported(self):
        with temp_dir() as tmp:
            skill = copy_skill(tmp)
            index_path = os.path.join(skill, "content", "index.json")
            with open(index_path, encoding="utf-8") as handle:
                index = json.load(handle)
            index["worlds"].append({"id": "ghost_world", "status": "released"})
            with open(index_path, "w", encoding="utf-8") as handle:
                json.dump(index, handle, ensure_ascii=False)
            entry = os.path.join(skill, "scripts", "adult_tension.py")
            code, env, _raw = run_cli(["doctor"], os.path.join(tmp, "data"), entry=entry)
            self.assertEqual(code, 10)
            self.assertEqual(env["error"]["code"], "CONTENT_ERROR")
            self.assertTrue(any("ghost_world" in d["path"] for d in env["error"]["details"]))

    def test_newer_database_is_not_modified(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            self.assertEqual(run_cli(["doctor"], data_dir)[0], 0)
            conn = sqlite3.connect(os.path.join(data_dir, "adult_tension.db"))
            conn.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
            conn.commit()
            tables_before = conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
            conn.close()
            code, env, _raw = run_cli(["doctor"], data_dir)
            self.assertEqual(code, 20)
            self.assertEqual(env["error"]["code"], "UNSUPPORTED_VERSION")
            self.assertEqual(schema_version(data_dir), 99)
            conn = sqlite3.connect(os.path.join(data_dir, "adult_tension.db"))
            self.assertEqual(conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall(), tables_before)
            conn.close()

    def test_failed_first_migration_leaves_nothing_half_done(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            code, env, _raw = run_cli(["doctor"], data_dir, env=clean_env(ADULT_TENSION_FAULT="migration_fail"))
            self.assertEqual(code, 20)
            self.assertEqual(env["error"]["code"], "MIGRATION_FAILED")
            self.assertEqual(schema_version(data_dir), 0)
            self.assertFalse(os.path.exists(os.path.join(data_dir, "version.json")))
            code, env, _raw = run_cli(["doctor"], data_dir)
            self.assertEqual(code, 0, env)
            self.assertEqual(schema_version(data_dir), DB_SCHEMA_VERSION)


class CliSurfaceTest(unittest.TestCase):
    def test_version(self):
        code, env, _raw = run_cli(["version"])
        self.assertEqual(code, 0)
        for key in ("skill_version", "content_version", "db_schema_version", "state_schema_version", "save_format", "rng_version"):
            self.assertIn(key, env["data"])

    def test_unknown_command_and_flag(self):
        code, env, _raw = run_cli(["fly"])
        self.assertEqual((code, env["error"]["code"]), (10, "INVALID_INPUT"))
        code, env, _raw = run_cli(["version", "--bogus"])
        self.assertEqual((code, env["error"]["code"]), (10, "INVALID_INPUT"))
        self.assertTrue(env["error"]["next_request_id"].startswith("r_"))

    def test_commands_without_input_reject_fields(self):
        with temp_dir() as tmp:
            code, env, _raw = run_cli(["version"], os.path.join(tmp, "d"), payload={"surprise": 1})
            self.assertEqual(code, 10)
            self.assertEqual(env["error"]["details"][0]["path"], "$.surprise")

    def test_smoke_plays_both_modes_in_a_temporary_directory(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            code, env, _raw = run_cli(["smoke", "--turns", "30"], data_dir)
            self.assertEqual(code, 0, env)
            runs = env["data"]["runs"]
            self.assertEqual([r["mode"] for r in runs], ["daily", "pressure"])
            for run in runs:
                steps = [s["step"] for s in run["steps"]]
                for step in ("new-game", "replay", "stale", "reject", "save", "load"):
                    self.assertIn(step, steps)
                self.assertEqual(run["turn"], 31)
            self.assertFalse(os.path.exists(os.path.join(data_dir, "adult_tension.db")))  # the user's data dir is untouched

    def test_internal_error_is_an_envelope_with_log(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            self.assertEqual(run_cli(["doctor"], data_dir)[0], 0)
            code, env, _raw = run_cli(["version"], data_dir, env=clean_env(ADULT_TENSION_FAULT="internal_error"))
            self.assertEqual(code, 30)
            self.assertEqual(env["error"]["code"], "INTERNAL_ERROR")
            log = env["error"]["log"]
            self.assertTrue(os.path.isfile(log))
            with open(log, encoding="utf-8") as handle:
                self.assertIn(env["error"]["error_id"], handle.read())


if __name__ == "__main__":
    unittest.main()
