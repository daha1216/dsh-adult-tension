"""The single write path: transactions, idempotency, revisions (ACCEPTANCE.md 2)."""

import json
import os
import unittest

import _bootstrap  # noqa: F401
from adult_tension import DB_SCHEMA_VERSION
from adult_tension.application import service
from adult_tension.application.context import Context
from adult_tension.domain.state import digest as state_digest_of
from adult_tension.errors import AppError
from adult_tension.persistence import repo
from helpers.cli import clean_env
from helpers.domain import STORE
from helpers.fs import copy_skill, temp_dir
from helpers.service import Ids, app, open_game, session, table_counts


def continue_commit(state, npc, request_id, revision, text="看了一眼窗外"):
    return {
        "session_id": state["session_id"],
        "request_id": request_id,
        "expected_revision": revision,
        "action_mode": "continue",
        "player_input": "继续",
        "operations": [{"op": "npc_action", "npc_id": npc, "action": text}],
        "content_tags": [],
        "summary": "对方看了一眼窗外。",
        "open_action": "对方的目光停在窗上",
    }


class WritePathTest(unittest.TestCase):
    def setUp(self):
        self._app = app()
        self.ctx = self._app.__enter__()
        self.ids = Ids()
        opened = open_game(self.ctx, self.ids, mode="daily", seed=31)
        self.sid = opened["session_id"]
        self.state = session(self.ctx, self.sid)["state"]
        self.npc = [c for c in self.state["scene"]["present"] if c != "player"][0]

    def tearDown(self):
        self._app.__exit__(None, None, None)

    def snapshot(self):
        info = session(self.ctx, self.sid)
        return info["revision"], info["turn"], info["state"], table_counts(self.ctx, self.sid)

    def test_rejected_commit_changes_nothing(self):
        before = self.snapshot()
        bad = continue_commit(self.state, "nobody", self.ids(), 1)
        with self.assertRaises(AppError):
            service.commit_turn(self.ctx, bad)
        shape_bad = dict(continue_commit(self.state, self.npc, self.ids(), 1), surprise=1)
        with self.assertRaises(AppError):
            service.commit_turn(self.ctx, shape_bad)
        self.assertEqual(self.snapshot(), before)

    def test_replay_returns_the_same_response_without_advancing(self):
        payload = continue_commit(self.state, self.npc, self.ids(), 1)
        first = service.commit_turn(self.ctx, payload)
        after_first = self.snapshot()
        second = service.commit_turn(self.ctx, payload)
        self.assertTrue(second["replayed"])
        self.assertFalse(first["replayed"])
        self.assertEqual({k: v for k, v in second.items() if k != "replayed"}, {k: v for k, v in first.items() if k != "replayed"})
        self.assertEqual(self.snapshot(), after_first)

    def test_same_request_id_with_different_input_conflicts(self):
        rid = self.ids()
        service.commit_turn(self.ctx, continue_commit(self.state, self.npc, rid, 1))
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, continue_commit(self.state, self.npc, rid, 1, text="换了一个动作"))
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_CONFLICT")

    def test_lost_response_retry_gets_the_original_not_stale(self):
        payload = continue_commit(self.state, self.npc, self.ids(), 1)
        original = service.commit_turn(self.ctx, payload)
        # The caller never saw `original`; it retries the same request.
        retry = service.commit_turn(self.ctx, payload)
        self.assertEqual(retry["revision"], original["revision"])
        self.assertTrue(retry["replayed"])

    def test_stale_revision_includes_current_revision_and_context(self):
        service.commit_turn(self.ctx, continue_commit(self.state, self.npc, self.ids(), 1))
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, continue_commit(self.state, self.npc, self.ids(), 1))
        err = caught.exception
        self.assertEqual(err.code, "STALE_REVISION")
        self.assertEqual(err.extra["current_revision"], 2)
        self.assertEqual(err.extra["context"]["depth"], "brief")

    def test_new_game_retry_returns_the_same_session(self):
        rid = self.ids()
        a = open_game(self.ctx, lambda: rid, mode="pressure", seed=5)
        b = open_game(self.ctx, lambda: rid, mode="pressure", seed=5)
        self.assertEqual(a["session_id"], b["session_id"])
        self.assertTrue(b["replayed"])
        with self.assertRaises(AppError) as caught:
            open_game(self.ctx, lambda: rid, mode="daily", seed=5)
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_CONFLICT")

    def test_idempotency_records_are_bounded(self):
        conn = self.ctx.db()
        conn.execute("BEGIN IMMEDIATE")
        for i in range(repo.IDEMPOTENCY_KEEP + 25):
            repo.idem_put(conn, "scope_x", "rid_%06d" % i, "d", {"n": i}, "now")
        conn.execute("COMMIT")
        self.assertEqual(repo.idem_count(conn, "scope_x"), repo.IDEMPOTENCY_KEEP)
        self.assertIsNone(repo.idem_get(conn, "scope_x", "rid_000000"))
        self.assertIsNotNone(repo.idem_get(conn, "scope_x", "rid_%06d" % (repo.IDEMPOTENCY_KEEP + 24)))


