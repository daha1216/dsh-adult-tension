"""Forward migration of real old databases (SKILL_PACKAGING.md 8, 10).

tests/fixtures/db_v1/adult_tension.db was produced by the schema-1 version of
the Skill (tools/make_db_fixture.py): one session at turn 7 and a slot.
tests/fixtures/db_v2/adult_tension.db was produced by the schema-2 version
(stage 3): one session at turn 27 with undo points, a fact journal, archived
turns and events, and a slot holding its facts inside the slot blob.
"""

import json
import os
import pathlib
import shutil
import sqlite3
import unittest
import zlib

import _bootstrap  # noqa: F401
from adult_tension import DB_SCHEMA_VERSION
from helpers.cli import REPO_ROOT, clean_env, run_cli
from helpers.fs import temp_dir

FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "db_v1", "adult_tension.db")
FIXTURE_V2 = os.path.join(REPO_ROOT, "tests", "fixtures", "db_v2", "adult_tension.db")
FIXTURES = (FIXTURE, FIXTURE_V2)
ENV = clean_env(ADULT_TENSION_INCLUDE_DRAFTS="1")
SLOT = "旧版本的存档"


def connect(path):
    if os.path.abspath(path) in [os.path.abspath(f) for f in FIXTURES]:
        # The committed fixtures are only ever read: no journal or WAL files next to them.
        return sqlite3.connect(pathlib.Path(path).as_uri() + "?immutable=1", uri=True)
    return sqlite3.connect(path)


def schema(path):
    conn = connect(path)
    try:
        return int(conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
    finally:
        conn.close()


def tables(path):
    conn = connect(path)
    try:
        return sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    finally:
        conn.close()


def old_session_facts(path):
    conn = connect(path)
    try:
        return json.loads(zlib.decompress(conn.execute("SELECT state FROM sessions").fetchone()[0]))["facts"]
    finally:
        conn.close()


def old_data_dir(tmp, fixture=FIXTURE):
    data_dir = os.path.join(tmp, "data")
    os.makedirs(data_dir)
    shutil.copyfile(fixture, os.path.join(data_dir, "adult_tension.db"))
    return data_dir


def slot_blobs(path):
    conn = connect(path)
    try:
        state, archive = conn.execute("SELECT state, archive FROM slots").fetchone()
        return json.loads(zlib.decompress(state)), json.loads(zlib.decompress(archive))
    finally:
        conn.close()


class MigrationFromV2Test(unittest.TestCase):
    def test_fixture_is_a_real_v2_database(self):
        self.assertEqual(schema(FIXTURE_V2), 2)
        self.assertIn("fact_journal", tables(FIXTURE_V2))
        self.assertNotIn("slot_facts", tables(FIXTURE_V2))

    def test_slots_become_rows_and_the_old_session_still_undoes_and_plays(self):
        old_state, old_archive = slot_blobs(FIXTURE_V2)
        with temp_dir() as tmp:
            data_dir = old_data_dir(tmp, FIXTURE_V2)
            code, env, _raw = run_cli(["doctor"], data_dir)
            self.assertEqual(code, 0, env)
            migrations = next(c for c in env["data"]["checks"] if c["id"] == "migrations")
            self.assertIn("从 schema 2 迁移到 %d" % DB_SCHEMA_VERSION, migrations["message"])
            db = os.path.join(data_dir, "adult_tension.db")
            backups = os.listdir(os.path.join(data_dir, "backups"))
            self.assertEqual(len(backups), 1)
            self.assertIn("schema2", backups[0])
            conn = sqlite3.connect(db)
            try:
                facts = sorted(r[0] for r in conn.execute("SELECT id FROM slot_facts WHERE slot=?", (SLOT,)))
                archive = conn.execute("SELECT COUNT(*) FROM slot_archive WHERE slot=?", (SLOT,)).fetchone()[0]
                slot_state = json.loads(zlib.decompress(conn.execute("SELECT state FROM slots").fetchone()[0]))
            finally:
                conn.close()
            self.assertEqual(facts, sorted(old_state["facts"]))
            self.assertEqual(archive, len(old_archive))
            self.assertTrue(archive > 0)
            self.assertNotIn("facts", slot_state)
            # the session from schema 2 keeps its undo history and plays on
            code, env, _raw = run_cli(["list-sessions"], data_dir)
            self.assertEqual(code, 0, env)
            old = env["data"]["sessions"][0]
            code, env, _raw = run_cli(["undo-turn"], data_dir, payload={"session_id": old["session_id"], "request_id": "req_undo_after_v3", "expected_revision": old_revision(db, old["session_id"])}, env=ENV)
            self.assertEqual(code, 0, env)
            self.assertEqual(env["data"]["turn"], old["turn"] - 1)
            npc = next(c for c in env["data"]["context"]["scene"]["present"] if c != "player")
            code, env, _raw = run_cli(["commit-turn"], data_dir, payload=continue_commit(old["session_id"], "req_turn_after_v3", env["data"]["revision"], npc), env=ENV)
            self.assertEqual(code, 0, env)
            code, env, _raw = run_cli(["load-slot"], data_dir, payload={"request_id": "req_load_after_v3", "name": SLOT}, env=ENV)
            self.assertEqual(code, 0, env)
            loaded = env["data"]
            npc = next(c for c in loaded["context"]["scene"]["present"] if c != "player")
            code, env, _raw = run_cli(["commit-turn"], data_dir, payload=continue_commit(loaded["session_id"], "req_turn_on_loaded", loaded["revision"], npc), env=ENV)
            self.assertEqual(code, 0, env)


def old_revision(db, session_id):
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT revision FROM sessions WHERE session_id=?", (session_id,)).fetchone()[0]
    finally:
        conn.close()


def continue_commit(session_id, request_id, revision, npc):
    return {
        "session_id": session_id,
        "request_id": request_id,
        "expected_revision": revision,
        "action_mode": "continue",
        "player_input": "继续",
        "operations": [{"op": "npc_action", "npc_id": npc, "action": "揉了揉眼睛"}],
        "content_tags": [],
        "summary": "迁移之后继续。",
        "open_action": "有人揉了揉眼睛",
    }


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
            # and the slot's facts too (schema 3)
            conn = sqlite3.connect(db)
            try:
                slot_rows = sorted(r[0] for r in conn.execute("SELECT id FROM slot_facts"))
            finally:
                conn.close()
            self.assertEqual(slot_rows, sorted(slot_blobs(FIXTURE)[0]["facts"]))
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
