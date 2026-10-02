"""Stage 2 rules: knowledge, voice, cards, new characters, leverage, intimacy, safety."""

import re
import unittest

import _bootstrap  # noqa: F401
from adult_tension.domain import meta
from adult_tension.projections import status as STATUS
from helpers.domain import apply, commit, content, new_state, npcs, rejected


def reasons(err):
    return " | ".join(d["reason"] for d in err.details)


def major_card(cid="new_face", name="区嘉言", age=31, gender="female", **extra):
    card = {
        "op": "introduce_character",
        "id": cid,
        "name": name,
        "tier": "major",
        "age": age,
        "gender": gender,
        "adult_context": "码头新调来的成年调度员",
        "public_role": "夜班调度",
        "appearance": "袖口总是卷得整整齐齐",
        "identity": {"authority": "排吊装顺序", "resources": ["六频道"], "limits": ["刚来，谁都不认识"], "exposure_risk": "档案里少了一页", "hidden_mismatch": "其实会说三种方言"},
        "decision": {
            "core_value": "先站稳脚跟",
            "current_goal": "摸清谁说了算",
            "pressure_responses": {"low": "装糊涂", "mid": "讲条件", "high": "找人撑腰", "breaking": "直接走人"},
            "withdrawal": "只在对讲机里说话",
            "relationship_stance": "谁先示好就先信谁三分",
            "contrast": "看着冷，其实怕寂寞",
            "prefers": ["说清楚"],
            "avoids": ["欠人情"],
            "never": ["出卖同事"],
        },
        "intimacy": {
            "desire_level": 2,
            "attraction_sources": ["对方守信", "对方不拿身份压人"],
            "likes": ["慢"],
            "dislikes": ["被试探"],
            "preconditions": ["不在当班时"],
            "boundaries": ["不在控制塔里"],
            "expression": "递一杯茶",
            "self_control": 4,
            "desired_position": "平等",
        },
        "voices": {"surface": "“下一个。”", "inner": "“别走。”"},
        "situation": {"trigger": "刚调来就被人盯上", "pressure": "站错队就要被调走", "exits": [{"option": "低头做事", "cost": "被当成软柿子"}, {"option": "找靠山", "cost": "欠一个大人情"}]},
    }
    card.update(extra)
    return card


class KnowledgeTravelTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=41)
        self.a, self.b = npcs(self.state)[:2]
        self.secret = next(f for f in self.state["facts"].values() if f["known_by"] == [self.a])

    def test_reveal_along_edges_to_people_present(self):
        op = {"op": "reveal_fact", "fact_id": self.secret["id"], "from": self.a, "to": ["player"]}
        new, result = apply(self.state, commit("continue", [op]))
        self.assertIn("player", new["facts"][self.secret["id"]]["known_by"])
        not_knower = dict(op, **{"from": self.b})
        err = rejected(self.state, commit("continue", [not_knower]))
        self.assertIn("并不知道", reasons(err))

    def test_reveal_needs_a_relationship_edge(self):
        del self.state["relationships"]["%s>%s" % (self.a, self.b)]
        del self.state["relationships"]["%s>%s" % (self.b, self.a)]
        err = rejected(self.state, commit("continue", [{"op": "reveal_fact", "fact_id": self.secret["id"], "from": self.a, "to": [self.b]}]))
        self.assertIn("关系边", reasons(err))

    def test_inner_facts_never_travel(self):
        inner = {"op": "add_fact", "key": "a.inner", "text": "心里其实很怕", "visibility": "inner", "origin": "observed", "known_by": [self.a]}
        state, result = apply(self.state, commit("continue", [inner]))
        fid = result["applied"][0]["fact_id"]
        err = rejected(state, commit("continue", [{"op": "reveal_fact", "fact_id": fid, "from": self.a, "to": ["player"]}]))
        self.assertIn("内心", reasons(err))
        err = rejected(state, commit("continue", [{"op": "spread_rumor", "from": self.a, "source_fact_id": fid, "key": "x.y", "text": "听说", "believed_by": [self.b]}]))
        self.assertIn("内心", reasons(err))

    def test_truth_reveal_corrects_a_misbelief(self):
        false = {"op": "add_fact", "key": "box.content", "text": "柜子里装的是旧轮胎", "truth": False, "believed_by": [self.b], "visibility": "private", "origin": "told"}
        true = {"op": "add_fact", "key": "box.content", "text": "柜子里装的是走私表", "visibility": "private", "origin": "observed", "known_by": [self.a]}
        state, result = apply(self.state, commit("continue", [false, true]))
        false_id, true_id = result["applied"][0]["fact_id"], result["applied"][1]["fact_id"]
        new, result = apply(state, commit("continue", [{"op": "reveal_fact", "fact_id": true_id, "from": self.a, "to": [self.b]}]))
        self.assertEqual(result["applied"][0]["corrected"], [{"character_id": self.b, "false_fact_id": false_id}])
        self.assertNotIn(self.b, new["facts"][false_id]["believed_by"])
        self.assertIn(self.b, new["facts"][true_id]["known_by"])

    def test_rumor_is_a_new_false_fact_and_the_original_is_untouched(self):
        before = dict(self.secret)
        op = {"op": "spread_rumor", "from": self.a, "source_fact_id": self.secret["id"], "key": "rumor.a", "text": "有人说那个人早就想走", "believed_by": [self.b]}
        new, result = apply(self.state, commit("continue", [op]))
        rumor = new["facts"][result["applied"][0]["fact_id"]]
        self.assertEqual((rumor["truth"], rumor["origin"]), (False, "rumor"))
        self.assertEqual(new["facts"][self.secret["id"]], before)

    def test_distorted_channels_reach_people_without_edges_but_exact_ones_do_not_distort(self):
        absent = next(c for c in self.state["characters"] if c not in self.state["scene"]["present"])
        op = {"op": "spread_rumor", "from": self.a, "key": "rumor.far", "text": "码头要裁人", "believed_by": [absent], "channel_id": "ch_teahouse"}
        apply(self.state, commit("continue", [op]))
        err = rejected(self.state, commit("continue", [dict(op, channel_id="ch_radio")]))
        self.assertIn("精确渠道", reasons(err))
        err = rejected(self.state, commit("continue", [dict(op, channel_id=None)]))
        self.assertIn("关系边", reasons(err))


class VoiceTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=43)
        self.a, self.b = npcs(self.state)[:2]

    def test_npc_self_switch_needs_a_real_trigger(self):
        op = {"op": "set_voice", "npc_id": self.a, "voice": "inner", "cause": "npc_self", "trigger": "alone", "note": "终于只剩两个人"}
        err = rejected(self.state, commit("continue", [op]))
        self.assertIn("独处", reasons(err))
        state, _ = apply(self.state, commit("continue", [{"op": "exit_scene", "character_id": self.b}]))
        state, _ = apply(state, commit("continue", [op]))
        self.assertEqual(state["preferences"]["voice"][self.a]["voice"], "inner")
        rejected(self.state, commit("continue", [dict(op, trigger="drunk")]))
        rejected(self.state, commit("continue", [dict(op, trigger=None)]))

    def test_player_request_wins_and_voice_is_not_escalation(self):
        ask = {"op": "set_voice", "npc_id": self.a, "voice": "inner", "cause": "player_request", "note": "玩家说别装了"}
        state, _ = apply(self.state, commit("attempt", [ask, {"op": "npc_response", "npc_id": self.a, "response": "refuse", "note": "换了语气，还是说不"}], acts_on=[self.a], player_authorized=True))
        edge_before = self.state["relationships"]["%s>player" % self.a]
        edge_after = state["relationships"]["%s>player" % self.a]
        self.assertEqual((edge_before["trust"], edge_before["tension"], edge_before["stage"]), (edge_after["trust"], edge_after["tension"], edge_after["stage"]))
        revert = {"op": "set_voice", "npc_id": self.a, "voice": "surface", "cause": "revert", "note": "情绪过去了"}
        err = rejected(state, commit("continue", [revert]))
        self.assertIn("玩家要求", reasons(err))

    def test_voice_and_relationship_cannot_share_a_reason(self):
        ops = [
            {"op": "set_voice", "npc_id": self.a, "voice": "inner", "cause": "player_request", "note": "玩家戳破了面具"},
            {"op": "npc_response", "npc_id": self.a, "response": "partial", "note": "肯说一点"},
            {"op": "relationship", "from": self.a, "to": "player", "tension_delta": 1, "reason": "玩家戳破了面具"},
        ]
        err = rejected(self.state, commit("attempt", ops, acts_on=[self.a], player_authorized=True))
        self.assertIn("同一条原因", reasons(err))


class CardEvolutionTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=47)
        self.a = npcs(self.state)[0]

    def evidence(self, **kw):
        base = {"op": "intimacy_evidence", "npc_id": self.a, "item": "likes", "direction": "add", "value": "被人记住口味", "evidence": "玩家记得"}
        base.update(kw)
        return base

    def test_two_distinct_turns_are_needed(self):
        state, r1 = apply(self.state, commit("continue", [self.evidence()]))
        self.assertFalse(r1["applied"][0]["changed"])
        state, r2 = apply(state, commit("continue", [self.evidence(evidence="又一次")]))
        self.assertTrue(r2["applied"][0]["changed"])
        self.assertIn("被人记住口味", state["characters"][self.a]["intimacy"]["likes"])

    def test_same_turn_evidence_counts_once_and_whole_card_rewrites_are_refused(self):
        state, result = apply(self.state, commit("continue", [self.evidence(), self.evidence(evidence="同一回合第二条")]))
        self.assertEqual(result["applied"][1]["evidence_count"], 1)
        three = [self.evidence(), self.evidence(item="dislikes", value="被催"), self.evidence(item="desire_level", direction="increase", value=None)]
        err = rejected(self.state, commit("continue", three))
        self.assertIn("最多改 2 项", reasons(err))

    def test_relaxing_a_boundary_needs_three(self):
        boundary = self.state["characters"][self.a]["intimacy"]["boundaries"][0]
        op = self.evidence(item="boundaries", direction="remove", value=boundary)
        state = self.state
        for expected in (False, False, True):
            state, result = apply(state, commit("continue", [op]))
            self.assertEqual(result["applied"][0]["changed"], expected)
        self.assertNotIn(boundary, state["characters"][self.a]["intimacy"]["boundaries"])

    def test_numeric_items_are_bounded_not_clamped(self):
        self.state["characters"][self.a]["intimacy"]["self_control"] = 5
        err = rejected(self.state, commit("continue", [self.evidence(item="self_control", direction="increase", value=None)]))
        self.assertIn("到头", reasons(err))

    def test_identity_evolves_item_by_item(self):
        op = {"op": "identity_update", "npc_id": self.a, "item": "resources", "action": "add", "value": "一把备用钥匙", "reason": "师傅给的"}
        state, _ = apply(self.state, commit("continue", [op]))
        self.assertIn("一把备用钥匙", state["characters"][self.a]["identity"]["resources"])
        rejected(self.state, commit("continue", [dict(op, action="set")]))


class NewCharacterTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=53)

    def test_underage_introduction_is_a_safety_block(self):
        err = rejected(self.state, commit("continue", [major_card(age=17)]))
        self.assertEqual(err.code, "SAFETY_BLOCK")
        # the introduction check itself fires (not only the invariant net)
        self.assertIn("$.operations[0].age", [d["path"] for d in err.details])

    def test_missing_age_cannot_create_a_character(self):
        from adult_tension import schema
        from helpers.domain import COMMIT

        card = major_card()
        del card["age"]
        raw = {"action_mode": "continue", "player_input": "", "operations": [card], "content_tags": [], "summary": "s", "open_action": "o"}
        _out, errors = schema.validate(COMMIT, raw)
        self.assertIn("$.operations[0].age", [e["path"] for e in errors])

    def test_major_introduction_needs_the_full_card(self):
        card = major_card()
        del card["intimacy"]
        del card["decision"]["withdrawal"]
        err = rejected(self.state, commit("continue", [card]))
        paths = {d["path"] for d in err.details}
        self.assertIn("$.operations[0].intimacy", paths)
        self.assertIn("$.operations[0].decision.withdrawal", paths)
        new, result = apply(self.state, commit("continue", [major_card()]))
        self.assertIn("new_face", new["scene"]["present"])
        self.assertEqual(result["new_characters"], ["new_face"])

    def test_names_come_from_the_pool_and_families_do_not_repeat(self):
        err = rejected(self.state, commit("continue", [major_card(name="司马懿")]))
        self.assertIn("名字池", reasons(err))
        taken = next(c["family"] for c in self.state["characters"].values() if c["tier"] == "major" and c["id"] != "player")
        err = rejected(self.state, commit("continue", [major_card(name=taken + "海宁")]))
        self.assertIn("已经有人姓", reasons(err))

    def test_world_ids_and_existing_ids_are_never_reused(self):
        err = rejected(self.state, commit("continue", [major_card(cid="player")]))
        self.assertIn("已被使用", reasons(err))
        err = rejected(self.state, commit("continue", [major_card(cid="bg_patrol")]))
        self.assertIn("已被使用", reasons(err))

    def test_gender_preference_applies_to_new_characters(self):
        state, _ = new_state("daily", seed=53, npc_gender_preference="female_only")
        err = rejected(state, commit("continue", [major_card(gender="male", name="冯志强")]))
        self.assertIn("配对偏好", reasons(err))
        apply(state, commit("continue", [major_card(gender="male", name="冯志强", gender_reason="剧情需要一位男性调度")]))

    def test_promotion_goes_up_keeps_the_id_and_fills_fields(self):
        bg = next(c for c in self.state["characters"].values() if c["tier"] == "background")
        card = major_card()
        promo = {"op": "promote_character", "character_id": bg["id"], "to_tier": "major"}
        promo.update({k: card[k] for k in ("appearance", "identity", "decision", "intimacy", "voices", "situation")})
        new, _ = apply(self.state, commit("continue", [promo]))
        self.assertEqual(new["characters"][bg["id"]]["tier"], "major")
        down = {"op": "promote_character", "character_id": bg["id"], "to_tier": "supporting"}
        err = rejected(new, commit("continue", [down]))
        self.assertIn("只升不降", reasons(err))
        partial = dict(promo)
        del partial["voices"]
        err = rejected(self.state, commit("continue", [partial]))
        self.assertIn("$.operations[0].voices", {d["path"] for d in err.details})

    def test_identity_is_created_once(self):
        major = npcs(self.state)[0]
        self.state["characters"][major]["tier"] = "supporting"
        card = major_card()
        promo = {"op": "promote_character", "character_id": major, "to_tier": "major", "identity": card["identity"]}
        err = rejected(self.state, commit("continue", [promo]))
        self.assertIn("只能逐项演化", reasons(err))


class LeverageAndIntimacyTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=59)
        self.a, self.b = npcs(self.state)[:2]

    def intimate(self, ops=None, mode="attempt", participants=None, tags=("intimate",), **kw):
        ops = ops if ops is not None else [{"op": "npc_response", "npc_id": self.a, "response": "genuine", "note": "靠了过来"}]
        return commit(mode, ops, acts_on=[self.a], player_authorized=True, tags=list(tags), intimate_participants=participants or ["player", self.a], **kw)

    def test_a_valid_intimate_step(self):
        apply(self.state, self.intimate())

    def test_structural_checks_each_reject(self):
        err = rejected(self.state, self.intimate(ops=[{"op": "npc_response", "npc_id": self.a, "response": "negotiate", "note": "先谈条件"}]))
        self.assertIn("partial/genuine", reasons(err))
        err = rejected(self.state, self.intimate(participants=["player"]))
        self.assertIn("参与者", reasons(err))
        bg = next(c for c in self.state["characters"].values() if c["tier"] == "background")
        err = rejected(self.state, self.intimate(participants=["player", self.a, bg["id"]]))
        self.assertIn("不是重要角色", reasons(err))
        self.state["characters"][self.a]["status"]["conditions"].append({"kind": "drunk", "text": "醉了", "until": None, "since_turn": 1})
        err = rejected(self.state, self.intimate())
        self.assertIn("醉了", reasons(err))

    def test_participants_age_is_checked_by_the_intimacy_gate(self):
        self.state["characters"][self.a]["age"] = 17
        err = rejected(self.state, self.intimate())
        self.assertEqual(err.code, "SAFETY_BLOCK")
        self.assertIn("$.intimate_participants[1]", [d["path"] for d in err.details])
        del self.state["characters"][self.a]["age"]
        err = rejected(self.state, self.intimate())
        self.assertIn("年龄不明确", reasons(err))
        self.assertIn("$.intimate_participants[1]", [d["path"] for d in err.details])

    def test_absent_participant_and_player_consent_outside_player_modes(self):
        state, _ = apply(self.state, commit("continue", [{"op": "exit_scene", "character_id": self.b}]))
        err = rejected(state, self.intimate(ops=[{"op": "npc_response", "npc_id": self.a, "response": "genuine", "note": "好"}], participants=["player", self.a, self.b]))
        self.assertIn("不在场", reasons(err))
        err = rejected(self.state, commit("continue", [{"op": "npc_action", "npc_id": self.a, "action": "靠近"}], tags=["intimate"], intimate_participants=["player", self.a]))
        self.assertIn("玩家角色的同意", reasons(err))

    def test_leverage_blocks_intimacy_even_if_released_in_the_same_commit(self):
        secret = next(f for f in self.state["facts"].values() if f["known_by"] == [self.a])
        lever = {"op": "leverage_set", "holder": self.b, "subject": self.a, "basis_fact_id": secret["id"], "origin": "偷看到了"}
        err = rejected(self.state, commit("continue", [lever]))
        self.assertIn("不知道这件事", reasons(err))
        player_secret = next(f for f in self.state["facts"].values() if f["key"] == "player.baseline")
        lever = {"op": "leverage_set", "holder": self.a, "subject": "player", "basis_text": "%s撞见了玩家收红包" % self.state["characters"][self.a]["name"], "origin": "撞见"}
        state, result = apply(self.state, commit("continue", [lever, {"op": "npc_action", "npc_id": self.a, "action": "意味深长地笑"}]))
        lid = result["applied"][0]["leverage_id"]
        err = rejected(state, self.intimate())
        self.assertIn("处境不是同意", " ".join(d["hint"] or "" for d in err.details) + reasons(err))
        release = {"op": "leverage_release", "leverage_id": lid, "reason": "当着面把账本烧了"}
        err = rejected(state, self.intimate(ops=[release, {"op": "npc_response", "npc_id": self.a, "response": "genuine", "note": "靠了过来"}]))
        self.assertIn("把柄", reasons(err))
        released, _ = apply(state, commit("continue", [release, {"op": "npc_action", "npc_id": self.a, "action": "烧掉账本"}]))
        apply(released, self.intimate())
        del player_secret

    def test_player_as_holder_needs_the_players_own_command(self):
        secret = next(f for f in self.state["facts"].values() if f["key"] == "player.baseline")
        lever = {"op": "leverage_set", "holder": "player", "subject": self.a, "basis_text": "玩家知道对方的底细", "origin": "威胁"}
        err = rejected(self.state, commit("continue", [lever, {"op": "npc_action", "npc_id": self.a, "action": "愣住"}]))
        self.assertIn("玩家本人", reasons(err))
        del secret

    def test_no_consent_carries_over_to_the_next_commit(self):
        state, _ = apply(self.state, self.intimate())
        err = rejected(state, self.intimate(ops=[{"op": "npc_action", "npc_id": self.b, "action": "咳嗽"}]))
        self.assertIn("没有 partial/genuine", reasons(err))


class SafetyTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("daily", seed=61)
        self.a = npcs(self.state)[0]
        self.content = content()

    def test_boundaries_block_matching_tags(self):
        state, result = meta.set_boundary(self.state, self.content, "add", "不要涉及怀孕", ["pregnancy"])
        self.assertEqual(result["receipt"], "已记下：不会出现涉及怀孕")
        err = rejected(state, commit("continue", [{"op": "npc_action", "npc_id": self.a, "action": "提起孩子"}], tags=["pregnancy"]))
        self.assertEqual(err.code, "SAFETY_BLOCK")
        apply(state, commit("continue", [{"op": "npc_action", "npc_id": self.a, "action": "聊天气"}]))
        removed, _ = meta.set_boundary(state, self.content, "remove", text="不要涉及怀孕")
        apply(removed, commit("continue", [{"op": "npc_action", "npc_id": self.a, "action": "提起孩子"}], tags=["pregnancy"]))

    def test_boundary_on_intimacy_blocks_intimate_scenes(self):
        state, _ = meta.set_boundary(self.state, self.content, "add", "不要亲密场景", ["intimate", "explicit"])
        ops = [{"op": "npc_response", "npc_id": self.a, "response": "genuine", "note": "靠近"}]
        err = rejected(state, commit("attempt", ops, acts_on=[self.a], player_authorized=True, tags=["intimate"], intimate_participants=["player", self.a]))
        self.assertEqual(err.code, "SAFETY_BLOCK")
        self.assertIn("不要亲密场景", reasons(err))

    def test_custom_boundary_is_kept_verbatim_and_shown_in_context(self):
        state, result = meta.set_boundary(self.state, self.content, "add", "不要写到海里的东西", [])
        self.assertEqual(result["boundary"]["tags"], ["custom"])
        from adult_tension.projections import context as CX

        self.assertIn("不要写到海里的东西", CX.brief(state, self.content)["safety"]["boundaries"])

    def test_pause_blocks_intimacy_and_conflict_but_not_plot(self):
        state, _ = meta.set_safety(self.state, True)
        for tag in ("intimate", "violence", "humiliation"):
            ops = [{"op": "npc_response", "npc_id": self.a, "response": "genuine", "note": "好"}]
            extra = {"intimate_participants": ["player", self.a]} if tag == "intimate" else {}
            err = rejected(state, commit("attempt", ops, acts_on=[self.a], player_authorized=True, tags=[tag], **extra))
            self.assertEqual(err.code, "SAFETY_BLOCK", tag)
        apply(state, commit("continue", [{"op": "npc_action", "npc_id": self.a, "action": "收拾桌子"}]))

    def test_change_scene_keeps_pause_and_resume_clears_judgments(self):
        state, _ = apply(self.state, commit("attempt", [{"op": "npc_response", "npc_id": self.a, "response": "partial", "note": "只肯一半"}], acts_on=[self.a], player_authorized=True))
        paused, _ = meta.set_safety(state, True)
        moved, result = meta.set_safety(paused, True, change_scene=True)
        self.assertTrue(moved["safety"]["paused"])
        self.assertNotEqual(moved["scene"]["id"], paused["scene"]["id"])
        self.assertEqual(moved["scene"]["responses"], [])
        resumed, _ = meta.set_safety(paused, False)
        self.assertFalse(resumed["safety"]["paused"])
        self.assertEqual(resumed["scene"]["responses"], [])
        again, result = meta.set_safety(paused, True)
        self.assertIsNone(again)

    def test_preferences_and_player_requested_voice(self):
        state, result = meta.set_preferences(self.state, self.content, {"inner_view": True, "person": "third", "voice": {"npc_id": self.a, "voice": "inner"}})
        self.assertTrue(state["preferences"]["inner_view"])
        self.assertEqual(state["preferences"]["voice"][self.a]["cause"], "player_request")
        self.assertIn("内心可见：开", result["receipt"])
        self.assertEqual(state["revision"], self.state["revision"] + 1)
        self.assertEqual(state["turn"], self.state["turn"])


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.state, _ = new_state("pressure", seed=67)
        self.content = content()

    def test_six_plain_lines_without_field_names_or_relationship_numbers(self):
        lines = STATUS.lines(self.state, self.content)
        self.assertEqual(len(lines), 6)
        text = "".join(lines)
        for word in ("trust", "tension", "revision", "stage", "npc_", "_id"):
            self.assertNotIn(word, text)
        relation_line = lines[2]
        self.assertIsNone(re.search(r"[-+]?\d", relation_line))

    def test_foreshadows_are_not_on_the_players_todo_list(self):
        far = next(e for e in self.state["events"].values() if e["tier"] == "far")
        text = "".join(STATUS.lines(self.state, self.content))
        self.assertNotIn(far["title"], text)
        near = next(e for e in self.state["events"].values() if e["tier"] == "near")
        self.assertIn(near["title"], text)

    def test_detail_lists_only_what_the_player_knows(self):
        sections = STATUS.detail_sections(self.state, self.content)
        secrets = next(s for s in sections if s["title"] == "你知道的秘密")["items"]
        hidden = [f["text"] for f in self.state["facts"].values() if "player" not in f["known_by"] and "player" not in f["believed_by"]]
        self.assertTrue(hidden)
        for text in hidden:
            self.assertNotIn(text, secrets)


