"""Opening generation: determinism, constraints, player settings, safety."""

import copy
import unittest

import _bootstrap  # noqa: F401
from adult_tension.domain import opening
from adult_tension.domain.opening_checks import check_opening
from adult_tension.errors import AppError
from helpers.domain import STORE, WORLD, new_state, state_digest

PACK = STORE.world(WORLD)


def build(mode="daily", seed=1, **request):
    request = dict(request, mode=mode)
    request["locks"] = dict(request.get("locks") or {}, world_id=WORLD)
    conditions = opening.normalize_conditions(request)
    return opening.build(PACK, seed, conditions, "test")


class DeterminismTest(unittest.TestCase):
    def test_same_seed_and_conditions_give_the_same_opening(self):
        for mode in ("daily", "pressure"):
            a, pa = build(mode, 77, excludes={"content_tags": ["crime"]}, npc_gender_preference="mostly_female")
            b, pb = build(mode, 77, excludes={"content_tags": ["crime"]}, npc_gender_preference="mostly_female")
            self.assertEqual(state_digest(a), state_digest(b))
            self.assertEqual(pa, pb)

    def test_conditions_are_part_of_the_seed(self):
        a, _ = build("daily", 77)
        b, _ = build("daily", 77, npc_gender_preference="male_only")
        self.assertNotEqual(state_digest(a), state_digest(b))

    def test_fixed_seed_openings_are_structurally_valid(self):
        for mode in ("daily", "pressure"):
            for seed in range(1, 11):
                state, payload = build(mode, seed)
                self.assertEqual(check_opening(state, PACK, payload), [], (mode, seed))
                self.assertTrue(payload["footer"].endswith("种子：%d" % seed))


class ConstraintTest(unittest.TestCase):
    def test_locks_are_honoured(self):
        state, payload = build("pressure", 5, locks={"pressure_id": "p_typhoon", "combo_id": "combo_agent_number"})
        self.assertEqual(state["opening"]["pressure_id"], "p_typhoon")
        self.assertEqual(state["opening"]["combo_id"], "combo_agent_number")
        self.assertEqual(payload["pressure"]["title"], "台风提前转向")

    def test_excluded_tags_never_appear(self):
        for seed in range(1, 30):
            state, _ = build("pressure", seed, excludes={"content_tags": ["workplace_power", "crime"]})
            pressure = next(p for p in PACK["pressures"] if p["id"] == state["opening"]["pressure_id"])
            combo = next(c for c in PACK["cast_combos"] if c["id"] == state["opening"]["combo_id"])
            self.assertFalse({"workplace_power", "crime"} & set(pressure["tags"] + combo["tags"]))

    def test_impossible_constraints_give_no_match_with_relaxations(self):
        with self.assertRaises(AppError) as caught:
            build("daily", 3, locks={"pressure_id": "p_typhoon"})
        self.assertEqual(caught.exception.code, "NO_MATCH")
        with self.assertRaises(AppError) as caught:
            build("daily", 3, excludes={"content_tags": ["workplace"]})
        self.assertEqual(caught.exception.code, "NO_MATCH")
        self.assertTrue(caught.exception.extra["relax"])

    def test_no_identity_for_the_player_gender_gives_no_match(self):
        pack = dict(PACK, player_identities=[dict(i, gender="male") for i in PACK["player_identities"]])
        conditions = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}, "player": {"gender": "female"}})
        with self.assertRaises(AppError) as caught:
            opening.plan(pack, 6, conditions)
        self.assertEqual(caught.exception.code, "NO_MATCH")

    def test_random_mode_falls_back_when_only_one_mode_matches(self):
        for seed in range(1, 21):
            state, _ = build("random", seed, locks={"activity_id": "a_supper"})
            self.assertEqual(state["mode"], "daily")
            self.assertEqual(state["opening"]["activity_id"], "a_supper")
        for seed in range(1, 21):
            state, _ = build("random", seed, locks={"pressure_id": "p_typhoon"})
            self.assertEqual(state["mode"], "pressure")
            self.assertEqual(state["opening"]["pressure_id"], "p_typhoon")
        with self.assertRaises(AppError) as caught:
            build("random", 3, excludes={"content_tags": ["workplace"]})
        self.assertEqual(caught.exception.code, "NO_MATCH")

    def test_identity_lock_is_not_bypassed_by_custom_identity(self):
        locked = PACK["player_identities"][0]["id"]
        with self.assertRaises(AppError) as caught:
            build("daily", 3, locks={"identity_id": locked}, player={"identity_hint": "完全不存在的自定义身份"})
        self.assertEqual(caught.exception.code, "NO_MATCH")

    def test_player_social_position_filters_identities_and_custom_combos(self):
        for position in ("low", "equal", "high"):
            for seed in range(1, 8):
                state, payload = build("daily", seed, player={"social_position": position})
                self.assertEqual(state["characters"]["player"]["social_position"], position)
                self.assertEqual(payload["player"]["social_position"], position)
        # Custom identity with explicit social_position preserves it and filters combos.
        pack = copy.deepcopy(PACK)
        pack["cast_combos"][0]["player_positions"] = ["equal", "high"]
        combo_id = pack["cast_combos"][0]["id"]
        conditions = opening.normalize_conditions(
            {
                "mode": "daily",
                "locks": {"world_id": WORLD, "combo_id": combo_id},
                "player": {"identity_hint": "裁缝", "social_position": "high"},
            }
        )
        state, payload = opening.build(pack, 5, conditions, "test")
        self.assertEqual(state["characters"]["player"]["social_position"], "high")
        self.assertEqual(payload["player"]["social_position"], "high")
        # Incompatible social_position on custom identity raises NO_MATCH.
        pack["cast_combos"][0]["player_positions"] = ["low"]
        with self.assertRaises(AppError) as caught:
            opening.plan(pack, 5, conditions)
        self.assertEqual(caught.exception.code, "NO_MATCH")

    def test_leverage_pressure_registers_leverage_and_basis(self):
        state, _ = build("pressure", 2, locks={"pressure_id": "p_owner_men"})
        (lv,) = state["leverage"].values()
        self.assertEqual((lv["holder"], lv["subject"]), ("ship_agent_rep", "player"))
        basis = state["facts"][lv["basis_fact_id"]]
        self.assertIn("ship_agent_rep", basis["known_by"])


