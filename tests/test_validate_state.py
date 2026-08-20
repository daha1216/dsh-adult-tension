from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_state.py"
SPEC = importlib.util.spec_from_file_location("validate_state", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def valid_save() -> dict:
    return {
        "save_version": 3,
        "meta": {"turn": 5, "mode": "reliable", "tier": 2, "simulation": True, "safety_state": "running", "power_structure": "equal"},
        "world": {
            "clock": "2026-07-14T20:00:00+08:00", "previous_clock": "2026-07-14T19:55:00+08:00", "delta_t": 300,
            "constants": ["board approval is required"], "tension_engines": ["resource lock", "deadline pressure"],
            "setting_shell": {"type": "institutional drama", "place": "office", "rule": "approval required", "pressure": "deadline"},
            "pressure_seeds": {"immediate": "deadline", "near_event_id": "evt-near", "far_event_id": "evt-far"},
        },
        "boundaries": [{"id": "boundary-001", "topic": "no coercion", "status": "active", "created_turn": 0, "revoked_turn": None}],
        "consent": {
            "scene_id": "scene-001", "location": "office", "participants": ["player-001", "npc-001"],
            "grants": [{"id": "consent-001", "scene_id": "scene-001", "participants": ["player-001", "npc-001"], "scope": [{"type": "scene", "permission": "remain together"}], "status": "granted", "granted_turn": 4, "withdrawn_turn": None, "last_checked_turn": 5}],
        },
        "player": {"id": "player-001", "name": "Player", "age": 30, "identity": "investigator", "location": "office", "baseline": "healthy", "resources": [], "knowledge": [], "reputation": "unknown"},
        "player_naming_audit": {"chosen": "Player", "source": "player provided", "approved_turn": 0},
        "npcs": [{
            "id": "npc-001", "name": "NPC", "age": 32, "role_level": "main", "identity": "consultant", "location": "office", "goal": "resolve the case", "boundary": "no coercion", "resources": [], "knowledge": [], "recent_memories": [], "signature": "checks the clock",
            "core_personality": "careful", "pressure_strategy": "negotiate", "voice_filter": "brief", "withdrawal_signal": "stop", "emotion": "alert",
            "autonomy": {"last_turn": 3, "recent_turns": [3], "cooldown_until": 6},
            "identity_profile": {"role": "consultant"}, "situation": {"type": "deadline"}, "decision_card": {"goal": "resolve"}, "sexuality_profile": {"baseline": "private"}, "sexuality_development": {"trend": "stable"},
            "naming_audit": {"chosen": "NPC", "source": "generator", "approved_turn": 0},
        }],
        "relationships": [{"source": "player-001", "target": "npc-001", "type": "allies", "channel": "direct", "trust": 1, "last_updated_turn": 5, "opening": {"status": True, "covered_turn": 0}}],
        "events": [
            {"id": "evt-near", "source": "turn:3", "created_turn": 3, "kind": "near", "semantic_key": "meeting reply", "trigger": "meeting ends", "due_at": None, "status": "pending", "consequence": "reply due", "hook": False, "probability": None},
            {"id": "evt-far", "source": "world:initial", "created_turn": 0, "kind": "far", "semantic_key": "board review", "trigger": "board convenes", "due_at": "2026-07-15T20:00:00+08:00", "status": "pending", "consequence": "review", "hook": True, "probability": None},
        ],
        "checkpoint": {"last_full_turn": 5, "changed": [], "next_full_turn": 10, "force_full": False, "force_reason": None, "invariants": {"age_verified": True, "player_control_preserved": True}},
        "resolved_summary": [],
        "current_node": {
            "scene_id": "scene-001", "location": "office", "participants": ["player-001", "npc-001"],
            "situation": {"trigger": "meeting started", "pressure": "deadline", "immediate_objective": "decide", "deadline": "2026-07-14T21:00:00+08:00", "unresolved_choice": "approve", "knowledge_gap": {"player_knows": [], "npc_knows": [], "both_mistake": []}, "exits": {"available": True, "cost": None, "blocked_by": None}, "consequence": {"immediate": "meeting ends", "near_term": "approval delayed"}},
            "last_committed_result": "door closed", "unresolved_action": "NPC awaits answer", "natural_next_pressure": "deadline approaches",
        },
    }


class ValidateStateTests(unittest.TestCase):
    def assert_invalid(self, mutate, expected: str, profile: str = "save") -> None:
        data = copy.deepcopy(valid_save())
        mutate(data)
        errors = VALIDATOR.validate_data(data, profile)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_complete_save_passes(self) -> None:
        self.assertEqual([], VALIDATOR.validate_data(valid_save()))

    def test_time_rejects_fractional_seconds_and_reversal(self) -> None:
        self.assert_invalid(lambda data: data["world"].update(clock="2026-07-14T20:00:00.500000+08:00", delta_t=300), "whole seconds")
        self.assert_invalid(lambda data: data["world"].update(clock="2026-07-14T19:00:00+08:00"), "cannot be earlier")

    def test_pressure_seeds_require_near_and_far_references(self) -> None:
        self.assert_invalid(lambda data: data["world"]["pressure_seeds"].update(near_event_id=""), "near_event_id")
        self.assert_invalid(lambda data: data["world"]["pressure_seeds"].update(far_event_id="evt-near"), "must reference a far event")

    def test_scene_consent_binding_is_strict(self) -> None:
        self.assert_invalid(lambda data: data["consent"].update(location="lobby"), "consent.location")
        self.assert_invalid(lambda data: data["consent"].update(participants=["player-001"]), "consent.participants")
        self.assert_invalid(lambda data: data["consent"]["grants"][0].update(withdrawn_turn=5), "withdrawn_turn")

    def test_consent_scope_and_withdrawal_rules(self) -> None:
        self.assert_invalid(lambda data: data["consent"]["grants"][0]["scope"][0].update(type="freeform"), "scope[0].type")
        data = valid_save()
        data["consent"]["grants"][0].update(status="withdrawn", withdrawn_turn=5)
        self.assertEqual([], VALIDATOR.validate_data(data))

    def test_relationship_edges_are_unique_and_opening_is_structured(self) -> None:
        def duplicate(data):
            data["relationships"].append(copy.deepcopy(data["relationships"][0]))
        self.assert_invalid(duplicate, "duplicates an existing relationship edge")
        self.assert_invalid(lambda data: data["relationships"][0]["opening"].update(status="yes"), "opening.status")

    def test_main_npc_and_naming_audits_are_strict(self) -> None:
        self.assert_invalid(lambda data: data["npcs"][0].pop("decision_card"), "npcs[0].decision_card")
        self.assert_invalid(lambda data: data["npcs"][0]["decision_card"].pop("goal"), "decision_card.goal")
        self.assert_invalid(lambda data: data["npcs"][0]["naming_audit"].update(chosen="Other"), "must match NPC name")
        self.assert_invalid(lambda data: data["player_naming_audit"].update(chosen="Other"), "player_naming_audit.chosen")

    def test_opening_requires_player_and_main_relationship_coverage(self) -> None:
        data = copy.deepcopy(valid_save())
        data["meta"]["turn"] = 1
        for event in data["events"]:
            event["created_turn"] = 1
        data["relationships"][0]["last_updated_turn"] = 1
        data["checkpoint"].update(last_full_turn=1, next_full_turn=6)
        data["npcs"][0]["autonomy"] = {"last_turn": None, "recent_turns": [], "cooldown_until": 0}
        data["consent"]["grants"][0].update(granted_turn=1, last_checked_turn=1)
        data["events"].append({"id": "evt-immediate", "source": "system:opening", "created_turn": 1, "kind": "immediate", "semantic_key": "opening beat", "trigger": "scene begins", "due_at": None, "status": "pending", "consequence": "pressure starts", "hook": False, "probability": None})
        second = copy.deepcopy(data["npcs"][0])
        second.update(id="npc-002", name="NPC2")
        data["npcs"].append(second)
        data["current_node"]["participants"].append("npc-002")
        data["consent"]["participants"].append("npc-002")
        data["consent"]["grants"][0]["participants"].append("npc-002")
        self.assertTrue(any("player relationship coverage" in error for error in VALIDATOR.validate_data(data, "opening")))

    def test_opening_requires_structural_top_level_fields(self) -> None:
        data = valid_save()
        data.pop("player_naming_audit")
        self.assertTrue(any("C1-C14 structural field" in error for error in VALIDATOR.validate_data(data, "opening")))

    def test_intimate_supporting_participant_must_be_upgraded(self) -> None:
        def add_supporting(data):
            npc = copy.deepcopy(data["npcs"][0])
            npc.update(id="npc-002", name="Witness", role_level="supporting", intimacy={"eligible": True, "scope": "intimate"})
            for key in ("identity_profile", "situation", "decision_card", "sexuality_profile", "sexuality_development", "naming_audit"):
                npc.pop(key, None)
            data["npcs"].append(npc)
            data["current_node"]["participants"].append("npc-002")
            data["consent"]["participants"].append("npc-002")
            data["consent"]["grants"][0]["participants"].append("npc-002")
            data["consent"]["grants"][0]["scope"].append({"type": "physical", "permission": "intimate participation"})
        self.assert_invalid(add_supporting, "intimate participation")

    def test_autonomy_consistency(self) -> None:
        self.assert_invalid(lambda data: data["npcs"][0]["autonomy"].update(recent_turns=[3, 2]), "unique and chronological")
        self.assert_invalid(lambda data: data["npcs"][0]["autonomy"].update(cooldown_until=2), "cannot precede last_turn")

    def test_checkpoint_invariants_and_force_reason(self) -> None:
        self.assert_invalid(lambda data: data["checkpoint"]["invariants"].update(age_verified=False), "must be true")
        self.assert_invalid(lambda data: data["checkpoint"].update(force_full=True), "force_reason")
        data = valid_save()
        data["checkpoint"].update(force_full=True, force_reason="schema migration")
        self.assertEqual([], VALIDATOR.validate_data(data))

    def _opening_ready(self, data: dict) -> dict:
        data["meta"]["turn"] = 1
        data.pop("directives", None)
        for event in data["events"]:
            event["created_turn"] = 1
        data["relationships"][0]["last_updated_turn"] = 1
        data["checkpoint"].update(last_full_turn=1, next_full_turn=6)
        data["npcs"][0]["autonomy"] = {"last_turn": None, "recent_turns": [], "cooldown_until": 0}
        data["consent"]["grants"][0].update(granted_turn=1, last_checked_turn=1)
        data["events"].append({"id": "evt-immediate", "source": "system:opening", "created_turn": 1, "kind": "immediate", "semantic_key": "opening beat", "trigger": "scene begins", "due_at": None, "status": "pending", "consequence": "pressure starts", "hook": False, "probability": None})
        return data

    def test_legacy_directive_fields_are_ignored(self) -> None:
        # 指令契约已从状态模型移除；历史存档中残留的 directives 字段与
        # directive_priority_preserved 不参与校验，旧档仍可通过。
        data = valid_save()
        data["directives"] = [{
            "id": "directive-001", "raw": "do this", "kind": "action",
            "required_outcome": "done", "protected_details": [], "adaptation_scope": ["scene"],
            "deadline": "current_turn", "status": "fulfilled", "created_turn": 5,
            "event_id": None, "resolution": "done", "block_code": None, "block_context": None,
        }]
        data["checkpoint"]["invariants"]["directive_priority_preserved"] = True
        self.assertEqual([], VALIDATOR.validate_data(data))

    def test_opening_rejects_new_directives(self) -> None:
        data = self._opening_ready(valid_save())
        data["directives"] = [{
            "id": "directive-001", "raw": "do this", "kind": "action",
            "required_outcome": "done", "protected_details": [], "adaptation_scope": ["scene"],
            "deadline": "current_turn", "status": "fulfilled", "created_turn": 1,
            "event_id": None, "resolution": "done", "block_code": None,
        }]
        self.assertTrue(any("must not write directives" in error for error in VALIDATOR.validate_data(data, "opening")))

    def test_event_sources_pending_due_and_probability(self) -> None:
        self.assert_invalid(lambda data: data["events"][0].update(source="turn-3"), "legal 'type:id'")
        self.assert_invalid(lambda data: data["events"][0].update(due_at="2026-07-14T19:00:00+08:00"), "must be later")
        self.assert_invalid(lambda data: data["events"][0].update(kind="probabilistic", probability=None), "probabilistic events")
        data = valid_save()
        data["events"].append({"id": "evt-prob", "source": "system:probability", "created_turn": 5, "kind": "probabilistic", "semantic_key": "chance outcome", "trigger": "roll", "due_at": None, "status": "pending", "consequence": "outcome varies", "hook": False, "probability": 0.25})
        self.assertEqual([], VALIDATOR.validate_data(data))

    def test_resolved_summary_has_required_structure(self) -> None:
        self.assert_invalid(lambda data: data.update(resolved_summary=[{"event_id": "evt-near"}]), "resolved_summary[0].outcome")

    def test_opening_profile_requires_initial_events(self) -> None:
        data = valid_save()
        data["meta"]["turn"] = 1
        data.pop("directives", None)
        for event in data["events"]:
            event["created_turn"] = 1
        data["relationships"][0]["last_updated_turn"] = 1
        data["checkpoint"].update(last_full_turn=1, next_full_turn=6)
        data["npcs"][0]["autonomy"] = {"last_turn": None, "recent_turns": [], "cooldown_until": 0}
        data["consent"]["grants"][0].update(granted_turn=1, last_checked_turn=1)
        data["events"].append({"id": "evt-immediate", "source": "system:opening", "created_turn": 1, "kind": "immediate", "semantic_key": "opening beat", "trigger": "scene begins", "due_at": None, "status": "pending", "consequence": "pressure starts", "hook": False, "probability": None})
        self.assertEqual([], VALIDATOR.validate_data(data, "opening"))
        data["world"]["tension_engines"] = ["only one"]
        self.assertTrue(any("two distinct engines" in error for error in VALIDATOR.validate_data(data, "opening")))

    def test_cli_profile_argument_exists(self) -> None:
        self.assertEqual([], VALIDATOR.validate_data(valid_save(), "save"))
        self.assertTrue(VALIDATOR.validate_data(valid_save(), "invalid"))


if __name__ == "__main__":
    unittest.main()
