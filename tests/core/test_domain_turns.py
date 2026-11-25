"""Domain rules of a turn, exercised on real openings (no mocks)."""

import unittest

import _bootstrap  # noqa: F401
from adult_tension.domain import clock as CL
from adult_tension.domain import rng
from helpers.domain import apply, commit, new_state, npcs, rejected


def reasons(err):
    return " | ".join(d["reason"] for d in err.details)


class ModeRulesTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("pressure", seed=11)
        self.npc = npcs(self.state)[0]

    def test_attempt_on_npc_needs_a_response(self):
        err = rejected(self.state, commit("attempt", [], acts_on=[self.npc], player_authorized=True))
        self.assertIn("没有", reasons(err))
        ok = commit("attempt", [{"op": "npc_response", "npc_id": self.npc, "response": "refuse", "note": "摇头"}], acts_on=[self.npc], player_authorized=True)
        new, result = apply(self.state, ok)
        self.assertEqual(new["turn"], self.state["turn"] + 1)
        self.assertEqual(result["applied"][0]["response"], "refuse")

    def test_attempt_without_target_declaration_or_response_is_rejected(self):
        err = rejected(self.state, commit("attempt", [], player_authorized=True))
        self.assertIn("acts_on", err.details[0]["path"])
        new, _ = apply(self.state, commit("attempt", [], acts_on=[], player_authorized=True))
        self.assertEqual(new["turn"], 2)

    def test_result_mode_cannot_act_on_an_npc(self):
        err = rejected(self.state, commit("result", [], acts_on=[self.npc], player_authorized=True))
        self.assertIn("尝试档", reasons(err))

    def test_continue_cannot_move_the_player_or_carry_authorization(self):
        here = self.state["scene"]["location_id"]
        world_exit = next(loc for loc in _world_locations() if loc["id"] == here)["exits"][0]
        err = rejected(self.state, commit("continue", [{"op": "move", "character_id": "player", "location_id": world_exit}]))
        self.assertIn("玩家角色的移动", reasons(err))
        err = rejected(self.state, commit("continue", [{"op": "npc_action", "npc_id": self.npc, "action": "抬头"}], player_authorized=True))
        self.assertIn("player_authorized", err.details[0]["path"])

    def test_continue_needs_an_observable_change(self):
        err = rejected(self.state, commit("continue", []))
        self.assertIn("可观察的变化", reasons(err))
        new, result = apply(self.state, commit("continue", [{"op": "npc_action", "npc_id": self.npc, "action": "看了看表"}]))
        self.assertTrue(result["default_time_advance"])
        self.assertEqual(CL.minutes_between(self.state["clock"], new["clock"]), 3)
        # a short wait is no change by itself; a skip into a new scene is one: with the world
        # frozen a fast-forward asks for no offscreen beats and is advance_time alone
        frozen = dict(self.state, preferences=dict(self.state["preferences"], offscreen_simulation=False))
        err = rejected(frozen, commit("continue", [{"op": "advance_time", "minutes": 59}]))
        self.assertIn("可观察的变化", reasons(err))
        new, result = apply(frozen, commit("continue", [{"op": "advance_time", "until": "next_morning"}]))
        self.assertEqual((new["turn"], result["applied"][0]["new_scene"]), (frozen["turn"] + 1, True))

    def test_wait_mode_promise_and_consent_are_refused(self):
        err = rejected(
            self.state,
            commit("wait", [{"op": "event_create", "kind": "promise", "title": "约定", "participants": ["player", self.npc], "in_minutes": 60, "dedupe_key": "t.promise"}]),
        )
        self.assertIn("承诺", reasons(err))


def _world_locations():
    from helpers.domain import content

    return content()["world"]["locations"]


class NpcRulesTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=3)
        self.npc = npcs(self.state)[0]

    def test_basis_facts_must_be_in_the_npcs_information_set(self):
        foreign = next(f for f in self.state["facts"].values() if self.npc not in f["known_by"] and self.npc not in f["believed_by"])
        op = {"op": "npc_response", "npc_id": self.npc, "response": "negotiate", "note": "开条件", "basis_fact_ids": [foreign["id"]]}
        err = rejected(self.state, commit("attempt", [op], acts_on=[self.npc], player_authorized=True))
        self.assertIn("不知道事实", reasons(err))
        own = next(f for f in self.state["facts"].values() if self.npc in f["known_by"])
        op["basis_fact_ids"] = [own["id"]]
        apply(self.state, commit("attempt", [op], acts_on=[self.npc], player_authorized=True))

    def test_surface_cooperation_records_true_intent_only_for_the_npc(self):
        op = {"op": "npc_response", "npc_id": self.npc, "response": "surface", "note": "口头答应", "true_intent": "回头就去告诉班组长"}
        new, result = apply(self.state, commit("attempt", [op], acts_on=[self.npc], player_authorized=True))
        fact = new["facts"][result["applied"][0]["intent_fact_id"]]
        self.assertEqual(fact["known_by"], [self.npc])
        self.assertEqual(fact["visibility"], "private")
        missing = dict(op, true_intent=None)
        rejected(self.state, commit("attempt", [missing], acts_on=[self.npc], player_authorized=True))

    def test_significant_action_cooldown(self):
        act = {"op": "npc_action", "npc_id": self.npc, "action": "主动走过来搭话", "significant": True, "kind": "approach"}
        state, _ = apply(self.state, commit("wait", [act]))
        err = rejected(state, commit("wait", [act]))
        self.assertIn("冷却", reasons(err))
        quiet = dict(act, significant=False)
        state, _ = apply(state, commit("wait", [quiet]))
        state, _ = apply(state, commit("wait", [quiet]))
        state, _ = apply(state, commit("wait", [act]))  # turn 5: three player turns after turn 2

    def test_absent_npc_cannot_act_when_offscreen_is_frozen(self):
        absent = next(c for c, ch in self.state["characters"].items() if c not in self.state["scene"]["present"])
        self.state["preferences"]["offscreen_simulation"] = False
        err = rejected(self.state, commit("continue", [{"op": "npc_action", "npc_id": absent, "action": "托人带了句话"}]))
        self.assertIn("冻结", reasons(err))
        self.state["preferences"]["offscreen_simulation"] = True
        apply(self.state, commit("continue", [{"op": "npc_action", "npc_id": absent, "action": "托人带了句话"}]))

    def test_unknown_character_is_not_found(self):
        err = rejected(self.state, commit("continue", [{"op": "npc_action", "npc_id": "ghost", "action": "出现"}]))
        self.assertEqual(err.code, "NOT_FOUND")
        self.assertEqual(err.details[0]["path"], "$.operations[0].npc_id")


class KnowledgeTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=5)
        self.npc = npcs(self.state)[0]

    def test_public_fact_is_known_by_everyone_present(self):
        op = {"op": "add_fact", "key": "scene.broken_lamp", "text": "泊位的一盏灯坏了", "visibility": "public", "origin": "observed"}
        new, result = apply(self.state, commit("continue", [op]))
        fact = new["facts"][result["applied"][0]["fact_id"]]
        self.assertEqual(sorted(fact["known_by"]), sorted(self.state["scene"]["present"]))

    def test_inner_fact_belongs_to_one_npc_and_never_spreads(self):
        good = {"op": "add_fact", "key": "npc.inner.t2", "text": "其实很想留下", "visibility": "inner", "origin": "observed", "known_by": [self.npc]}
        apply(self.state, commit("continue", [good]))
        for bad in (dict(good, known_by=["player"]), dict(good, known_by=[self.npc, "player"]), dict(good, spread=True)):
            rejected(self.state, commit("continue", [bad]))

    def test_same_key_true_fact_cannot_be_added_twice(self):
        existing = next(iter(self.state["facts"].values()))
        op = {"op": "add_fact", "key": existing["key"], "text": "另一种说法", "visibility": "private", "origin": "observed", "known_by": ["player"]}
        err = rejected(self.state, commit("continue", [op]))
        self.assertIn("同键的真事实", reasons(err))

    def test_misbelief_uses_false_fact_with_believers(self):
        op = {"op": "add_fact", "key": "rumor.box", "text": "有人说柜子里是走私的表", "truth": False, "believed_by": [self.npc], "visibility": "private", "origin": "told"}
        new, result = apply(self.state, commit("continue", [op]))
        fact = new["facts"][result["applied"][0]["fact_id"]]
        self.assertFalse(fact["truth"])
        rejected(self.state, commit("continue", [dict(op, believed_by=[])]))

    def test_absent_characters_cannot_learn_in_this_scene(self):
        absent = next(c for c in self.state["characters"] if c not in self.state["scene"]["present"])
        op = {"op": "add_fact", "key": "far.news", "text": "消息", "visibility": "private", "origin": "told", "known_by": [absent]}
        rejected(self.state, commit("continue", [op]))

    def test_retcon_origin_is_not_available_outside_rewrite(self):
        op = {"op": "add_fact", "key": "player.past", "text": "早年在别的码头干过", "visibility": "private", "origin": "retcon", "known_by": ["player"]}
        rejected(self.state, commit("continue", [op]))


class RelationshipTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=9)
        self.npc = npcs(self.state)[0]

    def rel(self, **kw):
        base = {"op": "relationship", "from": self.npc, "to": "player", "reason": "测试原因"}
        base.update(kw)
        return base

    def test_trust_net_change_per_commit_is_limited(self):
        err = rejected(self.state, commit("continue", [self.rel(trust_delta=2), self.rel(trust_delta=1)]))
        self.assertIn("净变化", reasons(err))

    def test_values_clamp_at_bounds(self):
        edge = self.state["relationships"]["%s>player" % self.npc]
        edge["trust"] = 5
        edge["tension"] = 5
        new, _ = apply(self.state, commit("continue", [self.rel(trust_delta=1, tension_delta=2)]))
        self.assertEqual(new["relationships"]["%s>player" % self.npc]["trust"], 5)
        self.assertEqual(new["relationships"]["%s>player" % self.npc]["tension"], 5)
        edge["trust"] = -5
        edge["tension"] = 0
        low, _ = apply(self.state, commit("continue", [self.rel(trust_delta=-2, tension_delta=-2)]))
        self.assertEqual(low["relationships"]["%s>player" % self.npc]["trust"], -5)
        self.assertEqual(low["relationships"]["%s>player" % self.npc]["tension"], 0)

    def test_stage_advance_needs_both_sides(self):
        err = rejected(self.state, commit("continue", [self.rel(stage_advance=True)]))
        self.assertIn("result/attempt", reasons(err))
        err = rejected(self.state, commit("attempt", [self.rel(stage_advance=True)], acts_on=[], player_authorized=True))
        self.assertIn("partial 或 genuine", reasons(err))
        ok = [
            {"op": "npc_response", "npc_id": self.npc, "response": "genuine", "note": "笑了"},
            self.rel(stage_advance=True),
        ]
        before = self.state["relationships"]["%s>player" % self.npc]["stage"]
        new, _ = apply(self.state, commit("attempt", ok, acts_on=[self.npc], player_authorized=True))
        after = new["relationships"]["%s>player" % self.npc]
        self.assertNotEqual(after["stage"], before)
        self.assertEqual(new["relationships"]["player>%s" % self.npc]["stage"], after["stage"])
        self.assertEqual(after["history"][-1]["evidence"]["npc_response"], "genuine")
        err = rejected(new, commit("attempt", ok + [self.rel(stage_advance=True)], acts_on=[self.npc], player_authorized=True))
        self.assertIn("一个阶段", reasons(err))

    def test_reason_is_required_and_players_feelings_are_not_decided_by_the_model(self):
        from adult_tension import schema
        from helpers.domain import COMMIT

        raw = {"action_mode": "continue", "player_input": "", "operations": [dict(self.rel(trust_delta=1), reason="")], "content_tags": [], "summary": "s", "open_action": "o"}
        _out, errors = schema.validate(COMMIT, raw)
        self.assertEqual([e["path"] for e in errors], ["$.operations[0].reason"])
        err = rejected(self.state, commit("continue", [{"op": "relationship", "from": "player", "to": self.npc, "trust_delta": 1, "reason": "觉得对方可靠"}]))
        self.assertIn("玩家角色对别人的态度", reasons(err))

    def test_new_edges_only_between_people_in_the_same_scene(self):
        absent = next(c for c in self.state["characters"] if c not in self.state["scene"]["present"])
        err = rejected(self.state, commit("continue", [{"op": "relationship", "from": absent, "to": "player", "tension_delta": 1, "reason": "远远看见"}]))
        self.assertIn("没有实际接触", reasons(err))


class EventsTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("pressure", seed=13)
        self.npc = npcs(self.state)[0]

    def test_pressure_opening_has_three_tiers(self):
        tiers = sorted(e["tier"] for e in self.state["events"].values())
        self.assertEqual(tiers, ["far", "immediate", "near"])

    def test_due_events_expire_once_when_time_passes(self):
        immediate = next(e for e in self.state["events"].values() if e["tier"] == "immediate")
        minutes = CL.minutes_between(self.state["clock"], immediate["due"])
        new, result = apply(self.state, commit("continue", [{"op": "advance_time", "minutes": minutes}, {"op": "npc_action", "npc_id": self.npc, "action": "看表"}]))
        self.assertEqual(new["events"][immediate["id"]]["outcome"], "expired")
        self.assertEqual([r["event_id"] for r in result["resolved_events"]], [immediate["id"]])
        again, result2 = apply(new, commit("continue", [{"op": "advance_time", "minutes": 30}, {"op": "npc_action", "npc_id": self.npc, "action": "又看表"}]))
        self.assertNotIn(immediate["id"], [r["event_id"] for r in result2["resolved_events"]])

    def test_terminal_events_cannot_change(self):
        near = next(e for e in self.state["events"].values() if e["tier"] == "near")
        state, _ = apply(self.state, commit("result", [{"op": "event_resolve", "event_id": near["id"], "outcome": "fulfilled", "note": "交了说明"}], player_authorized=True))
        err = rejected(state, commit("result", [{"op": "event_cancel", "event_id": near["id"], "reason": "改主意"}], player_authorized=True))
        self.assertIn("终态", reasons(err))

    def test_past_due_and_dedupe(self):
        past = {"op": "event_create", "kind": "opportunity", "title": "机会", "participants": [self.npc], "due": dict(self.state["clock"]), "dedupe_key": "t.chance"}
        err = rejected(self.state, commit("continue", [past]))
        self.assertIn("晚于现在", reasons(err))
        ok = dict(past)
        del ok["due"]
        ok["in_minutes"] = 90
        state, _ = apply(self.state, commit("continue", [ok]))
        err = rejected(state, commit("continue", [ok]))
        self.assertIn("去重键", reasons(err))

    def test_chance_events_roll_at_due_deterministically(self):
        chance = {"op": "event_create", "kind": "chance", "title": "会不会下雨", "participants": [self.npc], "in_minutes": 30, "probability": 0.5, "dedupe_key": "t.rain"}
        state, result = apply(self.state, commit("continue", [chance]))
        eid = result["applied"][0]["event_id"]
        tick = commit("continue", [{"op": "advance_time", "minutes": 40}, {"op": "npc_action", "npc_id": self.npc, "action": "看天"}])
        first, _ = apply(state, tick)
        second, _ = apply(state, tick)
        self.assertIn(first["events"][eid]["outcome"], ("hit", "miss"))
        self.assertEqual(first["events"][eid]["outcome"], second["events"][eid]["outcome"])
        coord = state["events"][eid]["coord"]
        self.assertEqual(coord, [state["turn"], 1])
        expected = "hit" if rng.unit(state["seed"], "event", coord[0], coord[1]) < 0.5 else "miss"
        self.assertEqual(first["events"][eid]["outcome"], expected)
        rejected(state, commit("continue", [{"op": "event_resolve", "event_id": eid, "outcome": "fulfilled", "note": "手动"}]))

    def test_daily_mode_has_no_countdowns(self):
        daily, _ = new_state("daily", seed=13)
        self.assertEqual(daily["events"], {})
        npc = npcs(daily)[0]
        op = {"op": "event_create", "kind": "deadline", "title": "截止", "participants": [npc], "in_minutes": 60, "dedupe_key": "t.deadline"}
        err = rejected(daily, commit("continue", [op]))
        self.assertIn("日常模式", reasons(err))


class RollAndTimeTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=21)
        self.npc = npcs(self.state)[0]

    def test_roll_is_derived_from_turn_and_index_not_from_text(self):
        def roll(purpose):
            return commit(
                "attempt",
                [
                    {
                        "op": "roll",
                        "purpose": purpose,
                        "probability": 0.5,
                        "on_success": [{"op": "add_fact", "key": "roll.win", "text": "成了", "visibility": "private", "origin": "observed", "known_by": ["player"]}],
                        "on_failure": [],
                    }
                ],
                acts_on=[],
                player_authorized=True,
            )

        _, a = apply(self.state, roll("能不能听清"))
        _, b = apply(self.state, roll("换一种说法再问一次"))
        self.assertEqual(a["applied"][0]["result"], b["applied"][0]["result"])
        expected = "success" if rng.unit(self.state["seed"], "roll", self.state["turn"] + 1, 0) < 0.5 else "failure"
        self.assertEqual(a["applied"][0]["result"], expected)

    def test_nested_roll_and_time_in_branches_are_rejected(self):
        bad = commit(
            "attempt",
            [{"op": "roll", "purpose": "试试", "probability": 0.5, "on_success": [{"op": "advance_time", "minutes": 5}], "on_failure": []}],
            acts_on=[],
            player_authorized=True,
        )
        rejected(self.state, bad)

    def test_time_never_flows_back_and_has_one_advance_per_commit(self):
        rejected(self.state, commit("continue", [{"op": "advance_time", "minutes": 5}, {"op": "advance_time", "minutes": 5}, {"op": "npc_action", "npc_id": self.npc, "action": "等"}]))
        rejected(self.state, commit("continue", [{"op": "advance_time", "minutes": 5, "days": 1}, {"op": "npc_action", "npc_id": self.npc, "action": "等"}]))

    def test_until_goes_to_next_occurrence(self):
        new, _ = apply(self.state, commit("continue", [{"op": "advance_time", "until": "next_morning"}, {"op": "npc_action", "npc_id": self.npc, "action": "伸懒腰"}]))
        self.assertEqual(new["clock"]["minute"], 7 * 60)
        self.assertEqual(new["clock"]["day"], self.state["clock"]["day"] + 1)

    def test_long_skip_opens_a_new_scene_and_clears_interaction_judgments(self):
        state, _ = apply(self.state, commit("attempt", [{"op": "npc_response", "npc_id": self.npc, "response": "partial", "note": "只答应一半"}], acts_on=[self.npc], player_authorized=True))
        self.assertTrue(state["scene"]["responses"])
        new, _ = apply(state, commit("continue", [{"op": "advance_time", "minutes": 90}, {"op": "npc_action", "npc_id": self.npc, "action": "收拾东西"}]))
        self.assertNotEqual(new["scene"]["id"], state["scene"]["id"])
        self.assertEqual(new["scene"]["responses"], [])


class PlayerAndSceneTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=17)
        self.npc = npcs(self.state)[0]

    def test_player_move_changes_scene_and_companions_follow_when_moved(self):
        here = self.state["scene"]["location_id"]
        target = next(loc for loc in _world_locations() if loc["id"] == here)["exits"][0]
        ops = [{"op": "move", "character_id": self.npc, "location_id": target}, {"op": "move", "character_id": "player", "location_id": target}]
        new, result = apply(self.state, commit("result", ops, player_authorized=True))
        self.assertEqual(new["scene"]["location_id"], target)
        self.assertEqual(sorted(new["scene"]["present"]), sorted(["player", self.npc]))
        self.assertTrue(result["location_changed"])

    def test_player_update_only_in_result_or_rewrite(self):
        op = {"op": "player_update", "title": "陈师傅"}
        rejected(self.state, commit("continue", [op, {"op": "npc_action", "npc_id": self.npc, "action": "点头"}]))
        new, _ = apply(self.state, commit("result", [op], player_authorized=True))
        self.assertEqual(new["characters"]["player"]["title"], "陈师傅")

    def test_enter_and_exit_scene(self):
        absent = next(c for c in self.state["characters"] if c not in self.state["scene"]["present"])
        new, _ = apply(self.state, commit("continue", [{"op": "enter_scene", "character_id": absent}]))
        self.assertIn(absent, new["scene"]["present"])
        rejected(new, commit("continue", [{"op": "enter_scene", "character_id": absent}]))
        newer, _ = apply(new, commit("continue", [{"op": "exit_scene", "character_id": absent}]))
        self.assertNotIn(absent, newer["scene"]["present"])
        rejected(self.state, commit("continue", [{"op": "exit_scene", "character_id": "player"}]))

    def test_standby_template_auto_instantiates_on_enter_scene(self):
        from adult_tension.domain import opening
        from helpers.domain import content

        world = content()["world"]
        previews = opening.standby_previews(self.state, world)
        self.assertTrue(previews)
        standby_id, preview = next(iter(sorted(previews.items())))
        self.assertNotIn(standby_id, self.state["characters"])
        new, result = apply(
            self.state,
            commit("continue", [{"op": "enter_scene", "character_id": standby_id}, {"op": "npc_action", "npc_id": standby_id, "action": "推门进来"}]),
        )
        self.assertIn(standby_id, new["characters"])
        self.assertIn(standby_id, new["scene"]["present"])
        self.assertIn(standby_id, result["new_characters"])
        char = new["characters"][standby_id]
        self.assertEqual((char["name"], char["tier"], char["introduced_turn"]), (preview["name"], "major", new["turn"]))
        self.assertTrue(char.get("identity") and char.get("decision") and char.get("intimacy") and char.get("voices"))
        keys = {f["key"] for f in new["facts"].values()}
        self.assertIn("%s.exposure" % standby_id, keys)
        self.assertIn("%s.hidden" % standby_id, keys)

    def test_all_errors_are_reported_together_with_paths(self):
        bad = commit(
            "continue",
            [
                {"op": "npc_action", "npc_id": "ghost", "action": "a"},
                {"op": "move", "character_id": "player", "location_id": "nowhere"},
                {"op": "relationship", "from": self.npc, "to": self.npc, "tension_delta": 1, "reason": "r"},
            ],
        )
        err = rejected(self.state, bad)
        paths = {d["path"].split(".")[1] for d in err.details if d["path"].startswith("$.operations")}
        self.assertTrue({"operations[0]", "operations[1]", "operations[2]"} <= paths, err.details)


