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
        "meta": {
            "turn": 5,
            "mode": "reliable",
            "tier": 2,
            "simulation": True,
            "safety_state": "running",
            "power_structure": "equal",
        },
        "world": {
            "clock": "2026-07-14T20:00:00+08:00",
            "previous_clock": "2026-07-14T19:55:00+08:00",
            "delta_t": 300,
            "delta_human": "5 minutes",
            "constants": ["access to the original records requires board authorization"],
            "tension_engines": ["resource lock"],
            "setting_shell": {
                "type": "institutional drama",
                "place": "office",
                "rule": "access to records requires authorization",
                "pressure": "the meeting deadline is close",
            },
            "pressure_seeds": {
                "immediate": "meeting deadline",
                "near_event_id": "evt-001",
                "far_event_id": "",
            },
        },
        "boundaries": [
            {
                "id": "boundary-001",
                "topic": "example boundary",
                "status": "active",
                "created_turn": 0,
                "revoked_turn": None,
            }
        ],
        "consent": {
            "scene_id": "scene-001",
            "grants": [
                {
                    "id": "consent-001",
                    "scene_id": "scene-001",
                    "participants": ["player-001", "npc-001"],
                    "scope": ["example explicit scope"],
                    "status": "granted",
                    "granted_turn": 4,
                    "last_checked_turn": 5,
                }
            ],
        },
        "player": {
            "id": "player-001",
            "name": "Player",
            "age": 30,
            "identity": "investigator",
            "location": "office",
            "baseline": "healthy",
            "resources": [],
            "knowledge": [],
            "reputation": "unknown",
        },
        "npcs": [
            {
                "id": "npc-001",
                "name": "NPC",
                "age": 32,
                "role_level": "main",
                "identity": "consultant",
                "location": "office",
                "core_personality": "careful",
                "pressure_strategy": "negotiate",
                "voice_filter": "brief",
                "goal": "resolve the case",
                "boundary": "no coercion",
                "withdrawal_signal": "stop",
                "emotion": "alert",
                "resources": [],
                "knowledge": [],
                "recent_memories": [],
                "signature": "checks the clock",
                "autonomy": {"last_turn": 3, "recent_turns": [3], "cooldown_until": 6},
                "identity_profile": {"role": "consultant"},
                "situation": {"type": "deadline"},
                "decision_card": {"goal": "resolve"},
                "sexuality_profile": {"baseline": "private"},
                "sexuality_development": {"trend": "stable"},
                "naming_audit": {"chosen": "NPC"},
            }
        ],
        "relationships": [
            {
                "source": "player-001",
                "target": "npc-001",
                "type": "allies",
                "channel": "direct",
                "trust": 1,
                "last_updated_turn": 5,
            }
        ],
        "events": [
            {
                "id": "evt-001",
                "source": "turn-3",
                "created_turn": 3,
                "kind": "near",
                "semantic_key": "meeting reply due",
                "trigger": "the meeting ends",
                "due_at": None,
                "status": "pending",
                "consequence": "a reply becomes due",
                "hook": False,
            }
        ],
        "directives": [],
        "checkpoint": {
            "last_full_turn": 5,
            "changed": [],
            "next_full_turn": 10,
            "force_full": False,
            "invariants": {
                "age_verified": True,
                "player_control_preserved": True,
                "directive_priority_preserved": True,
            },
        },
        "resolved_summary": [],
        "current_node": {
            "location": "office",
            "participants": ["player-001", "npc-001"],
            "situation": {
                "trigger": "the meeting started",
                "pressure": "the deadline is close",
                "immediate_objective": "reach a decision",
                "deadline": "2026-07-14T21:00:00+08:00",
                "unresolved_choice": "whether to approve the proposal",
                "knowledge_gap": {"player_knows": [], "npc_knows": [], "both_mistake": []},
                "exits": {"available": True, "cost": None, "blocked_by": None},
                "consequence": {"immediate": "the meeting ends", "near_term": "approval is delayed"},
            },
            "last_committed_result": "the door closed",
            "unresolved_action": "the NPC is waiting for the player's answer",
            "natural_next_pressure": "the meeting deadline approaches",
        },
    }


