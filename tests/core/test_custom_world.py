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
from adult_tension.domain import structure as ST
from adult_tension.domain import worldpack
from adult_tension.errors import AppError
from adult_tension.persistence import repo
from helpers.cli import REPO_ROOT
from helpers.domain import STORE
from helpers.service import Ids, app, open_game, record, session

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

    def test_overlong_cards_and_pressures_are_refused(self):
        # A card or pressure on stage goes into every full context; the
        # ceilings keep one long item from squeezing the others.
        world = example()
        template, pressure = world["character_templates"][0], world["pressures"][0]
        template["situation"]["pressure"] += "风" * (ST.TEMPLATE_TEXT_MAX - worldpack.text_chars(template) + 1)
        pressure["trigger"] += "雨" * (ST.PRESSURE_TEXT_MAX - worldpack.text_chars(pressure) + 1)
        reasons = {p["path"]: p["reason"] for p in worldpack.length_problems(world)}
        self.assertEqual(set(reasons), {"$.character_templates[0]", "$.pressures[0]"})
        self.assertIn("%d 字 > %d" % (ST.TEMPLATE_TEXT_MAX + 1, ST.TEMPLATE_TEXT_MAX), reasons["$.character_templates[0]"])
        self.assertIn("%d 字 > %d" % (ST.PRESSURE_TEXT_MAX + 1, ST.PRESSURE_TEXT_MAX), reasons["$.pressures[0]"])
        template["situation"]["pressure"] = template["situation"]["pressure"][:-1]
        pressure["trigger"] = pressure["trigger"][:-1]
        self.assertEqual(worldpack.length_problems(world), [])
        # IDs and tags do not count.
        pressure["tags"] = ["violence"] * 500
        self.assertEqual(worldpack.length_problems(world), [])

    def test_the_validator_applies_the_text_ceilings(self):
        world = example()
        lowest = min(worldpack.text_chars(t) for t in world["character_templates"])
        saved = ST.TEMPLATE_TEXT_MAX
        ST.TEMPLATE_TEXT_MAX = lowest - 1
        try:
            _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        finally:
            ST.TEMPLATE_TEXT_MAX = saved
        self.assertEqual({p["path"] for p in problems}, {"$.character_templates[%d]" % i for i in range(len(world["character_templates"]))})
        with app() as ctx:
            ST.TEMPLATE_TEXT_MAX = lowest - 1
            try:
                err = refused(self, ctx, Ids(), world)
            finally:
                ST.TEMPLATE_TEXT_MAX = saved
        self.assertIn("$.custom_world.character_templates[0]", paths(err))

    def test_gendered_address_needs_a_known_gender(self):
        # The player is not asked their gender, so 先生 or 小姐 may only
        # address someone whose gender the world fixes (P16).
        world = example()
        world["name_pools"]["nickname_patterns"].append({"pattern": "{family}哥", "gender": "any"})
        world["player_identities"][0]["title_patterns"] = [{"pattern": "{family}先生", "gender": "any"}]
        world["hooks"][0]["text"] = "{npc.name}朝{player.name}先生点了点头"
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        reasons = {p["path"]: p["reason"] for p in problems}
        self.assertEqual(
            set(reasons),
            {
                "$.name_pools.nickname_patterns[1].gender",
                "$.player_identities[0].title_patterns[0].gender",
                "$.player_identities[0].title_patterns",
                "$.hooks[0].text",
            },
        )
        self.assertIn("女性", reasons["$.player_identities[0].title_patterns"])
        self.assertIn("先生", reasons["$.hooks[0].text"])
        # Marked for its gender, with a title for the other one: accepted.
        world["name_pools"]["nickname_patterns"][1]["gender"] = "male"
        world["player_identities"][0]["title_patterns"] = [{"pattern": "{family}先生", "gender": "male"}, {"pattern": "{family}小姐", "gender": "female"}]
        world["hooks"][0]["text"] = "{npc.name}朝{player.title}点了点头"
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertEqual(problems, [])
        # An identity whose gender is fixed needs no title for the other one.
        world["player_identities"][0]["gender"] = "male"
        world["player_identities"][0]["title_patterns"] = [{"pattern": "{family}先生", "gender": "any"}]
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertEqual(problems, [])
        # Neutral address compounds (e.g. 郎中) are not falsely flagged as gendered.
        world["player_identities"][0]["gender"] = "any"
        world["player_identities"][0]["title_patterns"] = [{"pattern": "{family}老师", "gender": "any"}]
        world["hooks"][0]["text"] = "{npc.name}递给{player.name}郎中一包草药"
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertEqual(problems, [])
        # Opposite-gender title or nickname patterns are refused; female + 先生 (评弹女先生) is exempted.
        world["hooks"][0]["text"] = "{npc.name}朝{player.title}点了点头"
        world["name_pools"]["nickname_patterns"].append({"pattern": "{family}小姐", "gender": "male"})
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertTrue(any("nickname_patterns[2].gender" in p["path"] for p in problems), problems)
        world["name_pools"]["nickname_patterns"][-1] = {"pattern": "{family}先生", "gender": "female"}
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertEqual(problems, [])
        # Fixed-gender identity still rejects opposite-gender title patterns.
        world["player_identities"][0]["gender"] = "male"
        world["player_identities"][0]["title_patterns"] = [{"pattern": "{family}小姐", "gender": "any"}]
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertTrue(any("player_identities[0].title_patterns[0]" in p["path"] for p in problems), problems)
        # Mixed-gender wording does not count as covering both male and female players.
        world["player_identities"][0]["gender"] = "any"
        world["player_identities"][0]["title_patterns"] = [{"pattern": "{family}女伯爵", "gender": "any"}]
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertTrue(any(p["path"] == "$.player_identities[0].title_patterns" for p in problems), problems)

    def test_explicit_requires_intimate_and_custom_tag_is_refused(self):
        world = example()
        world["content_tags"] = ["explicit"]
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        hits = [p for p in problems if p["path"] == "$.content_tags"]
        self.assertTrue(hits and "explicit" in hits[0]["reason"] and "intimate" in hits[0]["reason"], problems)
        world["content_tags"] = ["intimate", "explicit"]
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertEqual(problems, [])
        world["content_tags"] = ["intimate", "custom"]
        world["locations"][0]["tags"] = ["custom"]
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertTrue({"$.content_tags[1]", "$.locations[0].tags[0]"} <= {p["path"] for p in problems}, problems)

    def test_custom_world_checks_identity_fit_and_hook_location_intersection(self):
        world = example()
        world["cast_combos"][0]["player_positions"] = ["high"]
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertTrue(any(p["path"] == "$.cast_combos[0].player_positions" for p in problems), problems)
        world = example()
        for hook in world["hooks"]:
            hook["location_ids"] = ["terrace"]
        for act in world["daily_activities"]:
            act["location_ids"] = ["living_room"]
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertTrue(any(p["path"] == "$.cast_combos[0]" for p in problems), problems)

    def test_a_text_may_not_name_someone_with_a_pool_name(self):
        # The runtime draws each character's name, so a pool name written
        # into a text may belong to nobody, or read as a name where it was
        # meant as a word; one-character names are too often words to count.
        world = example()
        world["hooks"][0]["text"] = "{npc.name}说晚晴明早就到"
        world["character_templates"][0]["voices"]["inner"] = "“许家的人都走了。”"
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        reasons = {p["path"]: p["reason"] for p in problems}
        self.assertEqual(set(reasons), {"$.hooks[0].text"})
        self.assertIn("晚晴", reasons["$.hooks[0].text"])
        world["hooks"][0]["text"] = "{npc.name}说{player.name}明早就到"
        _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
        self.assertEqual(problems, [])

    def test_the_start_label_names_the_day_not_the_hour(self):
        # Activities and pressures choose their own start minute, so a clock
        # time or a countdown in the label would contradict the clock.
        world = example()
        for label in ("暴雨深夜十一点半", "子时初刻", "闭馆倒计时", "开播前十五秒", "第一天 22:30"):
            world["clock_start"]["label"] = label
            _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
            self.assertEqual([p["path"] for p in problems], ["$.clock_start.label"], label)
        for label in ("民国十五年，梅雨季", "1987 年 11 月，一个下着冷雨的星期三", None):
            world["clock_start"]["label"] = label
            _pack, problems = worldpack.validate_world(world, custom=True, tag_ids=TAG_IDS)
            self.assertEqual(problems, [], label)

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
            service.commit_turn(ctx, record(sid, ids(), info["revision"], payload))

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
                self.assertEqual(imported["commit_template"]["session_id"], imported["session_id"])
                self.assertTrue(copy_info["content"]["world"]["custom"])
                self.assertEqual(SS.digest(copy_info["state"]), SS.digest(session(ctx, sid)["state"]))
                self.assertEqual(repo.opening_history(ctx.db()), [])

    def test_want_twist_in_a_world_without_twists_says_so_without_failing(self):
        with app() as ctx:
            ids = Ids()
            sid = new_custom(ctx, ids, copy.deepcopy(example()), mode="pressure", seed=3)["session_id"]
            out = service.get_context(ctx, {"session_id": sid, "want_twist": True})
            self.assertEqual(out["twist_candidates"], [])