class InvariantNetTest(unittest.TestCase):
    """The last net catches states that no single operation should produce."""

    def test_underage_character_in_state_blocks_every_commit(self):
        state, _ = new_state("daily", seed=2)
        npc = npcs(state)[0]
        state["characters"][npc]["age"] = 17
        err = rejected(state, commit("continue", [{"op": "npc_action", "npc_id": npc, "action": "抬头"}]))
        self.assertEqual(err.code, "SAFETY_BLOCK")

    def test_missing_age_is_an_invariant_violation(self):
        state, _ = new_state("daily", seed=2)
        npc = npcs(state)[0]
        del state["characters"][npc]["age"]
        err = rejected(state, commit("continue", [{"op": "npc_action", "npc_id": npc, "action": "抬头"}]))
        self.assertEqual(err.code, "INVARIANT_VIOLATION")

    def test_bool_age_and_non_str_adult_context_are_rejected(self):
        from adult_tension.domain import invariants, state_check
        from helpers.domain import content

        state, _ = new_state("daily", seed=2)
        npc = npcs(state)[0]
        state["characters"][npc]["age"] = True
        state["characters"][npc]["adult_context"] = 123
        inv_paths = {d["path"] for d in invariants.check(state)}
        self.assertIn("$.state.characters.%s.age" % npc, inv_paths)
        self.assertIn("$.state.characters.%s.adult_context" % npc, inv_paths)
        chk_paths = {d["path"] for d in state_check.check_state(state, content()["world"])}
        self.assertIn("$.characters.%s.age" % npc, chk_paths)
        self.assertIn("$.characters.%s.adult_context" % npc, chk_paths)


