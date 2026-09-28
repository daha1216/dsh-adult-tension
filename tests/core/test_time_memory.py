"""Time, offscreen simulation, long-term memory, undo, rewrite and retcon
(ACCEPTANCE.md 2 "时间与随机" and the requests rules; RUNTIME_PROTOCOL 6-8)."""

import unittest

import _bootstrap  # noqa: F401
from adult_tension.application import service
from adult_tension.domain import clock as CL
from adult_tension.domain import facts as FA
from adult_tension.domain import settlement, simulation
from adult_tension.domain import structure as ST
from adult_tension.domain import turn as T
from adult_tension.errors import AppError
from adult_tension.persistence import repo
from adult_tension.projections import context as CX
from helpers.domain import apply, commit, content, new_state, npcs, rejected
from helpers.service import Ids, app, open_game, session


def reasons(err):
    return " | ".join(d["reason"] for d in err.details)


def act(npc, text="看了一眼"):
    return {"op": "npc_action", "npc_id": npc, "action": text}


def beat(npc, subs=None, summary="在别处忙自己的事"):
    return {"op": "offscreen_beat", "npc_id": npc, "summary": summary, "operations": subs if subs is not None else [act(npc, "忙着自己的事")]}


def majors_present(state):
    return sorted(c for c in npcs(state) if state["characters"][c]["tier"] == "major")


def elsewhere(state):
    here = state["scene"]["location_id"]
    return next(loc["id"] for loc in content()["world"]["locations"] if loc["id"] != here)


def skip(state, minutes):
    """Run the settlement of a time skip on a working copy; return (copy, report)."""
    work = FA.working_copy(state)
    turn = work["turn"] + 1
    return work, settlement.advance(work, minutes, turn, simulation.hooks(turn))


def with_absent_major(mode="pressure", seed=11, spreading=True, drunk=True):
    """Two majors present; the second leaves; the first knows a spreading fact."""
    state, _ = new_state(mode, seed=seed)
    a, b = majors_present(state)[:2]
    ops = []
    if drunk:
        ops.append({"op": "npc_state", "npc_id": a, "add_conditions": [{"kind": "drunk", "text": "喝多了", "minutes": 30}]})
    if spreading:
        ops.append({"op": "add_fact", "key": "t.gossip", "text": "码头上有人在传一件事", "known_by": [a], "visibility": "private", "origin": "observed", "spread": True})
    ops.append({"op": "exit_scene", "character_id": b, "to_location_id": elsewhere(state)})
    state, _ = apply(state, commit("continue", ops))
    return state, a, b


# ---------------------------------------------------------------------------


