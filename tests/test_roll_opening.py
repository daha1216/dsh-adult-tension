from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import unittest
from unittest import mock
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "roll_opening.py"
SPEC = importlib.util.spec_from_file_location("roll_opening", SCRIPT)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class RollOpeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pools = MOD.load_pools()

    def test_surface_flavor_pool_nonempty_and_within_length_contract(self) -> None:
        items = self.pools["表层风味"]
        self.assertTrue(items)
        for item in items:
            self.assertLessEqual(len(item), 8, f"表层风味条目超过 8 字会被脚本筛掉: {item!r}")

    def test_quirk_pool_nonempty_and_within_length_contract(self) -> None:
        items = self.pools["口癖"]
        self.assertTrue(items)
        for item in items:
            self.assertLessEqual(len(item), 8, f"口癖条目超过 8 字会被脚本筛掉: {item!r}")

    def test_appearance_axes_have_groups(self) -> None:
        axes = self.pools["外观轴"]
        self.assertGreaterEqual(len(axes), 4)
        for axis, groups in axes.items():
            self.assertTrue(groups, f"外观子轴 {axis} 没有分组条目")

    def test_decision_axes_contract(self) -> None:
        axes = self.pools["决策轴"]
        self.assertGreaterEqual(len(axes), 3)
        for axis, items in axes.items():
            self.assertGreaterEqual(len(items), 2, f"决策轴 {axis} 至少需要两项")

    def test_profile_weights_sum_to_100(self) -> None:
        weights = self.pools["人物生成倾向"]
        self.assertEqual(sum(weights.values()), 100)

    def test_supporting_functions_nonempty(self) -> None:
        self.assertTrue(self.pools["配角功能"])

    def test_material_pools_nonempty(self) -> None:
        for key in ("核心规则", "美学基调", "权力结构", "张力引擎", "社会规则",
                    "压力来源", "场景动作", "身份侧", "处境侧", "反差轴"):
            self.assertTrue(self.pools[key], key)
        self.assertTrue(self.pools["时代与地点"]["时代"])
        self.assertTrue(self.pools["时代与地点"]["地点"])

    def test_twist_pool_has_seven_categories(self) -> None:
        twists = self.pools["转折池"]
        self.assertGreaterEqual(len(twists), 6)
        for category, items in twists.items():
            self.assertTrue(items, f"转折类 {category} 没有条目")

    def test_same_seed_is_deterministic(self) -> None:
        self.assertEqual(MOD.build_roll(self.pools, 7), MOD.build_roll(self.pools, 7))

    def test_different_seeds_differ(self) -> None:
        self.assertNotEqual(MOD.build_roll(self.pools, 3), MOD.build_roll(self.pools, 99))

    def test_protocol_version_and_draw_plan_are_explicit(self) -> None:
        roll = MOD.build_roll(self.pools, 1)
        self.assertEqual(roll["protocol_version"], MOD.PROTOCOL_VERSION)
        self.assertEqual(tuple(MOD.DRAW_PLAN), MOD.DRAW_PLAN)

    def test_all_custom_requires_custom_values_or_marks_required(self) -> None:
        roll = MOD.build_roll(self.pools, 1, mode="all_custom")
        for key in MOD.CUSTOM_KEYS:
            self.assertEqual(roll.get(key), "custom_required", key)
        roll = MOD.build_roll(self.pools, 1, mode="all_custom", custom={"时代": "自定义时代"})
        self.assertEqual(roll["时代"], "自定义时代")

    def test_explicit_lock_precedes_all_custom(self) -> None:
        roll = MOD.build_roll(self.pools, 1, mode="all_custom", locks={"时代": "当代都市"})
        self.assertEqual(roll["时代"], "当代都市")

    def test_invalid_locks_raise_anchor_error(self) -> None:
        for locks in ({"不存在": "x"}, {"时代": ""}):
            with self.assertRaises(MOD.AnchorError):
                MOD.build_roll(self.pools, 1, locks=locks)

    def test_force_table_rejects_out_of_pool_lock(self) -> None:
        with self.assertRaises(MOD.AnchorError):
            MOD.build_roll(self.pools, 1, mode="force_table", locks={"时代": "表外时代"})

    def test_all_custom_marks_axes(self) -> None:
        roll = MOD.build_roll(self.pools, 1, mode="all_custom")
        for key in MOD.CUSTOM_KEYS:
            self.assertEqual(roll.get(key), "custom_required", key)

    def test_lock_overrides_draw(self) -> None:
        roll = MOD.build_roll(self.pools, 1, locks={"时代": "当代都市"})
        self.assertEqual(roll["时代"], "当代都市")

    def test_lock_value_must_be_in_pool(self) -> None:
        with self.assertRaises(MOD.AnchorError):
            MOD.build_roll(self.pools, 1, locks={"时代": "表外时代"})

    def test_lock_single_tension_engine_completes_to_two_distinct(self) -> None:
        roll = MOD.build_roll(self.pools, 7, locks={"张力引擎": "情感拉扯"})
        engines = [part.strip() for part in roll["张力引擎"].split("、")]
        self.assertEqual(2, len(engines))
        self.assertIn("情感拉扯", engines)
        self.assertEqual(len(set(engines)), 2)
        for engine in engines:
            self.assertIn(engine, self.pools["张力引擎"], engine)

    def test_lock_double_tension_engine_preserved(self) -> None:
        roll = MOD.build_roll(self.pools, 7, locks={"张力引擎": "情感拉扯、时限逼近"})
        self.assertEqual("情感拉扯、时限逼近", roll["张力引擎"])
        roll = MOD.build_roll(self.pools, 7, locks={"张力引擎": "情感拉扯,组织更迭"})
        self.assertEqual("情感拉扯、组织更迭", roll["张力引擎"])

    def test_lock_duplicate_tension_engine_rejected(self) -> None:
        with self.assertRaises(MOD.AnchorError):
            MOD.build_roll(self.pools, 7, locks={"张力引擎": "情感拉扯、情感拉扯"})

    def test_lock_tension_engine_out_of_pool_rejected(self) -> None:
        with self.assertRaises(MOD.AnchorError):
            MOD.build_roll(self.pools, 7, locks={"张力引擎": "表外引擎"})
        with self.assertRaises(MOD.AnchorError):
            MOD.build_roll(self.pools, 7, locks={"张力引擎": "情感拉扯、表外引擎"})

    def test_lock_tension_engine_too_many_values_rejected(self) -> None:
        with self.assertRaises(MOD.AnchorError):
            MOD.build_roll(self.pools, 7, locks={"张力引擎": "情感拉扯、时限逼近、名声保卫"})

    def test_all_custom_tension_engine_custom_completes_to_two(self) -> None:
        roll = MOD.build_roll(self.pools, 7, mode="all_custom", custom={"张力引擎": "自定义引擎"})
        engines = [part.strip() for part in roll["张力引擎"].split("、")]
        self.assertEqual(2, len(engines))
        self.assertIn("自定义引擎", engines)
        self.assertEqual(len(set(engines)), 2)
        roll = MOD.build_roll(self.pools, 7, mode="all_custom",
                              custom={"张力引擎": "自定义引擎A、自定义引擎B"})
        self.assertEqual("自定义引擎A、自定义引擎B", roll["张力引擎"])

    def test_realism_aesthetic_skips_flavor_and_quirk(self) -> None:
        roll = MOD.build_roll(self.pools, 1, locks={"美学基调": "写实文学"})
        self.assertEqual(roll["表层风味"], "—")
        self.assertEqual(roll["口癖"], "—")

    def test_realism_aesthetic_restricts_appearance(self) -> None:
        roll = MOD.build_roll(self.pools, 2, locks={"美学基调": "写实文学"})
        for entry in roll["外观·主NPC"]:
            if entry["axis"] == "发色":
                self.assertEqual(entry["group"], "自然发色")
            if entry["axis"] == "瞳与面部" and entry["group"] == "瞳色":
                self.assertNotEqual(entry["item"], "异色瞳")

    def test_twists_draw_2_or_3_distinct(self) -> None:
        picks = MOD.draw_twists(self.pools, 5)
        self.assertIn(len(picks), (2, 3))
        self.assertEqual(len(picks), len(set(picks)))

    def test_main_self_check_passes(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = MOD.main(["--seed", "1", "--no-history", "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(buffer.getvalue())
        self.assertEqual(data["seed"], 1)
        self.assertEqual(data["mode"], "table")
        self.assertTrue(data["核心规则"])

    def test_default_seed_retries_when_history_signature_repeats(self) -> None:
        first = MOD.build_roll(self.pools, 10)
        with mock.patch.object(MOD, "recent_signatures", return_value={MOD._roll_signature(first)}), \
             mock.patch.object(MOD, "append_history") as append, \
             mock.patch.object(MOD.random, "SystemRandom", return_value=mock.Mock(randrange=mock.Mock(side_effect=[10, 11]))):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = MOD.main(["--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(buffer.getvalue())
        self.assertEqual(data["seed"], 11)
        append.assert_called_once()

    def test_explicit_seed_warns_but_remains_deterministic(self) -> None:
        roll = MOD.build_roll(self.pools, 10)
        stderr = io.StringIO()
        with mock.patch.object(MOD, "recent_signatures", return_value={MOD._roll_signature(roll)}), \
             mock.patch.object(MOD, "append_history"):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = MOD.main(["--seed", "10", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn("显式 seed 保持确定性", stderr.getvalue())

    def test_no_history_neither_reads_nor_writes(self) -> None:
        with mock.patch.object(MOD, "recent_signatures", side_effect=AssertionError("must not read")), \
             mock.patch.object(MOD, "append_history", side_effect=AssertionError("must not write")):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = MOD.main(["--seed", "1", "--no-history", "--format", "json"])
        self.assertEqual(code, 0)

    def test_main_twist_mode(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = MOD.main(["--twist", "--seed", "5", "--no-history", "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(buffer.getvalue())
        self.assertIn(len(data["twists"]), (2, 3))

    def test_negative_seed_rejected(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = MOD.main(["--seed", "-1"])
        self.assertEqual(code, 2)

    def test_scene_action_buckets_exist(self) -> None:
        self.assertTrue(self.pools["场景动作·靠近"])
        self.assertTrue(self.pools["场景动作·交易"])
        self.assertTrue(self.pools["玩家化身轴"]["称谓"])

    def test_scene_action_defaults_to_approach_bucket(self) -> None:
        for seed in range(24):
            roll = MOD.build_roll(self.pools, seed)
            self.assertIn(roll["场景动作"], self.pools["场景动作·靠近"], roll["场景动作"])

    def test_lock_can_use_trade_scene_action(self) -> None:
        item = self.pools["场景动作·交易"][0]
        roll = MOD.build_roll(self.pools, 1, locks={"场景动作": item})
        self.assertEqual(item, roll["场景动作"])

    def test_table_mode_does_not_stack_leverage_engines(self) -> None:
        for seed in range(40):
            roll = MOD.build_roll(self.pools, seed)
            engines = {part.strip() for part in roll["张力引擎"].split("、") if part.strip()}
            self.assertFalse(engines <= MOD.LEVERAGE_ENGINES and len(engines) == 2, roll["张力引擎"])

    def test_lock_may_stack_leverage_engines(self) -> None:
        roll = MOD.build_roll(self.pools, 1, locks={"张力引擎": "债务压力、第三方施压"})
        self.assertEqual("债务压力、第三方施压", roll["张力引擎"])

    def test_player_high_avoids_leverage_situation(self) -> None:
        for seed in range(24):
            roll = MOD.build_roll(self.pools, seed, locks={"权力结构": "player_high"})
            self.assertNotIn(roll["处境"], MOD.SITUATION_LEVERAGE, roll["处境"])

    def test_player_avatar_axes_present(self) -> None:
        roll = MOD.build_roll(self.pools, 3)
        self.assertIn(roll["玩家称谓"], self.pools["玩家化身轴"]["称谓"])
        self.assertIn(roll["玩家年龄段"], self.pools["玩家化身轴"]["年龄段"])
        self.assertIn(roll["玩家社会位置"], self.pools["玩家化身轴"]["社会位置"])
        self.assertIn("未决动作须落在非交易靠近", roll["开局约束"])
        self.assertEqual(roll["protocol_version"], "opening-roll/v3")


if __name__ == "__main__":
    unittest.main()