class PeopleTest(unittest.TestCase):
    def test_gender_preferences(self):
        for pref, allowed in (("female_only", {"female"}), ("male_only", {"male"})):
            for seed in range(1, 15):
                state, _ = build("daily", seed, npc_gender_preference=pref)
                genders = {c["gender"] for c in state["characters"].values() if c["tier"] == "major" and c["id"] != "player"}
                self.assertTrue(genders <= allowed, (pref, seed, genders))
        for seed in range(1, 15):
            state, _ = build("daily", seed, npc_gender_preference="mostly_male")
            majors = [c["gender"] for c in state["characters"].values() if c["tier"] == "major" and c["id"] != "player"]
            self.assertGreater(majors.count("male") * 2, len(majors))

    def test_without_a_preference_the_npcs_are_the_other_gender(self):
        for player_gender, other in (("male", "female"), ("female", "male")):
            for seed in range(1, 15):
                state, _ = build("daily", seed, player={"gender": player_gender})
                genders = {c["gender"] for c in state["characters"].values() if c["tier"] == "major" and c["id"] != "player"}
                self.assertEqual(genders, {other}, (player_gender, seed))
        # A preference the player set comes first.
        state, _ = build("daily", 3, player={"gender": "male"}, npc_gender_preference="male_only")
        self.assertEqual({c["gender"] for c in state["characters"].values() if c["tier"] == "major" and c["id"] != "player"}, {"male"})
        # No gender given: the player's character is male, the NPCs female.
        for mode in ("daily", "pressure"):
            for seed in range(1, 15):
                state, _ = build(mode, seed)
                self.assertEqual(state["characters"]["player"]["gender"], "male", (mode, seed))
                genders = {c["gender"] for c in state["characters"].values() if c["tier"] == "major" and c["id"] != "player"}
                self.assertEqual(genders, {"female"}, (mode, seed))

    def test_a_world_without_a_male_identity_opens_by_its_identities(self):
        pack = dict(PACK, player_identities=[dict(i, gender="female") for i in PACK["player_identities"]])
        conditions = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}})
        state, _ = opening.build(pack, 6, conditions, "test")
        self.assertEqual(state["characters"]["player"]["gender"], "female")
        # The world's own identity for the player's wish comes before a custom one.
        first = PACK["player_identities"][0]
        pack = dict(PACK, player_identities=[dict(first, gender="female")] + PACK["player_identities"][1:])
        conditions = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}, "player": {"identity_hint": first["id"]}})
        state, _ = opening.build(pack, 6, conditions, "test")
        self.assertEqual((state["characters"]["player"]["gender"], state["opening"]["identity_id"]), ("female", first["id"]))

    def test_player_settings_are_respected(self):
        state, payload = build("daily", 4, player={"gender": "female", "age": 45, "identity_hint": "裁缝", "name": "罗秀英", "title": "罗师傅"})
        player = state["characters"]["player"]
        self.assertEqual((player["gender"], player["age"], player["name"], player["title"]), ("female", 45, "罗秀英", "罗师傅"))
        self.assertEqual(player["public_role"], "裁缝")
        families = [c["family"] for c in state["characters"].values() if c["tier"] == "major" and c["id"] != "player"]
        self.assertNotIn("罗", families)

    def test_underage_player_is_blocked(self):
        with self.assertRaises(AppError) as caught:
            build("daily", 4, player={"age": 17})
        self.assertEqual(caught.exception.code, "SAFETY_BLOCK")

    def test_age_band_enforces_adult_floor_and_order(self):
        with self.assertRaises(AppError) as caught:
            build("daily", 4, player={"age_band": [15, 25]})
        self.assertEqual(caught.exception.code, "SAFETY_BLOCK")
        self.assertEqual(caught.exception.details[0]["path"], "$.player.age_band")
        self.assertIn("年满 18 岁", caught.exception.details[0]["hint"])
        with self.assertRaises(AppError) as caught:
            build("daily", 4, player={"age_band": [25, 10]})
        self.assertEqual(caught.exception.code, "INVALID_INPUT")
        self.assertEqual(caught.exception.details[0]["path"], "$.player.age_band")
        state, _ = build("daily", 4, player={"age_band": [18, 22]})
        self.assertTrue(18 <= state["characters"]["player"]["age"] <= 22)

    def test_mixed_preference_is_preserved_for_male_and_female_players(self):
        self.assertEqual(opening.npc_preference("mixed", "male"), "mixed")
        self.assertEqual(opening.npc_preference("mixed", "female"), "mixed")
        self.assertEqual(opening.npc_preference("any", "male"), "other_female")
        self.assertEqual(opening.npc_preference("any", "female"), "other_male")
        multi_combo = next(c["id"] for c in PACK["cast_combos"] if len(c["slots"]) >= 2)
        for player_gender in ("male", "female"):
            for seed in range(1, 10):
                state, _ = build("daily", seed, locks={"combo_id": multi_combo}, player={"gender": player_gender}, npc_gender_preference="mixed")
                genders = {c["gender"] for c in state["characters"].values() if c["tier"] == "major" and c["id"] != "player"}
                self.assertTrue({"female", "male"} <= genders, (player_gender, seed, genders))
        err = opening.no_match(["无候选"], WORLD, opening.normalize_conditions({"npc_gender_preference": "female_only"}))
        self.assertTrue(any("配对偏好" in r for r in err.extra["relax"]))
        self.assertFalse(any("NPC 性别偏好" in r for r in err.extra["relax"]))

    def test_player_title_and_name_splitting_never_degrade(self):
        # Long custom identity_hint (>6 chars) falls back to full name, never "" or bare family.
        state, payload = build("daily", 4, player={"identity_hint": "从海外归来的退役军医", "name": "欧阳明"})
        player = state["characters"]["player"]
        self.assertEqual((player["family"], player["given"]), ("欧阳", "明"))
        self.assertEqual((player["title"], player["call"], payload["player"]["title"]), ("欧阳明", "欧阳明", "欧阳明"))
        # Non-pool single Chinese surname still splits cleanly.
        state, _ = build("daily", 4, player={"name": "诸葛亮"})
        self.assertEqual((state["characters"]["player"]["family"], state["characters"]["player"]["given"]), ("诸葛", "亮"))
        state, _ = build("daily", 4, player={"name": "张默"})
        self.assertEqual((state["characters"]["player"]["family"], state["characters"]["player"]["given"]), ("张", "默"))
        # Unsplittable name with {family}-based patterns falls back to full name, avoiding "小"/"老" or "".
        pack = copy.deepcopy(PACK)
        for ident in pack["player_identities"]:
            ident["title_patterns"] = [{"pattern": "小{family}", "gender": "any"}]
        cond = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}, "player": {"name": "Alex"}})
        state, payload = opening.build(pack, 4, cond, "test")
        self.assertEqual((state["characters"]["player"]["family"], state["characters"]["player"]["title"]), ("", "Alex"))
        self.assertEqual(payload["player"]["title"], "Alex")
        # Nonbinary player without matching gender pattern falls back to full name instead of forcing "先生".
        for ident in pack["player_identities"]:
            ident["title_patterns"] = [{"pattern": "{family}先生", "gender": "male"}, {"pattern": "{family}小姐", "gender": "female"}]
        cond = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}, "player": {"gender": "nonbinary", "name": "林澈"}})
        state, payload = opening.build(pack, 4, cond, "test")
        self.assertEqual(state["characters"]["player"]["title"], "林澈")
        self.assertNotIn("先生", payload["player"]["title"])
        # given_first world splits non-pool name by '·'.
        gf_pack = copy.deepcopy(PACK)
        gf_pack["name_pools"]["order"] = "given_first"
        cond = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}, "player": {"name": "艾达·冯"}})
        state, _ = opening.build(gf_pack, 4, cond, "test")
        self.assertEqual((state["characters"]["player"]["family"], state["characters"]["player"]["given"]), ("冯", "艾达"))

    def test_standby_previews_do_not_drift_after_activation(self):
        for pref in ("any", "mixed", "mostly_female"):
            state, _ = build("pressure", 7, npc_gender_preference=pref)
            before = opening.standby_previews(state, PACK)
            self.assertGreaterEqual(len(before), 2)
            first_slot = sorted(before)[0]
            opening.instantiate_standby(state, PACK, first_slot)
            after = opening.standby_previews(state, PACK)
            self.assertNotIn(first_slot, after)
            for slot, prev in after.items():
                for field in ("gender", "family", "given", "name", "call", "age"):
                    self.assertEqual(prev[field], before[slot][field], (pref, slot, field))

    def test_every_generated_character_is_an_explicit_adult(self):
        for seed in range(1, 25):
            state, _ = build("pressure", seed)
            for char in state["characters"].values():
                self.assertGreaterEqual(char["age"], 18)
                self.assertTrue(char["adult_context"])

    def test_player_identity_varies(self):
        identities = {build("daily", seed)[0]["opening"]["identity_id"] for seed in range(1, 30)}
        self.assertGreaterEqual(len(identities), 3)

    def test_no_shared_family_names_among_major_characters(self):
        for seed in range(1, 25):
            state, _ = build("pressure", seed)
            families = [c["family"] for c in state["characters"].values() if c["tier"] == "major"]
            self.assertEqual(len(families), len(set(families)))


