#!/usr/bin/env python3
"""Validate a version 3 adult-tension-narrative YAML save file."""

from __future__ import annotations

import argparse
import datetime as dt
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
ROLE_LEVELS = {"main", "important_supporting", "supporting"}
DIRECTIVE_KINDS = {"action", "outcome", "canon", "retcon", "style"}
DIRECTIVE_STATUSES = {"pending", "fulfilled", "blocked"}
DIRECTIVE_DEADLINES = {"current_turn", "earliest_possible"}
DIRECTIVE_SCOPES = {"world", "player", "npc", "relationship", "event", "scene"}
DIRECTIVE_BLOCK_CODES = {
    "adult_requirement", "safety_paused",
}


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_iso_datetime(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.ids: dict[str, str] = {}
        self.character_ids: set[str] = set()
        self._current_turn: int | None = None
        self._scene_participants: set[str] = set()

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

    def required_text(self, data: dict[str, Any], keys: tuple[str, ...], path: str) -> None:
        for key in keys:
            if not is_nonempty_string(data.get(key)):
                self.error(f"{path}.{key}", "must be a non-empty string")

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
        meta_data = data.get("meta")
        if isinstance(meta_data, dict) and is_int(meta_data.get("turn")) and meta_data.get("turn") >= 0:
            self._current_turn = meta_data["turn"]
        node_data = data.get("current_node")
        if isinstance(node_data, dict) and isinstance(node_data.get("participants"), list):
            self._scene_participants = {
                item for item in node_data["participants"] if is_nonempty_string(item)
            }

        self.validate_meta(data.get("meta"))
        self.validate_world(data.get("world"), data.get("events"))
        self.validate_player(data.get("player"))
        self.validate_npcs(data.get("npcs"))
        self.validate_boundaries(data.get("boundaries"))
        self.validate_consent(data.get("consent"))
        self.validate_relationships(data.get("relationships"))
        self.validate_events(data.get("events"), data.get("meta"))
        if "directives" in data:
            self.validate_directives(data.get("directives"), data.get("events"))
        self.validate_checkpoint(data.get("checkpoint"), data.get("meta"), data.get("directives"))
        self.sequence(data.get("resolved_summary"), "resolved_summary")
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

    def validate_world(self, value: Any, events_value: Any) -> None:
        data = self.mapping(value, "world")
        if data is None:
            return
        required = {
            "clock", "previous_clock", "delta_t", "constants", "tension_engines",
            "setting_shell", "pressure_seeds",
        }
        self.required(data, required, "world")
        constants = self.sequence(data.get("constants"), "world.constants")
        if constants is not None and not constants:
            self.error("world.constants", "must contain at least one world constant")
        engines = self.sequence(data.get("tension_engines"), "world.tension_engines")
        if engines is not None and not engines:
            self.error("world.tension_engines", "must contain at least one engine")
        shell_data = self.mapping(data.get("setting_shell"), "world.setting_shell")
        if shell_data is not None:
            self.required_text(shell_data, ("type", "place", "rule", "pressure"), "world.setting_shell")
        clock = data.get("clock")
        previous_clock = data.get("previous_clock")
        if not isinstance(clock, str) or not clock.strip():
            self.error("world.clock", "must be a non-empty ISO 8601 string")
        elif parse_iso_datetime(clock) is None:
            self.error("world.clock", "must include a timezone offset")
        if not isinstance(previous_clock, str) or not previous_clock.strip():
            self.error("world.previous_clock", "must be a non-empty ISO 8601 string")
        elif parse_iso_datetime(previous_clock) is None:
            self.error("world.previous_clock", "must include a timezone offset")
        delta_t = data.get("delta_t")
        if not is_int(delta_t) or delta_t < 0:
            self.error("world.delta_t", "must be a non-negative integer number of seconds")
        parsed_clock = parse_iso_datetime(clock)
        parsed_previous = parse_iso_datetime(previous_clock)
        if parsed_clock is not None and parsed_previous is not None:
            elapsed = int((parsed_clock - parsed_previous).total_seconds())
            if elapsed < 0:
                self.error("world.clock", "cannot be earlier than previous_clock")
            elif is_int(delta_t) and delta_t != elapsed:
                self.error("world.delta_t", "must equal clock minus previous_clock in seconds")
        if "delta_human" in data and data.get("delta_human") not in (None, "") and not isinstance(data.get("delta_human"), str):
            self.error("world.delta_human", "must be a string when present")
        pressure = self.mapping(data.get("pressure_seeds"), "world.pressure_seeds")
        if pressure is not None:
            self.required(pressure, {"immediate", "near_event_id", "far_event_id"}, "world.pressure_seeds")
            if not is_nonempty_string(pressure.get("immediate")):
                self.error("world.pressure_seeds.immediate", "must be a non-empty string")
            events: dict[str, dict[str, Any]] = {}
            if isinstance(events_value, list):
                events = {item.get("id"): item for item in events_value
                          if isinstance(item, dict) and is_nonempty_string(item.get("id"))}
            for field, kind in (("near_event_id", "near"), ("far_event_id", "far")):
                event_id = pressure.get(field)
                if event_id not in (None, ""):
                    event = events.get(event_id)
                    if event is None:
                        self.error(f"world.pressure_seeds.{field}", "must reference an existing event ID")
                    elif event.get("kind") != kind:
                        self.error(f"world.pressure_seeds.{field}", f"must reference a {kind} event")
                    elif kind == "far" and event.get("hook") is not True:
                        self.error(f"world.pressure_seeds.{field}", "must reference a hook event")

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
        self.required_text(data, ("name", "identity", "location", "baseline", "reputation"), "player")
        self.sequence(data.get("resources"), "player.resources")
        self.sequence(data.get("knowledge"), "player.knowledge")

    def validate_npcs(self, value: Any) -> None:
        items = self.sequence(value, "npcs")
        if items is None:
            return
        if not items:
            self.error("npcs", "must contain at least one NPC")
        base_required = {
            "id", "name", "age", "role_level", "identity", "location", "goal", "boundary",
            "resources", "knowledge", "recent_memories", "signature", "autonomy",
        }
        expressive_fields = {
            "core_personality", "pressure_strategy", "voice_filter", "withdrawal_signal", "emotion",
        }
        main_required = {
            "identity_profile", "situation", "decision_card", "sexuality_profile",
            "sexuality_development", "naming_audit",
        }
        main_count = 0
        for index, item in enumerate(items):
            path = f"npcs[{index}]"
            npc = self.mapping(item, path)
            if npc is None:
                continue
            role_level = npc.get("role_level")
            required = base_required | expressive_fields if role_level in {"main", "important_supporting"} else base_required
            self.required(npc, required, path)
            self.required_text(
                npc,
                ("name", "identity", "location", "goal", "boundary", "signature"),
                path,
            )
            if role_level in {"main", "important_supporting"}:
                self.required_text(npc, tuple(expressive_fields), path)
            else:
                for field in expressive_fields:
                    if field in npc and not isinstance(npc[field], str):
                        self.error(f"{path}.{field}", "must be a string when present for a supporting NPC")
            if role_level not in ROLE_LEVELS:
                self.error(f"{path}.role_level", f"must be one of {sorted(ROLE_LEVELS)}")
            if role_level == "main":
                main_count += 1
                self.required(npc, main_required, path)
                for field in main_required:
                    if field in npc:
                        detail = self.mapping(npc.get(field), f"{path}.{field}")
                        if detail is not None and not detail:
                            self.error(f"{path}.{field}", "must not be empty for a main NPC")
            if "relation" in npc:
                self.error(f"{path}.relation", "must not duplicate the top-level relationships graph")
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
                turn = self._current_turn
                if is_int(turn):
                    if last_turn is not None and last_turn > turn:
                        self.error(f"{path}.autonomy.last_turn", "cannot be greater than meta.turn")
                    if recent is not None and any(item > turn for item in recent if is_int(item)):
                        self.error(f"{path}.autonomy.recent_turns", "cannot contain turns greater than meta.turn")
        if main_count < 1:
            self.error("npcs", "must contain at least one main NPC")

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
            created_turn = boundary.get("created_turn")
            if not is_int(created_turn) or created_turn < 0:
                self.error(f"{path}.created_turn", "must be a non-negative integer")
            elif self._current_turn is not None and created_turn > self._current_turn:
                self.error(f"{path}.created_turn", "cannot be greater than meta.turn")
            revoked_turn = boundary.get("revoked_turn")
            if revoked_turn is not None and (not is_int(revoked_turn) or revoked_turn < 0):
                self.error(f"{path}.revoked_turn", "must be null or a non-negative integer")
            elif is_int(revoked_turn):
                if self._current_turn is not None and revoked_turn > self._current_turn:
                    self.error(f"{path}.revoked_turn", "cannot be greater than meta.turn")
                if is_int(created_turn) and revoked_turn < created_turn:
                    self.error(f"{path}.revoked_turn", "cannot be earlier than created_turn")
            if status == "active" and revoked_turn is not None:
                self.error(f"{path}.revoked_turn", "must be null for an active boundary")
            if status == "revoked" and revoked_turn is None:
                self.error(f"{path}.revoked_turn", "is required for a revoked boundary")

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
            elif grant.get("scene_id") != data.get("scene_id"):
                self.error(f"{path}.scene_id", "must match consent.scene_id")
            participants = self.sequence(grant.get("participants"), f"{path}.participants")
            if participants is not None:
                valid_participants = [item for item in participants if is_nonempty_string(item)]
                if len(valid_participants) != len(participants):
                    self.error(f"{path}.participants", "must contain only non-empty character IDs")
                if len(valid_participants) != len(set(valid_participants)):
                    self.error(f"{path}.participants", "must not contain duplicate character IDs")
                if len(set(valid_participants)) < 2:
                    self.error(f"{path}.participants", "must contain at least two distinct character IDs")
                for participant in valid_participants:
                    if participant not in self.character_ids:
                        self.error(f"{path}.participants", f"references unknown character ID {participant!r}")
                if self._scene_participants:
                    outside = [participant for participant in valid_participants
                               if participant not in self._scene_participants]
                    if outside:
                        self.error(
                            f"{path}.participants",
                            f"must all appear in current_node.participants; outside scene: {outside!r}",
                        )
            scope = self.sequence(grant.get("scope"), f"{path}.scope")
            if scope is not None and not any(is_nonempty_string(item) for item in scope):
                self.error(f"{path}.scope", "must describe at least one explicit permission")
            if grant.get("status") not in CONSENT_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(CONSENT_STATUSES)}")
            granted_turn = grant.get("granted_turn")
            if grant.get("status") == "granted" and not is_int(granted_turn):
                self.error(f"{path}.granted_turn", "is required for granted consent")
            elif granted_turn is not None and (not is_int(granted_turn) or granted_turn < 0):
                self.error(f"{path}.granted_turn", "must be null or a non-negative integer")
            if is_int(granted_turn) and self._current_turn is not None and granted_turn > self._current_turn:
                self.error(f"{path}.granted_turn", "cannot be greater than meta.turn")
            checked_turn = grant.get("last_checked_turn")
            if not is_int(checked_turn) or checked_turn < 0:
                self.error(f"{path}.last_checked_turn", "must be a non-negative integer")
            elif self._current_turn is not None and checked_turn > self._current_turn:
                self.error(f"{path}.last_checked_turn", "cannot be greater than meta.turn")

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
            if relation.get("source") == relation.get("target") and relation.get("source") in self.character_ids:
                self.error(path, "source and target must be different characters")
            self.required_text(relation, ("type", "channel"), path)
            trust = relation.get("trust")
            if not is_int(trust) or not -5 <= trust <= 5:
                self.error(f"{path}.trust", "must be an integer from -5 to 5")
            if not is_int(relation.get("last_updated_turn")) or relation.get("last_updated_turn") < 0:
                self.error(f"{path}.last_updated_turn", "must be a non-negative integer")
            elif self._current_turn is not None and relation.get("last_updated_turn") > self._current_turn:
                self.error(f"{path}.last_updated_turn", "cannot be greater than meta.turn")

    def validate_events(self, value: Any, meta_value: Any) -> None:
        items = self.sequence(value, "events")
        if items is None:
            return
        current_turn = self._current_turn
        semantic_keys: dict[str, str] = {}
        required = {"id", "source", "created_turn", "kind", "trigger", "due_at", "status", "consequence", "hook"}
        for index, item in enumerate(items):
            path = f"events[{index}]"
            event = self.mapping(item, path)
            if event is None:
                continue
            self.required(event, required, path)
            self.add_id(event.get("id"), f"{path}.id")
            semantic_key = event.get("semantic_key")
            if semantic_key not in (None, ""):
                if not is_nonempty_string(semantic_key):
                    self.error(f"{path}.semantic_key", "must be a non-empty string when present")
                elif semantic_key in semantic_keys:
                    self.error(f"{path}.semantic_key", f"duplicates {semantic_keys[semantic_key]}")
                else:
                    semantic_keys[semantic_key] = path
            if event.get("kind") not in EVENT_KINDS:
                self.error(f"{path}.kind", f"must be one of {sorted(EVENT_KINDS)}")
            if event.get("status") not in EVENT_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(EVENT_STATUSES)}")
            if event.get("status") == "pending" and not is_nonempty_string(semantic_key):
                self.error(f"{path}.semantic_key", "pending events require a non-empty semantic_key")
            if event.get("status") == "pending":
                if not is_nonempty_string(event.get("trigger")) and event.get("due_at") in (None, ""):
                    self.error(path, "pending event needs a non-empty trigger or due_at")
            created_turn = event.get("created_turn")
            if not is_int(created_turn) or created_turn < 0:
                self.error(f"{path}.created_turn", "must be a non-negative integer")
            elif is_int(current_turn) and created_turn > current_turn:
                self.error(f"{path}.created_turn", "cannot be greater than meta.turn")
            due_at = event.get("due_at")
            if due_at not in (None, "") and parse_iso_datetime(due_at) is None:
                self.error(f"{path}.due_at", "must be an ISO 8601 string with timezone when present")
            if not isinstance(event.get("hook"), bool):
                self.error(f"{path}.hook", "must be a boolean")
            if event.get("hook") and event.get("kind") != "far":
                self.error(f"{path}.hook", "hook events must have kind far")

    def validate_directives(self, value: Any, events_value: Any) -> None:
        items = self.sequence(value, "directives")
        if items is None:
            return
        events = {
            item.get("id"): item for item in events_value or []
            if isinstance(item, dict) and is_nonempty_string(item.get("id"))
        } if isinstance(events_value, list) else {}
        required = {
            "id", "raw", "kind", "required_outcome", "protected_details",
            "adaptation_scope", "deadline", "status", "created_turn", "event_id",
            "resolution", "block_code",
        }
        for index, item in enumerate(items):
            path = f"directives[{index}]"
            directive = self.mapping(item, path)
            if directive is None:
                continue
            self.required(directive, required, path)
            self.add_id(directive.get("id"), f"{path}.id")
            self.required_text(directive, ("raw", "required_outcome"), path)
            kind = directive.get("kind")
            if kind not in DIRECTIVE_KINDS:
                self.error(f"{path}.kind", f"must be one of {sorted(DIRECTIVE_KINDS)}")
            status = directive.get("status")
            if status not in DIRECTIVE_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(DIRECTIVE_STATUSES)}")
            deadline = directive.get("deadline")
            if deadline not in DIRECTIVE_DEADLINES:
                self.error(f"{path}.deadline", f"must be one of {sorted(DIRECTIVE_DEADLINES)}")

            protected = self.sequence(directive.get("protected_details"), f"{path}.protected_details")
            if protected is not None and any(not is_nonempty_string(detail) for detail in protected):
                self.error(f"{path}.protected_details", "must contain only non-empty strings")
            scopes = self.sequence(directive.get("adaptation_scope"), f"{path}.adaptation_scope")
            if scopes is not None:
                invalid_scopes = [scope for scope in scopes if scope not in DIRECTIVE_SCOPES]
                if invalid_scopes:
                    self.error(f"{path}.adaptation_scope",
                               f"contains invalid values {invalid_scopes!r}")
                if len(scopes) != len(set(scopes)):
                    self.error(f"{path}.adaptation_scope", "must not contain duplicates")

            created_turn = directive.get("created_turn")
            if not is_int(created_turn) or created_turn < 0:
                self.error(f"{path}.created_turn", "must be a non-negative integer")
            elif self._current_turn is not None and created_turn > self._current_turn:
                self.error(f"{path}.created_turn", "cannot be greater than meta.turn")

            event_id = directive.get("event_id")
            if event_id not in (None, "") and not is_nonempty_string(event_id):
                self.error(f"{path}.event_id", "must be null or a non-empty event ID")
            resolution = directive.get("resolution")
            block_code = directive.get("block_code")
            if status == "pending":
                if deadline != "earliest_possible":
                    self.error(f"{path}.deadline", "pending directives must use earliest_possible")
                event = events.get(event_id)
                if event is None:
                    self.error(f"{path}.event_id", "pending directive must reference an existing event ID")
                else:
                    if event.get("status") != "pending":
                        self.error(f"{path}.event_id", "must reference a pending event")
                    if event.get("source") != directive.get("id"):
                        self.error(f"{path}.event_id", "referenced event source must equal directive ID")
                if resolution not in (None, ""):
                    self.error(f"{path}.resolution", "must be empty while pending")
            elif status in {"fulfilled", "blocked"} and not is_nonempty_string(resolution):
                self.error(f"{path}.resolution", f"is required when status is {status}")

            if status == "blocked":
                if block_code not in DIRECTIVE_BLOCK_CODES:
                    self.error(f"{path}.block_code",
                               f"must be one of {sorted(DIRECTIVE_BLOCK_CODES)} when blocked")
            elif block_code not in (None, ""):
                self.error(f"{path}.block_code", "must be null unless status is blocked")

    def validate_checkpoint(self, value: Any, meta_value: Any,
                            directives_value: Any = None) -> None:
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
        if self.sequence(data.get("changed"), "checkpoint.changed") is not None:
            for index, change in enumerate(data.get("changed", [])):
                path = f"checkpoint.changed[{index}]"
                item = self.mapping(change, path)
                if item is not None:
                    self.required(item, {"turn", "field", "reason"}, path)
                    if not is_int(item.get("turn")) or item.get("turn") < 0:
                        self.error(f"{path}.turn", "must be a non-negative integer")
                    elif is_int(turn) and item.get("turn") > turn:
                        self.error(f"{path}.turn", "cannot be greater than meta.turn")
                    if not is_nonempty_string(item.get("field")):
                        self.error(f"{path}.field", "must be a non-empty string")
                    if not is_nonempty_string(item.get("reason")):
                        self.error(f"{path}.reason", "must be a non-empty string")
        if not is_int(data.get("next_full_turn")) or data.get("next_full_turn") < 0:
            self.error("checkpoint.next_full_turn", "must be a non-negative integer")
        elif is_int(last_full) and data.get("next_full_turn") != last_full + 5:
            self.error("checkpoint.next_full_turn", "must equal last_full_turn + 5")
        if not isinstance(data.get("force_full"), bool):
            self.error("checkpoint.force_full", "must be a boolean")
        invariants = self.mapping(data.get("invariants"), "checkpoint.invariants")
        if invariants is not None:
            names = {"age_verified", "player_control_preserved"}
            self.required(invariants, names, "checkpoint.invariants")
            for name in names:
                if name in invariants and not isinstance(invariants[name], bool):
                    self.error(f"checkpoint.invariants.{name}", "must be a boolean")
            if ("directive_priority_preserved" in invariants
                    and not isinstance(invariants["directive_priority_preserved"], bool)):
                self.error("checkpoint.invariants.directive_priority_preserved",
                           "must be a boolean when present")
            if isinstance(directives_value, list) and directives_value:
                priority = invariants.get("directive_priority_preserved")
                if priority is not True:
                    self.error("checkpoint.invariants.directive_priority_preserved",
                               "must be true when directives are present")

    def validate_current_node(self, value: Any) -> None:
        data = self.mapping(value, "current_node")
        if data is None:
            return
        required = {"location", "participants", "situation", "last_committed_result", "unresolved_action", "natural_next_pressure"}
        self.required(data, required, "current_node")
        self.required_text(data, ("location", "last_committed_result", "natural_next_pressure"), "current_node")
        situation = self.mapping(data.get("situation"), "current_node.situation")
        if situation is not None:
            fields = {"trigger", "pressure", "immediate_objective", "deadline", "unresolved_choice", "knowledge_gap", "exits", "consequence"}
            self.required(situation, fields, "current_node.situation")
            for field in ("trigger", "pressure", "immediate_objective", "unresolved_choice"):
                if not is_nonempty_string(situation.get(field)):
                    self.error(f"current_node.situation.{field}", "must be a non-empty string")
            knowledge_gap = self.mapping(situation.get("knowledge_gap"), "current_node.situation.knowledge_gap")
            if knowledge_gap is not None:
                self.required(knowledge_gap, {"player_knows", "npc_knows", "both_mistake"}, "current_node.situation.knowledge_gap")
                for field in ("player_knows", "npc_knows", "both_mistake"):
                    self.sequence(knowledge_gap.get(field), f"current_node.situation.knowledge_gap.{field}")
            exits = self.mapping(situation.get("exits"), "current_node.situation.exits")
            if exits is not None:
                self.required(exits, {"available", "cost", "blocked_by"}, "current_node.situation.exits")
                if not isinstance(exits.get("available"), bool):
                    self.error("current_node.situation.exits.available", "must be a boolean")
            consequence = self.mapping(situation.get("consequence"), "current_node.situation.consequence")
            if consequence is not None:
                self.required(consequence, {"immediate", "near_term"}, "current_node.situation.consequence")
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
