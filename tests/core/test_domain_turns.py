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

    def test_values_are_never_clamped(self):
        self.state["relationships"]["%s>player" % self.npc]["trust"] = 5
        err = rejected(self.state, commit("continue", [self.rel(trust_delta=1)]))
        self.assertIn("超出", reasons(err))

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
        expected = "hit" if rng.unit(state["seed"], "event", eid) < 0.5 else "miss"
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


if __name__ == "__main__":
    unittest.main()
