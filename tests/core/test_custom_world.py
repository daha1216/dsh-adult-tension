"""Custom worlds (CONTENT_BIBLE 5; DATA_CONTRACTS 8.2; RUNTIME_PROTOCOL 4.3).

Same validator with lower minimums; the world exists only in that game's
snapshot: not in global content, not in the opening history.
"""

import copy
import json
import os
import unittest

import _bootstrap  # noqa: F401
from adult_tension.application import service
from adult_tension.application.fake_narrator import FakeNarrator
from adult_tension.domain import state as SS
from adult_tension.domain import worldpack
from adult_tension.errors import AppError
from adult_tension.persistence import repo
from helpers.cli import REPO_ROOT
from helpers.domain import STORE
from helpers.service import Ids, app, open_game, session

EXAMPLE_PATH = os.path.join(REPO_ROOT, "content-src", "examples", "custom_world.json")
TAG_IDS = {t["id"] for t in STORE.tags()["tags"]}


def example():
    with open(EXAMPLE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def new_custom(ctx, ids, world, mode="daily", seed=11, **extra):
    return service.new_game(ctx, dict({"request_id": ids(), "mode": mode, "seed": seed, "custom_world": world}, **extra))


def refused(test, ctx, ids, world, code="CONTENT_ERROR", **extra):
    with test.assertRaises(AppError) as caught:
        new_custom(ctx, ids, world, **extra)
    test.assertEqual(caught.exception.code, code, json.dumps(caught.exception.details, ensure_ascii=False)[:1500])
    test.assertEqual(ctx.db().execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
    return caught.exception


def paths(err):
    return {d["path"] for d in err.details}


class ExampleTest(unittest.TestCase):
    def test_the_documented_example_passes_the_custom_validator(self):
        pack, problems = worldpack.validate_world(example(), custom=True, tag_ids=TAG_IDS)
        self.assertEqual(problems, [])
        self.assertTrue(pack["custom"])

    def test_the_example_is_below_the_full_minimums(self):
        # It is a custom world, not a small release: the full validator must refuse it.
        _pack, problems = worldpack.validate_world(example(), custom=False, tag_ids=TAG_IDS)
        self.assertIn("$.character_templates", {p["path"] for p in problems})


class OpenTest(unittest.TestCase):
    def test_a_custom_world_opens_from_its_own_snapshot_only(self):
        with app() as ctx:
            ids = Ids()
            before = service.list_worlds(ctx, {"include_drafts": True})
            out = new_custom(ctx, ids, example(), mode="pressure", seed=5)
            info = session(ctx, out["session_id"])
            self.assertEqual(info["state"]["world_id"], "custom_guesthouse")
            self.assertEqual(info["content"]["world"]["title"], "淡季民宿")
            self.assertTrue(info["content"]["world"]["custom"])
            self.assertEqual(out["opening"]["pressure"]["title"] in ("明早有人来看房", "今晚的风暴潮"), True)
            # Not global content, not the opening history.
            self.assertEqual(service.list_worlds(ctx, {"include_drafts": True}), before)
            self.assertNotIn("custom_guesthouse", {w["id"] for w in STORE.index()["worlds"]})
            self.assertEqual(repo.opening_history(ctx.db()), [])
            # Every character is an explicit adult drawn from the custom pools.
            pools = info["content"]["world"]["name_pools"]
            for char in info["state"]["characters"].values():
                self.assertGreaterEqual(char["age"], 18)
                if char["family"]:
                    self.assertIn(char["family"], pools["family"])

    def test_the_same_world_and_seed_reproduce_the_opening(self):
        digests = []
        for _ in range(2):
            with app() as ctx:
                out = new_custom(ctx, Ids(), example(), mode="daily", seed=77)
                digests.append((SS.digest(session(ctx, out["session_id"])["state"]), out["opening"]["signature"]))
        self.assertEqual(digests[0], digests[1])

    def test_a_custom_game_does_not_take_part_in_opening_dedupe(self):
        with app() as ctx:
            ids = Ids()
            new_custom(ctx, ids, example(), seed=9)
            normal = open_game(ctx, ids, mode="daily", seed=None)
            history = repo.opening_history(ctx.db())
            self.assertEqual([h["seed"] for h in history], [normal["seed"]])
            self.assertTrue(all(not h["signature"].startswith("custom_guesthouse|") for h in history))

    def test_small_name_pools_do_not_repeat_given_names_while_unused_ones_remain(self):
        world = example()
        world["name_pools"].update(given_female=["晚晴", "若溪"], given_male=["远舟", "启明"], given_neutral=["一帆", "知秋"])
        for seed in range(1, 21):
            with app() as ctx:
                out = new_custom(ctx, Ids(), world, seed=seed, npc_gender_preference="female_only", player={"gender": "female"})
                state = session(ctx, out["session_id"])["state"]
                givens = [c["given"] for c in state["characters"].values() if c["given"]]
                self.assertEqual(len(givens), len(set(givens)), (seed, givens))


class ModeTest(unittest.TestCase):
    def test_random_mode_settles_on_the_only_mode_the_world_can_open(self):
        world = example()
        world["pressures"] = []
        with app() as ctx:
            ids = Ids()
            for seed in range(1, 8):
                out = new_custom(ctx, ids, world, mode="random", seed=seed)
                self.assertEqual(session(ctx, out["session_id"])["state"]["mode"], "daily")

    def test_random_mode_uses_both_modes_when_both_are_there(self):
        with app() as ctx:
            ids = Ids()
            modes = {session(ctx, new_custom(ctx, ids, example(), mode="random", seed=s)["session_id"])["state"]["mode"] for s in range(1, 21)}
        self.assertEqual(modes, {"daily", "pressure"})

    def test_asking_for_a_mode_the_world_cannot_open_names_the_list(self):
        world = example()
        world["pressures"] = world["pressures"][:1]
        with app() as ctx:
            err = refused(self, ctx, Ids(), world, mode="pressure")
            self.assertEqual(paths(err), {"$.custom_world.pressures"})
            self.assertIn("至少 2 条", err.details[0]["reason"])

    def test_a_world_with_neither_mode_is_refused(self):
        world = example()
        world["pressures"] = []
        world["daily_activities"] = world["daily_activities"][:1]
        with app() as ctx:
            err = refused(self, ctx, Ids(), world, mode="random")
            self.assertIn("$.custom_world.daily_activities", paths(err))


class ValidationTest(unittest.TestCase):
    def test_every_problem_comes_back_at_once_under_custom_world(self):
        world = example()
        world["rules"] = world["rules"][:1]
        world["character_templates"][1]["age_range"] = [16, 30]
        world["player_identities"][0]["age_range"] = [17, 40]
        world["character_templates"][0]["voices"]["inner"] = "“她要是也走了，这里就真的只剩风了。”"
        world["character_templates"][2]["adult_context"] = "码头上的学徒，跟着师傅学手艺"
        world["locations"][0]["exits"] = ["attic"]
        world["tension_engines"][0]["text"] = "整栋楼只有壁炉是暖的，连魔法都不管用"
        with app() as ctx:
            err = refused(self, ctx, Ids(), world)
        found = paths(err)
        for path in (
            "$.custom_world.rules",
            "$.custom_world.character_templates[1].age_range",
            "$.custom_world.player_identities[0].age_range",
            "$.custom_world.character_templates[0].voices.inner",
            "$.custom_world.character_templates[2].adult_context",
            "$.custom_world.locations[0].exits[0]",
            "$.custom_world.tension_engines[0].text",
        ):
            self.assertIn(path, found)
        self.assertTrue(all(d["path"].startswith("$.custom_world") for d in err.details))
        self.assertEqual(err.message, "自定义世界有 %d 处问题" % len(err.details))

    def test_missing_ages_unknown_fields_and_bad_shapes_are_refused(self):
        world = example()
        del world["character_templates"][0]["age_range"]
        world["character_templates"][1]["favorite_color"] = "蓝"
        with app() as ctx:
            ids = Ids()
            err = refused(self, ctx, ids, world)
            self.assertTrue({"$.custom_world.character_templates[0].age_range", "$.custom_world.character_templates[1].favorite_color"} <= paths(err))
            err = refused(self, ctx, ids, ["不是对象"])
            self.assertEqual(paths(err), {"$.custom_world"})

    def test_the_custom_flag_base_packs_and_existing_ids_are_checked(self):
        with app() as ctx:
            ids = Ids()
            world = example()
            world["custom"] = False
            self.assertIn("$.custom_world.custom", paths(refused(self, ctx, ids, world)))
            world = example()
            world["extends"] = "base_era"
            self.assertIn("$.custom_world.extends", paths(refused(self, ctx, ids, world)))
            world = example()
            world["id"] = "harbor_night_shift"
            self.assertIn("$.custom_world.id", paths(refused(self, ctx, ids, world)))

    def test_an_underage_player_setting_is_blocked_in_a_custom_world(self):
        with app() as ctx:
            with self.assertRaises(AppError) as caught:
                new_custom(ctx, Ids(), example(), player={"age": 17})
            self.assertEqual(caught.exception.code, "SAFETY_BLOCK")
            self.assertEqual(ctx.db().execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)

    def test_replay_and_world_locks_do_not_mix_with_a_custom_world(self):
        with app() as ctx:
            ids = Ids()
            self.assertIn("$.replay", paths(refused(self, ctx, ids, example(), code="INVALID_INPUT", replay=True)))
            err = refused(self, ctx, ids, example(), code="INVALID_INPUT", locks={"world_id": "harbor_night_shift"})
            self.assertIn("$.locks.world_id", paths(err))


class PlayTest(unittest.TestCase):
    """A small pack (no background cast, channels or twists) must carry a long game."""

    def play(self, ctx, ids, sid, narrator, turns):
        for _ in range(turns):
            info = repo.load_session(ctx.db(), sid)
            payload = narrator.commit(info["state"], info["content"])
            service.commit_turn(ctx, dict(payload, session_id=sid, request_id=ids(), expected_revision=info["revision"]))

    def test_a_custom_game_plays_saves_loads_exports_and_imports(self):
        for mode, seed in (("pressure", 3), ("daily", 4)):
            with app() as ctx:
                ids = Ids()
                sid = new_custom(ctx, ids, example(), mode=mode, seed=seed)["session_id"]
                self.play(ctx, ids, sid, FakeNarrator(seed), 60)
                state = session(ctx, sid)["state"]
                self.assertEqual(state["turn"], 61)
                self.assertGreaterEqual(state["clock"]["day"], 2)
                self.assertEqual(service.status(ctx, {"session_id": sid, "level": "debug"})["debug"]["state_problems"], [])
                service.save_slot(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": state["revision"], "name": "民宿"})
                loaded = service.load_slot(ctx, {"request_id": ids(), "name": "民宿"})
                self.assertEqual(SS.digest(session(ctx, loaded["session_id"])["state"]), SS.digest(session(ctx, sid)["state"]))
                self.play(ctx, ids, loaded["session_id"], FakeNarrator(seed + 100), 5)
                out = service.export_save(ctx, {"session_id": sid})
                imported = service.import_save(ctx, {"request_id": ids(), "path": out["path"]})
                copy_info = session(ctx, imported["session_id"])
                self.assertTrue(copy_info["content"]["world"]["custom"])
                self.assertEqual(SS.digest(copy_info["state"]), SS.digest(session(ctx, sid)["state"]))
                self.assertEqual(repo.opening_history(ctx.db()), [])

    def test_want_twist_in_a_world_without_twists_says_so_without_failing(self):
        with app() as ctx:
            ids = Ids()
            sid = new_custom(ctx, ids, copy.deepcopy(example()), mode="pressure", seed=3)["session_id"]
            out = service.get_context(ctx, {"session_id": sid, "want_twist": True})
            self.assertEqual(out["twist_candidates"], [])


if __name__ == "__main__":
    unittest.main()