class RegressionP0P1Test(unittest.TestCase):
    def test_offscreen_beat_cannot_resolve_player_event_release_player_leverage_or_add_public_fact(self):
        from helpers.domain import content

        state, _ = new_state("pressure", seed=11)
        majors = sorted(c for c in npcs(state) if state["characters"][c]["tier"] == "major")
        a, b = majors[:2]
        here = state["scene"]["location_id"]
        elsewhere = next(loc["id"] for loc in content()["world"]["locations"] if loc["id"] != here)
        state, result = apply(
            state,
            commit(
                "result",
                [
                    {"op": "event_create", "kind": "opportunity", "title": "带玩家的机会", "participants": ["player", b], "in_minutes": 600, "dedupe_key": "t.p_opp"},
                    {"op": "leverage_set", "holder": "player", "subject": b, "basis_text": "玩家握着对方的把柄", "origin": "扣下凭证"},
                    {"op": "exit_scene", "character_id": b, "to_location_id": elsewhere},
                ],
                player_authorized=True,
            ),
        )
        eid = result["applied"][0]["event_id"]
        lid = result["applied"][1]["leverage_id"]
        skip90 = {"op": "advance_time", "minutes": 90}
        act_a = {"op": "npc_action", "npc_id": a, "action": "看表"}
        for sub in (
            {"op": "event_resolve", "event_id": eid, "outcome": "fulfilled", "note": "离屏私自了结"},
            {"op": "event_cancel", "event_id": eid, "reason": "离屏私自取消"},
            {"op": "leverage_release", "leverage_id": lid, "reason": "离屏私自解除"},
        ):
            beat = {"op": "offscreen_beat", "npc_id": b, "summary": "私下动作", "operations": [sub]}
            err = rejected(state, commit("continue", [skip90, beat, act_a]))
            self.assertIn("玩家角色", reasons(err))
        # P0-5: offscreen add_fact forbids visibility="public"
        pub_fact = {"op": "add_fact", "key": "b.secret", "text": "离屏密谋", "known_by": [b], "visibility": "public", "origin": "observed"}
        err = rejected(state, commit("continue", [skip90, {"op": "offscreen_beat", "npc_id": b, "summary": "密谋", "operations": [pub_fact]}, act_a]))
        self.assertIn("public", reasons(err))
        # P1: offscreen move to player's location must not pull NPC into scene["present"]
        move_sub = {"op": "move", "character_id": b, "location_id": here}
        after, _ = apply(state, commit("continue", [skip90, {"op": "offscreen_beat", "npc_id": b, "summary": "悄悄靠近", "operations": [move_sub]}, act_a]))
        self.assertNotIn(b, after["scene"]["present"])
        self.assertEqual(after["characters"][b]["status"]["location_id"], here)

    def test_false_fact_forbids_public_and_overlap(self):
        state, _ = new_state("daily", seed=5)
        a = npcs(state)[0]
        err = rejected(state, commit("continue", [{"op": "add_fact", "key": "f.pub", "text": "假消息", "truth": False, "believed_by": [a], "visibility": "public", "origin": "told"}]))
        self.assertIn("public", reasons(err))
        err = rejected(state, commit("continue", [{"op": "add_fact", "key": "f.ov", "text": "假消息", "truth": False, "known_by": [a], "believed_by": [a], "visibility": "private", "origin": "told"}]))
        self.assertIn("同时在 known_by 与 believed_by", reasons(err))

    def test_state_check_catches_bad_ids_chance_prob_prefs_leverage_schedule_and_counters(self):
        from adult_tension.domain import state_check
        from adult_tension.jsonio import copy
        from helpers.domain import content

        state, _ = new_state("pressure", seed=11)
        world = content()["world"]
        self.assertEqual(state_check.check_state(state, world), [])
        # Bad fact id does not raise ValueError
        bad_id = copy(state)
        bad_id["facts"]["bad_id"] = dict(next(iter(bad_id["facts"].values())), id="bad_id")
        errs = state_check.check_state(bad_id, world)
        self.assertIn("$.facts.bad_id", {e["path"] for e in errs})
        # Bad chance probability, preferences, leverage, schedule, counters.next
        broken = copy(state)
        broken["events"]["e99"] = {
            "id": "e99",
            "kind": "chance",
            "tier": "near",
            "title": "坏概率",
            "text": None,
            "participants": ["player"],
            "due": CL.add_minutes(broken["clock"], 60),
            "probability": None,
            "dedupe_key": "bad.chance",
            "state": "pending",
            "outcome": None,
            "created_turn": 1,
            "resolved_turn": None,
            "note": None,
            "coord": [1, 99],
        }
        broken["preferences"]["person"] = "fourth"
        broken["preferences"]["pace"] = "turbo"
        broken["preferences"]["explicitness"] = "wild"
        broken["preferences"]["npc_gender_preference"] = "aliens"
        fid = next(iter(broken["facts"]))
        npc = npcs(broken)[0]
        broken["leverage"]["lv1"] = {
            "id": "lv_wrong",
            "holder": "player",
            "subject": npc,
            "basis_fact_id": fid,
            "origin": "x",
            "state": "broken",
            "created_turn": 1,
            "released_turn": None,
            "release_reason": None,
        }
        broken["characters"][npc]["schedule"] = [{"from": 0, "to": 1500, "location_id": "no_such_loc"}]
        broken["counters"]["next"]["scene"] = 0
        paths = {e["path"] for e in state_check.check_state(broken, world)}
        for expected in (
            "$.events.e99.probability",
            "$.preferences.person",
            "$.preferences.pace",
            "$.preferences.explicitness",
            "$.preferences.npc_gender_preference",
            "$.leverage.lv1.id",
            "$.leverage.lv1.state",
            "$.characters.%s.schedule[0].to" % npc,
            "$.characters.%s.schedule[0].location_id" % npc,
            "$.counters.next.scene",
        ):
            self.assertIn(expected, paths)

    def test_standby_not_instantiated_on_pure_reference_or_error(self):
        from adult_tension.domain import opening
        from helpers.domain import content

        state, _ = new_state("daily", seed=17)
        npc = npcs(state)[0]
        standby_id = sorted(opening.standby_previews(state, content()["world"]))[0]
        err = rejected(state, commit("continue", [{"op": "npc_action", "npc_id": npc, "action": "提起某人", "target_id": standby_id}]))
        self.assertEqual(err.code, "NOT_FOUND")
        self.assertNotIn(standby_id, state["characters"])

    def test_exit_scene_clears_moved_on_same_turn_bounce(self):
        state, _ = new_state("daily", seed=17)
        npc = npcs(state)[0]
        here = state["scene"]["location_id"]
        target = next(loc for loc in _world_locations() if loc["id"] == here)["exits"][0]
        ops = [
            {"op": "move", "character_id": npc, "location_id": target},
            {"op": "move", "character_id": "player", "location_id": target},
            {"op": "exit_scene", "character_id": npc},
            {"op": "move", "character_id": "player", "location_id": here},
            {"op": "move", "character_id": "player", "location_id": target},
        ]
        new, _ = apply(state, commit("result", ops, player_authorized=True))
        self.assertNotIn(npc, new["scene"]["present"])

    def test_player_update_splits_name_and_checks_duplicate(self):
        from helpers.domain import content

        state, _ = new_state("daily", seed=17)
        npc = npcs(state)[0]
        err = rejected(state, commit("result", [{"op": "player_update", "name": state["characters"][npc]["name"]}], player_authorized=True))
        self.assertIn("已经有人叫", reasons(err))
        fam = content()["world"]["name_pools"]["family"][0]
        new, _ = apply(state, commit("result", [{"op": "player_update", "name": fam + "明远"}], player_authorized=True))
        self.assertEqual((new["characters"]["player"]["family"], new["characters"]["player"]["given"]), (fam, "明远"))

    def test_relationship_uses_reverse_edge_contact_and_inherits_stage(self):
        state, _ = new_state("daily", seed=9)
        npc = npcs(state)[0]
        state, _ = apply(state, commit("continue", [{"op": "exit_scene", "character_id": npc}]))
        del state["relationships"]["player>%s" % npc]
        state["relationships"]["%s>player" % npc]["stage"] = "familiar"
        new, _ = apply(state, commit("result", [{"op": "relationship", "from": "player", "to": npc, "trust_delta": 1, "reason": "回想起来觉得可靠"}], player_authorized=True))
        self.assertEqual(new["relationships"]["player>%s" % npc]["stage"], "familiar")

    def test_restore_drops_meta_voice_for_undone_newcomer(self):
        from adult_tension.domain import meta, state_check, turn
        from helpers.domain import content
        from test_people_safety import major_card

        before, _ = new_state("daily", seed=53)
        after, _ = apply(before, commit("continue", [major_card(cid="temp_vip")]))
        after, _ = meta.set_preferences(after, content(), {"voice": {"npc_id": "temp_vip", "voice": "inner"}})
        undone, _ = turn.undo(after, before)
        self.assertNotIn("temp_vip", undone["preferences"]["voice"])
        self.assertEqual(state_check.check_state(undone, content()["world"]), [])

    def test_offscreen_truth_propagation_corrects_misbelief(self):
        from adult_tension.domain import facts as FA
        from adult_tension.domain import settlement, simulation

        state, _ = new_state("pressure", seed=11)
        a, b = sorted(c for c in npcs(state) if state["characters"][c]["tier"] == "major")[:2]
        ops = [
            {"op": "add_fact", "key": "cargo.real", "text": "货箱里是假货", "truth": False, "believed_by": [b], "visibility": "private", "origin": "told"},
            {"op": "add_fact", "key": "cargo.real", "text": "货箱里是真货", "truth": True, "known_by": [a], "visibility": "private", "origin": "observed", "spread": True},
        ]
        state, result = apply(state, commit("continue", ops))
        false_id, true_id = result["applied"][0]["fact_id"], result["applied"][1]["fact_id"]
        # Advance repeatedly until true fact propagates to b (deterministic seed)
        work = FA.working_copy(state)
        for step in range(1, 10):
            settlement.advance(work, 1440, work["turn"] + step, simulation.hooks(work["turn"] + step))
            if b in work["facts"][true_id]["known_by"]:
                break
            FA.edit(work, true_id)["spreading"] = True
            FA.edit(work, true_id)["spread_hops"] = 0
        self.assertIn(b, work["facts"][true_id]["known_by"])
        self.assertNotIn(b, work["facts"][false_id]["believed_by"])
        self.assertIn(b, work["facts"][false_id]["known_by"])

    def test_twist_accept_allows_attempt_mode(self):
        state, _ = new_state("pressure", seed=11)
        a = sorted(c for c in npcs(state) if state["characters"][c]["tier"] == "major")[0]
        state, _ = apply(state, commit("continue", [{"op": "advance_time", "until": "next_morning"}, {"op": "npc_action", "npc_id": a, "action": "看表"}]))
        chosen = state["requests"]["twist_offer"][0]
        new, res = apply(
            state,
            commit("attempt", [{"op": "twist_accept", "twist_id": chosen["id"]}], acts_on=[], player_authorized=True, chapter_summary="第一夜。"),
        )
        self.assertEqual(res["twist"]["twist_id"], chosen["id"])