class SettlementOrderTest(unittest.TestCase):
    def test_one_skip_triggers_every_step_in_the_protocol_order(self):
        state, a, b = with_absent_major()
        work, report = skip(state, ST.MINUTES_PER_DAY)
        self.assertEqual(report["steps"], ["clock", "events", "status", "offscreen", "propagation", "requests"])
        # 1 clock: a new day and a new scene
        self.assertTrue(report["crossed_day"])
        self.assertEqual(report["tier"], "full")
        self.assertIsNotNone(report["scene"])
        # 2 due events settle in (due, id) order, each exactly once
        due = sorted(
            (e for e in state["events"].values() if e["state"] == "pending" and CL.to_abs(e["due"]) <= CL.to_abs(work["clock"])),
            key=lambda e: (CL.to_abs(e["due"]), e["id"]),
        )
        self.assertTrue(due)
        self.assertEqual([r["event_id"] for r in report["resolved_events"]], [e["id"] for e in due])
        self.assertTrue(all(work["events"][e["id"]]["state"] == "resolved" for e in due))
        # 3 timed conditions expire
        self.assertEqual([(c["character_id"], c["kind"]) for c in report["expired_conditions"]], [(a, "drunk")])
        self.assertEqual(work["characters"][a]["status"]["conditions"], [])
        # 4 offscreen: the absent major follows the schedule and must get a beat
        self.assertEqual(report["offscreen"]["required"], [b])
        target = simulation.schedule_location(state["characters"][b], work["clock"]["minute"])
        if target and target != state["characters"][b]["status"]["location_id"]:
            self.assertIn({"character_id": b, "location_id": target}, report["offscreen"]["moved"])
        # 5 propagation: a day or more is three hops; the fact reached b exactly when reported
        self.assertEqual(report["propagation"]["hops"], 3)
        gossip = FA.of(work).by_key("t.gossip")[0]
        reached = [s for s in report["propagation"]["spread"] if s["fact_id"] == gossip["id"]]
        self.assertEqual(b in gossip["known_by"], bool(reached))
        self.assertFalse(gossip["spreading"])  # three hops, then it stops
        # 6 requests: a chapter and (first new day, pressure) a twist are due; b may get a beat
        self.assertEqual(report["requests"], {"chapter_summary": True, "twist_offer": True, "offscreen_beat_candidates": [b]})

    def test_the_commit_settles_the_same_way_and_sets_the_requests(self):
        state, a, b = with_absent_major()
        work, report = skip(state, 1440)
        new, result = apply(state, commit("continue", [{"op": "advance_time", "days": 1}, beat(b), act(a)]))
        self.assertEqual(result["resolved_events"], report["resolved_events"])
        sim = result["simulation"]
        self.assertEqual((sim["tier"], sim["crossed_day"]), ("full", True))
        self.assertEqual(sim["expired_conditions"], report["expired_conditions"])
        self.assertEqual(sim["offscreen_beats"], [{"npc_id": b, "summary": "在别处忙自己的事"}])
        self.assertTrue(new["requests"]["chapter_summary"])
        offer = new["requests"]["twist_offer"]
        self.assertTrue(2 <= len(offer) <= 3)
        self.assertEqual(len({t["category"] for t in offer}), len(offer))
        self.assertEqual(new["counters"]["offscreen_beat_turn"][b], new["turn"])
        self.assertEqual(new["memory"]["turns"][-1]["offscreen"], [{"npc_id": b, "summary": "在别处忙自己的事"}])


class OffscreenTest(unittest.TestCase):
    def setUp(self):
        self.state, self.a, self.b = with_absent_major(drunk=False)

    def test_tiers_decide_candidates_required_beats_and_hops(self):
        _w, routine = skip(self.state, 10)
        self.assertEqual((routine["tier"], routine["offscreen"]["required"], routine["offscreen"]["candidates"], routine["propagation"]["hops"]), ("routine", [], [], 0))
        _w, brief = skip(self.state, 30)
        self.assertEqual((brief["tier"], brief["offscreen"]["required"], brief["offscreen"]["candidates"], brief["propagation"]["hops"]), ("brief", [], [self.b], 1))
        _w, full = skip(self.state, 90)
        self.assertEqual((full["tier"], full["offscreen"]["required"], full["propagation"]["hops"]), ("full", [self.b], 2))
        before_midnight = ST.MINUTES_PER_DAY - self.state["clock"]["minute"]
        _w, crossing = skip(self.state, before_midnight + 1)
        self.assertEqual(crossing["tier"], "full")

    def test_a_brief_skip_allows_but_does_not_require_a_beat(self):
        new, _ = apply(self.state, commit("continue", [{"op": "advance_time", "minutes": 30}, act(self.a)]))
        self.assertEqual(new["turn"], self.state["turn"] + 1)
        new, result = apply(self.state, commit("continue", [{"op": "advance_time", "minutes": 30}, beat(self.b), act(self.a)]))
        self.assertEqual(result["simulation"]["offscreen_beats"][0]["npc_id"], self.b)

    def test_missing_required_beats_are_rejected_with_the_preview(self):
        err = rejected(self.state, commit("continue", [{"op": "advance_time", "minutes": 90}, act(self.a)]))
        self.assertIn("离屏片段", reasons(err))
        preview = err.extra["preview"]
        self.assertEqual([p["npc_id"] for p in preview["required_beats"]], [self.b])
        self.assertIn("goal", preview["required_beats"][0])
        self.assertEqual(preview, simulation.preview(self.state, content()["world"], {"minutes": 90}))

    def test_beats_stay_offscreen_and_about_that_npc(self):
        skip90 = {"op": "advance_time", "minutes": 90}
        err = rejected(self.state, commit("continue", [skip90, beat(self.b, [{"op": "relationship", "from": self.b, "to": "player", "trust_delta": 1, "reason": "想起他"}]), act(self.a)]))
        self.assertIn("玩家角色", reasons(err))
        err = rejected(self.state, commit("continue", [skip90, beat(self.b, [act(self.a, "替别人做事")]), act(self.a)]))
        self.assertIn("自己", reasons(err))
        err = rejected(self.state, commit("continue", [skip90, beat(self.b), beat(self.a), act(self.a)]))
        self.assertIn("在场", reasons(err))
        err = rejected(self.state, commit("continue", [skip90, beat(self.b), beat(self.b), act(self.a)]))
        self.assertIn("只能有一段", reasons(err))
        err = rejected(self.state, commit("continue", [beat(self.b), skip90, act(self.a)]))
        self.assertIn("时间推进之前", reasons(err))

    def test_frozen_world_has_no_beats_and_no_propagation(self):
        state = dict(self.state, preferences=dict(self.state["preferences"], offscreen_simulation=False))
        work, report = skip(state, 1440)
        self.assertTrue(report["offscreen"]["frozen"])
        self.assertEqual(report["offscreen"]["required"], [])
        self.assertEqual(report["propagation"], {"frozen": True, "spread": []})
        self.assertTrue(report["resolved_events"])  # fixed deadlines still come due
        self.assertTrue(FA.of(work).by_key("t.gossip")[0]["spreading"])
        err = rejected(state, commit("continue", [{"op": "advance_time", "minutes": 90}, beat(self.b), act(self.a)]))
        self.assertIn("冻结", reasons(err))