class RandomSeedTest(unittest.TestCase):
    def test_history_avoids_recent_signatures(self):
        conditions = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}})
        history = []
        seen = []
        stream = iter(range(1000, 100000, 7))
        for _ in range(10):
            seed, result = opening.choose_seed(lambda s: opening.plan(PACK, s, conditions)[0], stream, history)
            self.assertNotIn(result["signature"], seen)
            seen.append(result["signature"])
            history.insert(0, result)

    def test_power_structures_rotate_through_the_last_three(self):
        def result(structure, n):
            return {"signature": n, "power_structure": structure, "identity_id": n, "combo_id": n, "hook_kind": "approach"}

        history = [result("equal", 1), result("npc_high", 2), result("player_high", 3)]
        self.assertEqual(opening.penalty(result("switchable", 4), history), 0)
        self.assertGreater(opening.penalty(result("player_high", 5), history), 0)

    def test_candidates_exhausted_accepts_a_repeat(self):
        conditions = opening.normalize_conditions(
            {"mode": "daily", "locks": {"world_id": WORLD, "combo_id": "combo_tower_night", "activity_id": "a_supper", "hook_id": "h_thermos"}}
        )
        result = opening.plan(PACK, 1, conditions)[0]
        seed, again = opening.choose_seed(lambda s: opening.plan(PACK, s, conditions)[0], iter(range(1, 50)), [result])
        self.assertEqual(again["signature"], result["signature"])