class SaveLoadTest(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        with app() as ctx:
            ids = Ids()
            opened = open_game(ctx, ids, mode="pressure", seed=8)
            sid = opened["session_id"]
            state = session(ctx, sid)["state"]
            npc = [c for c in state["scene"]["present"] if c != "player"][0]
            service.commit_turn(ctx, continue_commit(state, npc, ids(), 1))
            saved = service.save_slot(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 2, "name": "港口 第一夜"})
            self.assertEqual(saved["slot"]["name"], "港口-第一夜")
            self.assertEqual(saved["receipt"], "已保存到「港口-第一夜」·第 2 回合")
            self.assertEqual(session(ctx, sid)["revision"], 2)  # saving does not change revision
            loaded = service.load_slot(ctx, {"request_id": ids(), "name": "港口-第一夜"})
            self.assertNotEqual(loaded["session_id"], sid)
            self.assertEqual(loaded["turn"], 2)
            self.assertEqual(loaded["resume"]["open_action"], "对方的目光停在窗上")
            original = session(ctx, sid)["state"]
            copy = session(ctx, loaded["session_id"])["state"]
            self.assertEqual({k: v for k, v in original.items() if k not in ("session_id", "undo_floor")}, {k: v for k, v in copy.items() if k not in ("session_id", "undo_floor")})
            slots = service.list_slots(ctx, {})["slots"]
            self.assertEqual([s["name"] for s in slots], ["港口-第一夜"])

    def test_slot_conflicts_and_overwrite(self):
        with app() as ctx:
            ids = Ids()
            a = open_game(ctx, ids, mode="daily", seed=1)["session_id"]
            b = open_game(ctx, ids, mode="daily", seed=2)["session_id"]
            service.save_slot(ctx, {"session_id": a, "request_id": ids(), "expected_revision": 1, "name": "共用"})
            with self.assertRaises(AppError) as caught:
                service.save_slot(ctx, {"session_id": b, "request_id": ids(), "expected_revision": 1, "name": "共用"})
            self.assertEqual((caught.exception.code, caught.exception.extra["reason"]), ("SLOT_CONFLICT", "exists"))
            service.save_slot(ctx, {"session_id": b, "request_id": ids(), "expected_revision": 1, "name": "共用", "overwrite": True})
            with self.assertRaises(AppError) as caught:
                service.save_slot(ctx, {"session_id": a, "request_id": ids(), "expected_revision": 1})
            self.assertEqual(caught.exception.extra["reason"], "changed_elsewhere")

    def test_bad_slot_names_are_rejected(self):
        for name in ("../etc", "a/b", "c:\\x", "CON", "nul.txt", "...", "x" * 41, "tab\tname\x01"):
            with self.assertRaises(AppError, msg=name) as caught:
                service.normalize_slot_name(name)
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
        self.assertEqual(service.normalize_slot_name("  夜班  存档 "), "夜班-存档")

    def test_quick_save_without_name_auto_names_then_reuses(self):
        with app() as ctx:
            ids = Ids()
            sid = open_game(ctx, ids, mode="daily", seed=3)["session_id"]
            first = service.save_slot(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 1})
            self.assertTrue(first["auto_named"])
            self.assertEqual(first["slot"]["name"], "港口夜班-第1回合")
            second = service.save_slot(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 1})
            self.assertEqual(second["slot"]["name"], first["slot"]["name"])
            self.assertEqual(second["slot"]["version"], 2)

    def test_load_missing_slot_lists_what_exists(self):
        with app() as ctx:
            with self.assertRaises(AppError) as caught:
                service.load_slot(ctx, {"request_id": "req_missing_1", "name": "没有这个"})
            self.assertEqual(caught.exception.code, "NOT_FOUND")


