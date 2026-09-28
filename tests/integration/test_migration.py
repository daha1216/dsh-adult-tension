"""Forward migration of a real old database (SKILL_PACKAGING.md 8, 10).

tests/fixtures/db_v1/adult_tension.db was produced by the schema-1 version of
the Skill (tools/make_db_fixture.py): one session at turn 7 and a slot.
"""

import json
import os
import shutil
import sqlite3
import unittest
import zlib

import _bootstrap  # noqa: F401
from adult_tension import DB_SCHEMA_VERSION
from helpers.cli import REPO_ROOT, clean_env, run_cli
from helpers.fs import temp_dir

FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "db_v1", "adult_tension.db")
SLOT = "旧版本的存档"


def schema(path):
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
    finally:
        conn.close()


def tables(path):
    conn = sqlite3.connect(path)
    try:
        return sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    finally:
        conn.close()


def old_session_facts(path):
    conn = sqlite3.connect(path)
    try:
        return json.loads(zlib.decompress(conn.execute("SELECT state FROM sessions").fetchone()[0]))["facts"]
    finally:
        conn.close()


def old_data_dir(tmp):
    data_dir = os.path.join(tmp, "data")
    os.makedirs(data_dir)
    shutil.copyfile(FIXTURE, os.path.join(data_dir, "adult_tension.db"))
    return data_dir


class MigrationTest(unittest.TestCase):
    def test_fixture_is_a_real_v1_database(self):
        self.assertEqual(schema(FIXTURE), 1)
        self.assertNotIn("commit_failures", tables(FIXTURE))

    def test_old_database_is_backed_up_then_migrated_and_still_playable(self):
        with temp_dir() as tmp:
            data_dir = old_data_dir(tmp)
            code, env, _raw = run_cli(["doctor"], data_dir)
            self.assertEqual(code, 0, env)
            migrations = next(c for c in env["data"]["checks"] if c["id"] == "migrations")
            self.assertIn("从 schema 1 迁移到 %d" % DB_SCHEMA_VERSION, migrations["message"])
            db = os.path.join(data_dir, "adult_tension.db")
            self.assertEqual(schema(db), DB_SCHEMA_VERSION)
            self.assertIn("commit_failures", tables(db))
            # facts moved out of the per-turn blob into rows, with random coordinates
            old_facts = old_session_facts(FIXTURE)
            conn = sqlite3.connect(db)
            try:
                rows = {r[0]: json.loads(r[1]) for r in conn.execute("SELECT id, data FROM facts")}
                blob = json.loads(zlib.decompress(conn.execute("SELECT state FROM sessions").fetchone()[0]))
            finally:
                conn.close()
            self.assertEqual(sorted(rows), sorted(old_facts))
            self.assertTrue(all("coord" in f for f in rows.values()))
            self.assertNotIn("facts", blob)
            self.assertEqual(blob["schema_version"], 2)
            backups = os.listdir(os.path.join(data_dir, "backups"))
            self.assertEqual(len(backups), 1)
            self.assertIn("schema1", backups[0])
            self.assertEqual(schema(os.path.join(data_dir, "backups", backups[0])), 1)
            code, env, _raw = run_cli(["list-slots"], data_dir)
            self.assertEqual([s["name"] for s in env["data"]["slots"]], [SLOT])
            code, env, _raw = run_cli(["load-slot"], data_dir, payload={"request_id": "req_load_after_migrate", "name": SLOT}, env=clean_env(ADULT_TENSION_INCLUDE_DRAFTS="1"))
            self.assertEqual(code, 0, env)
            loaded = env["data"]
            self.assertEqual(loaded["turn"], 7)
            npc = next(c for c in loaded["context"]["scene"]["present"] if c != "player")
            commit = {
                "session_id": loaded["session_id"],
                "request_id": "req_turn_after_migrate",
                "expected_revision": loaded["revision"],
                "action_mode": "continue",
                "player_input": "继续",
                "operations": [{"op": "npc_action", "npc_id": npc, "action": "揉了揉眼睛"}],
                "content_tags": [],
                "summary": "迁移之后继续。",
                "open_action": "有人揉了揉眼睛",
            }
            code, env, _raw = run_cli(["commit-turn"], data_dir, payload=commit)
            self.assertEqual(code, 0, env)
            self.assertEqual(env["data"]["turn"], 8)

    def test_failed_migration_restores_the_backup(self):
        with temp_dir() as tmp:
            data_dir = old_data_dir(tmp)
            db = os.path.join(data_dir, "adult_tension.db")
            code, env, _raw = run_cli(["list-slots"], data_dir, env=clean_env(ADULT_TENSION_FAULT="migration_fail"))
            self.assertEqual(code, 20)
            self.assertEqual(env["error"]["code"], "MIGRATION_FAILED")
            self.assertTrue(env["error"]["restored"])
            self.assertTrue(os.path.isfile(env["error"]["backup"]))
            self.assertEqual(schema(db), 1)
            self.assertNotIn("commit_failures", tables(db))
            conn = sqlite3.connect(db)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 1)
            conn.close()
            code, env, _raw = run_cli(["list-slots"], data_dir)
            self.assertEqual(code, 0, env)
            self.assertEqual(schema(db), DB_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
