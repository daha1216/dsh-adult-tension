"""Context budget (DATA_CONTRACTS.md 7).

Whatever a world puts on stage and however long the game runs, the full
context stays within 20 KB and keeps every section the contract names: all
major and supporting NPCs (at least a summary), relationships with the
player, the player's facts, world rules, the location list, the latest
chapter, every pending event and active leverage, and a name pool.
"""

import unittest

import _bootstrap  # noqa: F401
from adult_tension.application import service
from adult_tension.application.fake_narrator import FakeNarrator
from adult_tension.domain import state as SS
from adult_tension.domain.text import full_name
from adult_tension.persistence import repo
from adult_tension.projections import context as CX
from helpers.domain import STORE
from helpers.service import Ids, app, session

TRIOS = sorted(
    (pack["id"], combo["id"])
    for pack in (STORE.world(entry["id"]) for entry in STORE.index()["worlds"])
    for combo in pack["cast_combos"]
    if len(combo["slots"]) >= 3
)
FILL = "灯火夜雨人声旧街长巷风里"


def fill(n, salt=0):
    text = "".join(FILL[(i + salt) % len(FILL)] for i in range(n))
    return text


def card(tier, n, salt):
    """A card with every text field n characters long (capped at the field's maximum)."""

    def t(cap):
        return fill(min(n, cap), salt)

    out = {
        "appearance": t(120),
        "identity": {"authority": t(120), "resources": [t(80)] * 3, "limits": [t(80)] * 3, "obligations": [t(80)] * 2, "exposure_risk": t(120), "hidden_mismatch": t(120)},
        "decision": {"core_value": t(60), "current_goal": t(80)},
    }
    if tier == "major":
        out["decision"].update(
            {
                "pressure_responses": {level: t(120) for level in ("low", "mid", "high", "breaking")},
                "withdrawal": t(120),
                "relationship_stance": t(80),
                "contrast": t(80),
                "prefers": [t(80)] * 3,
                "avoids": [t(80)] * 3,
                "never": [t(80)] * 3,
            }
        )
        out["intimacy"] = {
            "desire_level": 2,
            "attraction_sources": [t(80)] * 3,
            "likes": [t(80)] * 3,
            "dislikes": [t(80)] * 3,
            "preconditions": [t(80)] * 3,
            "boundaries": [t(80)] * 3,
            "expression": t(80),
            "self_control": 3,
            "desired_position": t(40),
        }
        out["voices"] = {"surface": t(120), "inner": t(120)}
        out["situation"] = {"trigger": t(120), "pressure": t(120), "exits": [{"option": t(80), "cost": t(120)}] * 4}
    return out


class Game:
    def __init__(self, ctx, world_id, combo_id, mode="pressure", seed=11):
        self.ctx = ctx
        self.ids = Ids()
        out = service.new_game(ctx, {"request_id": self.ids(), "mode": mode, "seed": seed, "include_drafts": True, "locks": {"world_id": world_id, "combo_id": combo_id}})
        self.sid = out["session_id"]
        self.narrator = FakeNarrator(seed)

    def state(self):
        return session(self.ctx, self.sid)

    def commit(self, ops):
        info = repo.load_session(self.ctx.db(), self.sid)
        body = {"action_mode": "continue", "player_input": "……", "operations": ops, "content_tags": [], "summary": "有人来了", "open_action": "场面停住"}
        return service.commit_turn(self.ctx, dict(body, session_id=self.sid, request_id=self.ids(), expected_revision=info["revision"]))

    def play(self, turns):
        for _ in range(turns):
            info = repo.load_session(self.ctx.db(), self.sid)
            payload = self.narrator.commit(info["state"], info["content"])
            service.commit_turn(self.ctx, dict(payload, session_id=self.sid, request_id=self.ids(), expected_revision=info["revision"]))

    def introduce(self, count, tier, present, length, salt=0):
        info = self.state()
        state, world = info["state"], info["content"]["world"]
        # Major and supporting people need surnames of their own (background ones may share).
        taken = {c.get("family") for cid, c in state["characters"].items() if cid == state["player_id"] or c["tier"] in ("major", "supporting")}
        families = [f for f in world["name_pools"]["family"] if f not in taken]
        elsewhere = next(loc["id"] for loc in world["locations"] if loc["id"] != state["scene"]["location_id"])
        ops = []
        for i in range(count):
            cid = "guest_%s_%d_%d" % (tier, salt, i)
            op = dict(
                {
                    "op": "introduce_character",
                    "id": cid,
                    "name": full_name(world["name_pools"], families[i], "客" + FILL[i]),
                    "tier": tier,
                    "age": 30 + i,
                    "gender": ("female", "male")[i % 2],
                    "adult_context": fill(min(length, 80), salt),
                    "public_role": fill(min(length, 30), salt),
                    "present": present,
                    "location_id": None if present else elsewhere,
                },
                **card(tier, length, salt + i)
            )
            ops.append(op)
        return self.commit(ops)