class RegressionP2DomainTest(unittest.TestCase):
    def test_state_check_each_preserves_original_index_and_invariants_prefix(self):
        from adult_tension.domain import invariants, state_check
        from adult_tension.jsonio import copy
        from helpers.domain import content

        state, _ = new_state("daily", seed=11)
        world = content()["world"]
        npc = npcs(state)[0]
        # c.each keeps original index even when earlier item fails shape validation
        bad = copy(state)
        bad["characters"][npc]["status"]["conditions"] = [
            "not-a-dict",
            {"kind": "bogus_kind", "text": "怪状况", "until": None},
        ]
        bad["scene"]["responses"] = [
            "not-a-dict",
            {"turn": 1, "npc_id": npc, "response": "bogus_resp", "note": "怪回应"},
        ]
        bad["characters"][npc]["schedule"] = [
            "not-a-dict",
            {"from": 0, "to": 1500, "location_id": "no_loc"},
        ]
        paths = {e["path"] for e in state_check.check_state(bad, world)}
        self.assertIn("$.characters.%s.status.conditions[1].kind" % npc, paths)
        self.assertIn("$.scene.responses[1].response", paths)
        self.assertIn("$.characters.%s.schedule[1].to" % npc, paths)
        # state_check calls invariants with prefix="$" (no double $.state prefix)
        underage = copy(state)
        underage["characters"][npc]["age"] = 16
        inv_default = {e["path"] for e in invariants.check(underage)}
        inv_root = {e["path"] for e in invariants.check(underage, prefix="$")}
        chk = {e["path"] for e in state_check.check_state(underage, world)}
        self.assertIn("$.state.characters.%s.age" % npc, inv_default)
        self.assertIn("$.characters.%s.age" % npc, inv_root)
        self.assertIn("$.characters.%s.age" % npc, chk)
        self.assertFalse(any(p.startswith("$.state.") for p in chk))
        # counters.next equal to max used ID reports "小于或等于"
        eq_next = copy(state)
        max_fid = max(int(fid[1:]) for fid in eq_next["facts"])
        eq_next["counters"]["next"]["fact"] = max_fid
        errs = state_check.check_state(eq_next, world)
        self.assertTrue(any(e["path"] == "$.counters.next.fact" and "小于或等于" in e["reason"] for e in errs), errs)

    def test_continue_wait_reject_nonempty_acts_on_and_rewrite_hint_includes_offscreen_beat(self):
        from adult_tension.domain import turn as T

        state, _ = new_state("daily", seed=11)
        npc = npcs(state)[0]
        for mode in ("continue", "wait"):
            err = rejected(state, commit(mode, [{"op": "npc_action", "npc_id": npc, "action": "看表"}], acts_on=[npc]))
            self.assertIn("$.acts_on", [d["path"] for d in err.details])
            apply(state, commit(mode, [{"op": "npc_action", "npc_id": npc, "action": "看表"}], acts_on=[]))
        # rewrite disallowed op hint lists offscreen_beat
        err = rejected(
            state,
            commit("rewrite", [{"op": "relationship", "from": npc, "to": "player", "trust_delta": 1, "reason": "r"}], player_authorized=True),
        )
        self.assertIn("offscreen_beat", err.details[0]["hint"])
        # M16 wording alignment
        self.assertIn("含玩家时须填入 player", T.commit_fields()["intimate_participants"].desc)
        err = rejected(state, commit("result", [], player_authorized=True, tags=["intimate"], intimate_participants=["player"]))
        self.assertIn("含玩家时须填入 player", reasons(err))

    def test_dedupe_key_forbids_hash_archived_wording_and_ops_descriptions(self):
        from adult_tension import schema
        from adult_tension.domain import ops, ops_time, turn
        from helpers.domain import COMMIT

        state, _ = new_state("pressure", seed=13)
        npc = npcs(state)[0]
        raw = {
            "action_mode": "continue",
            "player_input": "",
            "operations": [{"op": "event_create", "kind": "opportunity", "title": "绕过去重", "participants": [npc], "in_minutes": 60, "dedupe_key": "t.dup#2"}],
            "content_tags": [],
            "summary": "s",
            "open_action": "o",
        }
        _out, errors = schema.validate(COMMIT, raw)
        self.assertIn("$.operations[0].dedupe_key", [e["path"] for e in errors])
        # Undone event ID reports "已归档或已撤销"
        after, res = apply(state, commit("continue", [{"op": "event_create", "kind": "opportunity", "title": "短机会", "participants": [npc], "in_minutes": 60, "dedupe_key": "t.undo_ev"}]))
        eid = res["applied"][0]["event_id"]
        undone, _ = turn.undo(after, state)
        err = rejected(undone, commit("continue", [{"op": "event_cancel", "event_id": eid, "reason": "取消"}]))
        self.assertIn("已归档或已撤销", reasons(err))
        # No dead attributes on TurnContext
        from helpers.domain import content

        ctx = ops.TurnContext(state, content()["world"], commit("continue", []))
        self.assertFalse(hasattr(ctx, "relationship_reasons"))
        self.assertFalse(hasattr(ctx, "voice_reasons"))
        # Descriptions updated
        self.assertIn("覆盖旧记录", ops.DESCRIPTIONS["npc_state"])
        self.assertIn("双向", ops.DESCRIPTIONS["relationship"])
        self.assertIn("两名 NPC", ops.DESCRIPTIONS["relationship"])
        beat_desc = ops.DESCRIPTIONS["offscreen_beat"]
        self.assertNotIn("`", beat_desc)
        self.assertIn("requests.offscreen_beat_candidates", beat_desc)
        self.assertIn("advance_time 之后", beat_desc)
        for allowed_op in ops_time.BEAT_OPS:
            self.assertIn(allowed_op, beat_desc)

    def test_rng_clock_facts_and_dead_code_cleanup(self):
        import math
        from unittest import mock

        from adult_tension.domain import facts as FA
        from adult_tension.domain import state as SS
        from adult_tension.domain import structure as ST

        # rng.unit clamps 1.0 rounding edge case to nextafter(1.0, 0.0)
        fake_hash = mock.Mock()
        fake_hash.digest.return_value = b"\xff" * 32
        with mock.patch("adult_tension.domain.rng.hashlib.sha256", return_value=fake_hash):
            val = rng.unit(1, "edge")
        self.assertLess(val, 1.0)
        self.assertEqual(val, math.nextafter(1.0, 0.0))
        # clock.cn_number handles 0..99, >=100, and rejects negative
        self.assertEqual(CL.cn_number(0), "零")
        self.assertEqual(CL.cn_number(99), "九十九")
        self.assertEqual(CL.cn_number(100), "100")
        with self.assertRaises(ValueError):
            CL.cn_number(-1)
        # facts.player_ranked with limit=0 returns [] for both DictSource and FactView
        state, _ = new_state("daily", seed=5)
        ds = FA.DictSource(state["facts"])
        fv = FA.FactView(state["facts"])
        self.assertEqual(ds.player_ranked("player", ["player"], [], 1, limit=0), [])
        self.assertEqual(fv.player_ranked("player", ["player"], [], 1, limit=0), [])
        # Dead symbols removed
        self.assertFalse(hasattr(ST, "MAX_FIX_ATTEMPTS"))
        self.assertFalse(hasattr(SS, "info_set"))


if __name__ == "__main__":
    unittest.main()
