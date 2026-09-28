"""Saves, sessions, export and import (ACCEPTANCE.md 2 "存档"; RUNTIME_PROTOCOL 9)."""

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
import zlib

import _bootstrap  # noqa: F401
from adult_tension import STATE_SCHEMA_VERSION
from adult_tension.application import service, transfer
from adult_tension.domain import state as SS
from adult_tension.errors import AppError
from adult_tension.persistence import repo
from helpers.cli import REPO_ROOT, SKILL_ROOT
from helpers.service import Ids, app, open_game, session

V1_FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "db_v1", "adult_tension.db")


def act(npc, text="看了一眼"):
    return {"op": "npc_action", "npc_id": npc, "action": text}


class Game:
    """A game played through the application layer."""

    def __init__(self, ctx, ids, mode="pressure", seed=11):
        self.ctx = ctx
        self.ids = ids
        self.sid = open_game(ctx, ids, mode=mode, seed=seed)["session_id"]

    def state(self, sid=None):
        return session(self.ctx, sid or self.sid)["state"]

    def npc(self):
        state = self.state()
        return sorted(c for c in state["scene"]["present"] if c != "player" and state["characters"][c]["tier"] == "major")[0]

    def write(self, func, extra, sid=None):
        state = self.state(sid)
        return func(self.ctx, dict(extra, session_id=state["session_id"], request_id=self.ids(), expected_revision=state["revision"]))

    def turn(self, ops, sid=None, mode="continue", **extra):
        body = {"action_mode": mode, "player_input": "……", "operations": ops, "content_tags": [], "summary": "测试回合", "open_action": "场面停住"}
        body.update(extra)
        return self.write(service.commit_turn, body, sid)

    def save(self, name=None, **extra):
        body = dict(extra)
        if name is not None:
            body["name"] = name
        return self.write(service.save_slot, body)


def counts(ctx):
    conn = ctx.db()
    return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in ("sessions", "slots", "facts", "slot_facts", "archive", "slot_archive", "turn_log")}


