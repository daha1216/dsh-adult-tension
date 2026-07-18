#!/usr/bin/env python3
"""Validate a version 3 adult-tension-narrative YAML save file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without the dependency
    yaml = None


SAVE_VERSION = 3
SAFETY_STATES = {"running", "paused"}
MODES = {"reliable", "immersive"}
POWER_STRUCTURES = {"player_high", "npc_high", "equal", "switchable"}
BOUNDARY_STATUSES = {"active", "revoked"}
CONSENT_STATUSES = {"unknown", "granted", "withdrawn", "not_applicable"}
EVENT_STATUSES = {"pending", "resolved", "cancelled"}
EVENT_KINDS = {"immediate", "near", "far", "timed", "probabilistic"}


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


class Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.ids: dict[str, str] = {}
        self.character_ids: set[str] = set()

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def mapping(self, value: Any, path: str) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.error(path, "must be a mapping")
            return None
        return value

    def sequence(self, value: Any, path: str) -> list[Any] | None:
        if not isinstance(value, list):
            self.error(path, "must be a list")
            return None
        return value

    def required(self, data: dict[str, Any], keys: set[str], path: str) -> None:
        for key in sorted(keys - data.keys()):
            self.error(f"{path}.{key}" if path else key, "is required")

    def add_id(self, value: Any, path: str, *, character: bool = False) -> None:
        if not is_nonempty_string(value):
            self.error(path, "must be a non-empty string")
            return
        if value in self.ids:
            self.error(path, f"duplicates {self.ids[value]}")
            return
        self.ids[value] = path
        if character:
            self.character_ids.add(value)

    def validate_age(self, value: Any, path: str) -> None:
        if not is_int(value):
            self.error(path, "must be an explicitly confirmed integer")
        elif value < 18:
            self.error(path, "must be at least 18")

    def validate(self, root: Any) -> list[str]:
        data = self.mapping(root, "root")
        if data is None:
            return self.errors

        top_level = {
            "save_version", "meta", "world", "boundaries", "consent", "player",
            "npcs", "relationships", "events", "checkpoint", "resolved_summary",
            "current_node",
        }
        self.required(data, top_level, "")
        if data.get("save_version") != SAVE_VERSION:
            self.error("save_version", f"must equal {SAVE_VERSION}")

        self.validate_meta(data.get("meta"))
        self.validate_world(data.get("world"))
        self.validate_player(data.get("player"))
        self.validate_npcs(data.get("npcs"))
        self.validate_boundaries(data.get("boundaries"))
        self.validate_consent(data.get("consent"))
        self.validate_relationships(data.get("relationships"))
        self.validate_events(data.get("events"))
        self.validate_checkpoint(data.get("checkpoint"), data.get("meta"))
        if self.sequence(data.get("resolved_summary"), "resolved_summary") is not None:
            pass
        self.validate_current_node(data.get("current_node"))
        return self.errors

    def validate_meta(self, value: Any) -> None:
        data = self.mapping(value, "meta")
        if data is None:
            return
        required = {"turn", "mode", "tier", "simulation", "safety_state", "power_structure"}
        self.required(data, required, "meta")
        turn = data.get("turn")
        if not is_int(turn) or turn < 0:
            self.error("meta.turn", "must be a non-negative integer")
        if data.get("mode") not in MODES:
            self.error("meta.mode", f"must be one of {sorted(MODES)}")
        if not is_int(data.get("tier")) or data.get("tier") not in {1, 2, 3}:
            self.error("meta.tier", "must be 1, 2, or 3")
        if not isinstance(data.get("simulation"), bool):
            self.error("meta.simulation", "must be a boolean")
        if data.get("safety_state") not in SAFETY_STATES:
            self.error("meta.safety_state", f"must be one of {sorted(SAFETY_STATES)}")
        if data.get("power_structure") not in POWER_STRUCTURES:
            self.error("meta.power_structure", f"must be one of {sorted(POWER_STRUCTURES)}")

    def validate_world(self, value: Any) -> None:
        data = self.mapping(value, "world")
        if data is None:
            return
        required = {
            "clock", "previous_clock", "delta_t", "constants", "tension_engines",
            "setting_shell", "pressure_seeds",
        }
        self.required(data, required, "world")
        self.sequence(data.get("constants"), "world.constants")
        self.sequence(data.get("tension_engines"), "world.tension_engines")
        pressure = self.mapping(data.get("pressure_seeds"), "world.pressure_seeds")
        if pressure is not None:
            self.required(pressure, {"immediate", "near_event_id", "far_event_id"}, "world.pressure_seeds")

    def validate_player(self, value: Any) -> None:
        data = self.mapping(value, "player")
        if data is None:
            return
        required = {
            "id", "name", "age", "identity", "location", "baseline", "resources",
            "knowledge", "reputation",
        }
        self.required(data, required, "player")
        self.add_id(data.get("id"), "player.id", character=True)
        self.validate_age(data.get("age"), "player.age")
        self.sequence(data.get("resources"), "player.resources")
        self.sequence(data.get("knowledge"), "player.knowledge")

    def validate_npcs(self, value: Any) -> None:
        items = self.sequence(value, "npcs")
        if items is None:
            return
        if not items:
            self.error("npcs", "must contain at least one NPC")
        required = {
            "id", "name", "age", "identity", "location", "core_personality",
            "pressure_strategy", "voice_filter", "goal", "boundary",
            "withdrawal_signal", "emotion", "relation", "resources", "knowledge",
            "recent_memories", "signature", "autonomy",
        }
        for index, item in enumerate(items):
            path = f"npcs[{index}]"
            npc = self.mapping(item, path)
            if npc is None:
                continue
            self.required(npc, required, path)
            self.add_id(npc.get("id"), f"{path}.id", character=True)
            self.validate_age(npc.get("age"), f"{path}.age")
            for field in ("resources", "knowledge", "recent_memories"):
                self.sequence(npc.get(field), f"{path}.{field}")
            autonomy = self.mapping(npc.get("autonomy"), f"{path}.autonomy")
            if autonomy is not None:
                fields = {"last_turn", "recent_turns", "cooldown_until"}
                self.required(autonomy, fields, f"{path}.autonomy")
                last_turn = autonomy.get("last_turn")
                if last_turn is not None and (not is_int(last_turn) or last_turn < 0):
                    self.error(f"{path}.autonomy.last_turn", "must be null or a non-negative integer")
                recent = self.sequence(autonomy.get("recent_turns"), f"{path}.autonomy.recent_turns")
                if recent is not None and any(not is_int(turn) or turn < 0 for turn in recent):
                    self.error(f"{path}.autonomy.recent_turns", "must contain only non-negative integers")
                cooldown = autonomy.get("cooldown_until")
                if not is_int(cooldown) or cooldown < 0:
                    self.error(f"{path}.autonomy.cooldown_until", "must be a non-negative integer")

    def validate_boundaries(self, value: Any) -> None:
        items = self.sequence(value, "boundaries")
        if items is None:
            return
        for index, item in enumerate(items):
            path = f"boundaries[{index}]"
            boundary = self.mapping(item, path)
            if boundary is None:
                continue
            self.required(boundary, {"id", "topic", "status", "created_turn", "revoked_turn"}, path)
            self.add_id(boundary.get("id"), f"{path}.id")
            status = boundary.get("status")
            if status not in BOUNDARY_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(BOUNDARY_STATUSES)}")
            if status == "active" and not is_nonempty_string(boundary.get("topic")):
                self.error(f"{path}.topic", "must be non-empty for an active boundary")
            if not is_int(boundary.get("created_turn")) or boundary.get("created_turn") < 0:
                self.error(f"{path}.created_turn", "must be a non-negative integer")
            revoked_turn = boundary.get("revoked_turn")
            if revoked_turn is not None and (not is_int(revoked_turn) or revoked_turn < 0):
                self.error(f"{path}.revoked_turn", "must be null or a non-negative integer")

    def validate_consent(self, value: Any) -> None:
        data = self.mapping(value, "consent")
        if data is None:
            return
        self.required(data, {"scene_id", "grants"}, "consent")
        if not is_nonempty_string(data.get("scene_id")):
            self.error("consent.scene_id", "must be a stable non-empty string")
        grants = self.sequence(data.get("grants"), "consent.grants")
        if grants is None:
            return
        for index, item in enumerate(grants):
            path = f"consent.grants[{index}]"
            grant = self.mapping(item, path)
            if grant is None:
                continue
            required = {
                "id", "scene_id", "participants", "scope", "status", "granted_turn",
                "last_checked_turn",
            }
            self.required(grant, required, path)
            self.add_id(grant.get("id"), f"{path}.id")
            if not is_nonempty_string(grant.get("scene_id")):
                self.error(f"{path}.scene_id", "must be a stable non-empty string")
            participants = self.sequence(grant.get("participants"), f"{path}.participants")
            if participants is not None:
                valid_participants = [item for item in participants if is_nonempty_string(item)]
                if len(valid_participants) != len(participants):
                    self.error(f"{path}.participants", "must contain only non-empty character IDs")
                if len(set(valid_participants)) < 2:
                    self.error(f"{path}.participants", "must contain at least two distinct character IDs")
                for participant in valid_participants:
                    if participant not in self.character_ids:
                        self.error(f"{path}.participants", f"references unknown character ID {participant!r}")
            scope = self.sequence(grant.get("scope"), f"{path}.scope")
            if scope is not None and not any(is_nonempty_string(item) for item in scope):
                self.error(f"{path}.scope", "must describe at least one explicit permission")
            if grant.get("status") not in CONSENT_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(CONSENT_STATUSES)}")
            granted_turn = grant.get("granted_turn")
            if granted_turn is not None and (not is_int(granted_turn) or granted_turn < 0):
                self.error(f"{path}.granted_turn", "must be null or a non-negative integer")
            checked_turn = grant.get("last_checked_turn")
            if not is_int(checked_turn) or checked_turn < 0:
                self.error(f"{path}.last_checked_turn", "must be a non-negative integer")

    def validate_relationships(self, value: Any) -> None:
        items = self.sequence(value, "relationships")
        if items is None:
            return
        for index, item in enumerate(items):
            path = f"relationships[{index}]"
            relation = self.mapping(item, path)
            if relation is None:
                continue
            required = {"source", "target", "type", "channel", "trust", "last_updated_turn"}
            self.required(relation, required, path)
            for field in ("source", "target"):
                if relation.get(field) not in self.character_ids:
                    self.error(f"{path}.{field}", "must reference an existing character ID")
            trust = relation.get("trust")
            if not is_int(trust) or not -5 <= trust <= 5:
                self.error(f"{path}.trust", "must be an integer from -5 to 5")
            if not is_int(relation.get("last_updated_turn")) or relation.get("last_updated_turn") < 0:
                self.error(f"{path}.last_updated_turn", "must be a non-negative integer")

    def validate_events(self, value: Any) -> None:
        items = self.sequence(value, "events")
        if items is None:
            return
        required = {"id", "source", "created_turn", "kind", "trigger", "due_at", "status", "consequence", "hook"}
        for index, item in enumerate(items):
            path = f"events[{index}]"
            event = self.mapping(item, path)
            if event is None:
                continue
            self.required(event, required, path)
            self.add_id(event.get("id"), f"{path}.id")
            if event.get("kind") not in EVENT_KINDS:
                self.error(f"{path}.kind", f"must be one of {sorted(EVENT_KINDS)}")
            if event.get("status") not in EVENT_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(EVENT_STATUSES)}")
            if event.get("status") == "pending":
                if not is_nonempty_string(event.get("trigger")) and event.get("due_at") in (None, ""):
                    self.error(path, "pending event needs a non-empty trigger or due_at")
            if not is_int(event.get("created_turn")) or event.get("created_turn") < 0:
                self.error(f"{path}.created_turn", "must be a non-negative integer")
            if not isinstance(event.get("hook"), bool):
                self.error(f"{path}.hook", "must be a boolean")

    def validate_checkpoint(self, value: Any, meta_value: Any) -> None:
        data = self.mapping(value, "checkpoint")
        if data is None:
            return
        required = {"last_full_turn", "changed", "next_full_turn", "force_full", "invariants"}
        self.required(data, required, "checkpoint")
        turn = meta_value.get("turn") if isinstance(meta_value, dict) else None
        last_full = data.get("last_full_turn")
        if not is_int(last_full) or last_full < 0:
            self.error("checkpoint.last_full_turn", "must be a non-negative integer")
        elif is_int(turn) and last_full > turn:
            self.error("checkpoint.last_full_turn", "cannot be greater than meta.turn")
        if self.sequence(data.get("changed"), "checkpoint.changed") is None:
            pass
        if not is_int(data.get("next_full_turn")) or data.get("next_full_turn") < 0:
            self.error("checkpoint.next_full_turn", "must be a non-negative integer")
        elif is_int(last_full) and data.get("next_full_turn") < last_full:
            self.error("checkpoint.next_full_turn", "cannot be earlier than last_full_turn")
        if not isinstance(data.get("force_full"), bool):
            self.error("checkpoint.force_full", "must be a boolean")
        invariants = self.mapping(data.get("invariants"), "checkpoint.invariants")
        if invariants is not None:
            names = {"age_verified", "boundaries_verified", "consent_verified", "player_control_preserved"}
            self.required(invariants, names, "checkpoint.invariants")
            for name in names:
                if name in invariants and not isinstance(invariants[name], bool):
                    self.error(f"checkpoint.invariants.{name}", "must be a boolean")

    def validate_current_node(self, value: Any) -> None:
        data = self.mapping(value, "current_node")
        if data is None:
            return
        required = {"location", "participants", "last_committed_result", "unresolved_action", "natural_next_pressure"}
        self.required(data, required, "current_node")
        participants = self.sequence(data.get("participants"), "current_node.participants")
        if participants is not None:
            if not participants:
                self.error("current_node.participants", "must not be empty")
            for participant in participants:
                if participant not in self.character_ids:
                    self.error("current_node.participants", f"references unknown character ID {participant!r}")
        if not is_nonempty_string(data.get("unresolved_action")):
            self.error("current_node.unresolved_action", "must describe the unresolved handoff point")


def validate_data(data: Any) -> list[str]:
    return Validator().validate(data)


def validate_text(text: str) -> list[str]:
    if yaml is None:
        return ["PyYAML is required; run: python -m pip install PyYAML"]
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"invalid YAML: {exc}"]
    return validate_data(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save_file", type=Path)
    args = parser.parse_args()

    if yaml is None:
        print("ERROR: PyYAML is required; run: python -m pip install PyYAML", file=sys.stderr)
        return 2
    try:
        text = args.save_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_text(text)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("OK: save invariants validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
