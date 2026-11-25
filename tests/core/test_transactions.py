"""The single write path: transactions, idempotency, revisions (ACCEPTANCE.md 2)."""

import json
import os
import time
import unittest

import _bootstrap  # noqa: F401
from adult_tension import DB_SCHEMA_VERSION, paths
from adult_tension.application import service
from adult_tension.application.context import Context
from adult_tension.domain.state import digest as state_digest_of
from adult_tension.errors import AppError
from adult_tension.persistence import repo
from helpers.cli import clean_env
from helpers.domain import STORE
from helpers.fs import copy_skill, temp_dir
from helpers.service import Ids, app, open_game, record, session, table_counts


def continue_turn(npc, text="看了一眼窗外", **extra):
    turn = {
        "action_mode": "continue",
        "player_input": "继续",
        "operations": [{"op": "npc_action", "npc_id": npc, "action": text}],
        "content_tags": [],
        "summary": "对方看了一眼窗外。",
        "open_action": "对方的目光停在窗上",
    }
    turn.update(extra)
    return turn


def continue_commit(state, npc, request_id, revision, text="看了一眼窗外"):
    return record(state["session_id"], request_id, revision, continue_turn(npc, text))


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
        flat = dict(continue_turn(self.npc), session_id=self.sid, request_id=self.ids(), expected_revision=1)
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, flat)  # one form only: a record
        self.assertIn("$.turns", [d["path"] for d in caught.exception.details])
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

    def record(self, request_id, revision, turns):
        return record(self.sid, request_id, revision, *turns)

    def item(self, npc=None, text="看了一眼窗外", **extra):
        return continue_turn(npc or self.npc, text, **extra)

    def test_a_record_holds_several_turns_in_one_transaction(self):
        revision, turn, _, _ = self.snapshot()
        texts = ("看了一眼窗外", "给自己倒了杯水", "把椅子往里推了推")
        out = service.commit_turn(self.ctx, self.record(self.ids(), revision, [self.item(text=t) for t in texts]))
        self.assertEqual(out["turn"], turn + 3)
        self.assertEqual([t["turn"] for t in out["turns"]], [turn + 1, turn + 2, turn + 3])
        self.assertTrue(all(t["applied"][0]["op"] == "npc_action" for t in out["turns"]))
        self.assertEqual(out["context"]["depth"], "full")
        info = session(self.ctx, self.sid)
        self.assertEqual((info["revision"], info["turn"]), (out["revision"], turn + 3))
        self.assertEqual(info["state"]["memory"]["turns"][-1]["summary"], "对方看了一眼窗外。")
        self.assertEqual(info["turns_since_save"], 3)
        # Each recorded turn keeps its own undo point.
        undone = service.undo_turn(self.ctx, {"session_id": self.sid, "request_id": self.ids(), "expected_revision": out["revision"]})
        self.assertEqual(undone["turn"], turn + 2)

    def test_requests_are_set_when_a_record_ends_and_paid_by_the_next_one(self):
        revision, turn, _, _ = self.snapshot()
        overnight = self.item()
        overnight["operations"].insert(0, {"op": "advance_time", "until": "next_morning"})
        # The day is crossed by the first turn; the turns after it were written
        # without seeing the request, so nothing is asked of them.
        out = service.commit_turn(self.ctx, self.record(self.ids(), revision, [overnight, self.item(), self.item(text="伸了个懒腰")]))
        self.assertEqual(out["turn"], turn + 3)
        self.assertTrue(session(self.ctx, self.sid)["state"]["requests"]["chapter_summary"])
        # Undoing the last turn leaves the game as a record of the first two would have.
        undone = service.undo_turn(self.ctx, {"session_id": self.sid, "request_id": self.ids(), "expected_revision": out["revision"]})
        self.assertTrue(session(self.ctx, self.sid)["state"]["requests"]["chapter_summary"])
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, self.record(self.ids(), undone["revision"], [self.item()]))
        self.assertEqual(caught.exception.details[0]["path"], "$.turns[0].chapter_summary")
        paid = service.commit_turn(self.ctx, self.record(self.ids(), undone["revision"], [self.item(chapter_summary="一夜过去，几个人各自收拾。")]))
        self.assertEqual(paid["turns"][0]["chapter"]["to_turn"], turn + 2)
        self.assertFalse(session(self.ctx, self.sid)["state"]["requests"]["chapter_summary"])
        # A later turn never carries one: the engine had asked for nothing when it was written.
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, self.record(self.ids(), paid["revision"], [self.item(), self.item(chapter_summary="写在第二项的章节。")]))
        self.assertEqual([d["path"] for d in caught.exception.details], ["$.turns[1].chapter_summary"])

    def test_a_rejected_turn_changes_nothing_and_says_which(self):
        before = self.snapshot()
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, self.record(self.ids(), before[0], [self.item(), self.item(npc="nobody")]))
        self.assertTrue(caught.exception.message.startswith("第 2 项"))
        self.assertTrue(all(d["path"].startswith("$.turns[1].") for d in caught.exception.details))
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, self.record(self.ids(), before[0], [self.item(), self.item(replaces_turn=before[1])]))
        self.assertEqual([d["path"] for d in caught.exception.details], ["$.turns[1].replaces_turn"])
        with self.assertRaises(AppError):
            service.commit_turn(self.ctx, self.record(self.ids(), before[0], [self.item()] * 13))
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, self.record(self.ids(), before[0], []))
        self.assertEqual([d["path"] for d in caught.exception.details], ["$.turns"])
        self.assertEqual(self.snapshot(), before)

    def test_a_record_replays_without_advancing(self):
        revision, turn, _, _ = self.snapshot()
        payload = self.record(self.ids(), revision, [self.item(), self.item(text="给自己倒了杯水"), self.item(text="伸了个懒腰")])
        first = service.commit_turn(self.ctx, payload)
        after = self.snapshot()
        second = service.commit_turn(self.ctx, payload)
        self.assertTrue(second["replayed"])
        self.assertEqual(second["turns"], first["turns"])
        self.assertEqual(after[1], turn + 3)
        self.assertEqual(self.snapshot(), after)

    def test_an_outcome_the_engine_decides_ends_the_record(self):
        before = self.snapshot()
        roll = {"op": "roll", "purpose": "对方是否注意到", "probability": 0.5,
                "on_success": [{"op": "npc_action", "npc_id": self.npc, "action": "注意到了"}], "on_failure": []}
        rolled = self.item()
        rolled["operations"].insert(0, roll)
        # The prose of a later turn would have been written before the roll was cast.
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, self.record(self.ids(), before[0], [rolled, self.item()]))
        self.assertEqual([d["path"] for d in caught.exception.details], ["$.turns[0]"])
        self.assertEqual(self.snapshot(), before)
        out = service.commit_turn(self.ctx, self.record(self.ids(), before[0], [self.item(), rolled]))
        self.assertEqual(out["turn"], before[1] + 2)
        # An event coming due is the same: it can only fall in the last turn.
        promise = self.item()
        promise["operations"].insert(0, {"op": "event_create", "kind": "promise", "title": "有人来敲门", "in_minutes": 10,
                                         "participants": [self.npc], "dedupe_key": "door.knock"})
        out = service.commit_turn(self.ctx, self.record(self.ids(), out["revision"], [promise]))
        waited = self.item()
        waited["operations"].insert(0, {"op": "advance_time", "minutes": 30})
        with self.assertRaises(AppError) as caught:
            service.commit_turn(self.ctx, self.record(self.ids(), out["revision"], [waited, self.item()]))
        self.assertEqual([d["path"] for d in caught.exception.details], ["$.turns[0]"])
        due = service.commit_turn(self.ctx, self.record(self.ids(), out["revision"], [waited]))
        self.assertTrue(due["turns"][0]["resolved_events"])

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
            # A new conversation that loads gets the commit template for the new session;
            # one that resumes ("继续上次") gets it with the full context.
            self.assertEqual(loaded["commit_template"]["session_id"], loaded["session_id"])
            resumed = service.get_context(ctx, {"session_id": loaded["session_id"], "depth": "full"})
            self.assertEqual(resumed["commit_template"], loaded["commit_template"])
            self.assertNotIn("commit_template", service.get_context(ctx, {"session_id": loaded["session_id"]}))
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
            self.assertEqual(first["receipt"], "已记下：不会出现怀孕")
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

    def test_style_preferences_change_how_it_is_written_not_the_game(self):
        # PRODUCT_SPEC 4.4: pace and explicitness only shape the writing.
        with app() as ctx:
            ids = Ids()
            sid = open_game(ctx, ids, mode="daily", seed=12, preferences={"pace": "slow"})["session_id"]
            shown = service.get_context(ctx, {"session_id": sid})["context"]["preferences"]
            self.assertEqual(shown["pace"], "slow")
            self.assertNotIn("explicitness", shown)  # absent means standard
            before = session(ctx, sid)["state"]
            changed = service.set_preferences(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 1, "pace": "direct", "explicitness": "explicit"})
            self.assertEqual(changed["receipt"], "节奏：直接；尺度：直白")
            self.assertEqual((changed["preferences"]["pace"], changed["preferences"]["explicitness"]), ("direct", "explicit"))
            self.assertEqual((changed["revision"], changed["turn"]), (2, 1))
            self.assertEqual((changed["context"]["preferences"]["pace"], changed["context"]["preferences"]["explicitness"]), ("direct", "explicit"))
            after = session(ctx, sid)["state"]
            for key in set(before) - {"preferences", "revision", "requests"}:
                self.assertEqual(after[key], before[key], key)
            self.assertEqual({k: v for k, v in after["preferences"].items() if k not in ("pace", "explicitness")}, {k: v for k, v in before["preferences"].items() if k not in ("pace", "explicitness")})
            settings = [s for s in service.status(ctx, {"session_id": sid, "level": "detail"})["sections"] if s["title"] == "设置"][0]["items"]
            self.assertIn("节奏：直接", settings)
            self.assertIn("尺度：直白", settings)
            with self.assertRaises(AppError) as caught:
                service.set_preferences(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 2, "pace": "fast"})
            self.assertEqual(caught.exception.details[0]["path"], "$.pace")
            self.assertEqual(session(ctx, sid)["revision"], 2)

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

    def test_unknown_excluded_tags_are_rejected_with_the_tag_list(self):
        # A misspelt tag excludes nothing; the player's "不要 X" must not fail silently.
        with app() as ctx:
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": "req_badtag_1", "mode": "daily", "excludes": {"content_tags": ["workplace", "office_job"]}})
            err = caught.exception
            self.assertEqual(err.code, "INVALID_INPUT")
            self.assertEqual([d["path"] for d in err.details], ["$.excludes.content_tags[1]"])
            for tag in STORE.tags()["tags"]:
                if tag["id"] != "custom":
                    self.assertIn("%s（%s）" % (tag["id"], tag["label"]), err.details[0]["hint"])
            with self.assertRaises(AppError):
                service.new_game(ctx, {"request_id": "req_badtag_2", "mode": "daily", "excludes": {"content_tags": ["custom"]}})
            opened = service.new_game(ctx, {"request_id": "req_badtag_3", "mode": "daily", "excludes": {"content_tags": ["workplace"]}})
            world_id = opened["opening"]["signature"].split("|")[0]
            entry = next(w for w in STORE.index()["worlds"] if w["id"] == world_id)
            self.assertNotIn("workplace", entry["content_tags"])

    def test_starting_or_loading_prunes_input_files_older_than_a_day(self):
        # Input files carry what the player said; nothing reads them after their call.
        with app() as ctx:
            folder = paths.inputs_dir(ctx.data_dir)
            os.makedirs(os.path.join(folder, "kept_dir.json"), exist_ok=True)
            day_old = time.time() - paths.INPUT_KEEP_SECONDS - 60

            def put(name, old):
                path = os.path.join(folder, name)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("{}")
                if old:
                    os.utime(path, (day_old, day_old))

            put("old_turn.json", True)
            put("fresh_turn.json", False)
            put("old_notes.txt", True)
            os.utime(os.path.join(folder, "kept_dir.json"), (day_old, day_old))
            ids = Ids()
            sid = open_game(ctx, ids)["session_id"]
            self.assertEqual(sorted(os.listdir(folder)), ["fresh_turn.json", "kept_dir.json", "old_notes.txt"])
            service.save_slot(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": 1, "name": "清理"})
            put("old_load.json", True)
            service.load_slot(ctx, {"request_id": ids(), "name": "清理"})
            self.assertNotIn("old_load.json", os.listdir(folder))
            self.assertIn("fresh_turn.json", os.listdir(folder))

    def test_a_named_world_opens_from_the_players_words(self):
        def world_of(opened):
            return opened["opening"]["signature"].split("|")[0]

        with app() as ctx:
            ids = Ids()
            for query, world_id in (
                ("港口夜班", "harbor_night_shift"),  # the title
                ("《港口夜班》那个世界", "harbor_night_shift"),  # the title inside the player's words
                ("凡尔赛", "versailles_corset_wardrobe_secret"),  # part of one title
                ("harbor_night_shift", "harbor_night_shift"),  # the ID
                ("秋雨录大理寺", "chang_an_rainy_dali_temple_inquest"),  # pieces of one title, clearly ahead
            ):
                opened = service.new_game(ctx, {"request_id": ids(), "mode": "daily", "world_query": query})
                self.assertEqual(world_of(opened), world_id, query)
            # The resolved world is what gets recorded: "重开 N 号" opens it again.
            first = service.new_game(ctx, {"request_id": ids(), "mode": "pressure", "seed": 5150, "world_query": "凡尔赛"})
            again = service.new_game(ctx, {"request_id": ids(), "seed": 5150, "replay": True})
            self.assertEqual(again["opening"]["signature"], first["opening"]["signature"])

    def test_a_world_query_never_picks_for_the_player(self):
        with app() as ctx:
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": "req_query_00001", "mode": "daily", "world_query": "雪山"})
            err = caught.exception
            self.assertEqual((err.code, err.details[0]["path"]), ("NO_MATCH", "$.world_query"))
            self.assertEqual({c["world_id"] for c in err.extra["candidates"]}, {"alpine_sanctuary_dagger_rescue", "snow_train_conductor_cliff_peril"})
            self.assertTrue(all(c["title"] and c["summary"] for c in err.extra["candidates"]))
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": "req_query_00002", "mode": "daily", "world_query": "修仙"})
            self.assertEqual((caught.exception.code, caught.exception.details[0]["path"]), ("NOT_FOUND", "$.world_query"))
            for extra in ({"locks": {"world_id": "harbor_night_shift"}}, {"replay": True, "seed": 3}):
                with self.assertRaises(AppError) as caught:
                    service.new_game(ctx, dict({"request_id": "req_query_00003", "mode": "daily", "world_query": "港口"}, **extra))
                self.assertEqual((caught.exception.code, caught.exception.details[-1]["path"]), ("INVALID_INPUT", "$.world_query"))

    def test_the_world_list_gives_one_line_each_and_answers_a_theme(self):
        released = {w["id"]: w for w in STORE.index()["worlds"] if w["status"] == "released"}
        with app() as ctx:
            listed = service.list_worlds(ctx, {})
            self.assertEqual((listed["total"], len(listed["worlds"])), (len(released), len(released)))
            for item in listed["worlds"]:
                self.assertEqual(set(item), {"id", "title", "modes", "summary"})
                # one line: the summary's first sentence, whole
                self.assertTrue(released[item["id"]]["summary"].startswith(item["summary"]), item["id"])
                self.assertIn(item["summary"].rstrip("”’」』）)")[-1], "。！？!?", item["id"])
            self.assertLess(sum(len(w["summary"]) for w in listed["worlds"]) * 2, sum(len(w["summary"]) for w in released.values()))
            # a theme lists only the worlds it matches, the named one first
            harbor = service.list_worlds(ctx, {"query": "港口"})
            self.assertTrue(0 < len(harbor["worlds"]) <= min(harbor["matched"], 20) and harbor["matched"] < harbor["total"])
            for item in harbor["worlds"]:
                entry = released[item["id"]]
                self.assertIn("港口", entry["title"] + entry["era"] + entry["region"] + entry["summary"], item["id"])
            self.assertEqual(service.list_worlds(ctx, {"query": "港口夜班"})["worlds"][0]["id"], "harbor_night_shift")
            none = service.list_worlds(ctx, {"query": "修仙"})
            self.assertEqual((none["worlds"], none["matched"]), ([], 0))
            self.assertIn("自定义世界", none["hint"])
            # under the development switch each world says whether it is released
            self.assertTrue(all("status" in w for w in service.list_worlds(ctx, {"include_drafts": True})["worlds"]))

    def test_the_world_list_browses_by_content_tag(self):
        released = {w["id"]: w for w in STORE.index()["worlds"] if w["status"] == "released"}
        labels = {t["id"]: t["label"] for t in STORE.tags()["tags"]}
        with app() as ctx:
            listed = service.list_worlds(ctx, {})
            counts = {t["id"]: t["count"] for t in listed["tag_counts"]}
            self.assertEqual(counts["supernatural"], sum("supernatural" in w["content_tags"] for w in released.values()))
            self.assertEqual([t["count"] for t in listed["tag_counts"]], sorted(counts.values(), reverse=True))
            self.assertTrue(all(t["label"] == labels[t["id"]] for t in listed["tag_counts"]))
            # with: every listed world carries all the tags
            uncanny = service.list_worlds(ctx, {"tags": ["supernatural"]})
            self.assertEqual(uncanny["matched"], counts["supernatural"])
            self.assertEqual(len(uncanny["worlds"]), counts["supernatural"])
            self.assertTrue(all("supernatural" in released[w["id"]]["content_tags"] for w in uncanny["worlds"]))
            self.assertEqual({t["id"]: t["count"] for t in uncanny["tag_counts"]}["supernatural"], counts["supernatural"])
            # without: none of the listed worlds carries any of them
            calm = service.list_worlds(ctx, {"exclude_tags": ["disaster", "violence"]})
            self.assertEqual(calm["matched"], sum(not {"disaster", "violence"} & set(w["content_tags"]) for w in released.values()))
            self.assertTrue(all(not {"disaster", "violence"} & set(released[w["id"]]["content_tags"]) for w in calm["worlds"]))
            self.assertNotIn("disaster", {t["id"] for t in calm["tag_counts"]})
            # tags narrow first, then the query ranks what is left
            both = service.list_worlds(ctx, {"query": "港口", "exclude_tags": ["disaster"]})
            self.assertTrue(all("disaster" not in released[w["id"]]["content_tags"] for w in both["worlds"]))
            self.assertLessEqual(both["matched"], service.list_worlds(ctx, {"query": "港口"})["matched"])
            nothing = service.list_worlds(ctx, {"tags": ["supernatural", "infidelity", "gambling"]})
            if not nothing["worlds"]:
                self.assertEqual(nothing["matched"], 0)
                self.assertIn("标签", nothing["hint"])
            # an unknown tag would silently filter nothing: refused with the list
            with self.assertRaises(AppError) as caught:
                service.list_worlds(ctx, {"tags": ["ghosts"], "exclude_tags": ["supernatural", "nope"]})
            self.assertEqual([d["path"] for d in caught.exception.details], ["$.tags[0]", "$.exclude_tags[1]"])
            self.assertIn("supernatural（超自然）", caught.exception.details[0]["hint"])

    def test_the_play_guide_fits_where_the_player_is(self):
        from adult_tension.application import guide

        with app() as ctx:
            ids = Ids()
            before = guide.run(ctx, {})
            self.assertEqual(before["stage"], "start")
            self.assertTrue(before["text"].startswith("怎么玩\n"))
            self.assertIn("世界列表", before["text"])
            self.assertNotIn("继续上次", before["text"])
            # plain words: none of the engine's own terms reach a new player
            for word in ("NPC", "回合", "session", "commit", "seed", "{"):
                self.assertNotIn(word, before["text"])
            # the first game on this machine points at the guide, later ones do not
            first = open_game(ctx, ids, mode="daily", seed=31)
            self.assertEqual(first["opening"]["tip"], service.FIRST_GAME_TIP)
            self.assertNotIn("tip", open_game(ctx, ids, mode="daily", seed=32)["opening"])
            self.assertIn("继续上次", guide.run(ctx, {})["text"])
            playing = guide.run(ctx, {"session_id": first["session_id"]})
            self.assertEqual(playing["stage"], "playing")
            self.assertIn("《%s》" % first["context"]["world"]["title"], playing["text"])
            for word in ("暂停", "换个场景", "边界", "存档", "撤销", "继续", "帮助"):
                self.assertIn(word, playing["text"])
            self.assertEqual(playing["text"], "\n".join(["怎么玩", ""] + playing["lines"]))
            with self.assertRaises(AppError) as caught:
                guide.run(ctx, {"session_id": "s_nothere"})
            self.assertEqual(caught.exception.code, "NOT_FOUND")
            with self.assertRaises(AppError) as caught:
                guide.run(ctx, {"level": "full"})
            self.assertEqual(caught.exception.code, "INVALID_INPUT")

    def test_random_openings_take_turns_with_worlds_that_are_not_disasters(self):
        # Most worlds trap two people in a disaster: one random opening after
        # another should not all be one.
        with app() as ctx:
            ids = Ids()
            disaster = {w["id"] for w in ctx.content().index()["worlds"] if "disaster" in w["content_tags"]}
            self.assertGreater(len(disaster), len(ctx.content().index()["worlds"]) / 2)
            for _ in range(16):
                service.new_game(ctx, {"request_id": ids(), "mode": "daily"})
            flags = [h["world_id"] in disaster for h in reversed(repo.opening_history(ctx.db(), 16))]
            self.assertLessEqual(sum(1 for a, b in zip(flags, flags[1:]) if a and b), 2, flags)
            self.assertTrue(any(flags), flags)

    def test_replay_restores_the_recorded_conditions(self):
        with app() as ctx:
            ids = Ids()
            first = open_game(ctx, ids, mode="pressure", seed=4242, npc_gender_preference="female_only", excludes={"content_tags": ["crime"]})
            again = service.new_game(ctx, {"request_id": ids(), "seed": 4242, "replay": True, "include_drafts": True})
            self.assertTrue(again["conditions_restored"])
            self.assertEqual(again["opening"]["signature"], first["opening"]["signature"])
            self.assertFalse(again["replay_changed"])
            self.assertNotIn("内容已更新", again["opening"]["footer"])
            # content updated since: the same seed opens differently, and the footer says so
            conn = ctx.db()
            with conn:
                conn.execute("UPDATE opening_history SET signature = 'before the update' WHERE seed = 4242")
            changed = service.new_game(ctx, {"request_id": ids(), "seed": 4242, "replay": True, "include_drafts": True})
            self.assertTrue(changed["replay_changed"])
            self.assertTrue(changed["opening"]["footer"].endswith("（内容已更新，和之前的 4242 号开局不同）"))

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
                self.assertEqual(len(listed), 211)
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


class RuntimeAppFixesTest(unittest.TestCase):
    def test_auto_slot_name_sanitizes_and_truncates_any_world_title(self):
        from helpers.cli import REPO_ROOT

        long_title = "甲乙丙丁戊己庚辛壬癸" * 4
        for title, turn in (
            (long_title, 1),
            (long_title, 1234),
            ('东京:雨夜/秘密*"<>|?\x07', 3),
            ("CON.夜班", 2),
            (":::/???", 1),
        ):
            name = service._auto_slot_name(title, turn)
            self.assertLessEqual(len(name), 40, (title, name))
            self.assertEqual(service.normalize_slot_name(name), name)
            self.assertTrue(name.endswith("-第%d回合" % turn), name)
        with open(os.path.join(REPO_ROOT, "content-src", "examples", "custom_world.json"), encoding="utf-8") as handle:
            world = json.load(handle)
        world["title"] = "雨夜:民宿/长标题" + "一二三四五六七八九十" * 3
        self.assertLessEqual(len(world["title"]), 40)
        with app() as ctx:
            ids = Ids()
            opened = service.new_game(ctx, {"request_id": ids(), "mode": "daily", "seed": 7, "custom_world": world})
            saved = service.save_slot(ctx, {"session_id": opened["session_id"], "request_id": ids(), "expected_revision": opened["revision"]})
            self.assertTrue(saved["auto_named"])
            self.assertLessEqual(len(saved["slot"]["name"]), 40)
            self.assertTrue(saved["slot"]["name"].endswith("-第1回合"))

    def test_status_detail_shows_one_way_edge_preferences_and_voice_and_hides_unknown_leverage(self):
        from adult_tension.domain.text import full_name

        with app() as ctx:
            ids = Ids()
            opened = open_game(ctx, ids, mode="daily", seed=31)
            sid = opened["session_id"]
            info = session(ctx, sid)
            state, world = info["state"], info["content"]["world"]
            npc = next(c for c in state["scene"]["present"] if c != "player" and state["characters"][c]["tier"] == "major")
            npc_name = state["characters"][npc]["name"]
            taken = {c.get("family") for c in state["characters"].values()}
            family = next(f for f in world["name_pools"]["family"] if f not in taken)
            away = next(loc["id"] for loc in world["locations"] if loc["id"] != state["scene"]["location_id"])
            guest_name = full_name(world["name_pools"], family, "客安")
            intro = continue_turn(
                npc,
                operations=[
                    {
                        "op": "introduce_character",
                        "id": "one_way_guest",
                        "name": guest_name,
                        "tier": "supporting",
                        "age": 31,
                        "gender": "female",
                        "adult_context": "码头常来的成年货运代理",
                        "public_role": "货运代理",
                        "present": True,
                        "appearance": "穿深色风衣",
                        "identity": {
                            "authority": "负责货单交接",
                            "resources": ["货单副本"],
                            "limits": ["不能进调度室"],
                            "obligations": ["按点验货"],
                            "exposure_risk": "怕货单对不上",
                            "hidden_mismatch": "表面客气，实则计较得失",
                        },
                        "decision": {"core_value": "稳妥", "current_goal": "尽快核完货单"},
                    },
                    {"op": "relationship", "from": "one_way_guest", "to": "player", "trust_delta": 1, "reason": "你递了手电"},
                    {"op": "exit_scene", "character_id": "one_way_guest", "to_location_id": away},
                    {"op": "add_fact", "key": "secret.hidden_leverage", "text": "暗中握着你的违章记录", "truth": True, "known_by": [npc], "visibility": "private", "origin": "observed"},
                ],
            )
            r1 = service.commit_turn(ctx, record(sid, ids(), info["revision"], intro))
            hidden_fid = next(a["fact_id"] for a in r1["turns"][0]["applied"] if a["op"] == "add_fact")
            r2 = service.commit_turn(
                ctx,
                record(
                    sid,
                    ids(),
                    r1["revision"],
                    continue_turn(
                        npc,
                        operations=[{"op": "leverage_set", "holder": npc, "subject": "player", "basis_fact_id": hidden_fid, "origin": "私下查档"}],
                    ),
                ),
            )
            # Unknown leverage against the player must not spoil in brief status.
            brief_hidden = service.status(ctx, {"session_id": sid, "level": "brief"})
            self.assertEqual(len(brief_hidden["lines"]), 6)
            self.assertNotIn("手里有你的把柄", brief_hidden["lines"][3])
            # Once revealed to the player, the leverage appears in brief status.
            r3 = service.commit_turn(
                ctx,
                record(
                    sid,
                    ids(),
                    r2["revision"],
                    continue_turn(npc, operations=[{"op": "reveal_fact", "from": npc, "to": ["player"], "fact_id": hidden_fid}]),
                ),
            )
            brief_known = service.status(ctx, {"session_id": sid, "level": "brief"})
            self.assertIn("%s手里有你的把柄" % npc_name, brief_known["lines"][3])
            for word in ("trust", "tension", "revision", "stage", "npc_", "_id"):
                self.assertNotIn(word, "".join(brief_known["lines"]))
            # Detail status shows offstage NPC with only npc>player edge, plus preference & non-default voice.
            r4 = service.set_preferences(
                ctx,
                {
                    "session_id": sid,
                    "request_id": ids(),
                    "expected_revision": r3["revision"],
                    "npc_gender_preference": "female_only",
                    "voice": {"npc_id": npc, "voice": "inner"},
                },
            )
            self.assertEqual(r4["revision"], r3["revision"] + 1)
            detail_view = service.status(ctx, {"session_id": sid, "level": "detail"})
            by_title = {s["title"]: s["items"] for s in detail_view["sections"]}
            self.assertTrue(any(guest_name in item for item in by_title["人物"]), by_title["人物"])
            self.assertIn("配对偏好：只要女性", by_title["设置"])
            self.assertIn("角色语态：%s（里层语态）" % npc_name, by_title["设置"])

    def test_corrupted_doctor_marker_falls_back_to_full_check(self):
        from adult_tension.application import doctor
        from helpers.cli import SKILL_ROOT

        with temp_dir() as tmp:
            data_dir = os.path.join(tmp, "data")

            def run_doctor():
                ctx = Context(SKILL_ROOT, data_dir, clean_env(), {}, False)
                try:
                    return doctor.run(ctx, {})
                finally:
                    ctx.close()

            first = run_doctor()
            self.assertFalse(first["fast_path"])
            marker_file = paths.marker_path(data_dir)
            with open(marker_file, encoding="utf-8") as handle:
                valid_marker = json.load(handle)
            for corrupted in ([], "not-a-dict", dict(valid_marker, content_check=["broken"])):
                with open(marker_file, "w", encoding="utf-8") as handle:
                    json.dump(corrupted, handle, ensure_ascii=False)
                repaired = run_doctor()
                self.assertFalse(repaired["fast_path"], corrupted)
                self.assertIn(repaired["status"], ("ok", "warn"))
                ids = [c["id"] for c in repaired["checks"]]
                self.assertEqual(len(ids), len(set(ids)))
                fast = run_doctor()
                self.assertTrue(fast["fast_path"], corrupted)

    def test_world_query_exact_match_beats_substring_matches(self):
        with temp_dir() as tmp:
            skill = copy_skill(tmp)
            index_path = os.path.join(skill, "content", "index.json")
            with open(index_path, encoding="utf-8") as handle:
                index = json.load(handle)
            index["worlds"].append(
                {
                    "id": "harbor",
                    "title": "夜班",
                    "era": "当代",
                    "region": "港区",
                    "summary": "一场独立的夜班故事。",
                    "modes": ["daily"],
                    "content_tags": [],
                    "status": "released",
                }
            )
            with open(index_path, "w", encoding="utf-8") as handle:
                json.dump(index, handle, ensure_ascii=False)
            ctx = Context(skill, os.path.join(tmp, "data"), clean_env(), {}, False)
            try:
                self.assertEqual(service._match_world_query(ctx, "夜班", drafts=True), "harbor")
                self.assertEqual(service._match_world_query(ctx, "harbor", drafts=True), "harbor")
            finally:
                ctx.close()

    def test_my_world_exclusions_save_world_conflict_and_specs_errors(self):
        from adult_tension import errors as E
        from adult_tension.application import specs
        from helpers.cli import REPO_ROOT

        with app() as ctx:
            ids = Ids()
            # Mutual exclusions run before DB lookup for my_world and distinguish my_world vs custom_world.
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": ids(), "mode": "daily", "my_world": "不存在", "replay": True, "seed": 3})
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
            self.assertIn("my_world", caught.exception.details[0]["hint"])
            self.assertNotIn("custom_world", caught.exception.details[0]["hint"])
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": ids(), "mode": "daily", "my_world": "不存在", "world_query": "港口"})
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
            self.assertIn("my_world", caught.exception.details[0]["reason"])
            self.assertNotIn("custom_world", caught.exception.details[0]["reason"])
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": ids(), "mode": "daily", "my_world": "不存在", "locks": {"world_id": "harbor_night_shift"}})
            self.assertEqual((caught.exception.code, caught.exception.details[0]["path"]), ("INVALID_INPUT", "$.locks.world_id"))
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": ids(), "mode": "daily", "my_world": "不存在", "excludes": {"world_ids": ["harbor_night_shift"]}})
            self.assertEqual((caught.exception.code, caught.exception.details[0]["path"]), ("INVALID_INPUT", "$.excludes.world_ids"))
            # save-world conflict includes reason="exists".
            with open(os.path.join(REPO_ROOT, "content-src", "examples", "custom_world.json"), encoding="utf-8") as handle:
                world = json.load(handle)
            sid = service.new_game(ctx, {"request_id": ids(), "mode": "daily", "seed": 5, "custom_world": world})["session_id"]
            service.save_world(ctx, {"request_id": ids(), "session_id": sid, "name": "重名世界"})
            with self.assertRaises(AppError) as caught:
                service.save_world(ctx, {"request_id": ids(), "session_id": sid, "name": "重名世界"})
            self.assertEqual((caught.exception.code, caught.exception.extra["reason"]), ("SLOT_CONFLICT", "exists"))
            self.assertEqual(caught.exception.extra["world"]["name"], "重名世界")
        self.assertIn("自定义世界名", E.ERROR_DESCRIPTIONS[E.SLOT_CONFLICT])
        age_band_desc = specs.PLAYER.fields["age_band"].desc
        self.assertIn("SAFETY_BLOCK", age_band_desc)
        self.assertIn("INVALID_INPUT", age_band_desc)
        self.assertIn("my_world", specs.NEW_GAME.fields["world_query"].desc)
        my_world_desc = specs.NEW_GAME.fields["my_world"].desc
        for token in ("custom_world", "locks.world_id", "excludes.world_ids", "replay", "world_query"):
            self.assertIn(token, my_world_desc)

    def test_p2_verify_guide_doctor_smoke_specs_and_errors(self):
        import ast
        import subprocess
        import sys
        from unittest import mock

        from adult_tension import errors as E
        from adult_tension.application import doctor, guide, smoke, specs, verify
        from helpers.cli import SKILL_ROOT

        # 1. verify._verify_file converts OSError into CONTENT_ERROR
        with temp_dir() as tmp:
            sample = os.path.join(tmp, "unreadable.json")
            with open(sample, "w", encoding="utf-8") as handle:
                handle.write("{}")
            with mock.patch("builtins.open", side_effect=PermissionError(13, "denied")):
                with self.assertRaises(AppError) as caught:
                    verify._verify_file({"file": sample, "stats": False}, set(), [])
            self.assertEqual((caught.exception.code, caught.exception.details[0]["path"]), (E.CONTENT_ERROR, "$.file"))

        # 2. guide includes standard tier and plain Chinese save-world phrase without <>
        with app() as ctx:
            ids = Ids()
            sid = open_game(ctx, ids, mode="daily", seed=15)["session_id"]
            playing = guide.run(ctx, {"session_id": sid})
            self.assertIn("节奏 慢热 / 标准 / 直接，尺度 含蓄 / 标准 / 直白", playing["text"])
            custom = guide.run(ctx, {"topic": "custom_world"})
            self.assertIn("保存世界 名字", custom["text"])
            self.assertNotIn("<", custom["text"])
            self.assertNotIn(">", custom["text"])

        # 3. doctor formats MIN_PYTHON dynamically
        with mock.patch.object(doctor, "MIN_PYTHON", (3, 99)):
            py_res = doctor._python_check()
            self.assertEqual((py_res["status"], py_res["code"]), ("fail", E.RUNTIME_UNSUPPORTED))
            self.assertIn("3.99+", py_res["hint"])
            with mock.patch.dict(sys.modules, {"sqlite3": None}):
                sq_res = doctor._sqlite_check()
            self.assertEqual((sq_res["status"], sq_res["code"]), ("fail", E.RUNTIME_UNSUPPORTED))
            self.assertIn("3.99+", sq_res["hint"])

        # 4. smoke has zero assert statements and enforces checks even under python -O
        with open(smoke.__file__, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        self.assertEqual([n for n in ast.walk(tree) if isinstance(n, ast.Assert)], [])
        runtime_dir = os.path.join(SKILL_ROOT, "runtime")
        check_o = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "from adult_tension import errors\n"
            "from adult_tension.application import smoke\n"
            "from adult_tension.application.context import Context\n"
            "from adult_tension.domain import invariants\n"
            "orig_check = invariants.check\n"
            "invariants.check = lambda state, before_clock=None: ['broken'] if before_clock is None else orig_check(state, before_clock)\n"
            "ctx = Context(%r, None, {}, {}, False)\n"
            "try:\n"
            "    smoke.run(ctx, {'seed': 7, 'turns': 2})\n"
            "    raise SystemExit(2)\n"
            "except errors.AppError as err:\n"
            "    if err.code != errors.INTERNAL_ERROR:\n"
            "        raise SystemExit(3)\n"
            "finally:\n"
            "    ctx.close()\n"
        ) % (runtime_dir, SKILL_ROOT)
        proc = subprocess.run(
            [sys.executable, "-B", "-O", "-c", check_o],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env(PYTHONDONTWRITEBYTECODE="1"),
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))

        # 5. specs & errors P2 descriptions
        self.assertIn("二选一", specs.EXPORT_SAVE.fields["session_id"].desc)
        self.assertIn("二选一", specs.EXPORT_SAVE.fields["slot"].desc)
        self.assertIn("二选一", specs.IMPORT_SAVE.fields["path"].desc)
        self.assertIn("二选一", specs.IMPORT_SAVE.fields["data"].desc)
        self.assertIn("add", specs.SET_BOUNDARY.fields["text"].desc)
        self.assertIn("remove", specs.SET_BOUNDARY.fields["text"].desc)
        self.assertIn("remove", specs.SET_BOUNDARY.fields["boundary_id"].desc)
        self.assertIn("tools/new_world.py", specs.VERIFY_CONTENT.fields["file"].desc)
        self.assertNotIn("new-world", specs.VERIFY_CONTENT.fields["file"].desc)
        self.assertEqual(specs.PREFERENCES.fields["pace"].desc, specs.SET_PREFERENCES.fields["pace"].desc)
        self.assertEqual(specs.PREFERENCES.fields["explicitness"].desc, specs.SET_PREFERENCES.fields["explicitness"].desc)
        self.assertIn("world_query", E.ERROR_DESCRIPTIONS[E.NO_MATCH])
        self.assertIn("candidates", E.ERROR_DESCRIPTIONS[E.NO_MATCH])


if __name__ == "__main__":
    unittest.main()