if __name__ == "__main__":
    unittest.main()


class NameOrderTest(unittest.TestCase):
    """name_pools.order given_first: names read 名·姓 at the opening and for newcomers."""

    def setUp(self):
        import copy

        from adult_tension.domain import opening, turn, worldpack
        from helpers.domain import STORE, WORLD

        self.turn = turn
        world = copy.deepcopy(STORE.world(WORLD))
        world["name_pools"].update(order="given_first", family=["米勒", "罗斯", "卡特", "黑尔", "韦伯", "福斯", "霍尔", "格林", "贝克", "奥康", "斯通", "莱尔"])
        pack, problems = worldpack.validate_world(world, tag_ids={t["id"] for t in STORE.tags()["tags"]})
        self.assertEqual(problems, [])
        self.world = pack
        self.content = dict(content(), world=pack)
        conditions = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}})
        self.state, _ = opening.build(pack, 5, conditions, "test")
        self.state["session_id"] = "s_test"

    def test_opening_names_put_the_given_name_first(self):
        for cid, char in self.state["characters"].items():
            self.assertIn(char["family"], self.world["name_pools"]["family"], cid)
            self.assertEqual(char["name"], char["given"] + "·" + char["family"], cid)

    def test_a_newcomer_takes_the_same_order(self):
        taken = {c["family"] for c in self.state["characters"].values()}
        family = next(f for f in self.world["name_pools"]["family"] if f not in taken)
        good = major_card(name="艾达·" + family)
        new, _ = self.turn.commit_turn(self.state, self.content, commit("continue", [good]))
        self.assertEqual((new["characters"]["new_face"]["family"], new["characters"]["new_face"]["given"]), (family, "艾达"))
        with self.assertRaises(Exception) as caught:
            self.turn.commit_turn(self.state, self.content, commit("continue", [major_card(name=family + "艾达")]))
        self.assertIn("姓不在本世界", reasons(caught.exception))
        self.assertIn("·", " ".join(d.get("hint") or "" for d in caught.exception.details))
