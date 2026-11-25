"""Context budget (DATA_CONTRACTS.md 7).

Whatever a world puts on stage and however long the game runs, the full
context stays within 32 KB and keeps every section the contract names: all
major and supporting NPCs (at least a summary), relationships with the
player, the player's facts, world rules, the location list, the latest
chapter, every pending event and active leverage, and a name pool.
"""

import json
import os
import unittest

import _bootstrap  # noqa: F401
from adult_tension.application import service
from adult_tension.application.fake_narrator import FakeNarrator
from adult_tension.domain import simulation
from adult_tension.domain import state as SS
from adult_tension.domain import structure as ST
from adult_tension.domain.text import full_name
from adult_tension.persistence import repo
from adult_tension.projections import context as CX
from helpers.domain import STORE
from helpers.service import Ids, app, record, session



def _cast_weight(pack, combo):
    cards = {t["id"]: t for t in pack["character_templates"]}
    return len(combo["slots"]), sum(len(json.dumps(cards[s], ensure_ascii=False)) for s in combo["slots"])


# Every opening cast, the heaviest first (most people, then the longest cards).
# Core plays the heaviest few; tools/context_sweep.py plays them all before a
# release (ACCEPTANCE.md 4 keeps core under a minute).
CASTS = [
    (pack["id"], combo["id"])
    for _, pack, combo in sorted(
        ((_cast_weight(pack, combo), pack, combo) for pack in (STORE.world(entry["id"]) for entry in STORE.index()["worlds"]) for combo in pack["cast_combos"]),
        key=lambda item: (-item[0][0], -item[0][1], item[1]["id"], item[2]["id"]),
    )
]
SWEPT = CASTS if os.environ.get("AT_CONTEXT_SWEEP") == "all" else CASTS[:4]
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
        # Crossing midnight asks for a beat from every major who is away, as a
        # model would read it off the preview (RUNTIME_PROTOCOL 6.2).
        preview = simulation.preview(info["state"], info["content"]["world"], {"minutes": ST.DEFAULT_ADVANCE_MINUTES})
        beats = [{"op": "offscreen_beat", "npc_id": p["npc_id"], "summary": "在别处忙自己的事", "operations": []} for p in preview["required_beats"]]
        if beats:
            ops = [{"op": "advance_time", "minutes": ST.DEFAULT_ADVANCE_MINUTES}] + beats + ops
        body = {"action_mode": "continue", "player_input": "……", "operations": ops, "content_tags": [], "summary": "有人来了", "open_action": "场面停住"}
        if info["state"]["requests"].get("chapter_summary"):
            # A world that opens just before midnight crosses the day early.
            body["chapter_summary"] = "第一夜：几个人先后到了这里。"
        return service.commit_turn(self.ctx, record(self.sid, self.ids(), info["revision"], body))

    def play(self, turns):
        for _ in range(turns):
            info = repo.load_session(self.ctx.db(), self.sid)
            payload = self.narrator.commit(info["state"], info["content"])
            service.commit_turn(self.ctx, record(self.sid, self.ids(), info["revision"], payload))

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
        # Every active leverage is listed; only after every other step does what
        # touches no one on stage get cut, and the cut is counted.
        active = SS.active_leverage(state)
        listed = [lv["id"] for lv in full["leverage_all"]]
        omitted = full.get("leverage_omitted", {}).get("count", 0)
        self.assertLessEqual(set(listed), {lv["id"] for lv in active}, label)
        self.assertEqual(len(listed) + omitted, len(active), label)
        onstage = set(state["scene"]["present"])
        self.assertLessEqual({lv["id"] for lv in active if {lv["holder"], lv["subject"]} & onstage}, set(listed), label)
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

    def test_the_heaviest_casts_with_newcomers_stay_within_budget(self):
        for world_id, combo_id in SWEPT:
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
        world_id, combo_id = CASTS[0]
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
            self.assertTrue(all("detail" not in c for c in full["characters"]))
            self.assertTrue(all("detail" in loc for loc in full["locations"]))
            self.assertTrue(all("name" in npc for npc in full["present_npcs"]))
            self.assertTrue(full["world"].get("scene_ideas"))
            self.assertTrue(full.get("standby_cast"))
            compact = CX._card_compact(full["characters"][0])
            self.assertIn("appearance", compact)
            self.assertIn("voices", compact)

    def test_side_details_go_before_the_cards_on_stage_shrink(self):
        # Long cards on stage: nearby, sample lines and edges between NPCs go
        # first; the people on stage are cut only after that.
        with app() as ctx:
            game = Game(ctx, CASTS[0][0], CASTS[0][1])
            game.introduce(2, "major", True, 120, salt=7)
            info = game.state()
            state = info["state"]
            full = self.check(info, "long cards on stage")
            on_stage = [c for c in full["characters"] if c["present"]]
            self.assertTrue(any("detail" in c for c in on_stage))
            # Before a card on stage shrinks, the brief line of everyone with a
            # card loses what the card already says; mood stays.
            carded = {c["id"] for c in full["characters"]}
            for npc in full["present_npcs"]:
                if npc["id"] in carded:
                    self.assertLessEqual(set(npc), {"id", "mood", "conditions"})
                    self.assertEqual(npc["mood"], state["characters"][npc["id"]]["status"]["mood"])
            self.assertNotIn("nearby", full)
            self.assertTrue(all("line" not in item for item in full["background"]))
            player = state["player_id"]
            self.assertTrue(all(player in (e["from"], e["to"]) for e in full["relationships"]))

    def test_many_people_holding_much_leverage_still_fit(self):
        # Found by fuzzing: many important people and active leverage overflow the
        # full-context budget. The leverage touching someone on stage stays and
        # offstage leverage is trimmed last with leverage_omitted counted.
        with app() as ctx:
            game = Game(ctx, CASTS[0][0], CASTS[0][1])
            game.introduce(4, "major", True, 40, salt=8)
            game.introduce(4, "major", False, 120, salt=9)
            state = game.state()["state"]
            player = state["player_id"]
            here = sorted(cid for cid in state["scene"]["present"] if cid != player)
            away = sorted(cid for cid in state["characters"] if cid not in state["scene"]["present"])
            # Like the game the fuzzer found: a dozen touching people on stage,
            # the rest held between people elsewhere.
            pairs = ([(a, b) for a in here for b in away][:12] + [(a, b) for a in away for b in away if a != b] * 10)[:280]
            for start in range(0, len(pairs), 12):
                ops = [{"op": "leverage_set", "holder": a, "subject": b, "basis_text": "%s欠着一笔说不得的账" % fill(6, start + i), "origin": "账本"} for i, (a, b) in enumerate(pairs[start : start + 12])]
                game.commit(ops + [{"op": "npc_action", "npc_id": here[0], "action": "翻了一页账本"}])
            info = game.state()
            self.assertGreaterEqual(len(SS.active_leverage(info["state"])), 60)
            full = self.check(info, "leverage")
            self.assertGreater(full["leverage_omitted"]["count"], 0)
            brief = CX.brief(info["state"], info["content"])
            self.assertTrue(brief["safety"]["leverage"])
            self.assertNotIn("leverage", full["safety"])
            onstage = [lv["id"] for lv in brief["safety"]["leverage"]]
            self.assertEqual([lv["id"] for lv in full["leverage_all"][: len(onstage)]], onstage)

    def test_the_full_context_does_not_repeat_the_brief_lists(self):
        # known_facts and due_soon are the head of player_facts and events.
        with app() as ctx:
            game = Game(ctx, "harbor_night_shift", "combo_tower_night", "pressure", 3)
            info = game.state()
            brief = CX.brief(info["state"], info["content"])
            full = CX.full(info["state"], info["content"])
            self.assertTrue(brief["known_facts"] and brief["due_soon"])
            self.assertNotIn("known_facts", full)
            self.assertNotIn("due_soon", full)
            self.assertEqual(full["player_facts"][: len(brief["known_facts"])], brief["known_facts"])
            self.assertEqual(full["events"][: len(brief["due_soon"])], brief["due_soon"])

    def test_preferences_include_npc_gender_preference(self):
        with app() as ctx:
            ids = Ids()
            opened = service.new_game(
                ctx,
                {
                    "request_id": ids(),
                    "mode": "daily",
                    "seed": 3,
                    "include_drafts": True,
                    "locks": {"world_id": "harbor_night_shift"},
                    "npc_gender_preference": "mostly_female",
                },
            )
            sid = opened["session_id"]
            self.assertEqual(opened["context"]["preferences"]["npc_gender_preference"], "mostly_female")
            brief = service.get_context(ctx, {"session_id": sid, "depth": "brief"})["context"]
            self.assertEqual(brief["preferences"]["npc_gender_preference"], "mostly_female")
            self.assertLessEqual(CX.size_of(brief), CX.BRIEF_LIMIT)
            updated = service.set_preferences(
                ctx,
                {"session_id": sid, "request_id": ids(), "expected_revision": opened["revision"], "npc_gender_preference": "mixed"},
            )
            self.assertEqual(updated["context"]["preferences"]["npc_gender_preference"], "mixed")
            full = service.get_context(ctx, {"session_id": sid, "depth": "full"})["context"]
            self.assertEqual(full["preferences"]["npc_gender_preference"], "mixed")
            self.assertLessEqual(CX.size_of(full), CX.FULL_LIMIT)

    def test_dead_drop_goal_removed_and_brief_fit_trims_lists_cleanly(self):
        self.assertFalse(hasattr(CX, "_drop_goal"))
        sample = {
            "known_facts": [{"id": "f%d" % i, "text": fill(30, i)} for i in range(6)],
            "recent": [fill(30, i) for i in range(4)],
            "keep": {"a": 1},
        }
        limit = 220
        CX._fit(sample, limit, ("known_facts", "recent"))
        self.assertLessEqual(CX.size_of(sample), limit)
        self.assertEqual(sample["size_bytes"], CX.size_of({k: v for k, v in sample.items() if k != "size_bytes"}))
        self.assertEqual(sample["keep"], {"a": 1})
        self.assertEqual(sample["known_facts"], [])


if __name__ == "__main__":
    unittest.main()