class SaveLoadRestoreTest(unittest.TestCase):
    def test_load_restores_everything_as_saved_in_a_new_session(self):
        with app() as ctx:
            game = Game(ctx, Ids())
            npc = game.npc()
            game.turn([
                {"op": "npc_action", "npc_id": npc, "action": "主动递过来一支烟", "significant": True, "kind": "approach"},
                {"op": "event_create", "kind": "promise", "title": "明早再谈", "participants": [npc], "in_minutes": 600, "dedupe_key": "t.talk"},
                {"op": "npc_state", "npc_id": npc, "add_conditions": [{"kind": "busy", "text": "手上有活", "minutes": 120}]},
            ])
            game.write(service.set_boundary, {"action": "add", "text": "不要写到血", "tags": ["bodily_harm"]})
            game.write(service.set_safety, {"paused": True})
            game.write(service.set_preferences, {"inner_view": True, "person": "third", "voice": {"npc_id": npc, "voice": "inner"}})
            saved = game.save("全都记着")
            original = game.state()
            before_slot = repo.get_slot(ctx.db(), "全都记着")
            loaded = service.load_slot(ctx, {"request_id": game.ids(), "name": "全都记着"})
            self.assertNotEqual(loaded["session_id"], game.sid)
            copy = game.state(loaded["session_id"])
            self.assertEqual(SS.digest(copy), SS.digest(original))
            for key in ("safety", "events", "preferences", "memory", "facts", "relationships"):
                self.assertEqual(copy[key], original[key], key)
            self.assertEqual(copy["counters"]["major_action_turn"], original["counters"]["major_action_turn"])
            self.assertEqual(copy["characters"][npc]["status"], original["characters"][npc]["status"])
            self.assertEqual(copy["undo_floor"], copy["turn"])
            self.assertEqual(copy["preferences"]["voice"][npc]["voice"], "inner")
            self.assertEqual(copy["counters"]["major_action_turn"], {npc: 2})
            self.assertEqual([b["text"] for b in copy["safety"]["boundaries"]], ["不要写到血"])
            self.assertEqual(loaded["resume"]["open_action"], "场面停住")
            self.assertTrue(loaded["context"]["safety"]["paused"])
            # playing on the copy leaves the slot as it was
            game.turn([act(npc)], sid=loaded["session_id"])
            game.turn([act(npc, "又看了一眼")], sid=loaded["session_id"])
            after_slot = repo.get_slot(ctx.db(), "全都记着")
            self.assertEqual({k: after_slot[k] for k in ("revision", "turn", "version", "saved_at")}, {k: before_slot[k] for k in ("revision", "turn", "version", "saved_at")})
            self.assertEqual(repo.slot_facts(ctx.db(), "全都记着"), original["facts"])
            self.assertEqual(saved["slot"]["turn"], original["turn"])

    def test_a_slot_carries_the_archive_and_facts_as_rows(self):
        with app() as ctx:
            game = Game(ctx, Ids(), mode="daily")
            npc = game.npc()
            game.turn([{"op": "advance_time", "until": "next_morning"}, act(npc)])
            game.turn([act(npc), {"op": "add_fact", "key": "t.note", "text": "记下的事", "known_by": ["player"], "visibility": "private", "origin": "observed"}], chapter_summary="第一夜。")
            conn = ctx.db()
            archived = repo.count_archive(conn, game.sid)
            self.assertGreater(archived, 0)
            game.save("带归档")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM slot_archive WHERE slot=?", ("带归档",)).fetchone()[0], archived)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM slot_facts WHERE slot=?", ("带归档",)).fetchone()[0], repo.count_facts(conn, game.sid))
            loaded = service.load_slot(ctx, {"request_id": game.ids(), "name": "带归档"})
            self.assertEqual(repo.count_archive(conn, loaded["session_id"]), archived)
            self.assertEqual(repo.archive_items(conn, loaded["session_id"]), repo.archive_items(conn, game.sid))

    def test_delete_slot_needs_confirmation(self):
        with app() as ctx:
            game = Game(ctx, Ids(), mode="daily")
            game.save("要删的")
            with self.assertRaises(AppError) as caught:
                game.write(service.delete_slot, {"name": "要删的"})
            self.assertEqual(caught.exception.details[0]["path"], "$.confirm")
            done = game.write(service.delete_slot, {"name": "要删的", "confirm": True})
            self.assertEqual(done["receipt"], "已删除「要删的」")
            self.assertEqual(service.list_slots(ctx, {})["slots"], [])
            self.assertEqual(counts(ctx)["slot_facts"], 0)
            self.assertIsNone(session(ctx, game.sid)["current_slot"])
            with self.assertRaises(AppError) as caught:
                game.write(service.delete_slot, {"name": "要删的", "confirm": True})
            self.assertEqual(caught.exception.code, "NOT_FOUND")


class SessionListTest(unittest.TestCase):
    def test_most_recent_first_with_what_resuming_needs(self):
        with app() as ctx:
            ids = Ids()
            first = Game(ctx, ids, mode="daily", seed=1)
            second = Game(ctx, ids, mode="pressure", seed=2)
            first.turn([act(first.npc())])
            first.write(service.set_safety, {"paused": True})
            listed = service.list_sessions(ctx, {})["sessions"]
            self.assertEqual([s["session_id"] for s in listed], [first.sid, second.sid])
            top = listed[0]
            self.assertEqual((top["turn"], top["paused"], top["open_action"], top["last_summary"]), (2, True, "场面停住", "测试回合"))
            self.assertTrue(top["clock_label"].startswith("第"))
            self.assertEqual(top["turns_since_save"], 1)
            self.assertEqual(service.list_sessions(ctx, {"limit": 1})["sessions"][0]["session_id"], first.sid)