class StateShapeTest(unittest.TestCase):
    def test_opening_state_counters_and_turn(self):
        state, _ = new_state("pressure", seed=3)
        self.assertEqual((state["revision"], state["turn"]), (1, 1))
        self.assertEqual(state["counters"]["next"]["fact"], len(state["facts"]) + 1)


class P2OpeningTextChecksTest(unittest.TestCase):
    def test_single_gender_identity_world_applies_effective_gender_in_plan_candidates(self):
        pack = copy.deepcopy(PACK)
        for ident in pack["player_identities"]:
            ident["gender"] = "female"
        # Fix all character templates to female: effective player gender is female ->
        # default npc_preference is other_male, so no combo should pass plan_candidates.
        for tpl in pack["character_templates"]:
            tpl["gender"] = "female"
        conditions = opening.normalize_conditions({"mode": "daily", "locks": {"world_id": WORLD}})
        tuples, reasons = opening.plan_candidates(pack, "daily", conditions)
        self.assertEqual(tuples, [])
        self.assertTrue(reasons)
        # Allow one template to be male: only combos including it pass plan_candidates.
        male_slot = pack["cast_combos"][0]["slots"][0]
        for tpl in pack["character_templates"]:
            if tpl["id"] == male_slot:
                tpl["gender"] = "male"
        tuples, _reasons = opening.plan_candidates(pack, "daily", conditions)
        self.assertTrue(tuples)
        self.assertTrue(all(male_slot in t[0]["slots"] for t in tuples))

    def test_no_match_uses_world_title_and_omits_misleading_age(self):
        conditions = opening.normalize_conditions({"mode": "daily", "excludes": {"content_tags": ["workplace"]}})
        tuples, reasons = opening.plan_candidates(PACK, "daily", conditions)
        self.assertEqual(tuples, [])
        self.assertIn(PACK["title"], reasons[0])
        self.assertNotIn(PACK["id"], reasons[0])
        # Identity mismatch reason and relax hint never mention age.
        pack = copy.deepcopy(PACK)
        for ident in pack["player_identities"]:
            ident["gender"] = "male"
        cond = opening.normalize_conditions({"mode": "daily", "player": {"gender": "female"}})
        tuples, reasons = opening.plan_candidates(pack, "daily", cond)
        self.assertEqual(tuples, [])
        self.assertTrue(any("身份、性别" in r and "年龄" not in r for r in reasons), reasons)
        err = opening.no_match(reasons, WORLD, cond)
        self.assertTrue(any("放宽玩家设定" in r and "年龄" not in r for r in err.extra["relax"]), err.extra["relax"])
        # Non-filtering player fields (e.g. age only) do not trigger a player relaxation hint.
        err_age = opening.no_match(["无匹配"], WORLD, opening.normalize_conditions({"player": {"age": 25}}))
        self.assertFalse(any("放宽玩家设定" in r for r in err_age.extra["relax"]), err_age.extra["relax"])

    def test_pressure_leverage_and_foreshadow_are_not_double_rendered(self):
        # A player name containing placeholder syntax must stay verbatim after single render.
        state, payload = build("pressure", 2, locks={"pressure_id": "p_owner_men"}, player={"name": "甲{player.role}乙", "title": "甲{player.role}乙"})
        (lv,) = state["leverage"].values()
        basis = state["facts"][lv["basis_fact_id"]]["text"]
        if "甲" in basis:
            self.assertIn("甲{player.role}乙", basis)
        if "甲" in payload["pressure"]["foreshadow"]:
            self.assertIn("甲{player.role}乙", payload["pressure"]["foreshadow"])

    def test_opening_checks_family_name_events_braces_and_diversity(self):
        from adult_tension.domain import opening_checks

        state, payload = build("daily", 1)
        # Same family, different full names -> only "同姓" reported, not "重名".
        s_fam = copy.deepcopy(state)
        npc_id = next(c for c in s_fam["scene"]["present"] if c != "player")
        s_fam["characters"][npc_id]["family"] = s_fam["characters"]["player"]["family"]
        probs = opening_checks.check_opening(s_fam, PACK, payload)
        self.assertIn("同一局的重要人物同姓", probs)
        self.assertNotIn("同一局的重要人物重名", probs)
        # Duplicate full name with empty family -> "重名" reported.
        s_dup = copy.deepcopy(state)
        s_dup["characters"]["player"]["family"] = ""
        s_dup["characters"][npc_id]["family"] = ""
        s_dup["characters"][npc_id]["name"] = s_dup["characters"]["player"]["name"]
        probs = opening_checks.check_opening(s_dup, PACK, payload)
        self.assertIn("同一局的重要人物重名", probs)
        self.assertNotIn("同一局的重要人物同姓", probs)
        # Daily mode event check does not double-report deadline/chance events.
        s_ev = copy.deepcopy(state)
        s_ev["events"]["e1"] = {
            "id": "e1", "kind": "deadline", "tier": "immediate", "title": "t", "text": "x",
            "participants": ["player"], "due": {"day": 1, "minute": 1400}, "probability": None,
            "dedupe_key": "k", "state": "pending", "outcome": None, "created_turn": 1,
            "resolved_turn": None, "note": None, "coord": [1, 0],
        }
        ev_probs = [p for p in opening_checks.check_opening(s_ev, PACK, payload) if "日常模式开局" in p]
        self.assertEqual(ev_probs, ["日常模式开局出现了倒计时或概率事件"])
        s_ev["events"]["e1"]["kind"] = "foreshadow"
        ev_probs = [p for p in opening_checks.check_opening(s_ev, PACK, payload) if "日常模式开局" in p]
        self.assertEqual(ev_probs, ["日常模式开局不应有预设事件"])
        # Unrendered placeholders in opening_payload are caught; reversed "} ... {" is ignored.
        bad_payload = copy.deepcopy(payload)
        bad_payload["hook"]["text"] = "{npc.name}递过来一杯热茶"
        self.assertTrue(any("未渲染的占位" in p for p in opening_checks.check_opening(state, PACK, bad_payload)))
        rev_payload = copy.deepcopy(payload)
        rev_payload["hook"]["text"] = "右括}在左括{前"
        self.assertEqual(opening_checks.check_opening(state, PACK, rev_payload), [])
        # diversity() guards non-positive count and scales thresholds cleanly.
        for bad in (0, -3, False):
            with self.assertRaises(ValueError):
                opening_checks.diversity(PACK, "daily", base=1, count=bad)
        res10 = opening_checks.diversity(PACK, "daily", base=1, count=10)
        self.assertEqual(res10["checks"]["signatures"]["need"], ">= 6")
        self.assertEqual(res10["checks"]["identities"]["need"], ">= 3")

    def test_text_binding_none_fallback_and_given_first_full_name(self):
        from adult_tension.domain import text as TX

        scope = TX.binding({"name": None, "family": None, "given": None, "call": None, "public_role": None, "role": None, "title": None, "gender": None})
        self.assertEqual(scope["name"], "")
        self.assertEqual(scope["family"], "")
        self.assertEqual(scope["given"], "")
        self.assertEqual(scope["call"], "")
        self.assertEqual(scope["title"], "")
        self.assertEqual(scope["role"], "")
        self.assertEqual(TX.render("{npc.name}-{npc.family}-{npc.given}-{npc.ta}", {"npc": scope}), "---TA")
        gf = {"order": "given_first"}
        self.assertEqual(TX.full_name(gf, "米勒", "艾达"), "艾达·米勒")
        self.assertEqual(TX.full_name(gf, "", "艾达"), "艾达")
        self.assertEqual(TX.full_name(gf, "米勒", ""), "米勒")
        self.assertEqual(TX.full_name(gf, None, "艾达"), "艾达")
        self.assertEqual(TX.full_name(gf, "", ""), "")

    def test_stage1_standby_isolation_no_match_labels_and_worldpack_checks(self):
        from adult_tension.domain import turn as T
        from adult_tension.domain import worldpack as WP
        from helpers.domain import commit, content

        # Standby names stay unchanged when player_update changes the player's surname to a standby's surname
        state, _ = build("daily", 42)
        before = opening.standby_previews(state, PACK)
        sb_fam = next(iter(before.values()))["family"]
        updated, _ = T.commit_turn(state, content(), commit("result", [{"op": "player_update", "name": sb_fam + "改名"}], player_authorized=True))
        after = opening.standby_previews(updated, PACK)
        self.assertEqual({k: v["name"] for k, v in before.items()}, {k: v["name"] for k, v in after.items()})
        # no_match uses Chinese lock names and world title
        with self.assertRaises(AppError) as caught:
            build("daily", 3, locks={"pressure_id": "p_typhoon", "combo_id": "combo_agent_number"})
        err = caught.exception
        self.assertIn(PACK["title"], err.message)
        self.assertNotIn(WORLD, err.message)
        self.assertTrue(any("人物组合" in r and "combo_id" not in r for r in err.extra["relax"]), err.extra["relax"])
        # worldpack: gender desc uses "本局", PLAYER_ADDRESSED catches {player.称呼}先生, partial stage_labels & custom 4-slot family check
        self.assertIn("由本局的配对偏好决定", WP.TEMPLATE.fields["gender"].desc)
        tag_ids = {t["id"] for t in STORE.tags()["tags"]}
        raw = copy.deepcopy(STORE.world_raw(WORLD))
        raw["hooks"][0]["text"] = "{npc.name}喊了一声{player.称呼}先生。"
        _p, probs = WP.validate_world(raw, custom=False, tag_ids=tag_ids)
        self.assertTrue(any("先生" in p["reason"] for p in probs), probs)
        raw_stage = copy.deepcopy(STORE.world_raw(WORLD))
        raw_stage["stage_labels"] = {"stranger": "初见", "flirting": "试探"}
        _p, probs = WP.validate_world(raw_stage, custom=False, tag_ids=tag_ids)
        self.assertTrue(any(p["path"] == "$.stage_labels" for p in probs), probs)
        raw_cw = copy.deepcopy(STORE.world_raw(WORLD))
        raw_cw["id"] = "custom_four_slots"
        raw_cw["custom"] = True
        raw_cw["status"] = "draft"
        raw_cw["name_pools"]["family"] = raw_cw["name_pools"]["family"][:4]
        raw_cw["cast_combos"][0]["slots"] = [t["id"] for t in raw_cw["character_templates"][:4]]
        members = ["player"] + raw_cw["cast_combos"][0]["slots"]
        raw_cw["cast_combos"][0]["relations"] = [
            {"a": members[i], "b": members[j], "stage": "stranger", "a_to_b": {"trust": 0, "tension": 1}, "b_to_a": {"trust": 0, "tension": 1}, "reason": "同场"}
            for i in range(len(members))
            for j in range(i + 1, len(members))
        ]
        _p, probs = WP.validate_world(raw_cw, custom=True, tag_ids=tag_ids)
        self.assertTrue(any(p["path"] == "$.name_pools.family" for p in probs), probs)
        # Built-in worlds also enforce hook/activity and hook/pressure location intersection per combo (M4)
        raw_loc = copy.deepcopy(STORE.world_raw(WORLD))
        loc_a, loc_b = raw_loc["locations"][0]["id"], raw_loc["locations"][1]["id"]
        combo0_slots = set(raw_loc["cast_combos"][0]["slots"])
        for h in raw_loc["hooks"]:
            if h["slot"] in combo0_slots:
                h["location_ids"] = [loc_a]
        for act in raw_loc["daily_activities"]:
            act["location_ids"] = [loc_b]
        for pr in raw_loc["pressures"]:
            pr["location_ids"] = [loc_b]
        _p, probs = WP.validate_world(raw_loc, custom=False, tag_ids=tag_ids)
        reasons = [p["reason"] for p in probs if p["path"] == "$.cast_combos[0]"]
        self.assertIn("日常模式下没有能与这个组合配上的活动、地点与钩子", reasons)
        self.assertIn("压力模式下没有能与这个组合配上的压力、地点与钩子", reasons)


if __name__ == "__main__":
    unittest.main()
