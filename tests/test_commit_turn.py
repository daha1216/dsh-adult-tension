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

    def test_relationship_delta_semantics(self) -> None:
        updated = COMMIT.commit(self.state, {
            "delta_minutes": 3,
            "relationship_delta": {"trust": 7},
        })
        edge = updated["relationships"][0]
        # trust 始终是增量，并夹到 [-5,5]。
        self.assertEqual(5, edge["trust"])
        self.assertEqual(2, edge["last_updated_turn"])
        clamped = COMMIT.commit(updated, {"delta_minutes": 2, "relationship_delta": {"trust": 50}})
        self.assertEqual(5, clamped["relationships"][0]["trust"])
        set_value = COMMIT.commit(clamped, {"delta_minutes": 2, "relationship_delta": {"trust_set": -4}})
        self.assertEqual(-4, set_value["relationships"][0]["trust"])
        multi = COMMIT.commit(clamped, {
            "delta_minutes": 2,
            "relationship_delta": [
                {"source": "player-001", "target": "npc-001", "trust": -2},
                {"source": "npc-001", "target": "player-001", "type": "rivals"},
            ],
        })
        self.assertEqual(3, multi["relationships"][0]["trust"])

    def test_probabilistic_roll_is_deterministic_and_audited(self) -> None:
        state = copy.deepcopy(self.state)
        state["events"].append({
            "id": "evt-prob-hit",
            "semantic_key": "probability hit",
            "source": "turn:1",
            "created_turn": 1,
            "kind": "probabilistic",
            "trigger": "本回合检查",
            "due_at": None,
            "status": "pending",
            "consequence": "概率事件命中",
            "hook": False,
            "probability": 1.0,
        })
        updated = COMMIT.commit(state, {
            "delta_minutes": 2,
            "events_update": [{"id": "evt-prob-hit", "roll": True, "roll_outcome": "命中已落地"}],
        })
        event = next(item for item in updated["events"] if item["id"] == "evt-prob-hit")
        self.assertEqual("resolved", event["status"])
        self.assertEqual("hit", event["last_roll"]["outcome"])
        self.assertEqual(2, event["last_roll"]["turn"])
        self.assertEqual("命中已落地", next(item for item in updated["resolved_summary"] if item["event_id"] == "evt-prob-hit")["outcome"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))

    def test_probabilistic_miss_records_checked_turn(self) -> None:
        state = copy.deepcopy(self.state)
        event_id = "evt-prob-miss"
        roll_value = COMMIT.deterministic_event_roll(event_id, 2)
        probability = roll_value / 2 if roll_value else 0.5
        state["events"].append({
            "id": event_id,
            "semantic_key": "probability miss",
            "source": "turn:1",
            "created_turn": 1,
            "kind": "probabilistic",
            "trigger": "本回合检查",
            "due_at": None,
            "status": "pending",
            "consequence": "概率事件未命中",
            "hook": False,
            "probability": probability,
        })
        updated = COMMIT.commit(state, {
            "delta_minutes": 2,
            "events_update": [{"id": event_id, "roll": True}],
        })
        event = next(item for item in updated["events"] if item["id"] == event_id)
        self.assertEqual("pending", event["status"])
        self.assertEqual("miss", event["last_roll"]["outcome"])
        self.assertEqual([2], event["checked_turns"])
        self.assertEqual([], VALIDATOR.validate_data(updated, "save"))

    def test_simulation_gate_blocks_offline_effects(self) -> None:
        state = copy.deepcopy(self.state)
        state["meta"]["simulation"] = False
        with self.assertRaisesRegex(COMMIT.CommitError, "simulation=false"):
            COMMIT.commit(state, {
                "delta_minutes": 2,
                "npc_updates": {"npc-001": {"autonomy_now": True}},
            })

    def test_twist_generation_is_recorded_and_first_cross_day_is_one_time(self) -> None:
        from datetime import timedelta

        state = copy.deepcopy(self.state)
        clock = COMMIT.parse_clock(state["world"]["clock"]) + timedelta(days=1)
        first = COMMIT.commit(state, {
            "clock": COMMIT.iso(clock),
            "twist_generate": {"reason": "first_cross_day"},
        })
        self.assertEqual(1, first["world"]["twist_state"]["generated_count"])
        with self.assertRaisesRegex(COMMIT.CommitError, "already been generated"):
            COMMIT.commit(first, {
                "delta_minutes": 2,
                "twist_generate": {"reason": "first_cross_day"},
            })
        reroll = COMMIT.commit(first, {
            "delta_minutes": 2,
            "twist_generate": {"reason": "player_requested"},
        })
        self.assertEqual(2, reroll["world"]["twist_state"]["generated_count"])

    def test_time_span_escalates_and_large_jump_refreshes_checkpoint(self) -> None:
        mode, reasons = COMMIT.classify_turn(self.state, {"delta_minutes": 20})
        self.assertEqual("deep", mode)
        self.assertIn("short fast-forward", reasons)
        mode, reasons = COMMIT.classify_turn(self.state, {"delta_minutes": 60})
        self.assertEqual("deep", mode)
        self.assertIn("large time jump", reasons)
        updated = COMMIT.commit(self.state, {"delta_minutes": 60})
        self.assertEqual(2, updated["checkpoint"]["last_full_turn"])

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

    def test_turn_classifier_marks_ordinary_patch_fast(self) -> None:
        mode, reasons = COMMIT.classify_turn(self.state, {
            "delta_minutes": 4,
            "last_committed_result": "她抬眼看你。",
            "unresolved_action": "她在等你的下一句。",
        })
        self.assertEqual("fast", mode)
        self.assertIn("ordinary local turn", reasons)

    def test_turn_classifier_escalates_scene_and_event_changes(self) -> None:
        mode, reasons = COMMIT.classify_turn(self.state, {
            "delta_minutes": 5,
            "location": "走廊·电梯前·夜",
            "events_add": [{"id": "event-009"}],
        })
        self.assertEqual("deep", mode)
        self.assertIn("scene location changed", reasons)
        self.assertIn("structural state changed", reasons)

    def test_turn_classifier_marks_meta_without_narrative(self) -> None:
        mode, reasons = COMMIT.classify_turn(self.state, {"advance_turn": False, "safety_state": "paused"})
        self.assertEqual("meta", mode)
        self.assertIn("advance_turn=false", reasons)

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
