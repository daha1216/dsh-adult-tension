from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = load("build_opening", "scripts/build_opening.py")
FILL = load("fill_opening", "scripts/fill_opening.py")
COMMIT = load("commit_turn", "scripts/commit_turn.py")
VALIDATOR = load("validate_state", "scripts/validate_state.py")


def iso_plus(moment) -> str:
    return moment.replace(microsecond=0).astimezone().isoformat()


class CommitTurnLifecycleTests(unittest.TestCase):
    """P0/P1 回归：事件生命周期、许可链路、关系增量、深度校准实变判定、新通道。"""

    def setUp(self) -> None:
        # 显式预锁压力与处境：夹具不再依赖固定种子的抽取结果（任何表的词条增删都会
        # 级联改变各轴取值）。锁定非时限组合，保证 near 事件无死线、far 钩子过期测试成立。
        roll = BUILD.build_roll(7, {"压力来源": "舆论发酵", "处境": "资源断供"}, {}, False, False)
        self.state = FILL.fill_opening(BUILD.build_skeleton(roll), roll)
        self.near_id = "evt-002"
        self.far_id = "evt-003"

    # ---- 事件生命周期 ----

    def test_resolving_seed_event_keeps_commit_alive_and_repoints(self) -> None:
        updated = COMMIT.commit(self.state, {
            "delta_minutes": 5,
            "last_committed_result": "near 压力当场兑现。",
            "unresolved_action": "后续未决。",
            "events_resolve": [self.near_id],
            "resolve_outcome": "她当面把条件说完了。",
        })
        statuses = {e["id"]: e["status"] for e in updated["events"]}
        self.assertEqual("resolved", statuses[self.near_id])
        self.assertIn(self.near_id, [item["event_id"] for item in updated["resolved_summary"]])
        seeds = updated["world"]["pressure_seeds"]
        self.assertIsNone(seeds["near_event_id"])
        self.assertEqual(self.far_id, seeds["far_event_id"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))

    def test_far_hook_expiring_repoints_or_clears_without_bricking(self) -> None:
        from datetime import datetime, timedelta, timezone
        clock = datetime.fromisoformat(self.state["world"]["clock"])
        overdue = COMMIT.commit(self.state, {
            "clock": iso_plus(clock + timedelta(days=30)),
            "delta_minutes": 5,
            "last_committed_result": "一个月过去。",
            "unresolved_action": "长线压力落地。",
        })
        statuses = {e["id"]: e["status"] for e in overdue["events"]}
        self.assertEqual({"evt-001": "pending", self.near_id: "pending", self.far_id: "resolved"},
                         statuses)
        self.assertEqual(self.near_id, overdue["world"]["pressure_seeds"]["near_event_id"])
        self.assertIsNone(overdue["world"]["pressure_seeds"]["far_event_id"])
        self.assertEqual([], VALIDATOR.validate_data(overdue, "save"))

    def test_events_resolve_unknown_id_is_an_error(self) -> None:
        with self.assertRaisesRegex(COMMIT.CommitError, "unknown event ids"):
            COMMIT.commit(self.state, {"delta_minutes": 3, "events_resolve": ["evt-999"]})

    def test_semantic_key_dedup_covers_resolved_events(self) -> None:
        key = self.state["events"][0]["semantic_key"]
        with self.assertRaisesRegex(COMMIT.CommitError, "duplicate semantic_key"):
            COMMIT.commit(self.state, {
                "delta_minutes": 4,
                "events_resolve": ["evt-001"],
                "events_add": [{"semantic_key": key}],
            })

    def test_new_event_ids_never_reuse_resolved_numbers(self) -> None:
        updated = COMMIT.commit(self.state, {
            "delta_minutes": 4,
            "events_resolve": ["evt-001", "evt-002"],
            "events_add": [{"kind": "timed", "trigger": "新未决"}],
        })
        new_id = [e["id"] for e in updated["events"] if e["status"] == "pending" and e["id"] not in {"evt-001", "evt-002", "evt-003"}]
        self.assertEqual(["evt-004"], new_id)

    def test_events_cancel_and_update_checked_turns(self) -> None:
        updated = COMMIT.commit(self.state, {
            "delta_minutes": 4,
            "events_cancel": ["evt-001"],
            "events_update": [{"id": "evt-002", "checked_turn_add": True}],
        })
        statuses = {e["id"]: e["status"] for e in updated["events"]}
        self.assertEqual("cancelled", statuses["evt-001"])
        near = next(e for e in updated["events"] if e["id"] == self.near_id)
        self.assertEqual([2], near.get("checked_turns"))
        with self.assertRaisesRegex(COMMIT.CommitError, "immutable"):
            COMMIT.commit(updated, {
                "delta_minutes": 1,
                "events_update": [{"id": "evt-001", "kind": "far"}],
            })

    def test_cancel_and_update_same_event_still_repoints_seeds(self) -> None:
        # 同一 patch 内对同一种子事件既取消又更新：取消语义必须生效，
        # 压力种子要重指或置空，不能被 events_update 吞掉重指处理。
        updated = COMMIT.commit(self.state, {
            "delta_minutes": 4,
            "events_cancel": [self.near_id],
            "events_update": [{"id": self.near_id, "checked_turn_add": True}],
        })
        statuses = {e["id"]: e["status"] for e in updated["events"]}
        self.assertEqual("cancelled", statuses[self.near_id])
        seeds = updated["world"]["pressure_seeds"]
        self.assertNotEqual(self.near_id, seeds["near_event_id"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))

    # ---- 边界撤销 ----

    def test_boundaries_revoke_unknown_topic_is_an_error(self) -> None:
        # 与 grants_withdraw 同一严格度：话题对不上任何边界记录就报错，不静默无操作。
        with self.assertRaisesRegex(COMMIT.CommitError, "unknown boundary topics"):
            COMMIT.commit(self.state, {
                "delta_minutes": 2,
                "boundaries_revoke": ["不存在的话题"],
            })

    def test_boundaries_revoke_known_topic_succeeds_and_revokes(self) -> None:
        added = COMMIT.commit(self.state, {
            "delta_minutes": 2,
            "boundaries_add": ["不碰工作话题"],
        })
        updated = COMMIT.commit(added, {
            "delta_minutes": 2,
            "boundaries_revoke": ["不碰工作话题"],
        })
        statuses = {b["topic"]: b["status"] for b in updated["boundaries"]}
        self.assertEqual("revoked", statuses["不碰工作话题"])

    # ---- 许可归档上限 ----

    def test_grants_archive_keeps_only_recent_entries(self) -> None:
        stuffed = copy.deepcopy(self.state)
        archive = stuffed["consent"].setdefault("grants_archive", [])
        for index in range(25):
            archive.append({"id": f"consent-old-{index:02d}", "status": "withdrawn"})
        granted = COMMIT.commit(stuffed, {
            "delta_minutes": 3,
            "last_committed_result": "她允许你握一下她的手腕。",
            "unresolved_action": "手还没松开。",
            "grants_add": [{"scope": [{"type": "physical", "permission": "握着手腕"}]}],
        })
        origin = granted["current_node"]["location"]
        root = origin.split("·")[0]
        moved = COMMIT.commit(granted, {
            "delta_minutes": 2,
            "location": f"{root}·卧室·夜",
            "last_committed_result": "你们进了里间。",
            "unresolved_action": "门在身后合上。",
        })
        archived = moved["consent"]["grants_archive"]
        self.assertEqual(20, len(archived))
        ids = {g.get("id") for g in archived}
        self.assertNotIn("consent-old-00", ids)
        self.assertIn("consent-old-24", ids)
        self.assertEqual([], VALIDATOR.validate_data(moved, "save"))

    def test_grants_withdraw_then_move_does_not_resurrect_consent(self) -> None:
        granted = COMMIT.commit(self.state, {
            "delta_minutes": 3,
            "last_committed_result": "她允许你握一下她的手腕。",
            "unresolved_action": "手还没松开。",
            "grants_add": [{"scope": [{"type": "physical", "permission": "握着手腕"}]}],
        })
        grant_id = granted["consent"]["grants"][0]["id"]
        origin = granted["current_node"]["location"]
        root = origin.split("·")[0]
        moved = COMMIT.commit(granted, {
            "delta_minutes": 2,
            "location": f"{root}·卧室·夜",
            "grants_withdraw": [grant_id],
            "last_committed_result": "她抽回手，你们进了卧室。",
            "unresolved_action": "门在身后合上。",
        })
        self.assertEqual([], moved["consent"]["grants"])
        archived = moved["consent"].get("grants_archive") or []
        withdrawn = [g for g in archived if g.get("id") == grant_id]
        self.assertEqual(1, len(withdrawn))
        self.assertEqual("withdrawn", withdrawn[0]["status"])
        self.assertIsNotNone(withdrawn[0].get("withdrawn_turn"))
        self.assertEqual([], VALIDATOR.validate_data(moved, "save"))

    def test_leaving_private_space_does_not_inherit_physical_grant(self) -> None:
        # 用无私密词根名的确定性场景验证方向性：客厅（旧）→ 阳台（新）不继承。
        for npc in self.state["npcs"]:
            npc["location"] = "临江公寓·客厅·夜"
        self.state["player"]["location"] = "临江公寓·客厅·夜"
        self.state["current_node"]["location"] = "临江公寓·客厅·夜"
        self.state["consent"]["location"] = "临江公寓·客厅·夜"
        granted = COMMIT.commit(self.state, {
            "delta_minutes": 3,
            "last_committed_result": "她允许你握一下她的手腕。",
            "unresolved_action": "手还没松开。",
            "grants_add": [{"scope": [{"type": "physical", "permission": "握着手腕"}]}],
        })
        moved = COMMIT.commit(granted, {
            "delta_minutes": 2,
            "location": "临江公寓·阳台·夜",
            "last_committed_result": "你们走到阳台上吹风。",
            "unresolved_action": "风把她的发丝吹到唇边。",
        })
        self.assertEqual([], moved["consent"]["grants"])
        archived = moved["consent"].get("grants_archive") or []
        self.assertEqual(1, len(archived))
        self.assertEqual([], VALIDATOR.validate_data(moved, "save"))
        # 方向性纯函数断言：继承只看新地点（旧地点私密不再兜底）。
        self.assertFalse(COMMIT.adjacent_private("临江公寓·卧室·夜", "临江公寓·阳台·夜"))
        self.assertFalse(COMMIT.adjacent_private("临江公寓·套房·夜", "临江公寓·大堂·夜"))
        self.assertTrue(COMMIT.adjacent_private("临江公寓·阳台·夜", "临江公寓·卧室·夜"))
        self.assertTrue(COMMIT.adjacent_private("临江公寓·客厅·夜", "临江公寓·内间·夜"))

    def test_relationship_delta_semantics(self) -> None:
        updated = COMMIT.commit(self.state, {
            "delta_minutes": 3,
            "relationship_delta": {"trust": 7},
        })
        edge = updated["relationships"][0]
        # 绝对值大于 5 视为直接设定并夹到 [-5,5]。
        self.assertEqual(5, edge["trust"])
        self.assertEqual(2, edge["last_updated_turn"])
        clamped = COMMIT.commit(updated, {"delta_minutes": 2, "relationship_delta": {"trust": 50}})
        self.assertEqual(5, clamped["relationships"][0]["trust"])
        multi = COMMIT.commit(clamped, {
            "delta_minutes": 2,
            "relationship_delta": [
                {"source": "player-001", "target": "npc-001", "trust": -2},
                {"source": "npc-001", "target": "player-001", "type": "rivals"},
            ],
        })
        self.assertEqual(3, multi["relationships"][0]["trust"])

    def test_same_value_location_key_does_not_reset_full_calibration(self) -> None:
        location = self.state["current_node"]["location"]
        once = COMMIT.commit(self.state, {
            "delta_minutes": 3,
            "location": location,
            "last_committed_result": "原地没动，话头换了。",
            "unresolved_action": "她还在等下一句。",
        })
        self.assertEqual(1, once["checkpoint"]["last_full_turn"])
        self.assertEqual(6, once["checkpoint"]["next_full_turn"])

    def test_npcs_add_channel_and_guards(self) -> None:
        updated = COMMIT.commit(self.state, {
            "advance_turn": False,
            "npcs_add": [{
                "id": "npc-009", "name": "新进场者", "age": 27, "role_level": "supporting",
                "identity": "传话人", "goal": "把话带到", "boundary": "不掺和",
                "signature": "敲门两下",
            }],
        })
        ids = [n["id"] for n in updated["npcs"]]
        self.assertIn("npc-009", ids)
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))
        with self.assertRaisesRegex(COMMIT.CommitError, "duplicate npc id"):
            COMMIT.commit(updated, {"advance_turn": False, "npcs_add": [{"id": "npc-009", "name": "重名"}]})
        with self.assertRaisesRegex(COMMIT.CommitError, "missing id"):
            COMMIT.commit(updated, {"advance_turn": False, "npcs_add": [{"name": "没编号"}]})

    def test_retcon_add_records_without_rolling_back_turn(self) -> None:
        updated = COMMIT.commit(self.state, {
            "delta_minutes": 2,
            "retcon_add": "其实刚才她递的不是账本，是请柬。",
        })
        self.assertEqual(1, len(updated.get("retcons") or []))
        self.assertEqual(2, updated["meta"]["turn"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))
    def test_ordinary_turn_advances_clock_and_turn(self) -> None:
        updated = COMMIT.commit(self.state, {
            "delta_minutes": 6,
            "last_committed_result": "你把杯子放回原处，没有先谈条件。",
            "unresolved_action": "她的手还停在杯壁上，等你下一句。",
            "npc_updates": {"npc-001": {"emotion": "一紧，随即压回去", "memory": "你没有接那杯酒"}},
        })
        self.assertEqual(2, updated["meta"]["turn"])
        self.assertGreater(updated["world"]["delta_t"], 0)
        self.assertNotEqual(updated["world"]["clock"], self.state["world"]["clock"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))
        self.assertIn("你没有接那杯酒", updated["npcs"][0]["recent_memories"])

    def test_continue_without_patch_still_moves_clock(self) -> None:
        updated = COMMIT.commit(self.state, {})
        self.assertEqual(2, updated["meta"]["turn"])
        self.assertEqual(300, updated["world"]["delta_t"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))

    def test_meta_command_does_not_advance_turn(self) -> None:
        updated = COMMIT.commit(self.state, {
            "advance_turn": False,
            "safety_state": "paused",
            "delta_minutes": 0,
        })
        self.assertEqual(1, updated["meta"]["turn"])
        self.assertEqual("paused", updated["meta"]["safety_state"])
        self.assertEqual(self.state["world"]["clock"], updated["world"]["clock"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))

    def test_scene_change_resets_public_grants(self) -> None:
        granted = COMMIT.commit(self.state, {
            "delta_minutes": 3,
            "last_committed_result": "她允许你握一下她的手腕。",
            "unresolved_action": "手还没松开。",
            "grants_add": [{
                "scope": [{"type": "physical", "permission": "握着手腕"}],
            }],
        })
        self.assertEqual(1, len(granted["consent"]["grants"]))
        moved = COMMIT.commit(granted, {
            "delta_minutes": 2,
            "location": "走廊·电梯前·夜",
            "last_committed_result": "你们走进走廊。",
            "unresolved_action": "电梯门还没开。",
        })
        self.assertNotEqual(granted["consent"]["scene_id"], moved["consent"]["scene_id"])
        self.assertEqual([], moved["consent"]["grants"])
        self.assertEqual([], VALIDATOR.validate_data(moved, "save"))

    def test_adjacent_private_inherits_physical_grant(self) -> None:
        origin = self.state["current_node"]["location"]
        root = origin.split("·")[0]
        granted = COMMIT.commit(self.state, {
            "delta_minutes": 3,
            "last_committed_result": "她允许你握一下她的手腕。",
            "unresolved_action": "手还没松开。",
            "grants_add": [{
                "scope": [{"type": "physical", "permission": "握着手腕"}],
            }],
        })
        moved = COMMIT.commit(granted, {
            "delta_minutes": 2,
            "location": f"{root}·卧室·夜",
            "last_committed_result": "你们走进里间。",
            "unresolved_action": "门在身后合上。",
        })
        self.assertNotEqual(granted["consent"]["scene_id"], moved["consent"]["scene_id"])
        self.assertEqual(1, len(moved["consent"]["grants"]))
        self.assertEqual("握着手腕", moved["consent"]["grants"][0]["scope"][0]["permission"])
        self.assertEqual(granted["consent"]["grants"][0]["id"], moved["consent"]["grants"][0]["inherited_from"])
        self.assertEqual([], VALIDATOR.validate_data(moved, "save"))

    def test_voyeur_pov_and_grant_withdraw_trigger_full(self) -> None:
        paused = COMMIT.commit(self.state, {
            "advance_turn": False,
            "voyeur_pov": "on",
        })
        self.assertEqual("on", paused["meta"]["voyeur_pov"])
        self.assertEqual(1, paused["meta"]["turn"])
        granted = COMMIT.commit(paused, {
            "delta_minutes": 2,
            "grants_add": [{"scope": [{"type": "physical", "permission": "握着手腕"}]}],
            "last_committed_result": "她点了头。",
            "unresolved_action": "手还没松开。",
        })
        withdrawn = COMMIT.commit(granted, {
            "delta_minutes": 1,
            "grants_withdraw": [granted["consent"]["grants"][0]["id"]],
            "last_committed_result": "她抽回手。",
            "unresolved_action": "两个人都没再伸手。",
        })
        self.assertEqual(withdrawn["meta"]["turn"], withdrawn["checkpoint"]["last_full_turn"])
        self.assertEqual(withdrawn["meta"]["turn"] + 5, withdrawn["checkpoint"]["next_full_turn"])
        self.assertEqual([], VALIDATOR.validate_data(withdrawn, "save"))

    def test_cli_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.yaml"
            yaml = BUILD.load_yaml_module()
            path.write_text(yaml.safe_dump(self.state, allow_unicode=True, sort_keys=False), encoding="utf-8")
            patch = Path(tmp) / "patch.json"
            patch.write_text(json.dumps({
                "delta_minutes": 4,
                "last_committed_result": "你叫了她的名字。",
                "unresolved_action": "她转过脸来。",
            }), encoding="utf-8")
            self.assertEqual(0, COMMIT.main(["--state", str(path), "--patch-file", str(patch)]))
            updated = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(2, updated["meta"]["turn"])


if __name__ == "__main__":
    unittest.main()