class MetaCommandTest(unittest.TestCase):
    def test_meta_commands_change_revision_not_turn_and_replay(self):
        with app() as ctx:
            ids = Ids()
            sid = open_game(ctx, ids, mode="daily", seed=12)["session_id"]
            rid = ids()
            payload = {"session_id": sid, "request_id": rid, "expected_revision": 1, "action": "add", "text": "不要涉及怀孕", "tags": ["pregnancy"]}
            first = service.set_boundary(ctx, payload)
            self.assertEqual((first["revision"], first["turn"]), (2, 1))
            self.assertEqual(first["receipt"], "已记下：不会出现涉及怀孕")
            self.assertEqual(first["context"]["safety"]["boundaries"], ["不要涉及怀孕"])
            again = service.set_boundary(ctx, payload)
            self.assertTrue(again["replayed"])
            paused = service.set_safety(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 2, "paused": True})
            self.assertEqual(paused["receipt"], "已暂停。说“继续”恢复，或说“换个场景”")
            self.assertTrue(paused["context"]["safety"]["paused"])
            prefs = service.set_preferences(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 3, "assistant": True})
            self.assertEqual(prefs["receipt"], "叙事助手：开")
            status = service.status(ctx, {"session_id": sid})
            self.assertEqual(len(status["lines"]), 6)
            self.assertIn("已暂停", status["lines"][4])
            self.assertIn("不要涉及怀孕", status["lines"][4])
            detail_view = service.status(ctx, {"session_id": sid, "level": "detail"})
            self.assertTrue(detail_view["sections"])
            debug_view = service.status(ctx, {"session_id": sid, "level": "debug"})
            debug = debug_view["debug"]
            self.assertEqual(debug["state_problems"], [])  # the full state check, invariants included
            self.assertLessEqual(debug["context_bytes"]["brief"], 6 * 1024)
            self.assertEqual(debug["digest"], state_digest_of(session(ctx, sid)["state"]))
            self.assertEqual(debug["facts"]["count"], len(session(ctx, sid)["state"]["facts"]))
            self.assertEqual(debug["storage"]["undo"]["floor"], 1)
            self.assertEqual(debug["storage"]["db_schema_version"], DB_SCHEMA_VERSION)
            json.dumps(debug_view, ensure_ascii=False)  # the whole view can be written out
            self.assertEqual(session(ctx, sid)["turn"], 1)

    def test_bad_meta_inputs(self):
        with app() as ctx:
            ids = Ids()
            sid = open_game(ctx, ids, mode="daily", seed=13)["session_id"]
            with self.assertRaises(AppError) as caught:
                service.set_boundary(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 1, "action": "add", "text": "不要X", "tags": ["nope"]})
            self.assertEqual(caught.exception.details[0]["path"], "$.tags[0]")
            with self.assertRaises(AppError):
                service.set_safety(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 1, "paused": False, "change_scene": True})
            with self.assertRaises(AppError):
                service.set_preferences(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 1})
            self.assertEqual(session(ctx, sid)["revision"], 1)


class NewGameCommandTest(unittest.TestCase):
    def test_mode_is_required_unless_replaying(self):
        with app() as ctx:
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": "req_nomode_1", "include_drafts": True})
            self.assertEqual(caught.exception.details[0]["path"], "$.mode")

    def test_replay_restores_the_recorded_conditions(self):
        with app() as ctx:
            ids = Ids()
            first = open_game(ctx, ids, mode="pressure", seed=4242, npc_gender_preference="female_only", excludes={"content_tags": ["crime"]})
            again = service.new_game(ctx, {"request_id": ids(), "seed": 4242, "replay": True, "include_drafts": True})
            self.assertTrue(again["conditions_restored"])
            self.assertEqual(again["opening"]["signature"], first["opening"]["signature"])

    def test_unreleased_worlds_need_include_drafts(self):
        # CONTENT_BIBLE 7: a world under review opens only with --include-drafts (or the
        # development switch), is not listed, and random openings never land on it
        with temp_dir() as tmp:
            skill = copy_skill(tmp)
            under_review = STORE.index()["worlds"][0]["id"]
            index_path = os.path.join(skill, "content", "index.json")
            world_path = os.path.join(skill, "content", "worlds", under_review + ".json")
            for path in (index_path, world_path):
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
                for entry in data["worlds"] if path == index_path else [data]:
                    if entry["id"] == under_review:
                        entry["status"] = "review"
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False)
            ctx = Context(skill, os.path.join(tmp, "data"), clean_env(), {}, False)
            try:
                with self.assertRaises(AppError) as caught:
                    service.new_game(ctx, {"request_id": "req_draft_1", "mode": "daily", "locks": {"world_id": under_review}})
                self.assertEqual((caught.exception.code, caught.exception.details[0]["path"]), ("NOT_FOUND", "$.locks.world_id"))
                opened = service.new_game(ctx, {"request_id": "req_draft_2", "mode": "daily", "locks": {"world_id": under_review}, "include_drafts": True})
                self.assertEqual(opened["opening"]["mode"], "daily")
                self.assertNotIn(under_review, [w["id"] for w in service.list_worlds(ctx, {})["worlds"]])
                listed = service.list_worlds(ctx, {"include_drafts": True})["worlds"]
                self.assertEqual(len(listed), len(STORE.index()["worlds"]))
                self.assertEqual(len(listed), 6)
                released = {w["id"] for w in STORE.index()["worlds"] if w["status"] == "released"} - {under_review}
                for seed in range(1, 6):
                    try:
                        world = service.new_game(ctx, {"request_id": "req_draft_r%d" % seed, "mode": "daily", "seed": seed})["context"]["world"]["title"]
                    except AppError as err:  # nothing released yet besides the one under review
                        self.assertEqual((err.code, released), ("NO_MATCH", set()))
                        continue
                    self.assertIn(world, {w["title"] for w in STORE.index()["worlds"] if w["id"] in released})
            finally:
                ctx.close()

    def test_random_openings_avoid_recent_signatures(self):
        with app() as ctx:
            ids = Ids()
            signatures = [service.new_game(ctx, {"request_id": ids(), "mode": "daily", "include_drafts": True})["opening"]["signature"] for _ in range(10)]
            self.assertEqual(len(set(signatures)), 10)


if __name__ == "__main__":
    unittest.main()
