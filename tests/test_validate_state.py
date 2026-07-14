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
            "clock": "2026-07-14 20:00",
            "previous_clock": "2026-07-14 19:55",
            "delta_t": "5 minutes",
            "constants": [],
            "tension_engines": ["resource lock"],
            "setting_shell": "office",
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
                "identity": "consultant",
                "location": "office",
                "core_personality": "careful",
                "pressure_strategy": "negotiate",
                "voice_filter": "brief",
                "goal": "resolve the case",
                "boundary": "no coercion",
                "withdrawal_signal": "stop",
                "emotion": "alert",
                "relation": 1,
                "resources": [],
                "knowledge": [],
                "recent_memories": [],
                "signature": "checks the clock",
                "autonomy": {"last_turn": 3, "recent_turns": [3], "cooldown_until": 6},
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
                "trigger": "the meeting ends",
                "due_at": None,
                "status": "pending",
                "consequence": "a reply becomes due",
                "hook": False,
            }
        ],
        "checkpoint": {
            "last_full_turn": 5,
            "changed": [],
            "next_full_turn": 10,
            "force_full": False,
            "invariants": {
                "age_verified": True,
                "boundaries_verified": True,
                "consent_verified": True,
                "player_control_preserved": True,
            },
        },
        "resolved_summary": [],
        "current_node": {
            "location": "office",
            "participants": ["player-001", "npc-001"],
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

    def test_event_cannot_use_boundary_status(self) -> None:
        self.assert_invalid(lambda data: data["events"][0].update(status="active"), "events[0].status")

    def test_checkpoint_cannot_be_ahead(self) -> None:
        self.assert_invalid(lambda data: data["checkpoint"].update(last_full_turn=99), "cannot be greater")

    def test_consent_participant_must_exist(self) -> None:
        def mutate(data):
            data["consent"]["grants"][0]["participants"][1] = "npc-missing"

        self.assert_invalid(mutate, "unknown character ID")

    def test_duplicate_ids_fail(self) -> None:
        self.assert_invalid(lambda data: data["events"][0].update(id="npc-001"), "duplicates")


if __name__ == "__main__":
    unittest.main()
