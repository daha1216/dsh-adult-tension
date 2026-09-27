"""Opening generation: determinism, constraints, player settings, safety."""

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
                self.assertEqual(check_opening(state, PACK), [], (mode, seed))
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


if __name__ == "__main__":
    unittest.main()