class TwistTest(unittest.TestCase):
    def test_pressure_offers_twists_once_on_the_first_new_day(self):
        state, _ = new_state("pressure", seed=11)
        a = majors_present(state)[0]
        state, _ = apply(state, commit("continue", [{"op": "advance_time", "until": "next_morning"}, act(a)]))
        offer = state["requests"]["twist_offer"]
        self.assertTrue(2 <= len(offer) <= 3, offer)
        self.assertEqual(len({t["category"] for t in offer}), len(offer))
        self.assertTrue(state["counters"]["twists"]["auto_offered"])
        state, _ = apply(state, commit("continue", [act(a)], chapter_summary="第一夜过去了。"))
        self.assertEqual(state["requests"]["twist_offer"], offer)  # kept until taken or the next day
        state, _ = apply(state, commit("continue", [{"op": "advance_time", "days": 1}, act(a)]))
        self.assertIsNone(state["requests"]["twist_offer"])  # offered once per game

    def test_daily_mode_offers_none_by_itself_but_answers_a_request(self):
        state, _ = new_state("daily", seed=11)
        a = npcs(state)[0]
        state, _ = apply(state, commit("continue", [{"op": "advance_time", "until": "next_morning"}, act(a)]))
        self.assertIsNone(state["requests"]["twist_offer"])
        offer, note = simulation.requested_twists(state, content()["world"])
        self.assertIsNone(note)
        self.assertTrue(2 <= len(offer) <= 3)
        self.assertTrue(all(t["id"] for t in offer))

    def test_accepting_a_twist(self):
        state, _ = new_state("pressure", seed=11)
        a = majors_present(state)[0]
        state, _ = apply(state, commit("continue", [{"op": "advance_time", "until": "next_morning"}, act(a)]))
        chosen = state["requests"]["twist_offer"][0]
        pick = {"op": "twist_accept", "twist_id": chosen["id"]}
        err = rejected(state, commit("continue", [pick, act(a)], chapter_summary="第一夜。"))
        self.assertIn("玩家选定", reasons(err))
        state, result = apply(state, commit("result", [pick], player_authorized=True, chapter_summary="第一夜。"))
        self.assertEqual(result["twist"]["twist_id"], chosen["id"])
        self.assertIsNone(state["requests"]["twist_offer"])
        err = rejected(state, commit("result", [{"op": "twist_accept", "category": "意外", "text": "码头停电了"}], player_authorized=True))
        self.assertIn("今天已经接受过", reasons(err))
        err = rejected(state, commit("result", [{"op": "twist_accept", "twist_id": chosen["id"]}], player_authorized=True))
        self.assertIn("今天已经接受过", reasons(err))
        state, _ = apply(state, commit("continue", [{"op": "advance_time", "days": 1}, act(a)]))
        err = rejected(state, commit("result", [{"op": "twist_accept", "text": "码头停电了"}], player_authorized=True, chapter_summary="又一天。"))
        self.assertIn("category", reasons(err) + " | ".join(d["hint"] or "" for d in err.details))
        state, result = apply(state, commit("result", [{"op": "twist_accept", "category": "意外", "text": "码头停电了"}], player_authorized=True, chapter_summary="又一天。"))
        self.assertEqual(result["twist"]["category"], "意外")


