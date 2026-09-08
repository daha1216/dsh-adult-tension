from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = load("opening_modes_build", "scripts/build_opening.py")
FILL = load("opening_modes_fill", "scripts/fill_opening.py")
VALIDATOR = load("opening_modes_validator", "scripts/validate_state.py")
ROLL = BUILD.load_roll_opening()
COMMIT = load("opening_modes_commit", "scripts/commit_turn.py")
CONTENT = load("opening_modes_content", "scripts/check_content.py")
LIVE = BUILD.load_live_slice()


class OpeningModeTests(unittest.TestCase):
    @staticmethod
    def daily_state():
        roll = BUILD.build_roll(11, {}, {}, False, False, opening_mode="daily")
        return FILL.fill_opening(BUILD.build_skeleton(roll), roll)

    def test_unselected_complete_only_prints_choice_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(BUILD, "complete_opening") as complete:
            out = Path(tmp) / "opening.yaml"
            request = Path(tmp) / "request.yaml"
            with mock.patch("sys.stdout") as stdout:
                self.assertEqual(0, BUILD.main(["--complete", "--seed", "42", "--out", str(out), "--request", str(request)]))
            complete.assert_not_called()
            self.assertFalse(out.exists())
            self.assertFalse(request.exists())
            self.assertIn("压力开局", stdout.write.call_args_list[0].args[0])

    def test_daily_openings_reuse_curated_materials_and_validate(self) -> None:
        pools = ROLL.load_pools()
        legacy = set(pools["核心规则"]) | set(pools["社会规则"]) | set(pools["张力引擎"])
        legacy |= set(pools["处境侧"])
        legacy |= set(pools["场景动作"])
        for seed in range(20):
            roll = BUILD.build_roll(seed, {}, {}, False, False, opening_mode="daily")
            state = FILL.fill_opening(BUILD.build_skeleton(roll), roll)
            self.assertEqual([], VALIDATOR.validate_data(state, "opening"), seed)
            self.assertEqual([], VALIDATOR.validate_data(state, "save"), seed)
            self.assertIsNone(state["current_node"]["situation"]["deadline"])
            self.assertEqual("daily", state["meta"]["opening_mode"])
            self.assertEqual([], state["events"])
            self.assertEqual({"immediate": "", "near_event_id": None, "far_event_id": None}, state["world"]["pressure_seeds"])
            self.assertEqual("", state["world"]["setting_shell"]["pressure"])
            self.assertEqual("", state["current_node"]["natural_next_pressure"])
            self.assertLessEqual(len([x for x in state["world"]["tension_engines"] if x]), 1)
            selected = {roll[k] for k in ("核心规则", "社会规则", "处境", "场景动作")}
            selected |= set(x for x in roll["张力引擎"].split("、") if x)
            self.assertTrue(selected <= legacy, (seed, selected - legacy))

    def test_daily_roll_is_deterministic_and_pressure_remains_distinct(self) -> None:
        daily_a = BUILD.build_roll(123, {}, {}, False, False, opening_mode="daily")
        daily_b = BUILD.build_roll(123, {}, {}, False, False, opening_mode="daily")
        self.assertEqual(daily_a, daily_b)
        pressure = BUILD.build_roll(123, {}, {}, False, False, opening_mode="pressure")
        self.assertEqual("pressure", pressure["opening_mode"])
        self.assertGreaterEqual(len([x for x in pressure["张力引擎"].split("、") if x]), 2)

    def test_daily_rejects_explicit_pressure_material(self) -> None:
        with self.assertRaisesRegex(ROLL.AnchorError, "日常开局"):
            ROLL.build_roll(ROLL.load_pools(), 1, "table", {"压力来源": "舆论发酵"}, {}, opening_mode="daily")

    def test_roll_file_preserves_mode_and_rejects_conflict(self) -> None:
        roll = BUILD.build_roll(9, {}, {}, False, False, opening_mode="daily")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roll.json"
            path.write_text(__import__("json").dumps(roll, ensure_ascii=False), encoding="utf-8")
            loaded = BUILD.resolve_roll(BUILD.build_parser().parse_args(["--roll-file", str(path)]))
            self.assertEqual("daily", loaded["opening_mode"])
            with self.assertRaises(SystemExit):
                BUILD.resolve_roll(BUILD.build_parser().parse_args(["--roll-file", str(path), "--opening-mode", "pressure"]))