class FullContextBudgetTest(unittest.TestCase):
    def check(self, info, label):
        state, content = info["state"], info["content"]
        world = content["world"]
        full = CX.full(state, content)
        self.assertLessEqual(CX.size_of(full), CX.FULL_LIMIT, label)
        self.assertLessEqual(CX.size_of(CX.brief(state, content)), CX.BRIEF_LIMIT, label)
        player = state["player_id"]
        people = {cid for cid, c in state["characters"].items() if cid != player and c["tier"] in ("major", "supporting")}
        self.assertEqual({c["id"] for c in full["characters"]}, people, label)
        self.assertEqual(full["world"]["rules"], [r["text"] for r in world["rules"]], label)
        self.assertEqual([loc["id"] for loc in full["locations"]], [loc["id"] for loc in world["locations"]], label)
        pending = {e["id"] for e in state["events"].values() if e["state"] == "pending"}
        self.assertEqual({e["id"] for e in full["events"]}, pending, label)
        self.assertEqual({lv["id"] for lv in full["leverage_all"]}, {lv["id"] for lv in SS.active_leverage(state)}, label)
        with_player = {(e["from"], e["to"]) for e in state["relationships"].values() if player in (e["from"], e["to"]) and ({e["from"], e["to"]} - {player}) <= people}
        self.assertEqual({(e["from"], e["to"]) for e in full["relationships"] if player in (e["from"], e["to"])}, with_player, label)
        if state["memory"]["chapters"]:
            self.assertEqual(full["chapters"][-1], state["memory"]["chapters"][-1]["summary"], label)
        unused = [f for f in world["name_pools"]["family"] if f not in {c.get("family") for c in state["characters"].values()}]
        self.assertEqual(bool(full["name_pool"]["family_unused"]), bool(unused), label)
        on_stage = [c for c in full["characters"] if c["present"] and c["tier"] == "major"]
        if on_stage:
            # Someone on stage can always be played properly: pressure responses and boundaries.
            self.assertTrue(any("pressure_responses" in c.get("decision", {}) and "boundaries" in c.get("intimacy", {}) for c in on_stage), label)
        return full

    def test_three_person_combos_with_newcomers_stay_within_budget(self):
        self.assertEqual(len(TRIOS), 25)
        for world_id, combo_id in TRIOS:
            for mode in ("pressure", "daily"):
                with app() as ctx:
                    game = Game(ctx, world_id, combo_id, mode)
                    label = (world_id, mode)
                    self.check(game.state(), label + ("opening",))
                    game.introduce(2, "major", True, 30, salt=1)
                    game.introduce(3, "major", False, 30, salt=2)
                    game.introduce(3, "supporting", False, 30, salt=3)
                    for turn in range(40):
                        game.play(1)
                        self.check(game.state(), label + (turn,))

    def test_a_crowded_scene_of_long_cards_still_fits(self):
        world_id, combo_id = TRIOS[0]
        with app() as ctx:
            game = Game(ctx, world_id, combo_id)
            game.introduce(4, "major", True, 120, salt=5)
            game.introduce(4, "major", False, 120, salt=6)
            full = self.check(game.state(), "crowd")
            details = [c.get("detail") for c in full["characters"]]
            self.assertIn("roster", details)
            game.play(10)
            self.check(game.state(), "crowd after play")

    def test_nothing_is_cut_while_there_is_room(self):
        with app() as ctx:
            game = Game(ctx, "harbor_night_shift", "combo_tower_night", "daily", 3)
            info = game.state()
            full = CX.full(info["state"], info["content"])
            self.assertLess(CX.size_of(full), CX.FULL_LIMIT)
            self.assertIn("known_facts", full)
            self.assertIn("due_soon", full)
            self.assertTrue(all("detail" not in c for c in full["characters"]))
            self.assertTrue(all("detail" in loc for loc in full["locations"]))


if __name__ == "__main__":
    unittest.main()
