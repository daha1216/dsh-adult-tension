"""The single write path: transactions, idempotency, revisions (ACCEPTANCE.md 2)."""

import unittest

import _bootstrap  # noqa: F401
from adult_tension.application import service
from adult_tension.errors import AppError
from adult_tension.persistence import repo
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
        with app() as ctx:
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": "req_draft_1", "mode": "daily"})
            self.assertEqual(caught.exception.code, "NO_MATCH")
            self.assertEqual(service.list_worlds(ctx, {})["worlds"], [])
            self.assertEqual(len(service.list_worlds(ctx, {"include_drafts": True})["worlds"]), 1)

    def test_random_openings_avoid_recent_signatures(self):
        with app() as ctx:
            ids = Ids()
            signatures = [service.new_game(ctx, {"request_id": ids(), "mode": "daily", "include_drafts": True})["opening"]["signature"] for _ in range(10)]
            self.assertEqual(len(set(signatures)), 10)


if __name__ == "__main__":
    unittest.main()