class MyWorldsTest(unittest.TestCase):
    """“保存世界 / 我的世界”: a custom world kept under a name opens again later."""

    def test_a_saved_world_lists_reopens_and_deletes(self):
        with app() as ctx:
            ids = Ids()
            first = new_custom(ctx, ids, example(), mode="daily", seed=5)
            saved = service.save_world(ctx, {"request_id": ids(), "session_id": first["session_id"], "name": "淡季 民宿"})
            self.assertEqual(saved["world"]["name"], "淡季-民宿")
            listed = service.my_worlds(ctx, {})["worlds"]
            self.assertEqual([(w["name"], w["world_id"]) for w in listed], [("淡季-民宿", example()["id"])])
            self.assertTrue(listed[0]["summary"])
            again = service.new_game(ctx, {"request_id": ids(), "mode": "daily", "seed": 5, "my_world": "淡季-民宿"})
            self.assertEqual(session(ctx, again["session_id"])["content"]["world"], session(ctx, first["session_id"])["content"]["world"])
            self.assertEqual(again["opening"]["footer"].split("｜")[:2], first["opening"]["footer"].split("｜")[:2])
            self.assertEqual(repo.opening_history(ctx.db()), [])
            with self.assertRaises(AppError) as caught:
                service.delete_world(ctx, {"request_id": ids(), "name": "淡季-民宿"})
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
            service.delete_world(ctx, {"request_id": ids(), "name": "淡季-民宿", "confirm": True})
            self.assertEqual(service.my_worlds(ctx, {})["worlds"], [])
            # games played in it keep their world
            self.assertTrue(session(ctx, again["session_id"])["content"]["world"]["custom"])

    def test_a_taken_name_needs_overwrite_and_a_ready_made_world_cannot_be_saved(self):
        with app() as ctx:
            ids = Ids()
            sid = new_custom(ctx, ids, example())["session_id"]
            service.save_world(ctx, {"request_id": ids(), "session_id": sid, "name": "民宿"})
            with self.assertRaises(AppError) as caught:
                service.save_world(ctx, {"request_id": ids(), "session_id": sid, "name": "民宿"})
            self.assertEqual(caught.exception.code, "SLOT_CONFLICT")
            service.save_world(ctx, {"request_id": ids(), "session_id": sid, "name": "民宿", "overwrite": True})
            ready = open_game(ctx, ids)["session_id"]
            with self.assertRaises(AppError) as caught:
                service.save_world(ctx, {"request_id": ids(), "session_id": ready, "name": "港口"})
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
            self.assertEqual(len(service.my_worlds(ctx, {})["worlds"]), 1)

    def test_unknown_names_and_mixed_inputs_are_refused(self):
        with app() as ctx:
            ids = Ids()
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": ids(), "mode": "daily", "my_world": "没有"})
            self.assertEqual(caught.exception.code, "NOT_FOUND")
            sid = new_custom(ctx, ids, example())["session_id"]
            service.save_world(ctx, {"request_id": ids(), "session_id": sid, "name": "民宿"})
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": ids(), "mode": "daily", "my_world": "民宿", "custom_world": example()})
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
            with self.assertRaises(AppError) as caught:
                service.new_game(ctx, {"request_id": ids(), "mode": "daily", "my_world": "民宿", "replay": True, "seed": 3})
            self.assertEqual(caught.exception.code, "INVALID_INPUT")

    def test_the_inspiration_list_is_fixed_text(self):
        from adult_tension.application import guide

        with app() as ctx:
            out = guide.run(ctx, {"topic": "custom_world"})
            self.assertEqual(out["stage"], "custom_world")
            self.assertIn("保存世界", out["text"])
            self.assertIn("自定义世界", "\n".join(guide.run(ctx, {})["lines"]))