class OpeningModeLifecycleTests(unittest.TestCase):
    def test_ordinary_daily_turn_and_runtime_slice(self):
        state = OpeningModeTests.daily_state()
        updated = COMMIT.commit(state, {"delta_minutes": 5})
        self.assertEqual(state["meta"]["turn"] + 1, updated["meta"]["turn"])
        self.assertEqual([], updated["events"])
        self.assertEqual("daily", LIVE.extract_live_slice(updated)["opening_mode"])
        self.assertEqual("daily", LIVE.opening_brief(updated)["opening_mode"])

    def test_daily_cross_day_does_not_generate_crisis(self):
        state = OpeningModeTests.daily_state()
        updated = COMMIT.commit(state, {"delta_minutes": 1440})
        self.assertEqual([], updated["events"])
        self.assertEqual("", updated["current_node"]["natural_next_pressure"])
        with self.assertRaisesRegex(COMMIT.CommitError, "daily mode"):
            COMMIT.commit(state, {"delta_minutes": 1440,
                                  "twist_generate": {"reason": "first_cross_day"}})

    def test_player_requested_twist_still_supported(self):
        updated = COMMIT.commit(OpeningModeTests.daily_state(), {
            "delta_minutes": 5,
            "twist_generate": {"reason": "player_requested"},
            "events_add": [{"kind": "near", "trigger": "A visitor arrives",
                            "source": "turn:1", "semantic_key": "visit-1"}],
        })
        self.assertEqual(1, updated["world"]["twist_state"]["generated_count"])
        self.assertEqual(1, len(updated["events"]))

    def test_daily_later_events_resolve_cancel_and_keep_ids(self):
        state = COMMIT.commit(OpeningModeTests.daily_state(), {
            "delta_minutes": 5,
            "events_add": [
                {"kind": "near", "trigger": "Tomorrow appointment", "semantic_key": "appointment-1", "source": "turn:1"},
                {"kind": "far", "trigger": "Next month trip", "semantic_key": "trip-1", "source": "turn:1", "hook": True},
            ],
        })
        near, far = [event["id"] for event in state["events"]]
        state["world"]["pressure_seeds"].update(near_event_id=near, far_event_id=far)
        self.assertEqual([], VALIDATOR.validate_data(state, "save"))
        updated = COMMIT.commit(state, {"delta_minutes": 5, "events_resolve": [near],
                                       "events_cancel": [far], "resolve_outcome": "Completed"})
        self.assertEqual([near, far], [event["id"] for event in updated["events"]])
        self.assertEqual(["resolved", "cancelled"], [event["status"] for event in updated["events"]])
        self.assertIsNone(updated["world"]["pressure_seeds"]["near_event_id"])
        self.assertIsNone(updated["world"]["pressure_seeds"]["far_event_id"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))

    def test_daily_can_clear_pressure_but_not_set_invalid_type(self):
        state = OpeningModeTests.daily_state()
        state["current_node"]["natural_next_pressure"] = "An appointment is pending"
        updated = COMMIT.commit(state, {"delta_minutes": 5, "natural_next_pressure": ""})
        self.assertEqual("", updated["current_node"]["natural_next_pressure"])
        with self.assertRaisesRegex(COMMIT.CommitError, "natural_next_pressure"):
            COMMIT.commit(state, {"delta_minutes": 5, "natural_next_pressure": []})
        roll = BUILD.build_roll(1, {}, {}, False, False)
        pressure = FILL.fill_opening(BUILD.build_skeleton(roll), roll)
        with self.assertRaisesRegex(COMMIT.CommitError, "natural_next_pressure"):
            COMMIT.commit(pressure, {"delta_minutes": 5, "natural_next_pressure": ""})

    def test_invalid_modes_and_dangling_references_are_errors(self):
        for mode in ("unknown", [], None):
            state = OpeningModeTests.daily_state()
            state["meta"]["opening_mode"] = mode
            self.assertTrue(any("opening_mode" in error for error in VALIDATOR.validate_data(state, "save")))
        for value in ("evt-missing", [], 12):
            state = OpeningModeTests.daily_state()
            state["world"]["pressure_seeds"]["near_event_id"] = value
            self.assertTrue(any("near_event_id" in error for error in VALIDATOR.validate_data(state, "save")))

    def test_legacy_roll_and_save_keep_pressure_default(self):
        roll = BUILD.build_roll(4, {}, {}, False, False)
        roll.pop("opening_mode")
        state = FILL.fill_opening(BUILD.build_skeleton(roll), roll)
        state["meta"].pop("opening_mode")
        self.assertEqual([], VALIDATOR.validate_data(state, "opening"))
        self.assertEqual("pressure", LIVE.extract_live_slice(state)["opening_mode"])

    def test_single_daily_engine_is_not_supplemented(self):
        for engine in ROLL.load_pools()["meta"]["daily_opening"]["张力引擎"]:
            roll = BUILD.build_roll(4, {"张力引擎": engine}, {}, False, False, opening_mode="daily")
            self.assertEqual(engine, roll["张力引擎"])
            state = FILL.fill_opening(BUILD.build_skeleton(roll), roll)
            self.assertEqual([engine], state["world"]["tension_engines"])
            self.assertEqual([], VALIDATOR.validate_data(state, "opening"))

    def test_daily_locks_reject_crisis_situation_and_two_engines(self):
        pools = ROLL.load_pools()
        for locks in ({"张力引擎": "情感拉扯、旧情重逢"}, {"处境": "资源断供"}):
            with self.assertRaisesRegex(ROLL.AnchorError, "日常开局"):
                ROLL.build_roll(pools, 4, "table", locks, opening_mode="daily")
        roll = ROLL.build_roll(pools, 4, "table", {"处境": "今夜话没说完", "场景动作": "递纸巾"}, opening_mode="daily")
        self.assertEqual("今夜话没说完", roll["处境"])
        self.assertEqual("递纸巾", roll["场景动作"])

    def test_daily_all_custom_does_not_bypass_curated_axes(self):
        base = BUILD.build_roll(6, {}, {}, False, False, opening_mode="daily")
        curated = {"核心规则", "社会规则", "处境", "场景动作", "压力来源", "张力引擎"}
        custom = {key: base[key] for key in ROLL.CUSTOM_KEYS - curated}
        roll = ROLL.build_roll(ROLL.load_pools(), 6, "all_custom", {}, custom, opening_mode="daily")
        state = FILL.fill_opening(BUILD.build_skeleton(roll), roll)
        self.assertEqual([], VALIDATOR.validate_data(state, "opening"))
        self.assertEqual([], state["events"])
        incomplete = ROLL.build_roll(ROLL.load_pools(), 6, "all_custom", {}, {}, opening_mode="daily")
        with self.assertRaises(FILL.FillError):
            FILL.fill_opening(BUILD.build_skeleton(incomplete), incomplete)

    def test_daily_cli_records_mode_and_roll_reuse_skips_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roll = BUILD.build_roll(12, {}, {}, False, False, opening_mode="daily")
            roll_path = root / "roll.json"
            roll_path.write_text(json.dumps(roll, ensure_ascii=False), encoding="utf-8")
            for name, mode_args in (("fresh", ["--opening-mode", "daily", "--seed", "12"]),
                                    ("reuse", ["--roll-file", str(roll_path)])):
                out, request = root / (name + ".yaml"), root / (name + "-request.yaml")
                stdout = io.StringIO()
                with mock.patch.dict("os.environ", {"ADULT_TENSION_HISTORY_PATH": str(root / "history.jsonl")}), mock.patch("sys.stdout", stdout):
                    code = BUILD.main(["--complete", "--no-working", "--out", str(out),
                                       "--request", str(request), *mode_args])
                self.assertEqual(0, code)
                self.assertNotIn("请选择", stdout.getvalue())
                self.assertIn("opening_mode: daily", stdout.getvalue())
                yaml = BUILD.load_yaml_module()
                self.assertEqual("daily", yaml.safe_load(out.read_text(encoding="utf-8"))["meta"]["opening_mode"])
                self.assertEqual("daily", yaml.safe_load(request.read_text(encoding="utf-8"))["opening_mode"])

    def test_content_checker_rejects_missing_daily_material_and_template(self):
        pools = CONTENT._load("pools.yaml")
        mutations = [
            lambda r: r["核心规则"].append("missing-material"),
            lambda r: r["处境"]["今夜话没说完"].pop("trigger"),
            lambda r: r["处境"]["今夜话没说完"].update(trigger="{unknown}"),
        ]
        for mutate in mutations:
            data = copy.deepcopy(pools)
            mutate(data["meta"]["daily_opening"])
            report = CONTENT.Report()
            CONTENT.check_daily_opening(data, report)
            self.assertTrue(report.errors)
        report = CONTENT.Report()
        CONTENT.check_daily_opening(pools, report)
        self.assertEqual([], report.errors)

    def test_suggested_actions_still_work_without_mode_context(self):
        actions = FILL.suggested_actions("递纸巾", "NPC", "Player")
        self.assertEqual(3, len(actions))
        self.assertTrue(all(isinstance(action, str) and action for action in actions))

    def test_frozen_skill_section_is_unchanged(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        start = text.index("### 性行为场景写法（硬约束）")
        end = text.index("\n## ", start)
        section = text[start:end + 1]
        self.assertEqual("9f2c07591f74801308427924426316be7e0a3616e5b25c7f45ebf3b70a627576",
                         hashlib.sha256(section.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    unittest.main()