class ValidateStateTests(unittest.TestCase):
    def assert_invalid(self, mutate, expected: str) -> None:
        data = copy.deepcopy(valid_save())
        mutate(data)
        errors = VALIDATOR.validate_data(data)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_valid_save_passes(self) -> None:
        self.assertEqual([], VALIDATOR.validate_data(valid_save()))

    def test_malformed_yaml_fails(self) -> None:
        errors = VALIDATOR.validate_text("save_version: 3\nbroken: [")
        self.assertTrue(any("invalid YAML" in error for error in errors), errors)

    def test_missing_npc_age_fails(self) -> None:
        self.assert_invalid(lambda data: data["npcs"][0].pop("age"), "npcs[0].age")

    def test_boolean_age_fails(self) -> None:
        self.assert_invalid(lambda data: data["player"].update(age=True), "player.age")

    def test_pending_event_needs_trigger(self) -> None:
        def mutate(data):
            data["events"][0]["trigger"] = ""
            data["events"][0]["due_at"] = None

        self.assert_invalid(mutate, "pending event")

    def test_pending_event_needs_semantic_key(self) -> None:
        self.assert_invalid(
            lambda data: data["events"][0].pop("semantic_key"),
            "pending events require a non-empty semantic_key",
        )

    def test_resolved_event_may_omit_semantic_key(self) -> None:
        data = copy.deepcopy(valid_save())
        data["events"][0].update(status="resolved")
        data["events"][0].pop("semantic_key")
        self.assertEqual([], VALIDATOR.validate_data(data))

    @staticmethod
    def add_directive(data: dict, **updates) -> None:
        directive = {
            "id": "directive-001",
            "raw": "Make the impossible result happen",
            "kind": "outcome",
            "required_outcome": "the requested result becomes true",
            "protected_details": ["the result itself cannot be replaced"],
            "adaptation_scope": ["world", "scene"],
            "deadline": "current_turn",
            "status": "fulfilled",
            "created_turn": 5,
            "event_id": None,
            "resolution": "the world supplied a causal bridge and the result occurred",
            "block_code": None,
        }
        directive.update(updates)
        data["directives"] = [directive]

    def test_fulfilled_directive_passes(self) -> None:
        data = copy.deepcopy(valid_save())
        self.add_directive(data)
        self.assertEqual([], VALIDATOR.validate_data(data))

    def test_pending_directive_requires_linked_pending_event(self) -> None:
        data = copy.deepcopy(valid_save())
        data["events"][0]["source"] = "directive-001"
        self.add_directive(
            data, status="pending", deadline="earliest_possible",
            event_id="evt-001", resolution="",
        )
        self.assertEqual([], VALIDATOR.validate_data(data))

    def test_current_turn_directive_cannot_remain_pending(self) -> None:
        def mutate(data):
            data["events"][0]["source"] = "directive-001"
            self.add_directive(data, status="pending", event_id="evt-001", resolution="")

        self.assert_invalid(mutate, "pending directives must use earliest_possible")

    def test_pending_directive_event_source_must_match(self) -> None:
        def mutate(data):
            self.add_directive(
                data, status="pending", deadline="earliest_possible",
                event_id="evt-001", resolution="",
            )

        self.assert_invalid(mutate, "event source must equal directive ID")

    def test_blocked_directive_only_accepts_hard_invariant_code(self) -> None:
        def mutate(data):
            self.add_directive(
                data, status="blocked", resolution="the setting disallowed it",
                block_code="world_rule_conflict",
            )

        self.assert_invalid(mutate, "directives[0].block_code")

    def test_directive_priority_checkpoint_must_be_true(self) -> None:
        def mutate(data):
            self.add_directive(data)
            data["checkpoint"]["invariants"]["directive_priority_preserved"] = False

        self.assert_invalid(mutate, "directive_priority_preserved")

    def test_optional_directive_priority_checkpoint_must_be_boolean(self) -> None:
        self.assert_invalid(
            lambda data: data["checkpoint"]["invariants"].update(
                directive_priority_preserved="yes"
            ),
            "must be a boolean when present",
        )

    def test_event_cannot_use_boundary_status(self) -> None:
        self.assert_invalid(lambda data: data["events"][0].update(status="active"), "events[0].status")

    def test_checkpoint_cannot_be_ahead(self) -> None:
        self.assert_invalid(lambda data: data["checkpoint"].update(last_full_turn=99), "cannot be greater")

    def test_consent_participant_must_exist(self) -> None:
        def mutate(data):
            data["consent"]["grants"][0]["participants"][1] = "npc-missing"

        self.assert_invalid(mutate, "unknown character ID")

    def test_consent_participants_must_be_in_current_scene(self) -> None:
        def mutate(data):
            second = copy.deepcopy(data["npcs"][0])
            second.update(id="npc-002", name="NPC2")
            data["npcs"].append(second)
            data["consent"]["grants"][0]["participants"][1] = "npc-002"

        self.assert_invalid(mutate, "outside scene")

    def test_world_constants_must_not_be_empty(self) -> None:
        self.assert_invalid(
            lambda data: data["world"].update(constants=[]),
            "world.constants",
        )

    def test_duplicate_ids_fail(self) -> None:
        self.assert_invalid(lambda data: data["events"][0].update(id="npc-001"), "duplicates")

    def test_consent_must_match_current_scene(self) -> None:
        self.assert_invalid(lambda data: data["consent"]["grants"][0].update(scene_id="scene-old"), "must match consent.scene_id")

    def test_granted_consent_needs_turn(self) -> None:
        self.assert_invalid(lambda data: data["consent"]["grants"][0].update(granted_turn=None), "required for granted consent")

    def test_consent_participants_cannot_repeat(self) -> None:
        self.assert_invalid(lambda data: data["consent"]["grants"][0].update(participants=["player-001", "player-001"]), "duplicate character IDs")

    def test_relationship_cannot_self_reference(self) -> None:
        self.assert_invalid(lambda data: data["relationships"][0].update(target="player-001"), "different characters")

    def test_event_created_turn_cannot_be_future(self) -> None:
        self.assert_invalid(lambda data: data["events"][0].update(created_turn=6), "cannot be greater than meta.turn")

    def test_pressure_seed_event_must_exist(self) -> None:
        self.assert_invalid(lambda data: data["world"]["pressure_seeds"].update(near_event_id="evt-missing"), "existing event ID")

    def test_hook_must_be_far_event(self) -> None:
        def mutate(data):
            data["events"][0]["hook"] = True

        self.assert_invalid(mutate, "hook events must have kind far")

    def test_main_npc_needs_extended_state(self) -> None:
        self.assert_invalid(lambda data: data["npcs"][0].pop("decision_card"), "npcs[0].decision_card")

    def test_npc_relation_must_not_duplicate_graph(self) -> None:
        self.assert_invalid(lambda data: data["npcs"][0].update(relation=1), "must not duplicate")

    def test_at_least_one_main_npc_is_required(self) -> None:
        self.assert_invalid(lambda data: data["npcs"][0].update(role_level="supporting"), "at least one main NPC")

    def test_multiple_main_npcs_allowed(self) -> None:
        data = copy.deepcopy(valid_save())
        second = copy.deepcopy(data["npcs"][0])
        second.update(id="npc-002", name="NPC2")
        data["npcs"].append(second)
        self.assertEqual([], VALIDATOR.validate_data(data))

    def test_minimal_supporting_npc_passes(self) -> None:
        data = copy.deepcopy(valid_save())
        data["npcs"].append({
            "id": "npc-002",
            "name": "Witness",
            "age": 41,
            "role_level": "supporting",
            "identity": "witness",
            "location": "office",
            "goal": "leave safely",
            "boundary": "no violence",
            "resources": [],
            "knowledge": [],
            "recent_memories": [],
            "signature": "keeps the receipts",
            "autonomy": {"last_turn": None, "recent_turns": [], "cooldown_until": 0},
        })
        data["current_node"]["participants"].append("npc-002")
        self.assertEqual([], VALIDATOR.validate_data(data))

    def test_important_supporting_needs_expressive_fields(self) -> None:
        data = copy.deepcopy(valid_save())
        supporting = {
            "id": "npc-002",
            "name": "Witness",
            "age": 41,
            "role_level": "important_supporting",
            "identity": "witness",
            "location": "office",
            "goal": "leave safely",
            "boundary": "no violence",
            "resources": [],
            "knowledge": [],
            "recent_memories": [],
            "signature": "keeps the receipts",
            "autonomy": {"last_turn": None, "recent_turns": [], "cooldown_until": 0},
        }
        data["npcs"].append(supporting)
        data["current_node"]["participants"].append("npc-002")
        errors = VALIDATOR.validate_data(data)
        self.assertTrue(any("npcs[1].voice_filter" in error for error in errors), errors)

    def test_supporting_expressive_field_must_be_string_when_present(self) -> None:
        data = copy.deepcopy(valid_save())
        supporting = {
            "id": "npc-002",
            "name": "Witness",
            "age": 41,
            "role_level": "supporting",
            "identity": "witness",
            "location": "office",
            "goal": "leave safely",
            "boundary": "no violence",
            "emotion": ["nervous"],
            "resources": [],
            "knowledge": [],
            "recent_memories": [],
            "signature": "keeps the receipts",
            "autonomy": {"last_turn": None, "recent_turns": [], "cooldown_until": 0},
        }
        data["npcs"].append(supporting)
        data["current_node"]["participants"].append("npc-002")
        errors = VALIDATOR.validate_data(data)
        self.assertTrue(any("must be a string when present" in error for error in errors), errors)

    def test_supporting_still_needs_autonomy(self) -> None:
        data = copy.deepcopy(valid_save())
        supporting = {
            "id": "npc-002",
            "name": "Witness",
            "age": 41,
            "role_level": "supporting",
            "identity": "witness",
            "location": "office",
            "goal": "leave safely",
            "boundary": "no violence",
            "resources": [],
            "knowledge": [],
            "recent_memories": [],
            "signature": "keeps the receipts",
        }
        data["npcs"].append(supporting)
        data["current_node"]["participants"].append("npc-002")
        errors = VALIDATOR.validate_data(data)
        self.assertTrue(any("npcs[1].autonomy" in error for error in errors), errors)

    def test_current_node_needs_situation(self) -> None:
        self.assert_invalid(lambda data: data["current_node"].pop("situation"), "current_node.situation")

    def test_current_situation_needs_unresolved_choice(self) -> None:
        self.assert_invalid(lambda data: data["current_node"]["situation"].update(unresolved_choice=""), "unresolved_choice")

    def test_checkpoint_changed_entry_has_shape(self) -> None:
        def mutate(data):
            data["checkpoint"]["changed"] = [{"turn": 5, "field": "meta.turn"}]

        self.assert_invalid(mutate, "checkpoint.changed[0].reason")

    def test_recovery_invariants_reject_inconsistent_state(self) -> None:
        cases = {
            "world.clock": lambda data: data["world"].update(
                clock="2026-07-14T19:50:00+08:00", previous_clock="2026-07-14T20:00:00+08:00"
            ),
            "world.delta_t": lambda data: data["world"].update(delta_t=0),
            "world.setting_shell": lambda data: data["world"].update(setting_shell=None),
            "world.tension_engines": lambda data: data["world"].update(tension_engines=[]),
            "world.pressure_seeds.immediate": lambda data: data["world"]["pressure_seeds"].update(immediate=""),
            "world.pressure_seeds.far_event_id": lambda data: data["world"]["pressure_seeds"].update(far_event_id="evt-001"),
            "npcs[0].naming_audit": lambda data: data["npcs"][0].update(naming_audit={}),
            "boundaries[0].created_turn": lambda data: data["boundaries"][0].update(created_turn=6),
            "relationships[0].last_updated_turn": lambda data: data["relationships"][0].update(last_updated_turn=6),
            "checkpoint.next_full_turn": lambda data: data["checkpoint"].update(next_full_turn=5),
            "current_node.location": lambda data: data["current_node"].update(location=""),
        }
        for expected, mutate in cases.items():
            with self.subTest(expected=expected):
                self.assert_invalid(mutate, expected)

    def test_setting_shell_string_is_rejected(self) -> None:
        self.assert_invalid(
            lambda data: data["world"].update(setting_shell="office"),
            "world.setting_shell",
        )


if __name__ == "__main__":
    unittest.main()
