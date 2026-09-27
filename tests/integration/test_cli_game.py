"""Gameplay through the real entry script, one fresh process per call."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import zlib

import _bootstrap  # noqa: F401
from adult_tension.application.fake_narrator import FakeNarrator
from helpers.cli import ENTRY, clean_env, run_cli
from helpers.domain import state_digest
from helpers.fs import temp_dir

ENV = clean_env(ADULT_TENSION_INCLUDE_DRAFTS="1")


def db_state(data_dir, session_id):
    conn = sqlite3.connect(os.path.join(data_dir, "adult_tension.db"))
    try:
        row = conn.execute("SELECT state, content, revision FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        return json.loads(zlib.decompress(row[0])), json.loads(zlib.decompress(row[1])), row[2]
    finally:
        conn.close()


def counts(data_dir, session_id):
    conn = sqlite3.connect(os.path.join(data_dir, "adult_tension.db"))
    try:
        return (
            conn.execute("SELECT revision, turn FROM sessions WHERE session_id=?", (session_id,)).fetchone(),
            conn.execute("SELECT COUNT(*) FROM turn_log WHERE session_id=?", (session_id,)).fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM idempotency WHERE scope=?", (session_id,)).fetchone()[0],
        )
    finally:
        conn.close()


def new_game(data_dir, seed=5, mode="daily", rid="req_new_000001", **extra):
    payload = dict({"request_id": rid, "mode": mode, "seed": seed}, **extra)
    code, env, _raw = run_cli(["new-game"], data_dir, payload=payload, env=ENV)
    assert code == 0, env
    return env["data"]


class ConcurrencyAndCrashTest(unittest.TestCase):
    def test_two_processes_commit_the_same_revision(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            opened = new_game(data_dir)
            sid = opened["session_id"]
            narrator = FakeNarrator(1)
            outcomes = []
            for round_no in range(4):
                state, content, revision = db_state(data_dir, sid)
                results = [None, None]

                def worker(slot):
                    commit = narrator.commit(state, content, force_kind="continue")
                    payload = dict(commit, session_id=sid, request_id="req_race_%d_%d" % (round_no, slot), expected_revision=revision)
                    results[slot] = run_cli(["commit-turn"], data_dir, payload=payload, env=ENV)

                threads = [threading.Thread(target=worker, args=(slot,)) for slot in (0, 1)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                ok = [r for r in results if r[1]["ok"]]
                failed = [r for r in results if not r[1]["ok"]]
                self.assertEqual(len(ok), 1, results)
                self.assertIn(failed[0][1]["error"]["code"], ("STALE_REVISION", "STORAGE_BUSY"))
                outcomes.append(failed[0][1]["error"]["code"])
                _state, _content, new_revision = db_state(data_dir, sid)
                self.assertEqual(new_revision, revision + 1)

    def test_process_killed_inside_the_write_transaction(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            sid = new_game(data_dir)["session_id"]
            state, content, revision = db_state(data_dir, sid)
            before = counts(data_dir, sid)
            commit = FakeNarrator(2).commit(state, content, force_kind="continue")
            payload = dict(commit, session_id=sid, request_id="req_killed_0001", expected_revision=revision)
            handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False)
            handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            handle.close()
            try:
                proc = subprocess.run(
                    [sys.executable, ENTRY, "commit-turn", "--json", "--data-dir", data_dir, "--input-file", handle.name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    env=clean_env(ADULT_TENSION_INCLUDE_DRAFTS="1", ADULT_TENSION_FAULT="kill_in_commit"),
                    timeout=60,
                )
            finally:
                os.remove(handle.name)
            self.assertEqual(proc.returncode, 137)
            self.assertEqual(proc.stdout, b"")
            self.assertEqual(counts(data_dir, sid), before)
            # the same request now succeeds normally: nothing half-written blocks it
            code, env, _raw = run_cli(["commit-turn"], data_dir, payload=payload, env=ENV)
            self.assertEqual(code, 0, env)
            self.assertFalse(env["data"]["replayed"])
            self.assertEqual(env["data"]["revision"], revision + 1)


class EncodingAndInputTest(unittest.TestCase):
    def test_chinese_through_file_and_stdin_under_the_default_code_page(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            player = {"name": "罗秀英", "title": "罗师傅", "gender": "female", "age": 45}
            via_file = new_game(data_dir, player=player)
            self.assertEqual(via_file["context"]["player"]["name"], "罗秀英")
            payload = json.dumps({"request_id": "req_stdin_000001", "mode": "daily", "seed": 6, "player": player}, ensure_ascii=False).encode("utf-8")
            code, env, raw = run_cli(["new-game"], data_dir, stdin_bytes=payload, env=ENV)
            self.assertEqual(code, 0, env)
            self.assertIn("罗秀英".encode("utf-8"), raw)
            self.assertEqual(env["data"]["opening"]["player"]["title"], "罗师傅")
            bom = b"\xef\xbb\xbf" + json.dumps({"session_id": env["data"]["session_id"]}).encode("utf-8")
            code, env2, raw2 = run_cli(["get-context", "--input-file", "-"], data_dir, stdin_bytes=bom, env=ENV)
            self.assertEqual(code, 0, env2)
            self.assertIn("罗秀英".encode("utf-8"), raw2)

    def test_input_errors_have_json_paths(self):
        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")
            sid = new_game(data_dir)["session_id"]
            bad = {
                "session_id": sid,
                "request_id": "req_bad_00000001",
                "expected_revision": 1,
                "action_mode": "continue",
                "player_input": "继续",
                "operations": [{"op": "advance_time", "minutes": 999999}, {"op": "fly"}],
                "content_tags": [],
                "summary": "s",
                "open_action": "o",
                "extra_field": True,
            }
            code, env, _raw = run_cli(["commit-turn"], data_dir, payload=bad, env=ENV)
            self.assertEqual(code, 10)
            paths = sorted(d["path"] for d in env["error"]["details"])
            self.assertIn("$.extra_field", paths)
            self.assertIn("$.operations[0].minutes", paths)
            self.assertIn("$.operations[1].op", paths)
            handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False)
            handle.write(b'{"session_id": "s_1", "session_id": "s_2"}')
            handle.close()
            try:
                code, env, _raw = run_cli(["get-context", "--input-file", handle.name], data_dir, env=ENV)
            finally:
                os.remove(handle.name)
            self.assertEqual((code, env["error"]["code"]), (10, "INVALID_INPUT"))
            self.assertEqual(env["error"]["details"][0]["path"], "$.session_id")


class LongRouteTest(unittest.TestCase):
    """20 turns with cold processes; save at turn 10, load, continue; compare routes."""

    def play(self, data_dir, sid, narrator, turns, tag):
        for index in range(turns):
            state, content, revision = db_state(data_dir, sid)
            commit = narrator.commit(state, content)
            payload = dict(commit, session_id=sid, request_id="req_%s_%04d" % (tag, index), expected_revision=revision)
            code, env, _raw = run_cli(["commit-turn"], data_dir, payload=payload, env=ENV)
            self.assertEqual(code, 0, env)

    def test_save_load_route_matches_uninterrupted_route(self):
        with temp_dir() as tmp:
            straight = os.path.join(tmp, "straight")
            split = os.path.join(tmp, "split")
            a = new_game(straight, seed=99, mode="pressure", rid="req_new_straight")["session_id"]
            self.play(straight, a, FakeNarrator(99), 20, "a")
            b = new_game(split, seed=99, mode="pressure", rid="req_new_split01")["session_id"]
            self.play(split, b, FakeNarrator(99), 10, "b")
            state, _content, revision = db_state(split, b)
            code, env, _raw = run_cli(["save-slot"], split, payload={"session_id": b, "request_id": "req_save_000001", "expected_revision": revision, "name": "中途"}, env=ENV)
            self.assertEqual(code, 0, env)
            code, env, _raw = run_cli(["load-slot"], split, payload={"request_id": "req_load_000001", "name": "中途"}, env=ENV)
            self.assertEqual(code, 0, env)
            c = env["data"]["session_id"]
            self.assertNotEqual(c, b)
            self.play(split, c, FakeNarrator(99), 10, "c")
            final_a = db_state(straight, a)[0]
            final_c = db_state(split, c)[0]
            self.assertEqual(final_a["turn"], 21)
            self.assertEqual(state_digest(final_a), state_digest(final_c))


if __name__ == "__main__":
    unittest.main()
