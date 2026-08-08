from __future__ import annotations

import contextlib
import io
import importlib.util
import random
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "roll_opening.py"
SPEC = importlib.util.spec_from_file_location("roll_opening", SCRIPT)
assert SPEC and SPEC.loader
ROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROLLER)

REFS = Path(__file__).parents[1] / "references"
MATERIALS = ROLLER.load_materials(REFS)


def run_roll(seed: int, locks: dict | None = None, genre: str | None = None,
             allow_custom: bool = True, mains: int = 1) -> list[str]:
    lines, _record = ROLLER.roll_all(
        MATERIALS, random.Random(seed), locks or {}, genre,
        allow_custom=allow_custom, mains=mains,
    )
    return lines


def run_roll_with_record(seed: int, locks: dict | None = None,
                         genre: str | None = None,
                         allow_custom: bool = True, mains: int = 1
                         ) -> tuple[list[str], dict[str, str]]:
    return ROLLER.roll_all(
        MATERIALS, random.Random(seed), locks or {}, genre,
        allow_custom=allow_custom, mains=mains,
    )


def field(lines: list[str], key: str) -> str:
    for line in lines:
        if line.startswith(key + ":"):
            return line.partition(":")[2].strip()
    return ""


class ParseTests(unittest.TestCase):
    def test_dang_pool(self) -> None:
        self.assertEqual(MATERIALS["dang_pool"], ["现实", "半架空", "强架空"])

    def test_tone_axes(self) -> None:
        for axis in ROLLER.TONE_AXES:
            self.assertIn(axis, MATERIALS["tone_axes"])
            self.assertGreaterEqual(len(MATERIALS["tone_axes"][axis]), 5, axis)
        self.assertTrue(
            {"乙女向", "百合向", "耽美向"}.isdisjoint(MATERIALS["tone_axes"]["美学基调"])
        )

    def test_aesthetic_is_rolled_by_default(self) -> None:
        aesthetics = {
            next(line.partition(":")[2].strip() for line in run_roll(seed, allow_custom=False)
                 if line.strip().startswith("美学基调:"))
            for seed in range(20)
        }
        self.assertTrue(aesthetics.issubset(set(MATERIALS["tone_axes"]["美学基调"])))
        self.assertGreater(len(aesthetics), 1)

    def test_aesthetic_lock_wins(self) -> None:
        lines = run_roll(1, locks={"aesthetic": "写实文学"}, allow_custom=False)
        self.assertIn("  美学基调: 写实文学（预锁）", lines)

    def test_realistic_aesthetics_skip_flavor_and_speech(self) -> None:
        for aesthetic in ROLLER.REALISTIC_AESTHETICS:
            with self.subTest(aesthetic=aesthetic):
                lines = run_roll(
                    1,
                    locks={"aesthetic": aesthetic, "cast": "2"},
                    allow_custom=False,
                )
                self.assertEqual(field(lines, "主NPC表层风味"), "—")
                self.assertEqual(field(lines, "主NPC口癖"), "—")
                for line in lines:
                    if line.startswith("配角") and "功能=" in line:
                        self.assertIn("表层风味=—", line)
                        self.assertIn("口癖=—", line)

    def test_nonrealistic_aesthetic_keeps_flavor_and_speech(self) -> None:
        lines = run_roll(
            1,
            locks={"aesthetic": "怪谈绘卷"},
            allow_custom=False,
        )
        self.assertNotEqual(field(lines, "主NPC表层风味"), "—")
        self.assertNotEqual(field(lines, "主NPC口癖"), "—")

    def test_real_exclusions_are_explicit(self) -> None:
        exclusions = MATERIALS["real_exclusions"]
        self.assertTrue({"时代与技术", "地域气质"}.issubset(exclusions))
        self.assertIn("魔导科技", exclusions["时代与技术"])
        self.assertIn("丧尸病变", exclusions["大类/末世/灾变类型"])

    def test_world_rule_axes(self) -> None:
        self.assertEqual(set(MATERIALS["world_rule_base"]), set(ROLLER.WORLD_RULE_AXES))
        self.assertEqual(set(MATERIALS["world_rule_supp"]), {"半架空", "强架空"})
        roller = ROLLER.Roller(MATERIALS, random.Random(1), allow_custom=False)
        for axis in ROLLER.WORLD_RULE_AXES:
            real = roller.world_rule_pool("现实", axis)
            half = roller.world_rule_pool("半架空", axis)
            full = roller.world_rule_pool("强架空", axis)
            self.assertGreaterEqual(len(real), 6, axis)
            self.assertGreater(len(half), len(real), axis)
            self.assertGreater(len(full), len(real), axis)

    def test_scene_actions(self) -> None:
        self.assertEqual(len(MATERIALS["scene_actions"]), 16)
        self.assertIn("调查查证", {family for family, _seeds in MATERIALS["scene_actions"]})
        self.assertTrue(all(family and len(seeds.split("、")) >= 3
                            for family, seeds in MATERIALS["scene_actions"]))

    def test_timescape_axes(self) -> None:
        self.assertEqual(set(MATERIALS["timescape"]), {"季节", "时段", "天候", "现场密度"})
        for axis, options in MATERIALS["timescape"].items():
            self.assertGreaterEqual(len(options), 6, axis)

    def test_genres(self) -> None:
        self.assertGreaterEqual(len(MATERIALS["genres"]), 19)
        self.assertTrue(
            {"历史与年代", "犯罪与侦探", "战争与谍报", "职场与行业",
             "公路与荒野", "原生奇幻与神话"}.issubset(MATERIALS["genres"])
        )
        for name, axes in MATERIALS["genres"].items():
            self.assertGreaterEqual(len(axes), 2, name)
            for axis, options in axes.items():
                self.assertGreaterEqual(len(options), 2, f"{name}/{axis}")
        self.assertEqual(set(MATERIALS["genre_dangs"]), set(MATERIALS["genres"]))
        self.assertEqual(MATERIALS["genre_dangs"]["原生奇幻与神话"], {"强架空"})

    def test_engines(self) -> None:
        names = [f for f, _ in MATERIALS["engine_base"]]
        self.assertEqual(
            names,
            ["权力与控制", "身份与义务", "资源与依赖", "时限与取舍", "信息与误解",
             "目标与信任", "声誉与关系", "能力与限制", "成人关系张力"],
        )
        self.assertNotIn("咬合", names)
        for family, items in MATERIALS["engine_base"]:
            self.assertGreaterEqual(len(items), 5, family)
        self.assertEqual(sum(len(items) for _, items in MATERIALS["engine_base"]), 112)
        families = dict(MATERIALS["engine_base"])
        self.assertIn("一方必须借助另一方才能稳定能力", families["能力与限制"])
        self.assertIn("名分一旦确立，就无法继续对第三方含混带过", families["身份与义务"])
        self.assertIn("骄傲阻止了主动求助，但不求助的代价在持续累积", families["声誉与关系"])
        self.assertIn("能否进入或停留，本身就是双方当前最大的限制", families["能力与限制"])
        self.assertEqual(set(MATERIALS["engine_supp"]), {"半架空", "强架空"})
        for dang, count in (("半架空", 6), ("强架空", 7)):
            supplement = MATERIALS["engine_supp"][dang]
            self.assertTrue(set(supplement).issubset(names))
            self.assertEqual(sum(len(items) for items in supplement.values()), count)

    def test_nonreal_engine_supplements_stay_in_core_families(self) -> None:
        base_names = {family for family, _ in MATERIALS["engine_base"]}
        roller = ROLLER.Roller(MATERIALS, random.Random(1), allow_custom=False)
        for dang in ("半架空", "强架空"):
            pool = dict(roller.engine_pool(dang))
            self.assertEqual(set(pool), base_names)
            for family, items in MATERIALS["engine_supp"][dang].items():
                self.assertTrue(set(items).issubset(pool[family]))

    def test_shells(self) -> None:
        names = [name for name, _examples in MATERIALS["shell_base"]]
        self.assertEqual(len(names), 32)
        self.assertIn("密闭旅宿", names)
        self.assertIn("私密交易场", names)
        self.assertTrue({"桃色契约", "情色交易", "异世界迁移"}.isdisjoint(names))
        for dang, count in (("半架空", 4), ("强架空", 7)):
            supplement = MATERIALS["shell_supp"][dang]
            self.assertEqual(len(supplement), count)
            self.assertTrue(all(name and examples for name, examples in supplement))
            self.assertTrue(set(names).isdisjoint(name for name, _examples in supplement))

    def test_identities(self) -> None:
        families = [f for f, _ in MATERIALS["identity_base"]]
        self.assertEqual(len(families), 22)
        self.assertIn("市井与手艺", families)
        self.assertIn("侍奉与身契", families)
        self.assertIn("创作与传统演艺", families)
        self.assertIn("二次元与同人", families)
        self.assertIn("电竞与直播", families)
        self.assertIn("成人行业与感官服务", families)
        self.assertIn("私密撮合与契约中介", families)
        self.assertTrue({
            "春情侍奉", "情色行当", "肉体契约", "创作与演艺", "成人行业与私密服务",
        }.isdisjoint(families))
        self.assertEqual(len(MATERIALS["identity_supp"]["半架空"]), 4)
        self.assertEqual(len(MATERIALS["identity_supp"]["强架空"]), 6)

    def test_situations(self) -> None:
        types = [t for t, _ in MATERIALS["situation_base"]]
        self.assertEqual(len(types), 26)
        self.assertIn("告白悬置", types)
        self.assertIn("受限共处", types)
        self.assertIn("曝光与把柄", types)
        self.assertTrue({"共享空间", "秘密同居", "共处独室", "捡拾来客"}.isdisjoint(types))
        self.assertEqual(len(MATERIALS["situation_supp"]["半架空"]), 7)
        self.assertEqual(len(MATERIALS["situation_supp"]["强架空"]), 12)

    def test_world_specific_pools_extend_only_the_selected_dang(self) -> None:
        roller = ROLLER.Roller(MATERIALS, random.Random(1), allow_custom=False)
        expected_sizes = {
            "现实": (32, 22, 26),
            "半架空": (36, 26, 33),
            "强架空": (39, 28, 38),
        }
        for dang, expected in expected_sizes.items():
            actual = (len(roller.shell_pool(dang)), len(roller.identity_pool(dang)),
                      len(roller.situation_pool(dang)))
            self.assertEqual(actual, expected, dang)

    def test_flavors(self) -> None:
        flavors = MATERIALS["flavors"]
        self.assertGreaterEqual(len(flavors), 24)
        self.assertNotIn("系统自拟", flavors)
        for flavor in flavors:
            self.assertLessEqual(len(flavor), 8, flavor)
            self.assertNotIn("，", flavor)

    def test_appearance_axes(self) -> None:
        self.assertEqual(len(MATERIALS["appearance"]), 5)
        for axis, options in MATERIALS["appearance"].items():
            self.assertGreaterEqual(len(options), 8, axis)

    def test_profile_weights(self) -> None:
        self.assertEqual(sum(MATERIALS["profile_weights"].values()), 100)
        self.assertIn("ordinary_natural", MATERIALS["profile_weights"])

    def test_supporting_functions(self) -> None:
        self.assertEqual(
            MATERIALS["supporting_functions"],
            ["盟友", "阻力", "见证者", "信息源", "竞争者", "后果承接者",
             "引路人", "误导者", "催化剂", "庇护者", "传话人", "监视者"],
        )

    def test_contrast_and_relation_stages(self) -> None:
        self.assertEqual(len(MATERIALS["contrast"]), 22)
        self.assertIn("禁欲系×欲望深", MATERIALS["contrast"])
        self.assertEqual(len(MATERIALS["relation_stages"]), 24)
        self.assertIn("单向暗恋（方向另抽）", MATERIALS["relation_stages"])

    def test_speech_pool(self) -> None:
        self.assertGreaterEqual(len(MATERIALS["speech"]), 12)
        self.assertIn("敬语过剩", MATERIALS["speech"])

    def test_decision_axes(self) -> None:
        self.assertEqual(set(MATERIALS["decision_axes"]), set(ROLLER.DECISION_AXES))
        for axis, options in MATERIALS["decision_axes"].items():
            self.assertGreaterEqual(len(options), 10, axis)

    def test_twist_pool(self) -> None:
        self.assertEqual(
            set(MATERIALS["twists"]),
            {"信息类", "人事类", "资源类", "制度类", "时限类", "关系类", "意外类"},
        )
        for family, items in MATERIALS["twists"].items():
            self.assertGreaterEqual(len(items), 3, family)