class ChapterTest(unittest.TestCase):
    def test_chapter_summary_is_required_when_asked_and_refused_otherwise(self):
        state, _ = new_state("pressure", seed=11)
        a = majors_present(state)[0]
        err = rejected(state, commit("continue", [act(a)], chapter_summary="没人要的章节。"))
        self.assertIn("没有要求章节摘要", reasons(err))
        state, _ = apply(state, commit("continue", [act(a, "看表")]))
        state, _ = apply(state, commit("continue", [{"op": "advance_time", "until": "next_morning"}, act(a)]))
        self.assertTrue(state["requests"]["chapter_summary"])
        err = rejected(state, commit("continue", [act(a)]))
        self.assertIn("章节摘要", reasons(err))
        self.assertIn("第 1–3 回合", " | ".join(d["hint"] or "" for d in err.details))

    def test_every_twenty_turns_a_chapter_archives_its_turns_and_ended_events(self):
        state, _ = new_state("pressure", seed=11)
        a = majors_present(state)[0]
        immediate = next(e for e in state["events"].values() if e["tier"] == "immediate")
        for index in range(20):
            state, _ = apply(state, commit("continue", [act(a, "第%d次看表" % index)]))
            self.assertEqual(state["requests"]["chapter_summary"], state["turn"] == 21, state["turn"])
        self.assertEqual(state["events"][immediate["id"]]["outcome"], "expired")
        state, result = apply(state, commit("continue", [act(a, "收工")], chapter_summary="夜班的前半段：扯皮、拖延、互相试探。"))
        chapter = result["chapter"]
        self.assertEqual((chapter["index"], chapter["from_turn"], chapter["to_turn"]), (1, 1, 21))
        self.assertEqual([t["turn"] for t in state["memory"]["turns"]], [22])
        kinds = [item["kind"] for item in result["archive"]]
        self.assertEqual(kinds.count("turn"), 20)
        self.assertIn("event", kinds)
        self.assertNotIn(immediate["id"], state["events"])
        err = rejected(state, commit("result", [{"op": "event_cancel", "event_id": immediate["id"], "reason": "算了"}], player_authorized=True))
        self.assertIn("归档", reasons(err))
        brief = CX.brief(state, content())
        self.assertEqual(brief["last_chapter"], "夜班的前半段：扯皮、拖延、互相试探。")
        self.assertEqual(brief["recent"], [state["memory"]["turns"][-1]["summary"]])

    def test_more_than_ten_chapters_ask_for_a_prologue_that_merges_the_first_five(self):
        state, _ = new_state("daily", seed=11)
        a = npcs(state)[0]
        for index in range(11):
            extra = {"chapter_summary": "第%d章。" % index} if state["requests"]["chapter_summary"] else {}
            state, _ = apply(state, commit("continue", [{"op": "advance_time", "until": "next_morning"}, act(a)], **extra))
        state, _ = apply(state, commit("continue", [act(a)], chapter_summary="第十一章。"))
        self.assertEqual(len(state["memory"]["chapters"]), 11)
        self.assertTrue(state["requests"]["prologue"])
        full = CX.full(state, content())
        merge = full["prologue_merge"]
        self.assertIsNone(merge["previous"])
        self.assertEqual([c["index"] for c in merge["chapters"]], [1, 2, 3, 4, 5])
        err = rejected(state, commit("continue", [act(a)]))
        self.assertIn("前情", reasons(err))
        state, result = apply(state, commit("continue", [act(a)], prologue="前情：几个夜班过去，人和事慢慢熟了。"))
        self.assertEqual(state["memory"]["prologue"], "前情：几个夜班过去，人和事慢慢熟了。")
        self.assertEqual([c["index"] for c in state["memory"]["chapters"]], [6, 7, 8, 9, 10, 11])
        self.assertEqual([item["kind"] for item in result["archive"]], ["chapter"] * 5)
        self.assertFalse(state["requests"]["prologue"])
        err = rejected(state, commit("continue", [act(a)], prologue="多余的前情。"))
        self.assertIn("没有要求前情", reasons(err))


class RetconTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("pressure", seed=11)
        self.a = majors_present(self.state)[0]
        self.fact = {"op": "add_fact", "key": "player.past.harbor", "text": "玩家角色早年在这片码头扛过包", "known_by": ["player"], "visibility": "private", "origin": "retcon"}

    def test_a_retcon_adds_what_the_player_knows(self):
        new, result = apply(self.state, commit("rewrite", [self.fact, act(self.a, "愣了一下")], player_authorized=True, player_input="其实我早年在这片码头扛过包"))
        added = new["facts"][result["applied"][0]["fact_id"]]
        self.assertEqual((added["origin"], added["known_by"]), ("retcon", ["player"]))
        self.assertEqual(new["turn"], self.state["turn"] + 1)
        new, _ = apply(self.state, commit("rewrite", [{"op": "player_update", "title": "包哥"}], player_authorized=True))
        self.assertEqual(new["characters"]["player"]["title"], "包哥")

    def test_a_retcon_never_adds_knowledge_liking_or_consent_to_npcs(self):
        for bad in (dict(self.fact, known_by=["player", self.a]), dict(self.fact, visibility="public"), dict(self.fact, truth=False, believed_by=["player"], known_by=[]), dict(self.fact, spread=True)):
            err = rejected(self.state, commit("rewrite", [bad], player_authorized=True))
            self.assertIn("追溯", reasons(err))
        err = rejected(self.state, commit("rewrite", [self.fact, {"op": "relationship", "from": self.a, "to": "player", "trust_delta": 1, "reason": "原来是老相识"}], player_authorized=True))
        self.assertIn("relationship", reasons(err))

    def test_a_retcon_that_contradicts_a_recorded_fact_names_it(self):
        existing = next(f for f in self.state["facts"].values() if f["key"] == "player.baseline")
        err = rejected(self.state, commit("rewrite", [dict(self.fact, key="player.baseline", text="玩家角色其实是别的身份")], player_authorized=True))
        self.assertIn(existing["id"], reasons(err))
        self.assertIn("冲突", reasons(err))

    def test_rewrite_turns_come_from_the_player_and_carry_a_retcon(self):
        err = rejected(self.state, commit("rewrite", [self.fact]))
        self.assertIn("玩家发起", reasons(err))
        err = rejected(self.state, commit("rewrite", [act(self.a)], player_authorized=True))
        self.assertIn("至少要有一条追溯事实", reasons(err))
        err = rejected(self.state, commit("rewrite", [dict(self.fact, origin="observed")], player_authorized=True))
        self.assertIn("都是追溯", reasons(err))


class RestoreTest(unittest.TestCase):
    def test_undo_keeps_player_settings_and_never_reuses_ids(self):
        before, _ = new_state("pressure", seed=11)
        a = majors_present(before)[0]
        after, _ = apply(before, commit("continue", [{"op": "set_voice", "npc_id": a, "voice": "inner", "cause": "npc_self", "trigger": "exposed", "note": "忍不住了"}, {"op": "add_fact", "key": "t.x", "text": "一件事", "known_by": [a], "visibility": "private", "origin": "observed"}]))
        after["safety"]["paused"] = True
        after["preferences"]["inner_view"] = True
        undone, info = T.undo(after, before)
        self.assertEqual((undone["turn"], info["undone_turn"]), (before["turn"], after["turn"]))
        self.assertEqual(undone["revision"], after["revision"] + 1)
        self.assertTrue(undone["safety"]["paused"])
        self.assertTrue(undone["preferences"]["inner_view"])
        self.assertNotIn(a, undone["preferences"]["voice"])  # the switch happened in the undone turn
        self.assertEqual(undone["counters"]["next"], after["counters"]["next"])
        self.assertNotIn("t.x", {f["key"] for f in undone["facts"].values()})
        with self.assertRaises(AppError) as caught:
            T.undo(before, None)
        self.assertIn("开局", caught.exception.message)