class StoreUpgradeDbTest(unittest.TestCase):
    """Regression coverage for ContentStore, verify_installed, upgrade, and db.ensure_schema."""

    def test_store_caches_normalized_world_and_verify_checks_tags_and_index_shape(self):
        from adult_tension.content.store import ContentStore
        from adult_tension.content.verify import verify_installed
        from helpers.fs import temp_dir

        with temp_dir() as tmp:
            worlds_dir = os.path.join(tmp, "worlds")
            os.makedirs(worlds_dir)
            raw = copy.deepcopy(STORE.world_raw("harbor_night_shift"))
            raw.pop("clock_style", None)
            raw.pop("default_person", None)
            raw["hooks"][0].pop("location_ids", None)
            with open(os.path.join(worlds_dir, "harbor_night_shift.json"), "w", encoding="utf-8") as handle:
                json.dump(raw, handle, ensure_ascii=False)
            with open(os.path.join(tmp, "tags.json"), "w", encoding="utf-8") as handle:
                json.dump(STORE.tags(), handle, ensure_ascii=False)
            with open(os.path.join(tmp, "index.json"), "w", encoding="utf-8") as handle:
                json.dump({"content_version": "test", "worlds": [{"id": "harbor_night_shift", "status": "draft"}]}, handle, ensure_ascii=False)
            store = ContentStore(tmp)
            loaded = store.world("harbor_night_shift")
            self.assertEqual(loaded["clock_style"], "hm")
            self.assertEqual(loaded["default_person"], "second")
            self.assertEqual(loaded["hooks"][0]["location_ids"], [])
            self.assertIs(store.world("harbor_night_shift"), loaded)
            # Non-dict index.json and bad/missing tags.json are reported as CONTENT_ERROR.
            with open(os.path.join(tmp, "index.json"), "w", encoding="utf-8") as handle:
                json.dump(["not-a-dict"], handle)
            with open(os.path.join(tmp, "tags.json"), "w", encoding="utf-8") as handle:
                json.dump({"tags": []}, handle)
            problems, _summary = verify_installed(ContentStore(tmp))
            self.assertTrue(any("index.json" in p["path"] and p.get("code") == "CONTENT_ERROR" for p in problems), problems)
            self.assertTrue(any("tags.json" in p["path"] and p.get("code") == "CONTENT_ERROR" for p in problems), problems)
            self.assertTrue(all("重新编译内容" not in (p.get("hint") or "") for p in problems), problems)
            os.remove(os.path.join(tmp, "tags.json"))
            problems, _summary = verify_installed(ContentStore(tmp))
            self.assertTrue(any("tags.json" in p["path"] for p in problems), problems)

    def test_upgrade_rejects_bad_schema_version_and_handles_missing_keys(self):
        from adult_tension.domain.upgrade import upgrade

        for bad in (0, -1, False, True, "1", None):
            with self.assertRaises(AppError) as caught:
                upgrade({"schema_version": bad})
            self.assertEqual(caught.exception.code, "INVALID_INPUT", bad)
        malformed = {"schema_version": 1, "facts": {"f1": "bad"}, "events": {"e1": {}}, "counters": {}, "memory": None, "requests": "bad"}
        upgraded = upgrade(malformed)
        self.assertEqual(upgraded["schema_version"], 2)
        minimal = upgrade({"schema_version": 1})
        self.assertEqual(minimal["schema_version"], 2)

    def test_db_ensure_schema_rechecks_version_inside_write_lock(self):
        import sqlite3
        from unittest import mock

        from adult_tension import DB_SCHEMA_VERSION
        from adult_tension.persistence import db
        from helpers.fs import temp_dir

        with temp_dir() as tmp:
            db_file = os.path.join(tmp, "test.db")
            backups_dir = os.path.join(tmp, "backups")
            conn = db.connect(db_file)
            try:
                # Simulate another process upgrading to a newer version before we acquire the lock.
                with mock.patch.object(db, "read_schema_version", side_effect=[1, DB_SCHEMA_VERSION + 1]):
                    with self.assertRaises(AppError) as caught:
                        db.ensure_schema(conn, backups_dir)
                self.assertEqual(caught.exception.code, "UNSUPPORTED_VERSION")
                self.assertFalse(conn.in_transaction)
                self.assertFalse(os.path.exists(backups_dir))
                # Simulate another process finishing migration to DB_SCHEMA_VERSION before we acquire the lock.
                with mock.patch.object(db, "read_schema_version", side_effect=[1, DB_SCHEMA_VERSION]):
                    report = db.ensure_schema(conn, backups_dir)
                self.assertFalse(report["migrated"])
                self.assertIsNone(report["backup"])
                self.assertEqual(report["from"], DB_SCHEMA_VERSION)
                self.assertFalse(conn.in_transaction)
                self.assertFalse(os.path.exists(backups_dir))
            finally:
                conn.close()

    def test_worldpack_p2_cleanup_checks(self):
        pack = copy.deepcopy(STORE.world("harbor_night_shift"))
        # walk_texts skips name_pools.order; world_stats skips non-list keys.
        walked_paths = {path for path, _txt in worldpack.walk_texts(pack)}
        self.assertNotIn("$.name_pools.order", walked_paths)
        stats = worldpack.world_stats(pack)
        self.assertNotIn("order", stats["names"])
        # intimacy_tendency likes/dislikes have descriptions for doc generation.
        tendency_fields = worldpack.TEMPLATE.fields["intimacy_tendency"].spec.fields
        self.assertTrue(tendency_fields["likes"].desc)
        self.assertTrue(tendency_fields["dislikes"].desc)
        # text_chars excludes enum/ID fields (gender, source, flags, holder, subject, location exits).
        pr = copy.deepcopy(pack["pressures"][0])
        base_chars = worldpack.text_chars(pr)
        pr["source"] = "organization"
        pr["flags"] = ["timed", "leverage"]
        pr["leverage"] = {"holder": "very_long_template_id", "subject": "another_long_id", "basis": ""}
        self.assertEqual(worldpack.text_chars(pr), base_chars)
        tpl = copy.deepcopy(pack["character_templates"][0])
        tpl_chars = worldpack.text_chars(tpl)
        tpl["gender"] = "nonbinary"
        self.assertEqual(worldpack.text_chars(tpl), tpl_chars)
        loc = copy.deepcopy(pack["locations"][0])
        loc_chars = worldpack.text_chars(loc)
        loc["exits"] = ["very_long_exit_location_id_1", "very_long_exit_location_id_2"]
        self.assertEqual(worldpack.text_chars(loc), loc_chars)
        # validate_world(..., custom=False) symmetrically rejects custom: true.
        pack["custom"] = True
        _p, problems = worldpack.validate_world(pack, custom=False, tag_ids=TAG_IDS)
        self.assertTrue(any(p["path"] == "$.custom" for p in problems), problems)
        # Pronoun hint adapts to allowed scopes of the field.
        w = example()
        w["premise"] = "他站在礁石上等船。"
        w["character_templates"][0]["voices"]["inner"] = "“她真麻烦。”"
        w["daily_activities"][0]["beats"][0] = "她递来一杯姜茶。"
        w["cast_combos"][0]["chemistry"] = "他和谁都不对付。"
        _p, problems = worldpack.validate_world(w, custom=True, tag_ids=TAG_IDS)
        hints = {p["path"]: p["hint"] for p in problems if "写死了" in p["reason"]}
        self.assertIn("不支持占位符", hints["$.premise"])
        self.assertIn("{npc.ta}", hints["$.character_templates[0].voices.inner"])
        self.assertIn("{player.ta}", hints["$.daily_activities[0].beats[0]"])
        self.assertIn("{槽位.ta}", hints["$.cast_combos[0].chemistry"])

    def test_upgrade_coord_prescan_and_rpartition_dedupe_keys(self):
        from adult_tension.domain.upgrade import upgrade

        state = {
            "schema_version": 1,
            "facts": {
                "f1": {"id": "f1", "turn": 1, "coord": [1, 0]},
                "f2": {"id": "f2", "turn": 1},
                "f3": {"id": "f3", "turn": 2, "coord": [2, 1]},
                "f4": {"id": "f4", "turn": 2},
                "f5": {"id": "f5", "turn": 3},
            },
            "events": {
                "e1": {"id": "e1", "created_turn": 1, "dedupe_key": "room#3#2"},
                "e2": {"id": "e2", "created_turn": 1, "dedupe_key": "room#bar"},
                "e3": {"id": "e3", "created_turn": 1, "dedupe_key": "plain"},
                "e4": {"id": "e4", "created_turn": 1, "dedupe_key": "123"},
            },
            "counters": {},
            "memory": {"chapters": []},
            "requests": {},
        }
        upgraded = upgrade(state)
        self.assertEqual(upgraded["facts"]["f1"]["coord"], [1, 0])
        self.assertEqual(upgraded["facts"]["f2"]["coord"], [1, 1])
        self.assertEqual(upgraded["facts"]["f3"]["coord"], [2, 1])
        self.assertEqual(upgraded["facts"]["f4"]["coord"], [2, 2])
        self.assertEqual(upgraded["facts"]["f5"]["coord"], [3, 1])
        # Turn 1 events without existing coords start at 0 (matching opening.py).
        self.assertEqual(upgraded["events"]["e1"]["coord"], [1, 0])
        self.assertEqual(upgraded["events"]["e2"]["coord"], [1, 1])
        self.assertEqual(
            upgraded["counters"]["event_keys"],
            {"room#3": 2, "room#bar": 1, "plain": 1, "123": 1},
        )

    def test_store_slash_normalization_db_busy_and_repo_guards(self):
        import sqlite3
        from unittest import mock

        from adult_tension import DB_SCHEMA_VERSION
        from adult_tension.content.store import ContentStore
        from adult_tension.errors import NOT_FOUND, STORAGE_BUSY, UNSUPPORTED_VERSION
        from adult_tension.persistence import db
        from helpers.fs import temp_dir

        with temp_dir() as tmp:
            store = ContentStore(tmp)
            with self.assertRaises(AppError) as caught:
                store.world_raw("no_such_world")
            self.assertIn("content/worlds/no_such_world.json", caught.exception.message)
            self.assertNotIn("\\", caught.exception.message)
            self.assertEqual(caught.exception.details[0]["path"], "content/worlds/no_such_world.json")

            # db.py: case-insensitive busy/locked + WAL pragma wrapped to STORAGE_BUSY
            class FakeConn:
                in_transaction = False

                def __init__(self, err):
                    self.err = err

                def execute(self, sql, *args):
                    if "PRAGMA journal_mode=WAL" in sql or "BEGIN IMMEDIATE" in sql:
                        raise sqlite3.OperationalError(self.err)
                    return mock.MagicMock(fetchone=lambda: None)

            with self.assertRaises(AppError) as caught:
                db.begin_write(FakeConn("DATABASE IS LOCKED"))
            self.assertEqual(caught.exception.code, STORAGE_BUSY)
            self.assertEqual(caught.exception.details[0]["code"], STORAGE_BUSY)
            with self.assertRaises(AppError) as caught:
                db.ensure_schema(FakeConn("Database is BUSY"), os.path.join(tmp, "backups"))
            self.assertEqual(caught.exception.code, STORAGE_BUSY)
            self.assertEqual(caught.exception.details[0]["code"], STORAGE_BUSY)

            # db.py: _unsupported_schema code and wording
            err = db._unsupported_schema(DB_SCHEMA_VERSION + 1)
            self.assertEqual(err.code, UNSUPPORTED_VERSION)
            self.assertEqual(err.details[0]["code"], UNSUPPORTED_VERSION)
            self.assertIn("数据库格式", err.message)

            # db.py: schema 0 failure does not falsely claim backup restoration
            conn = db.connect(os.path.join(tmp, "fresh.db"))
            try:
                with mock.patch.dict(os.environ, {"ADULT_TENSION_FAULT": "migration_fail"}):
                    with self.assertRaises(AppError) as caught:
                        db.ensure_schema(conn, os.path.join(tmp, "backups2"))
                self.assertEqual(caught.exception.code, "MIGRATION_FAILED")
                self.assertFalse(caught.exception.extra["restored"])
                self.assertIsNone(caught.exception.extra["backup"])
                self.assertNotIn("已恢复备份", caught.exception.message)
                self.assertNotIn("已恢复备份", caught.exception.details[0]["hint"])
            finally:
                conn.close()

        # repo.py: count_rows whitelist & put_slot missing session preserves existing slot
        with app() as ctx:
            ids = Ids()
            sid = open_game(ctx, ids)["session_id"]
            self.assertGreaterEqual(repo.count_rows(ctx.db(), "turn_log", sid), 0)
            with self.assertRaises(ValueError):
                repo.count_rows(ctx.db(), "sqlite_master", sid)
            with self.assertRaises(ValueError):
                repo.count_rows(ctx.db(), "turn_log; DROP TABLE sessions", sid)
            state = session(ctx, sid)["state"]
            service.save_slot(ctx, {"session_id": sid, "request_id": ids(), "expected_revision": state["revision"], "name": "保留档"})
            with self.assertRaises(AppError) as caught:
                repo.put_slot(ctx.db(), "保留档", "nonexistent_session", "标签", None, 2, "2026-01-01T00:00:00Z")
            self.assertEqual(caught.exception.code, NOT_FOUND)
            # Existing slot was NOT wiped.
            self.assertIsNotNone(repo.get_slot(ctx.db(), "保留档"))


if __name__ == "__main__":
    unittest.main()