class ExportImportTest(unittest.TestCase):
    def setUp(self):
        self._app = app()
        self.ctx = self._app.__enter__()
        self.game = Game(self.ctx, Ids())
        npc = self.game.npc()
        self.game.turn([act(npc), {"op": "add_fact", "key": "t.secret", "text": "一件事", "known_by": [npc], "visibility": "private", "origin": "observed"}])
        self.tmp = tempfile.mkdtemp(prefix="at-export-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._app.__exit__(None, None, None)

    def export(self, **payload):
        return service.export_save(self.ctx, dict({"session_id": self.game.sid}, **payload))

    def importing(self, **payload):
        return service.import_save(self.ctx, dict({"request_id": self.game.ids()}, **payload))

    def rejected(self, code, **payload):
        before = counts(self.ctx)
        with self.assertRaises(AppError) as caught:
            self.importing(**payload)
        self.assertEqual(caught.exception.code, code, caught.exception.details[:3])
        self.assertEqual(counts(self.ctx), before)
        return caught.exception

    def test_export_then_import_is_the_same_game_in_a_new_session(self):
        out = self.export()
        self.assertTrue(out["path"].startswith(os.path.join(self.ctx.data_dir, "exports")))
        with open(out["path"], encoding="utf-8") as handle:
            doc = json.load(handle)
        self.assertEqual((doc["format"], doc["schema_version"], doc["checksum"]), ("adult-tension-save", STATE_SCHEMA_VERSION, out["checksum"]))
        done = self.importing(path=out["path"], slot="导入的")
        self.assertNotEqual(done["session_id"], self.game.sid)
        self.assertEqual(done["receipt"], "已导入「港口夜班」·第 2 回合")
        original, copy = self.game.state(), self.game.state(done["session_id"])
        self.assertEqual(SS.digest(copy), SS.digest(original))
        self.assertEqual(copy["undo_floor"], copy["turn"])
        self.assertEqual(done["slot"], {"name": "导入的", "version": 1})
        self.game.turn([act(self.game.npc())], sid=done["session_id"])  # playable
        again = self.importing(data=doc)  # pasted JSON works the same
        self.assertEqual(SS.digest(self.game.state(again["session_id"])), SS.digest(original))

    def test_a_slot_can_be_exported(self):
        self.game.save("出口")
        out = service.export_save(self.ctx, {"slot": "出口"})
        with open(out["path"], encoding="utf-8") as handle:
            doc = json.load(handle)
        self.assertEqual(doc["source"]["kind"], "slot")
        self.assertEqual(transfer.checksum(doc), doc["checksum"])
        self.assertEqual(len(doc["session"]["state"]["facts"]), repo.count_facts(self.ctx.db(), self.game.sid))

    def test_tampered_truncated_incomplete_and_newer_files_are_refused(self):
        out = self.export()
        with open(out["path"], "rb") as handle:
            raw = handle.read()
        doc = json.loads(raw.decode("utf-8"))
        tampered = os.path.join(self.tmp, "tampered.json")
        with open(tampered, "wb") as handle:
            handle.write(raw.replace("港口夜班".encode("utf-8"), "港口日班".encode("utf-8"), 1))
        err = self.rejected("INVALID_INPUT", path=tampered)
        self.assertEqual(err.details[0]["path"], "$.checksum")
        truncated = os.path.join(self.tmp, "truncated.json")
        with open(truncated, "wb") as handle:
            handle.write(raw[: len(raw) // 2])
        self.rejected("INVALID_INPUT", path=truncated)
        # a missing field, with a checksum recomputed to match: the full check finds it
        missing = json.loads(json.dumps(doc))
        del missing["session"]["state"]["clock"]
        missing["checksum"] = transfer.checksum(missing)
        err = self.rejected("INVALID_INPUT", data=missing)
        self.assertIn("$.session.state.clock", [d["path"] for d in err.details])
        underage = json.loads(json.dumps(doc))
        npc = next(c for c in underage["session"]["state"]["characters"] if c != "player")
        underage["session"]["state"]["characters"][npc]["age"] = 16
        underage["checksum"] = transfer.checksum(underage)
        self.rejected("SAFETY_BLOCK", data=underage)
        newer = json.loads(json.dumps(doc))
        newer["schema_version"] = STATE_SCHEMA_VERSION + 1
        newer["checksum"] = transfer.checksum(newer)
        err = self.rejected("UNSUPPORTED_VERSION", data=newer)
        self.assertIn("升级 Skill", err.details[0]["hint"])
        unknown = json.loads(json.dumps(doc))
        unknown["session"]["state"]["characters"][npc]["secret_flag"] = True
        unknown["checksum"] = transfer.checksum(unknown)
        err = self.rejected("INVALID_INPUT", data=unknown)
        self.assertIn("$.session.state.characters.%s.secret_flag" % npc, [d["path"] for d in err.details])
        broken_world = json.loads(json.dumps(doc))
        broken_world["session"]["content"]["world"]["locations"] = broken_world["session"]["content"]["world"]["locations"][:1]
        broken_world["checksum"] = transfer.checksum(broken_world)
        self.rejected("CONTENT_ERROR", data=broken_world)
        self.rejected("INVALID_INPUT", path=os.path.join(self.tmp, "nope.json"))

    def test_an_older_export_is_backed_up_then_upgraded(self):
        conn = sqlite3.connect("file:%s?immutable=1" % V1_FIXTURE.replace("\\", "/"), uri=True)
        try:
            state_blob, content_blob, archive_blob = conn.execute("SELECT state, content, archive FROM slots").fetchone()
        finally:
            conn.close()
        state = json.loads(zlib.decompress(state_blob))
        self.assertEqual(state["schema_version"], 1)
        doc = {
            "format": "adult-tension-save",
            "schema_version": 1,
            "content_version": state["content_version"],
            "rng_version": state["rng_version"],
            "skill_version": "0.1.0",
            "exported_at": "2026-09-01T00:00:00+08:00",
            "source": {"kind": "slot", "name": "旧版本的存档", "version": 1},
            "session": {"state": state, "content": json.loads(zlib.decompress(content_blob)), "archive": json.loads(zlib.decompress(archive_blob))},
        }
        doc["checksum"] = transfer.checksum(doc)
        done = self.importing(data=doc)
        self.assertEqual(done["upgraded_from"], 1)
        self.assertTrue(os.path.isfile(done["backup"]))
        self.assertEqual(self.game.state(done["session_id"])["schema_version"], STATE_SCHEMA_VERSION)
        npc = next(c for c in self.game.state(done["session_id"])["scene"]["present"] if c != "player")
        self.game.turn([act(npc)], sid=done["session_id"])

    def test_export_paths(self):
        for bad in ("relative.json", os.path.join(self.tmp, "..", "x.json"), os.path.join(self.tmp, "x.txt"), os.path.join(SKILL_ROOT, "x.json"), os.path.join(self.tmp, "no-such-dir", "x.json")):
            with self.assertRaises(AppError, msg=bad) as caught:
                self.export(path=bad)
            self.assertEqual(caught.exception.code, "INVALID_INPUT", bad)
        target = os.path.join(self.tmp, "我的存档.json")
        self.assertEqual(self.export(path=target)["path"], os.path.normpath(target))
        with self.assertRaises(AppError) as caught:
            self.export(path=target)
        self.assertIn("已存在", caught.exception.message)
        self.export(path=target, overwrite=True)
        self.assertFalse([n for n in os.listdir(self.tmp) if ".tmp-" in n])
        with self.assertRaises(AppError):
            service.export_save(self.ctx, {"session_id": self.game.sid, "slot": "x"})

    def test_import_into_an_existing_slot_name_needs_overwrite(self):
        self.game.save("占用")
        out = self.export()
        with self.assertRaises(AppError) as caught:
            self.importing(path=out["path"], slot="占用")
        self.assertEqual((caught.exception.code, caught.exception.extra["reason"]), ("SLOT_CONFLICT", "exists"))
        done = self.importing(path=out["path"], slot="占用", overwrite=True)
        self.assertEqual(done["slot"]["version"], 2)


if __name__ == "__main__":
    unittest.main()