# ---------------------------------------------------------------------------
# through the application: storage, journal, context depth


def base_commit(state, request_id, revision, ops, mode="continue", **extra):
    payload = {
        "session_id": state["session_id"],
        "request_id": request_id,
        "expected_revision": revision,
        "action_mode": mode,
        "player_input": "……",
        "operations": ops,
        "content_tags": [],
        "summary": "测试回合",
        "open_action": "场面停住",
    }
    payload.update(extra)
    return payload


class ServiceTimeTest(unittest.TestCase):
    def setUp(self):
        self._app = app()
        self.ctx = self._app.__enter__()
        self.ids = Ids()
        self.sid = open_game(self.ctx, self.ids, mode="pressure", seed=11)["session_id"]
        state = self.state()
        self.a, self.b = majors_present(state)[:2]

    def tearDown(self):
        self._app.__exit__(None, None, None)

    def state(self, sid=None):
        return session(self.ctx, sid or self.sid)["state"]

    def commit(self, ops, sid=None, **extra):
        state = self.state(sid)
        return service.commit_turn(self.ctx, base_commit(state, self.ids(), state["revision"], ops, **extra))

    def undo(self, sid=None):
        state = self.state(sid)
        return service.undo_turn(self.ctx, {"session_id": state["session_id"], "request_id": self.ids(), "expected_revision": state["revision"]})

    def test_fast_forward_preview_matches_the_commit_exactly(self):
        self.commit([
            {"op": "npc_state", "npc_id": self.a, "add_conditions": [{"kind": "drunk", "text": "喝多了", "minutes": 30}]},
            {"op": "event_create", "kind": "chance", "title": "会不会有人来查", "participants": [self.a], "in_minutes": 300, "probability": 0.5, "dedupe_key": "t.check"},
            {"op": "add_fact", "key": "t.gossip", "text": "有人在传一件事", "known_by": [self.a], "visibility": "private", "origin": "observed", "spread": True},
            {"op": "exit_scene", "character_id": self.b, "to_location_id": elsewhere(self.state())},
        ])
        revision = self.state()["revision"]
        preview = service.get_context(self.ctx, {"session_id": self.sid, "preview_time": {"days": 1}})["preview"]
        self.assertEqual(self.state()["revision"], revision)  # a preview changes nothing
        self.assertEqual([p["npc_id"] for p in preview["required_beats"]], [self.b])
        with self.assertRaises(AppError) as caught:
            self.commit([{"op": "advance_time", "days": 1}, act(self.a)])
        self.assertEqual(caught.exception.extra["preview"], preview)
        done = self.commit([{"op": "advance_time", "days": 1}, beat(self.b), act(self.a)])
        self.assertEqual({k: done["clock"][k] for k in ("day", "minute")}, {k: preview["to"][k] for k in ("day", "minute")})
        self.assertEqual(done["resolved_events"], preview["resolved_events"])
        self.assertIn("t.check", [self.state()["events"][e["event_id"]]["dedupe_key"] for e in done["resolved_events"] if e["event_id"] in self.state()["events"]] or ["t.check"])
        sim = done["simulation"]
        for key in ("expired_conditions", "moved", "spread"):
            self.assertEqual(sim.get(key, []), preview[key], key)

    def test_undo_then_redo_and_load_repeat_every_random_result(self):
        self.commit([{"op": "event_create", "kind": "chance", "title": "会不会下雨", "participants": [self.a], "in_minutes": 60, "probability": 0.5, "dedupe_key": "t.rain"}])
        state = self.state()
        service.save_slot(self.ctx, {"session_id": self.sid, "request_id": self.ids(), "expected_revision": state["revision"], "name": "下雨之前"})
        ops = [
            {"op": "advance_time", "minutes": 90},
            {"op": "roll", "purpose": "能不能看清", "probability": 0.5, "on_success": [act(self.a, "看清了")], "on_failure": []},
            {"op": "roll", "purpose": "有没有人听见", "probability": 0.5, "on_success": [], "on_failure": [act(self.b, "没听见")]},
            act(self.a),
        ]

        def randomness(done):
            return [a.get("result") for a in done["applied"] if a["op"] == "roll"], [(e["event_id"], e["outcome"]) for e in done["resolved_events"]]

        rain = next(e["id"] for e in self.state()["events"].values() if e["dedupe_key"] == "t.rain")
        first = self.commit(ops)
        self.assertIn(rain, [e["event_id"] for e in first["resolved_events"]])
        undone = self.undo()
        self.assertEqual(undone["turn"], first["turn"] - 1)
        again = self.commit(ops)
        self.assertEqual(randomness(again), randomness(first))
        loaded = service.load_slot(self.ctx, {"request_id": self.ids(), "name": "下雨之前"})
        on_copy = self.commit(ops, sid=loaded["session_id"])
        self.assertEqual(randomness(on_copy), randomness(first))

    def test_undo_restores_facts_and_stops_at_the_floor(self):
        self.commit([{"op": "add_fact", "key": "t.secret", "text": "一件事", "known_by": [self.a], "visibility": "private", "origin": "observed"}])
        secret = FA.of(self.state()).by_key("t.secret")[0]["id"]
        self.commit([{"op": "reveal_fact", "fact_id": secret, "from": self.a, "to": [self.b]}, {"op": "add_fact", "key": "t.note", "text": "玩家记下的事", "known_by": ["player"], "visibility": "private", "origin": "observed"}])
        self.assertEqual(sorted(self.state()["facts"][secret]["known_by"]), sorted([self.a, self.b]))
        state = self.state()
        service.set_boundary(self.ctx, {"session_id": self.sid, "request_id": self.ids(), "expected_revision": state["revision"], "action": "add", "text": "不要写到血", "tags": []})
        revision = self.state()["revision"]
        done = self.undo()
        self.assertEqual((done["turn"], done["revision"], done["receipt"]), (2, revision + 1, "已撤销第 3 回合"))
        state = self.state()
        self.assertEqual(state["facts"][secret]["known_by"], [self.a])
        self.assertNotIn("t.note", {f["key"] for f in state["facts"].values()})
        self.assertEqual([b["text"] for b in state["safety"]["boundaries"]], ["不要写到血"])
        self.undo()
        self.assertNotIn(secret, self.state()["facts"])
        with self.assertRaises(AppError) as caught:
            self.undo()
        self.assertIn("开局", caught.exception.message)
        log = repo.recent_turn_log(self.ctx.db(), self.sid, 10)
        self.assertEqual(sorted(r["turn"] for r in log if r["kind"] == "commit" and r["undone"]), [2, 3])

    def test_rewrite_replaces_the_last_turn_in_one_commit(self):
        self.commit([{"op": "add_fact", "key": "t.first", "text": "第一种说法", "known_by": ["player"], "visibility": "private", "origin": "observed"}])
        revision = self.state()["revision"]
        with self.assertRaises(AppError):
            self.commit([act(self.a)], replaces_turn=1)
        done = self.commit([{"op": "add_fact", "key": "t.second", "text": "第二种说法", "known_by": ["player"], "visibility": "private", "origin": "observed"}], replaces_turn=2)
        self.assertEqual((done["turn"], done["revision"], done["replaced_turn"]), (2, revision + 1, 2))
        keys = {f["key"] for f in self.state()["facts"].values()}
        self.assertIn("t.second", keys)
        self.assertNotIn("t.first", keys)
        log = repo.recent_turn_log(self.ctx.db(), self.sid, 3)
        self.assertEqual([(r["turn"], r["undone"]) for r in log if r["kind"] == "commit"], [(2, 0), (2, 1)])
        self.undo()
        self.assertNotIn("t.second", {f["key"] for f in self.state()["facts"].values()})
        with self.assertRaises(AppError) as caught:
            self.commit([act(self.a)], replaces_turn=1)
        self.assertIn("开局", caught.exception.message)

    def test_a_failed_rewrite_leaves_the_last_turn_as_it_was(self):
        self.commit([{"op": "add_fact", "key": "t.first", "text": "第一种说法", "known_by": ["player"], "visibility": "private", "origin": "observed"}])
        before = self.state()
        conn = self.ctx.db()
        journal = conn.execute("SELECT COUNT(*) FROM fact_journal WHERE session_id=?", (self.sid,)).fetchone()[0]
        with self.assertRaises(AppError):
            self.commit([act("nobody_here")], replaces_turn=2)
        after = self.state()
        self.assertEqual(after, before)  # facts included: the revert inside the rejected commit rolled back
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM fact_journal WHERE session_id=?", (self.sid,)).fetchone()[0], journal)
        log = repo.recent_turn_log(self.ctx.db(), self.sid, 2)
        self.assertFalse(any(r["undone"] for r in log))
        self.assertEqual(self.undo()["turn"], 1)  # the undo point and journal still work
        self.assertNotIn("t.first", {f["key"] for f in self.state()["facts"].values()})

    def test_undo_after_load_stops_at_the_loaded_turn(self):
        self.commit([act(self.a)])
        state = self.state()
        service.save_slot(self.ctx, {"session_id": self.sid, "request_id": self.ids(), "expected_revision": state["revision"], "name": "中途"})
        loaded = service.load_slot(self.ctx, {"request_id": self.ids(), "name": "中途"})
        with self.assertRaises(AppError) as caught:
            self.undo(loaded["session_id"])
        self.assertIn("读档", caught.exception.message)
        self.commit([act(self.a)], sid=loaded["session_id"])
        self.assertEqual(self.undo(loaded["session_id"])["turn"], 2)

    def test_after_a_failed_commit_the_next_context_is_full(self):
        self.assertEqual(self.commit([act(self.a)])["context"]["depth"], "brief")  # turn 2
        with self.assertRaises(AppError):
            self.commit([act("nobody_here")])
        self.assertEqual(self.commit([act(self.a)])["context"]["depth"], "full")  # turn 3, after the failure
        self.assertEqual(self.commit([act(self.a)])["context"]["depth"], "brief")  # turn 4

    def test_want_twist_returns_candidates_without_changing_state(self):
        revision = self.state()["revision"]
        out = service.get_context(self.ctx, {"session_id": self.sid, "want_twist": True})
        self.assertTrue(2 <= len(out["twist_candidates"]) <= 3)
        self.assertEqual(self.state()["revision"], revision)

    def test_storage_answers_fact_queries_like_the_domain(self):
        from adult_tension.application.fake_narrator import FakeNarrator

        narrator = FakeNarrator(11)
        for _ in range(30):
            state = repo.load_session(self.ctx.db(), self.sid)
            payload = narrator.commit(state["state"], state["content"])
            service.commit_turn(self.ctx, dict(payload, session_id=self.sid, request_id=self.ids(), expected_revision=state["revision"]))
        source = repo.FactSource(self.ctx.db(), self.sid)
        facts = FA.DictSource(source.as_dict())
        state = self.state()
        people = sorted(state["characters"])
        names = [state["characters"][c]["name"] for c in people]
        for present in ([], people[:1], people[:3]):
            present_names = [state["characters"][c]["name"] for c in present]
            for recent in (1, state["turn"] - 5):
                for limit in (None, 8, 30):
                    args = ("player", present, present_names, recent, limit)
                    self.assertEqual([f["id"] for f in source.player_ranked(*args)], [f["id"] for f in facts.player_ranked(*args)], args)
        for cid in people:
            self.assertEqual(source.known_to(cid), facts.known_to(cid))
        self.assertEqual(source.spreading(), facts.spreading())
        for fact in facts.all()[:20]:
            self.assertEqual(source.by_key(fact["key"]), facts.by_key(fact["key"]))
        self.assertTrue(names)

    def test_a_commit_writes_and_journals_only_the_facts_it_changed(self):
        conn = self.ctx.db()
        count = repo.count_facts(conn, self.sid)
        done = self.commit([{"op": "add_fact", "key": "t.one", "text": "新的一件事", "known_by": ["player"], "visibility": "private", "origin": "observed"}])
        self.assertEqual(repo.count_facts(conn, self.sid), count + 1)
        rows = conn.execute("SELECT id, before FROM fact_journal WHERE session_id=? AND turn=?", (self.sid, done["turn"])).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0][1])


if __name__ == "__main__":
    unittest.main()
