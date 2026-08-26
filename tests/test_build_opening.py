from __future__ import annotations

import datetime as dt
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_opening.py"
SPEC = importlib.util.spec_from_file_location("build_opening", SCRIPT)
assert SPEC and SPEC.loader
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)

VALIDATE_SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_state.py"
VSPEC = importlib.util.spec_from_file_location("validate_state", VALIDATE_SCRIPT)
assert VSPEC and VSPEC.loader
VALIDATOR = importlib.util.module_from_spec(VSPEC)
VSPEC.loader.exec_module(VALIDATOR)

SAVE_SCRIPT = Path(__file__).parents[1] / "scripts" / "manage_saves.py"
SSPEC = importlib.util.spec_from_file_location("manage_saves", SAVE_SCRIPT)
assert SSPEC and SSPEC.loader
MANAGE = importlib.util.module_from_spec(SSPEC)
SSPEC.loader.exec_module(MANAGE)


def fill_complete(skeleton: dict, roll: dict) -> dict:
    """把骨架填成可通过 opening profile 校验的完整状态（行为级 fixture）。"""
    import copy

    data = copy.deepcopy(skeleton)
    player_name = "顾北"
    npc_name = "沈若"
    location = "宁江大厦·三十一层会客室·夜"
    data["world"]["constants"] = ["这座城里声誉即资本，白纸条款是给翻检那天准备的。"]
    data["player"].update(
        name=player_name, age=29, identity="独立声誉风险顾问",
        location=location, baseline="话少，习惯先把对方的筹码盘清楚。",
        resources=["两家媒体的延迟发稿权"], knowledge=["对手手里有账目副本"], reputation="不站队但能改舆论走向",
        appellation=roll.get("玩家称谓") or "直呼其名",
    )
    data["player_naming_audit"]["chosen"] = player_name
    npc = data["npcs"][0]
    npc.update(
        name=npc_name, age=31, identity="并购部董事总经理",
        location=location, core_personality="外冷内热，怕欠人情，把请求做成交易",
        voice_filter="表层敬语过剩，里层直白；失控时句子先碎",
        goal="在死线前压住流言且不欠下人情", boundary="不用身体换声誉",
        withdrawal_signal="把口罩戴严、改口此事到此",
        emotion="表面端着，指节发白", resources=["反证U盘"], knowledge=["衡浦在散风"],
        recent_memories=["电梯里她确认过口罩与领口"], signature="几乎不摘口罩",
    )
    npc["identity_profile"]["role"] = "并购部董事总经理"
    npc["situation"]["type"] = roll.get("处境", "审查将至")
    npc["decision_card"]["goal"] = "压住流言"
    npc["sexuality_profile"]["baseline"] = "private"
    npc["naming_audit"]["chosen"] = npc_name
    for event in data["events"]:
        event["semantic_key"] = f"opening-{event['kind']}-{event['id']}"
        event["trigger"] = f"{event['kind']} trigger description"
        event["consequence"] = f"{event['kind']} consequence"
    data["relationships"][0].update(type="profession", channel="direct")
    data["current_node"].update(
        location=location,
        last_committed_result="门已关上",
        unresolved_action="沈若正在斟酌如何开口",
        natural_next_pressure="死线在逼近",
    )
    data["current_node"]["situation"].update(
        trigger="会面开始", pressure=roll.get("压力来源", "时限逼近"),
        immediate_objective="谈成交易", deadline=None, unresolved_choice="是否接下这单",
    )
    data["consent"]["location"] = location
    return data


def advance_one_turn(data: dict, seconds: int = 300) -> dict:
    """模拟推进一回合：时钟前移、回合号 +1，其余结构保持可恢复。"""
    import copy

    data = copy.deepcopy(data)
    previous = data["world"]["clock"]
    new_clock = (dt.datetime.fromisoformat(previous) + dt.timedelta(seconds=seconds)).isoformat()
    data["meta"]["turn"] = 2
    data["world"]["previous_clock"] = previous
    data["world"]["clock"] = new_clock
    data["world"]["delta_t"] = seconds
    data["checkpoint"]["changed"] = [{"turn": 2, "field": "world.clock", "reason": "one turn advance"}]
    return data


class BuildOpeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.roll = BUILD.build_roll(7, {}, {}, False, False)
        self.skeleton = BUILD.build_skeleton(self.roll)

    def test_skeleton_has_opening_structure(self) -> None:
        self.assertEqual(1, self.skeleton["meta"]["turn"])
        self.assertEqual("running", self.skeleton["meta"]["safety_state"])
        engines = [item for item in self.skeleton["world"]["tension_engines"] if item]
        self.assertGreaterEqual(len(engines), 2)
        kinds = {event["kind"] for event in self.skeleton["events"]}
        self.assertEqual({"immediate", "near", "far"}, kinds)
        far = [event for event in self.skeleton["events"] if event["kind"] == "far"]
        self.assertTrue(far and far[0]["hook"] is True)
        self.assertEqual(6, self.skeleton["checkpoint"]["next_full_turn"])
        self.assertEqual(["player-001", "npc-001"], self.skeleton["current_node"]["participants"])

    def test_unfilled_skeleton_reports_pending_fields(self) -> None:
        errors = VALIDATOR.validate_data(self.skeleton, "opening")
        self.assertTrue(errors)
        joined = "\n".join(errors)
        for expected in ("world.constants", "player.name", "current_node.unresolved_action",
                         "events[0].semantic_key"):
            self.assertIn(expected, joined)

    def test_filled_opening_passes_opening_validation(self) -> None:
        filled = fill_complete(self.skeleton, self.roll)
        self.assertEqual([], VALIDATOR.validate_data(filled, "opening"))

    def test_advance_one_turn_passes_save_validation(self) -> None:
        filled = fill_complete(self.skeleton, self.roll)
        self.assertEqual([], VALIDATOR.validate_data(advance_one_turn(filled), "save"))

    def test_cli_generate_then_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "opening.yaml"
            self.assertEqual(0, BUILD.main(["--seed", "7", "--out", str(out)]))
            self.assertTrue(out.exists())
            self.assertEqual(1, BUILD.main(["--check", str(out)]))
            skeleton = BUILD.load_yaml_module().safe_load(out.read_text(encoding="utf-8"))
            filled = fill_complete(skeleton, self.roll)
            out.write_text(BUILD.load_yaml_module().safe_dump(
                filled, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")
            self.assertEqual(0, BUILD.main(["--check", str(out)]))

    def test_roll_file_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roll_path = Path(tmp) / "roll.json"
            roll_path.write_text(
                __import__("json").dumps(self.roll, ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "opening.yaml"
            self.assertEqual(0, BUILD.main(["--roll-file", str(roll_path), "--out", str(out)]))
            data = BUILD.load_yaml_module().safe_load(out.read_text(encoding="utf-8"))
            self.assertEqual(1, data["meta"]["turn"])

    def test_end_to_end_slot_lifecycle(self) -> None:
        filled = fill_complete(self.skeleton, self.roll)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "state.yaml"
            state_path.write_text(BUILD.load_yaml_module().safe_dump(
                filled, allow_unicode=True, sort_keys=False, default_flow_style=False),
                encoding="utf-8")
            store = MANAGE.SaveStore(root)
            manifest = store.init_slot("main", state_path)
            loaded, loaded_manifest = store.load_slot("main")
            self.assertEqual(loaded_manifest["updated_at"], manifest["updated_at"])

            candidate = advance_one_turn(filled)
            candidate_path = root / "candidate.yaml"
            candidate_path.write_text(BUILD.load_yaml_module().safe_dump(
                candidate, allow_unicode=True, sort_keys=False, default_flow_style=False),
                encoding="utf-8")
            updated = store.save_slot("main", candidate_path,
                                      expected_updated_at=manifest["updated_at"])
            self.assertNotEqual(manifest["updated_at"], updated["updated_at"])
            with self.assertRaises(MANAGE.SaveError):
                store.save_slot("main", candidate_path,
                                expected_updated_at=manifest["updated_at"])

    def test_repo_opening_fixtures_pass(self) -> None:
        root = Path(__file__).parents[1]
        fixtures = sorted((root / "tests" / "fixtures").glob("_opening_*.yaml"))
        self.assertTrue(fixtures, "no _opening_* fixtures found under tests/fixtures/")
        for path in fixtures:
            errors = VALIDATOR.validate_text(path.read_text(encoding="utf-8"), "opening")
            self.assertEqual([], errors, str(path))

    def test_complete_fill_passes_opening_validation(self) -> None:
        fill = _load("fill_opening", Path(__file__).parents[1] / "scripts" / "fill_opening.py")
        filled = fill.fill_opening(self.skeleton, self.roll)
        self.assertEqual([], VALIDATOR.validate_data(filled, "opening"))
        self.assertEqual(self.roll["玩家称谓"], filled["player"]["appellation"])
        self.assertEqual(1, filled["meta"]["turn"])
        self.assertFalse(filled["checkpoint"]["force_full"])
        self.assertEqual(1, len(filled["npcs"]))
        self.assertIsNone(filled.get("directives"))

    def test_complete_fill_is_deterministic(self) -> None:
        fill = _load("fill_opening", Path(__file__).parents[1] / "scripts" / "fill_opening.py")
        a = fill.fill_opening(self.skeleton, self.roll)
        b = fill.fill_opening(BUILD.build_skeleton(self.roll), self.roll)
        self.assertEqual(a["player"]["name"], b["player"]["name"])
        self.assertEqual(a["npcs"][0]["name"], b["npcs"][0]["name"])
        self.assertEqual(a["current_node"]["location"], b["current_node"]["location"])

    def test_complete_cli_writes_valid_state_and_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "opening.yaml"
            working = Path(tmp) / "current.yaml"
            code = BUILD.main([
                "--complete", "--seed", "7", "--out", str(out),
                "--working", str(working),
            ])
            self.assertEqual(0, code)
            self.assertTrue(out.exists())
            self.assertTrue(working.exists())
            self.assertEqual([], VALIDATOR.validate_text(out.read_text(encoding="utf-8"), "opening"))

    def test_ten_seeds_keep_triple_diversity(self) -> None:
        fill = _load("fill_opening", Path(__file__).parents[1] / "scripts" / "fill_opening.py")
        triples = []
        for seed in range(1, 11):
            roll = BUILD.build_roll(seed, {}, {}, False, False)
            filled = fill.fill_opening(BUILD.build_skeleton(roll), roll)
            self.assertEqual([], VALIDATOR.validate_data(filled, "opening"), seed)
            shell = filled["world"]["setting_shell"]
            engines = tuple(filled["world"]["tension_engines"])
            triples.append((shell["type"], shell["place"], engines))
            self.assertEqual(roll["玩家称谓"], filled["player"]["appellation"])
        self.assertGreaterEqual(len(set(triples)), 8)

    def test_era_lock_uses_dedicated_name_pool(self) -> None:
        names_table = BUILD.load_yaml_module().safe_load(
            (Path(__file__).parents[1] / "scripts" / "data" / "names.yaml").read_text(encoding="utf-8"))
        meiji = names_table["eras"]["明治东京"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "opening.yaml"
            working = Path(tmp) / "current.yaml"
            code = BUILD.main([
                "--complete", "--seed", "5", "--lock", "时代=明治东京",
                "--out", str(out), "--working", str(working),
            ])
            self.assertEqual(0, code)
            data = BUILD.load_yaml_module().safe_load(out.read_text(encoding="utf-8"))
        for role_obj in (data["player"], data["npcs"][0]):
            name = role_obj["name"]
            hit = [s for s in meiji["surnames"]
                   if name.startswith(s) and name[len(s):] in meiji["given"]]
            self.assertTrue(hit, f"{name} 不在明治池内")
        self.assertEqual(
            "pass", data["npcs"][0]["naming_audit"]["checks"]["culture_match"])

    def test_default_pool_kept_for_era_without_dedicated_pool(self) -> None:
        # 现在全部时代都有专属名池；回退路径改为注入「无专属池」的 names 表来端到端验证。
        names_table = BUILD.load_yaml_module().safe_load(
            (Path(__file__).parents[1] / "scripts" / "data" / "names.yaml").read_text(encoding="utf-8"))
        default_names = {key: value for key, value in names_table.items() if key != "eras"}
        original_loader = BUILD.load_fill_opening

        def loader_without_era_pools():
            fill_mod = original_loader()
            original_tables = fill_mod.load_tables

            def tables_without_era_pools():
                tables = original_tables()
                tables["names"] = dict(default_names)
                return tables

            fill_mod.load_tables = tables_without_era_pools
            return fill_mod

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "opening.yaml"
            working = Path(tmp) / "current.yaml"
            with mock.patch.object(BUILD, "load_fill_opening", loader_without_era_pools):
                code = BUILD.main([
                    "--complete", "--seed", "5", "--lock", "时代=当代都市",
                    "--out", str(out), "--working", str(working),
                ])
            self.assertEqual(0, code)
            data = BUILD.load_yaml_module().safe_load(out.read_text(encoding="utf-8"))
        for role_obj in (data["player"], data["npcs"][0]):
            name = role_obj["name"]
            hit = [s for s in default_names["surnames"]
                   if name.startswith(s) and name[len(s):] in default_names["given"]]
            self.assertTrue(hit, f"{name} 不在默认池内")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
