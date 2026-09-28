"""doctor / version through the real entry script in fresh processes."""

import json
import os
import sqlite3
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401
from adult_tension import DB_SCHEMA_VERSION
from helpers.cli import ENTRY, SKILL_ROOT, clean_env, run_cli
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
            for sub in ("backups", "exports", "inputs", "logs"):
                self.assertTrue(os.path.isdir(os.path.join(data_dir, sub)))
            # the host writes its input files here: in the data directory, ready, never in the Skill
            self.assertEqual(os.path.normcase(data["input_dir"]), os.path.normcase(os.path.join(data_dir, "inputs")))
            self.assertFalse(os.path.normcase(data["input_dir"]).startswith(os.path.normcase(SKILL_ROOT)))
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

    def test_unreleased_worlds_count_only_under_the_development_switch(self):
        # doctor tells the host what new-game offers, so the host need not look again
        with open(os.path.join(SKILL_ROOT, "content", "index.json"), encoding="utf-8") as handle:
            worlds = json.load(handle)["worlds"]
        released = sum(1 for w in worlds if w["status"] == "released")

        def content(env):
            return next(c for c in env["data"]["checks"] if c["id"] == "content")

        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            code, env, _raw = run_cli(["doctor"], data_dir)
            self.assertEqual(code, 0, env)
            if released:
                self.assertIn("%d 个世界可开局" % released, content(env)["message"])
            else:
                self.assertEqual((content(env)["status"], content(env)["hint"]), ("warn", "等待世界包发布"))
            drafts = clean_env(ADULT_TENSION_INCLUDE_DRAFTS="1")
            code, env, _raw = run_cli(["doctor"], data_dir, env=drafts)
            self.assertEqual(code, 0, env)
            self.assertFalse(env["data"]["fast_path"])  # the switch is part of what the fast path remembers
            self.assertEqual(content(env)["status"], "ok")
            self.assertIn("%d 个世界可开局" % len(worlds), content(env)["message"])
            code, env, _raw = run_cli(["doctor"], data_dir, env=drafts)
            self.assertTrue(env["data"]["fast_path"])
            self.assertIn("%d 个世界可开局" % len(worlds), content(env)["message"])

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

    def test_a_deleted_location_is_reported_and_existing_games_play_on(self):
        # SKILL_PACKAGING.md 10: compiled content tampered after a game started
        with temp_dir() as tmp:
            skill = copy_skill(tmp)
            entry = os.path.join(skill, "scripts", "adult_tension.py")
            data_dir = os.path.join(tmp, "data")
            env_drafts = clean_env(ADULT_TENSION_INCLUDE_DRAFTS="1")
            code, opened, _raw = run_cli(["new-game"], data_dir, payload={"request_id": "req_before_tamper", "mode": "daily", "seed": 5}, env=env_drafts, entry=entry)
            self.assertEqual(code, 0, opened)
            world_path = os.path.join(skill, "content", "worlds", "harbor_night_shift.json")
            with open(world_path, encoding="utf-8") as handle:
                world = json.load(handle)
            here = opened["data"]["context"]["scene"]["location_id"]
            removed = next(loc["id"] for loc in world["locations"] if loc["id"] != here and any(loc["id"] in other["exits"] for other in world["locations"]))
            world["locations"] = [loc for loc in world["locations"] if loc["id"] != removed]
            with open(world_path, "w", encoding="utf-8") as handle:
                json.dump(world, handle, ensure_ascii=False)
            code, env, _raw = run_cli(["doctor"], data_dir, entry=entry)
            self.assertEqual((code, env["error"]["code"]), (10, "CONTENT_ERROR"))
            self.assertTrue(any(removed in (d["reason"] + d["path"]) for d in env["error"]["details"]), env["error"]["details"][:5])
            state = opened["data"]
            npc = next(c for c in state["context"]["scene"]["present"] if c != "player")
            commit = {
                "session_id": state["session_id"],
                "request_id": "req_after_tamper",
                "expected_revision": state["revision"],
                "action_mode": "continue",
                "player_input": "继续",
                "operations": [{"op": "npc_action", "npc_id": npc, "action": "看了看天"}],
                "content_tags": [],
                "summary": "天色变了。",
                "open_action": "有人抬头看天",
            }
            code, env, _raw = run_cli(["commit-turn"], data_dir, payload=commit, env=env_drafts, entry=entry)
            self.assertEqual(code, 0, env)  # the game uses its own content snapshot

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

    def test_an_evaluation_trace_records_each_call_only_when_asked(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            trace = os.path.join(tmp, "trace.jsonl")
            self.assertEqual(run_cli(["doctor"], data_dir)[0], 0)
            self.assertFalse(os.path.exists(trace))
            env = clean_env(ADULT_TENSION_TRACE=trace, ADULT_TENSION_INCLUDE_DRAFTS="1")
            code, opened, raw = run_cli(["new-game"], data_dir, payload={"request_id": "req_trace_01", "mode": "daily", "seed": 3}, env=env)
            self.assertEqual(code, 0)
            code, failed, _raw = run_cli(["commit-turn"], data_dir, payload={"request_id": "req_trace_02"}, env=env)
            self.assertEqual(code, 10)
            with open(trace, encoding="utf-8") as handle:
                lines = [json.loads(line) for line in handle]
            self.assertEqual([line["argv"][0] for line in lines], ["new-game", "commit-turn"])
            self.assertEqual(lines[0]["input"]["seed"], 3)
            self.assertEqual(lines[0]["envelope"], json.loads(raw.decode("utf-8")))
            self.assertEqual((lines[1]["exit"], lines[1]["envelope"]["error"]["code"]), (10, failed["error"]["code"]))
            self.assertTrue(all(line["ms"] >= 0 for line in lines))
            self.assertEqual({os.path.normcase(os.path.normpath(line["skill_root"])) for line in lines}, {os.path.normcase(os.path.normpath(SKILL_ROOT))})

    def test_a_trace_that_cannot_be_written_is_reported_and_the_answer_stands(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            env = clean_env(ADULT_TENSION_TRACE=os.path.join(tmp, "missing", "trace.jsonl"))
            argv = [sys.executable, ENTRY, "doctor", "--json", "--data-dir", data_dir]
            proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60)
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(json.loads(proc.stdout.decode("utf-8"))["ok"])
            self.assertIn("ADULT_TENSION_TRACE not written", proc.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