class RollTests(unittest.TestCase):
    def test_deterministic_with_seed(self) -> None:
        self.assertEqual(run_roll(5), run_roll(5))

    def test_seeds_vary(self) -> None:
        engines = {field(run_roll(seed), "主引擎") for seed in range(12)}
        self.assertGreaterEqual(len(engines), 3)
        shells = {field(run_roll(seed), "制度与场合壳") for seed in range(12)}
        self.assertGreaterEqual(len(shells), 3)

    def test_sub_engine_family_differs(self) -> None:
        for seed in range(40):
            lines = run_roll(seed)
            if field(lines, "咬合") != "双引擎":
                continue
            main = field(lines, "主引擎").split(" → ")[0]
            sub = field(lines, "副引擎").split(" → ")[0]
            if ROLLER.CUSTOM in (main, sub):
                continue
            self.assertNotEqual(main, sub, f"seed={seed}")

    def test_real_dang_gates_supplements(self) -> None:
        nonreal_shells = {name for rows in MATERIALS["shell_supp"].values()
                          for name, _examples in rows}
        nonreal_identities = {name for rows in MATERIALS["identity_supp"].values()
                              for name, _seeds in rows}
        nonreal_situations = {name for rows in MATERIALS["situation_supp"].values()
                              for name, _hint in rows}
        for seed in range(40):
            lines = run_roll(seed, locks={"dang": "现实"}, allow_custom=False)
            shell = field(lines, "制度与场合壳").split("（")[0]
            identity = field(lines, "主NPC身份").split(" → ")[0]
            situation = field(lines, "主NPC处境").split("（")[0]
            self.assertNotIn(shell, nonreal_shells, f"seed={seed}")
            self.assertNotIn(identity, nonreal_identities, f"seed={seed}")
            self.assertNotIn(situation, nonreal_situations, f"seed={seed}")

    def test_real_dang_gates_explicit_base_exclusions(self) -> None:
        exclusions = MATERIALS["real_exclusions"]
        for seed in range(200):
            lines = run_roll(seed, locks={"dang": "现实"}, allow_custom=False)
            joined = "\n".join(lines)
            for value in exclusions["时代与技术"] | exclusions["地域气质"]:
                self.assertNotIn(f": {value}", joined, f"seed={seed} value={value}")

    def test_no_custom(self) -> None:
        for seed in range(30):
            text = "\n".join(run_roll(seed, allow_custom=False))
            self.assertNotIn("系统自拟", text, f"seed={seed}")

    def test_lock_echo(self) -> None:
        lines = run_roll(3, locks={"shell": "女仆与主题店", "cast": "2"})
        self.assertEqual(field(lines, "制度与场合壳"), "女仆与主题店（预锁）")
        self.assertEqual(field(lines, "配角数"), "2（预锁）")
        self.assertTrue(any(line.startswith("配角2:") for line in lines))

    def test_unknown_genre_notes_fallback(self) -> None:
        lines = run_roll(3, genre="不存在的大类")
        self.assertTrue(any("未收录该大类" in line for line in lines))

    def test_known_genre_rolls_all_axes(self) -> None:
        for name, axes in MATERIALS["genres"].items():
            lines = run_roll(9, genre=name)
            joined = "\n".join(lines)
            self.assertIn(f"大类细分（{name}）", joined)
            for axis in axes:
                self.assertTrue(any(line.strip().startswith(axis + ":") for line in lines),
                                f"{name}/{axis}")

    def test_genre_uses_only_compatible_world_dangs(self) -> None:
        for genre, allowed in MATERIALS["genre_dangs"].items():
            for seed in range(8):
                dang = field(run_roll(seed, genre=genre, allow_custom=False), "世界观档")
                self.assertIn(dang, allowed, f"{genre}/seed={seed}")

    def test_real_genre_axes_filter_explicit_exclusions(self) -> None:
        for genre in ("末世", "宫廷与内苑", "游戏与副本"):
            for seed in range(120):
                text = "\n".join(run_roll(
                    seed, locks={"dang": "现实"}, genre=genre, allow_custom=False,
                ))
                for pool_name, excluded in MATERIALS["real_exclusions"].items():
                    if not pool_name.startswith(f"大类/{genre}/"):
                        continue
                    for value in excluded:
                        self.assertNotIn(f": {value}", text, f"{genre}/seed={seed}/{value}")

    def test_flavors_distinct_within_run(self) -> None:
        for seed in range(20):
            lines = run_roll(seed, locks={"cast": "3"})
            flavors = [field(lines, "主NPC表层风味")]
            for line in lines:
                m = line.partition("表层风味=")[2]
                if line.startswith("配角") and m:
                    flavors.append(m.split(",")[0].strip())
            real = [f for f in flavors if f and f != "—" and "系统自拟" not in f]
            self.assertEqual(len(real), len(set(real)), f"seed={seed}")

    def test_new_opening_fields_roll(self) -> None:
        lines = run_roll(7, allow_custom=False)
        for key in (
            "开场动作", "主NPC关系阶段", "主NPC核心价值", "主NPC压力策略",
            "主NPC关系姿态", "主NPC反差轴", "主NPC口癖",
        ):
            self.assertTrue(field(lines, key), key)
        self.assertTrue(any(line.strip().startswith("核心规则来源:") for line in lines))

    def test_custom_tail_reaches_character_tables(self) -> None:
        seen = {"contrast": False, "flavor": False, "speech": False, "appearance": False}
        for seed in range(500):
            lines = run_roll(seed)
            seen["contrast"] |= ROLLER.CUSTOM in field(lines, "主NPC反差轴")
            seen["flavor"] |= ROLLER.CUSTOM in field(lines, "主NPC表层风味")
            seen["speech"] |= ROLLER.CUSTOM in field(lines, "主NPC口癖")
            seen["appearance"] |= ROLLER.CUSTOM in field(lines, "主NPC外观")
            if all(seen.values()):
                break
        self.assertTrue(all(seen.values()), seen)

    def test_one_way_crush_rolls_direction(self) -> None:
        for seed in range(200):
            stage = field(run_roll(seed, allow_custom=False), "主NPC关系阶段")
            if stage.startswith("单向暗恋"):
                self.assertIn(stage, {"单向暗恋（玩家方）", "单向暗恋（NPC方）"})
                return
        self.fail("did not roll 单向暗恋")

    def test_mains_roll_independently(self) -> None:
        lines = run_roll(11, allow_custom=False, mains=3)
        for label in ("主NPC", "主NPC2", "主NPC3"):
            for suffix in ("身份", "核心价值", "压力策略", "关系姿态",
                           "表层风味", "画像倾向", "外观"):
                self.assertTrue(field(lines, label + suffix), f"{label}{suffix}")

    def test_new_axis_locks_echo(self) -> None:
        lines = run_roll(3, locks={
            "world_rule": "行业规范", "action": "调查查证",
            "core_value": "真相", "pressure_strategy": "收集证据",
            "relationship_stance": "先验后信",
        })
        self.assertTrue(any("核心规则来源: 行业规范（预锁）" in line for line in lines))
        for key, value in (
            ("开场动作", "调查查证"), ("主NPC核心价值", "真相"),
            ("主NPC压力策略", "收集证据"), ("主NPC关系姿态", "先验后信"),
        ):
            self.assertEqual(field(lines, key), value + "（预锁）")

    def test_twists_are_seeded_and_have_two_or_three_directions(self) -> None:
        first = ROLLER.roll_twists(MATERIALS, random.Random(31))
        self.assertEqual(first, ROLLER.roll_twists(MATERIALS, random.Random(31)))
        self.assertIn(len(first), {2, 3})
        self.assertEqual(len({family for family, _item in first}), len(first))

    def test_twist_cli_mode(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(ROLLER.main(["--twist", "--seed", "31"]), 0)
        self.assertIn("中期转折骰结果", output.getvalue())

    def test_invalid_finite_locks_return_parameter_error(self) -> None:
        bad_args = [
            ["--lock", "配角数=abc"],
            ["--lock", "配角数=4"],
            ["--lock", "档位=未知"],
            ["--lock", "Tier=4"],
            ["--lock", "模式=未知"],
            ["--lock", "咬合=未知"],
            ["--lock", "权力结构=未知"],
            ["--mains", "0"],
            ["--mains", "4"],
            ["--all-custom", "--no-custom"],
        ]
        for argv in bad_args:
            with self.subTest(argv=argv):
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(ROLLER.main(argv), 2)
                self.assertEqual("", stdout.getvalue())
                self.assertIn("参数错误", stderr.getvalue())

    def test_real_lock_conflict_returns_parameter_error(self) -> None:
        conflicts = [
            "壳=机甲与舰队",
            "身份=异常与超自然",
            "身份=和风与仪式 → 异能证明神学家",
            "处境=能力失控",
            "处境=捡拾来客",
            "世界规则=魔法法则",
        ]
        for lock in conflicts:
            with self.subTest(lock=lock):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    result = ROLLER.main(["--lock", "档位=现实", "--lock", lock])
                self.assertEqual(result, 2)
                self.assertIn("现实档不能预锁", stderr.getvalue())

    def test_half_and_full_supplements_do_not_mix(self) -> None:
        conflicts = [
            ("半架空", "壳=机甲与舰队"),
            ("半架空", "世界规则=神明契约"),
            ("强架空", "壳=异常管控"),
            ("强架空", "处境=能力失控"),
        ]
        for dang, lock in conflicts:
            with self.subTest(dang=dang, lock=lock):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    result = ROLLER.main([
                        "--lock", f"档位={dang}", "--lock", lock, "--no-history",
                    ])
                self.assertEqual(result, 2)
                self.assertIn(f"{dang}档不能预锁", stderr.getvalue())

    def test_genre_dang_conflict_returns_parameter_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = ROLLER.main([
                "--genre", "原生奇幻", "--lock", "档位=现实", "--no-history",
            ])
        self.assertEqual(result, 2)
        self.assertIn("不支持世界观档", stderr.getvalue())

    def test_all_custom_sets_structural_fields(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(ROLLER.main(["--all-custom", "--no-history", "--seed", "7"]), 0)
        text = output.getvalue()
        for key in (
            "主引擎", "制度与场合壳", "开场动作", "主NPC身份", "主NPC处境",
            "主NPC核心价值", "主NPC压力策略", "主NPC关系姿态",
        ):
            self.assertIn(f"{key}: {ROLLER.CUSTOM}", text)


class HistoryTests(unittest.TestCase):
    def test_history_keeps_last_thirty_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".opening_history"
            for index in range(35):
                ROLLER.append_history(path, (f"engine-{index}", f"shell-{index}", f"identity-{index}"))
            history = ROLLER.load_history(path)
        self.assertEqual(len(history), 30)
        self.assertEqual(ROLLER.history_combo(history[0]),
                         ("engine-5", "shell-5", "identity-5"))
        self.assertEqual(ROLLER.history_combo(history[-1]),
                         ("engine-34", "shell-34", "identity-34"))

    def test_history_reads_legacy_triplets_and_rewrites_dicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".opening_history"
            path.write_text('["old-engine", "old-shell", "old-identity"]\n', encoding="utf-8")
            history = ROLLER.load_history(path)
            self.assertEqual(ROLLER.history_combo(history[0]),
                             ("old-engine", "old-shell", "old-identity"))
            ROLLER.append_history(path, {
                "engine": "new-engine", "shell": "new-shell", "identity": "new-identity",
                "action": "调查查证", "value": "真相",
            })
            first_line = path.read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(first_line.startswith("{"))

    def test_coverage_score_penalizes_repeated_dimensions_and_pairs(self) -> None:
        history = [{
            "dang": "现实", "engine": "信息与误解", "shell": "法律与仲裁",
            "action": "调查查证", "identity": "法律与合规", "value": "真相",
            "strategy": "收集证据",
        }]
        repeated = dict(history[0])
        varied = {
            "dang": "半架空", "engine": "资源与依赖", "shell": "密闭旅宿",
            "action": "共同旅行", "identity": "市井与手艺", "value": "自由",
            "strategy": "谈判交换",
        }
        self.assertGreater(
            ROLLER.coverage_score(repeated, history),
            ROLLER.coverage_score(varied, history),
        )

    def test_coverage_aware_roll_improves_first_candidate(self) -> None:
        _lines, first = run_roll_with_record(19, allow_custom=False)
        history = [first] * 5
        _lines, selected = ROLLER.roll_opening(
            MATERIALS, random.Random(19), {}, None, allow_custom=False,
            recent_history=history,
        )
        self.assertLess(
            ROLLER.coverage_score(selected, history),
            ROLLER.coverage_score(first, history),
        )

    def test_recent_combination_is_rerolled(self) -> None:
        _lines, first_record = run_roll_with_record(19, allow_custom=False)
        _lines, rerolled_record = ROLLER.roll_opening(
            MATERIALS, random.Random(19), {}, None, allow_custom=False,
            recent_combinations={ROLLER.history_combo(first_record)},
        )
        self.assertNotEqual(ROLLER.history_combo(rerolled_record), ROLLER.history_combo(first_record))

    def test_seed_path_can_skip_history_exclusion(self) -> None:
        _lines, expected = run_roll_with_record(23, allow_custom=False)
        _lines, seeded = ROLLER.roll_opening(
            MATERIALS, random.Random(23), {}, None, allow_custom=False,
        )
        self.assertEqual(ROLLER.history_combo(seeded), ROLLER.history_combo(expected))


if __name__ == "__main__":
    unittest.main()
