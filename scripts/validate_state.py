#!/usr/bin/env python3
"""Validate a version 3 adult-tension-narrative YAML state file."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


SAVE_VERSION = 3
PROFILES = {"save", "opening"}
SAFETY_STATES = {"running", "paused"}
MODES = {"reliable", "immersive"}
POWER_STRUCTURES = {"player_high", "npc_high", "equal", "switchable"}
BOUNDARY_STATUSES = {"active", "revoked"}
CONSENT_STATUSES = {"unknown", "granted", "withdrawn", "not_applicable"}
CONSENT_SCOPE_TYPES = {"scene", "physical", "emotional", "information"}
EVENT_STATUSES = {"pending", "resolved", "cancelled"}
EVENT_KINDS = {"immediate", "near", "far", "timed", "probabilistic"}
# "directive" 源类型仅为兼容历史存档保留（曾用于指令契约的兑现事件）；
# 新版流程不再创建指令契约，新事件一律使用 system/turn/npc/world 源。
EVENT_SOURCES = {"system", "turn", "npc", "directive", "world"}
ROLE_LEVELS = {"main", "important_supporting", "supporting"}


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_iso_datetime(value: Any) -> dt.datetime | None:
    if not is_nonempty_string(value):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def parse_event_source(value: Any) -> tuple[str, str] | None:
    if not is_nonempty_string(value) or ":" not in value:
        return None
    source_type, source_id = value.split(":", 1)
    if source_type not in EVENT_SOURCES or not is_nonempty_string(source_id):
        return None
    return source_type, source_id


class Validator:
    def __init__(self, profile: str = "save") -> None:
        self.errors: list[str] = []
        self.ids: dict[str, str] = {}
        self.character_ids: set[str] = set()
        self.current_turn: int | None = None
        self.scene_id: str | None = None
        self.scene_location: str | None = None
        self.scene_participants: set[str] = set()
        self.npcs: list[dict[str, Any]] = []
        self.profile = profile

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

    def validate_turn(self, value: Any, path: str, *, nullable: bool = False) -> None:
        if nullable and value is None:
            return
        if not is_int(value) or value < 0:
            self.error(path, "must be a non-negative integer")
        elif self.current_turn is not None and value > self.current_turn:
            self.error(path, "cannot be greater than meta.turn")

    def validate_age(self, value: Any, path: str) -> None:
        if not is_int(value):
            self.error(path, "must be an explicitly confirmed integer")
        elif value < 18:
            self.error(path, "must be at least 18")

    def validate(self, root: Any) -> list[str]:
        if self.profile not in PROFILES:
            self.error("profile", f"must be one of {sorted(PROFILES)}")
            return self.errors
        data = self.mapping(root, "root")
        if data is None:
            return self.errors
        self.required(data, {
            "save_version", "meta", "world", "boundaries", "consent", "player",
            "player_naming_audit", "npcs", "relationships", "events",
            "checkpoint", "resolved_summary", "current_node",
        }, "")
        if data.get("save_version") != SAVE_VERSION:
            self.error("save_version", f"must equal {SAVE_VERSION}")

        meta = data.get("meta")
        if isinstance(meta, dict) and is_int(meta.get("turn")) and meta["turn"] >= 0:
            self.current_turn = meta["turn"]
        node = data.get("current_node")
        if isinstance(node, dict):
            self.scene_id = node.get("scene_id") if is_nonempty_string(node.get("scene_id")) else None
            self.scene_location = node.get("location") if is_nonempty_string(node.get("location")) else None
            participants = node.get("participants")
            if isinstance(participants, list):
                self.scene_participants = {item for item in participants if is_nonempty_string(item)}

        self.validate_meta(meta)
        self.validate_player(data.get("player"))
        self.validate_player_naming_audit(data.get("player_naming_audit"), data.get("player"))
        if isinstance(data.get("npcs"), list):
            self.npcs = [item for item in data["npcs"] if isinstance(item, dict)]
        self.validate_npcs(data.get("npcs"))
        self.validate_current_node(node)
        self.validate_world(data.get("world"), data.get("events"))
        self.validate_boundaries(data.get("boundaries"))
        self.validate_consent(data.get("consent"))
        self.validate_relationships(data.get("relationships"))
        self.validate_events(data.get("events"), data.get("world"))
        self.validate_checkpoint(data.get("checkpoint"))
        self.validate_resolved_summary(data.get("resolved_summary"))
        if self.profile == "opening":
            self.validate_opening(data)
        return self.errors

    def validate_meta(self, value: Any) -> None:
        data = self.mapping(value, "meta")
        if data is None:
            return
        self.required(data, {"turn", "mode", "tier", "simulation", "safety_state", "power_structure"}, "meta")
        if not is_int(data.get("turn")) or data.get("turn") < 0:
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
        self.required(data, {"clock", "previous_clock", "delta_t", "constants", "tension_engines", "setting_shell", "pressure_seeds"}, "world")
        constants = self.sequence(data.get("constants"), "world.constants")
        if constants is not None and not constants:
            self.error("world.constants", "must contain at least one world constant")
        engines = self.sequence(data.get("tension_engines"), "world.tension_engines")
        if engines is not None:
            if not engines:
                self.error("world.tension_engines", "must contain at least one engine")
            if self.profile == "opening" and len({item for item in engines if is_nonempty_string(item)}) < 2:
                self.error("world.tension_engines", "opening profile requires at least two distinct engines")
        shell = self.mapping(data.get("setting_shell"), "world.setting_shell")
        if shell is not None:
            self.required_text(shell, ("type", "place", "rule", "pressure"), "world.setting_shell")
        clock = parse_iso_datetime(data.get("clock"))
        previous = parse_iso_datetime(data.get("previous_clock"))
        if clock is None:
            self.error("world.clock", "must be an ISO 8601 string with timezone")
        if previous is None:
            self.error("world.previous_clock", "must be an ISO 8601 string with timezone")
        delta = data.get("delta_t")
        if not is_int(delta) or delta < 0:
            self.error("world.delta_t", "must be a non-negative integer number of seconds")
        if clock is not None and previous is not None:
            seconds = (clock - previous).total_seconds()
            if seconds < 0:
                self.error("world.clock", "cannot be earlier than previous_clock")
            elif not seconds.is_integer():
                self.error("world.clock", "must differ from previous_clock by whole seconds")
            elif is_int(delta) and delta != int(seconds):
                self.error("world.delta_t", "must equal clock minus previous_clock in seconds exactly")
        pressure = self.mapping(data.get("pressure_seeds"), "world.pressure_seeds")
        if pressure is None:
            return
        self.required(pressure, {"immediate", "near_event_id", "far_event_id"}, "world.pressure_seeds")
        if not is_nonempty_string(pressure.get("immediate")):
            self.error("world.pressure_seeds.immediate", "must be a non-empty string")
        events = {event.get("id"): event for event in events_value or [] if isinstance(event, dict) and is_nonempty_string(event.get("id"))} if isinstance(events_value, list) else {}
        if self.profile == "opening" and not events:
            return
        for field, kind in (("near_event_id", "near"), ("far_event_id", "far")):
            event_id = pressure.get(field)
            if not is_nonempty_string(event_id):
                self.error(f"world.pressure_seeds.{field}", "must be a non-empty event ID")
                continue
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
        self.required(data, {"id", "name", "age", "identity", "location", "baseline", "resources", "knowledge", "reputation"}, "player")
        self.add_id(data.get("id"), "player.id", character=True)
        self.validate_age(data.get("age"), "player.age")
        self.required_text(data, ("name", "identity", "location", "baseline", "reputation"), "player")
        self.sequence(data.get("resources"), "player.resources")
        self.sequence(data.get("knowledge"), "player.knowledge")

    def validate_player_naming_audit(self, value: Any, player_value: Any) -> None:
        data = self.mapping(value, "player_naming_audit")
        player = player_value if isinstance(player_value, dict) else {}
        if data is None:
            return
        self.required(data, {"chosen", "source", "approved_turn"}, "player_naming_audit")
        self.required_text(data, ("chosen", "source"), "player_naming_audit")
        if is_nonempty_string(player.get("name")) and data.get("chosen") != player.get("name"):
            self.error("player_naming_audit.chosen", "must match player.name")
        self.validate_turn(data.get("approved_turn"), "player_naming_audit.approved_turn")

    def validate_npcs(self, value: Any) -> None:
        items = self.sequence(value, "npcs")
        if items is None:
            return
        if not items:
            self.error("npcs", "must contain at least one NPC")
        base = {"id", "name", "age", "role_level", "identity", "location", "goal", "boundary", "resources", "knowledge", "recent_memories", "signature", "autonomy"}
        expressive = {"core_personality", "pressure_strategy", "voice_filter", "withdrawal_signal", "emotion"}
        main_nested = {"identity_profile", "situation", "decision_card", "sexuality_profile", "sexuality_development", "naming_audit"}
        main_count = 0
        self.main_npc_ids: set[str] = set()
        self.npc_ids: set[str] = set()
        for index, value in enumerate(items):
            path = f"npcs[{index}]"
            npc = self.mapping(value, path)
            if npc is None:
                continue
            role = npc.get("role_level")
            self.required(npc, base | (expressive if role in {"main", "important_supporting"} else set()), path)
            self.required_text(npc, ("name", "identity", "location", "goal", "boundary", "signature"), path)
            self.add_id(npc.get("id"), f"{path}.id", character=True)
            if is_nonempty_string(npc.get("id")):
                self.npc_ids.add(npc["id"])
                if role == "main":
                    self.main_npc_ids.add(npc["id"])
            self.validate_age(npc.get("age"), f"{path}.age")
            if role not in ROLE_LEVELS:
                self.error(f"{path}.role_level", f"must be one of {sorted(ROLE_LEVELS)}")
            intimacy = npc.get("intimacy")
            if intimacy is not None:
                intimacy_data = self.mapping(intimacy, f"{path}.intimacy")
                if intimacy_data is not None:
                    self.required(intimacy_data, {"eligible", "scope"}, f"{path}.intimacy")
                    if not isinstance(intimacy_data.get("eligible"), bool):
                        self.error(f"{path}.intimacy.eligible", "must be a boolean")
                    if intimacy_data.get("scope") not in {"none", "non_intimate", "intimate"}:
                        self.error(f"{path}.intimacy.scope", "must be none, non_intimate, or intimate")
                    if intimacy_data.get("scope") == "intimate" and role == "supporting":
                        self.error(f"{path}.role_level", "supporting NPC with intimate participation must be upgraded")
            for field in ("resources", "knowledge", "recent_memories"):
                self.sequence(npc.get(field), f"{path}.{field}")
            if role in {"main", "important_supporting"}:
                self.required_text(npc, tuple(expressive), path)
            else:
                for field in expressive:
                    if field in npc and not isinstance(npc[field], str):
                        self.error(f"{path}.{field}", "must be a string when present for a supporting NPC")
            if role == "main":
                main_count += 1
                self.required(npc, main_nested, path)
                nested_requirements = {
                    "identity_profile": {"role"},
                    "situation": {"type"},
                    "decision_card": {"goal"},
                    "sexuality_profile": {"baseline"},
                    "sexuality_development": {"trend"},
                }
                for field, required_fields in nested_requirements.items():
                    detail = self.mapping(npc.get(field), f"{path}.{field}")
                    if detail is not None:
                        self.required(detail, required_fields, f"{path}.{field}")
                        for key in required_fields:
                            if not is_nonempty_string(detail.get(key)):
                                self.error(f"{path}.{field}.{key}", "must be a non-empty string")
                audit = self.mapping(npc.get("naming_audit"), f"{path}.naming_audit")
                if audit is not None:
                    self.required(audit, {"chosen", "source", "approved_turn"}, f"{path}.naming_audit")
                    self.required_text(audit, ("chosen", "source"), f"{path}.naming_audit")
                    if is_nonempty_string(npc.get("name")) and audit.get("chosen") != npc.get("name"):
                        self.error(f"{path}.naming_audit.chosen", "must match NPC name")
                    self.validate_turn(audit.get("approved_turn"), f"{path}.naming_audit.approved_turn")
            if "relation" in npc:
                self.error(f"{path}.relation", "must not duplicate the top-level relationships graph")
            autonomy = self.mapping(npc.get("autonomy"), f"{path}.autonomy")
            if autonomy is not None:
                self.required(autonomy, {"last_turn", "recent_turns", "cooldown_until"}, f"{path}.autonomy")
                self.validate_turn(autonomy.get("last_turn"), f"{path}.autonomy.last_turn", nullable=True)
                recent = self.sequence(autonomy.get("recent_turns"), f"{path}.autonomy.recent_turns")
                if recent is not None:
                    if any(not is_int(turn) or turn < 0 for turn in recent):
                        self.error(f"{path}.autonomy.recent_turns", "must contain only non-negative integers")
                    if recent != sorted(set(recent)):
                        self.error(f"{path}.autonomy.recent_turns", "must be unique and chronological")
                    if self.current_turn is not None and any(turn > self.current_turn for turn in recent if is_int(turn)):
                        self.error(f"{path}.autonomy.recent_turns", "cannot contain turns greater than meta.turn")
                    if is_int(autonomy.get("last_turn")) and recent and autonomy["last_turn"] != recent[-1]:
                        self.error(f"{path}.autonomy.last_turn", "must equal the most recent autonomy turn")
                cooldown = autonomy.get("cooldown_until")
                if not is_int(cooldown) or cooldown < 0:
                    self.error(f"{path}.autonomy.cooldown_until", "must be a non-negative integer")
                elif is_int(autonomy.get("last_turn")) and cooldown < autonomy["last_turn"]:
                    self.error(f"{path}.autonomy.cooldown_until", "cannot precede last_turn")
        if main_count < 1:
            self.error("npcs", "must contain at least one main NPC")

    def validate_current_node(self, value: Any) -> None:
        data = self.mapping(value, "current_node")
        if data is None:
            return
        self.required(data, {"scene_id", "location", "participants", "situation", "last_committed_result", "unresolved_action", "natural_next_pressure"}, "current_node")
        self.required_text(data, ("scene_id", "location", "last_committed_result", "unresolved_action", "natural_next_pressure"), "current_node")
        participants = self.sequence(data.get("participants"), "current_node.participants")
        if participants is not None:
            if not participants:
                self.error("current_node.participants", "must not be empty")
            if len(participants) != len(set(participants)):
                self.error("current_node.participants", "must not contain duplicates")
            for participant in participants:
                if participant not in self.character_ids:
                    self.error("current_node.participants", f"references unknown character ID {participant!r}")
        situation = self.mapping(data.get("situation"), "current_node.situation")
        if situation is not None:
            self.required(situation, {"trigger", "pressure", "immediate_objective", "deadline", "unresolved_choice", "knowledge_gap", "exits", "consequence"}, "current_node.situation")
            for field in ("trigger", "pressure", "immediate_objective", "unresolved_choice"):
                if not is_nonempty_string(situation.get(field)):
                    self.error(f"current_node.situation.{field}", "must be a non-empty string")
            if situation.get("deadline") not in (None, "") and parse_iso_datetime(situation.get("deadline")) is None:
                self.error("current_node.situation.deadline", "must be an ISO 8601 string with timezone when present")
            gap = self.mapping(situation.get("knowledge_gap"), "current_node.situation.knowledge_gap")
            if gap is not None:
                self.required(gap, {"player_knows", "npc_knows", "both_mistake"}, "current_node.situation.knowledge_gap")
                for field in ("player_knows", "npc_knows", "both_mistake"):
                    self.sequence(gap.get(field), f"current_node.situation.knowledge_gap.{field}")
            exits = self.mapping(situation.get("exits"), "current_node.situation.exits")
            if exits is not None:
                self.required(exits, {"available", "cost", "blocked_by"}, "current_node.situation.exits")
                if not isinstance(exits.get("available"), bool):
                    self.error("current_node.situation.exits.available", "must be a boolean")
            consequence = self.mapping(situation.get("consequence"), "current_node.situation.consequence")
            if consequence is not None:
                self.required(consequence, {"immediate", "near_term"}, "current_node.situation.consequence")

    def validate_boundaries(self, value: Any) -> None:
        items = self.sequence(value, "boundaries")
        if items is None:
            return
        for index, value in enumerate(items):
            path = f"boundaries[{index}]"
            boundary = self.mapping(value, path)
            if boundary is None:
                continue
            self.required(boundary, {"id", "topic", "status", "created_turn", "revoked_turn"}, path)
            self.add_id(boundary.get("id"), f"{path}.id")
            if boundary.get("status") not in BOUNDARY_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(BOUNDARY_STATUSES)}")
            if boundary.get("status") == "active" and not is_nonempty_string(boundary.get("topic")):
                self.error(f"{path}.topic", "must be non-empty for an active boundary")
            self.validate_turn(boundary.get("created_turn"), f"{path}.created_turn")
            self.validate_turn(boundary.get("revoked_turn"), f"{path}.revoked_turn", nullable=True)
            if is_int(boundary.get("created_turn")) and is_int(boundary.get("revoked_turn")) and boundary["revoked_turn"] < boundary["created_turn"]:
                self.error(f"{path}.revoked_turn", "cannot be earlier than created_turn")
            if boundary.get("status") == "active" and boundary.get("revoked_turn") is not None:
                self.error(f"{path}.revoked_turn", "must be null for an active boundary")
            if boundary.get("status") == "revoked" and boundary.get("revoked_turn") is None:
                self.error(f"{path}.revoked_turn", "is required for a revoked boundary")

    def validate_consent(self, value: Any) -> None:
        data = self.mapping(value, "consent")
        if data is None:
            return
        self.required(data, {"scene_id", "location", "participants", "grants"}, "consent")
        self.required_text(data, ("scene_id", "location"), "consent")
        if self.scene_id is not None and data.get("scene_id") != self.scene_id:
            self.error("consent.scene_id", "must match current_node.scene_id")
        if self.scene_location is not None and data.get("location") != self.scene_location:
            self.error("consent.location", "must match current_node.location")
        participants = self.sequence(data.get("participants"), "consent.participants")
        if participants is not None and set(participants) != self.scene_participants:
            self.error("consent.participants", "must exactly match current_node.participants")
        grants = self.sequence(data.get("grants"), "consent.grants")
        if grants is None:
            return
        for index, value in enumerate(grants):
            path = f"consent.grants[{index}]"
            grant = self.mapping(value, path)
            if grant is None:
                continue
            self.required(grant, {"id", "scene_id", "participants", "scope", "status", "granted_turn", "withdrawn_turn", "last_checked_turn"}, path)
            self.add_id(grant.get("id"), f"{path}.id")
            if grant.get("scene_id") != data.get("scene_id"):
                self.error(f"{path}.scene_id", "must match consent.scene_id")
            grant_participants = self.sequence(grant.get("participants"), f"{path}.participants")
            if grant_participants is not None:
                if len(grant_participants) < 2 or len(grant_participants) != len(set(grant_participants)):
                    self.error(f"{path}.participants", "must contain at least two distinct character IDs")
                if any(participant not in self.character_ids for participant in grant_participants):
                    self.error(f"{path}.participants", "references an unknown character ID")
                if not set(grant_participants).issubset(self.scene_participants):
                    self.error(f"{path}.participants", "must all appear in current_node.participants")
            scopes = self.sequence(grant.get("scope"), f"{path}.scope")
            if scopes is not None:
                if not scopes:
                    self.error(f"{path}.scope", "must contain at least one scope entry")
                for scope_index, scope_value in enumerate(scopes):
                    scope_path = f"{path}.scope[{scope_index}]"
                    scope = self.mapping(scope_value, scope_path)
                    if scope is not None:
                        self.required(scope, {"type", "permission"}, scope_path)
                        if scope.get("type") not in CONSENT_SCOPE_TYPES:
                            self.error(f"{scope_path}.type", f"must be one of {sorted(CONSENT_SCOPE_TYPES)}")
                        if not is_nonempty_string(scope.get("permission")):
                            self.error(f"{scope_path}.permission", "must be a non-empty string")
            status = grant.get("status")
            if status not in CONSENT_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(CONSENT_STATUSES)}")
            self.validate_turn(grant.get("granted_turn"), f"{path}.granted_turn", nullable=True)
            self.validate_turn(grant.get("withdrawn_turn"), f"{path}.withdrawn_turn", nullable=True)
            self.validate_turn(grant.get("last_checked_turn"), f"{path}.last_checked_turn")
            if status == "granted" and not is_int(grant.get("granted_turn")):
                self.error(f"{path}.granted_turn", "is required for granted consent")
            if status == "withdrawn" and not is_int(grant.get("withdrawn_turn")):
                self.error(f"{path}.withdrawn_turn", "is required for withdrawn consent")
            intimate = any(
                isinstance(scope, dict) and scope.get("type") == "physical"
                and "intimate" in str(scope.get("permission", "")).lower()
                for scope in (scopes or [])
            )
            if intimate:
                npc_roles = {npc.get("id"): npc.get("role_level") for npc in getattr(self, "npcs", []) if isinstance(npc, dict)}
                for participant in grant_participants or []:
                    if npc_roles.get(participant) == "supporting":
                        self.error(f"{path}.participants", "intimate scope participants must not be supporting NPCs")
            if status != "withdrawn" and grant.get("withdrawn_turn") is not None:
                self.error(f"{path}.withdrawn_turn", "must be null unless status is withdrawn")
            if is_int(grant.get("granted_turn")) and is_int(grant.get("withdrawn_turn")) and grant["withdrawn_turn"] < grant["granted_turn"]:
                self.error(f"{path}.withdrawn_turn", "cannot be earlier than granted_turn")

    def validate_relationships(self, value: Any) -> None:
        items = self.sequence(value, "relationships")
        if items is None:
            return
        seen: set[tuple[str, str, str, str]] = set()
        for index, value in enumerate(items):
            path = f"relationships[{index}]"
            relation = self.mapping(value, path)
            if relation is None:
                continue
            self.required(relation, {"source", "target", "type", "channel", "trust", "last_updated_turn", "opening"}, path)
            source, target = relation.get("source"), relation.get("target")
            if source not in self.character_ids:
                self.error(f"{path}.source", "must reference an existing character ID")
            if target not in self.character_ids:
                self.error(f"{path}.target", "must reference an existing character ID")
            if source == target and source in self.character_ids:
                self.error(path, "source and target must be different characters")
            self.required_text(relation, ("type", "channel"), path)
            edge = (str(source), str(target), str(relation.get("type")), str(relation.get("channel")))
            if edge in seen:
                self.error(path, "duplicates an existing relationship edge")
            seen.add(edge)
            if not is_int(relation.get("trust")) or not -5 <= relation.get("trust") <= 5:
                self.error(f"{path}.trust", "must be an integer from -5 to 5")
            self.validate_turn(relation.get("last_updated_turn"), f"{path}.last_updated_turn")
            opening = self.mapping(relation.get("opening"), f"{path}.opening")
            if opening is not None:
                self.required(opening, {"status", "covered_turn"}, f"{path}.opening")
                if not isinstance(opening.get("status"), bool):
                    self.error(f"{path}.opening.status", "must be a boolean")
                self.validate_turn(opening.get("covered_turn"), f"{path}.opening.covered_turn")

    def validate_events(self, value: Any, world_value: Any) -> None:
        items = self.sequence(value, "events")
        if items is None:
            return
        now = parse_iso_datetime(world_value.get("clock")) if isinstance(world_value, dict) else None
        semantic_keys: dict[str, str] = {}
        for index, value in enumerate(items):
            path = f"events[{index}]"
            event = self.mapping(value, path)
            if event is None:
                continue
            self.required(event, {"id", "source", "created_turn", "kind", "trigger", "due_at", "status", "consequence", "hook", "probability"}, path)
            self.add_id(event.get("id"), f"{path}.id")
            source = parse_event_source(event.get("source"))
            if source is None:
                self.error(f"{path}.source", "must be a legal 'type:id' source")
            elif source[0] == "npc" and source[1] not in self.character_ids:
                self.error(f"{path}.source", "NPC source must reference a known character")
            kind = event.get("kind")
            if kind not in EVENT_KINDS:
                self.error(f"{path}.kind", f"must be one of {sorted(EVENT_KINDS)}")
            status = event.get("status")
            if status not in EVENT_STATUSES:
                self.error(f"{path}.status", f"must be one of {sorted(EVENT_STATUSES)}")
            semantic_key = event.get("semantic_key")
            if semantic_key not in (None, ""):
                if not is_nonempty_string(semantic_key):
                    self.error(f"{path}.semantic_key", "must be a non-empty string when present")
                elif semantic_key in semantic_keys:
                    self.error(f"{path}.semantic_key", f"duplicates {semantic_keys[semantic_key]}")
                else:
                    semantic_keys[semantic_key] = path
            if status == "pending" and not is_nonempty_string(semantic_key):
                self.error(f"{path}.semantic_key", "pending events require a non-empty semantic_key")
            self.validate_turn(event.get("created_turn"), f"{path}.created_turn")
            due = event.get("due_at")
            due_time = None
            if due not in (None, ""):
                due_time = parse_iso_datetime(due)
                if due_time is None:
                    self.error(f"{path}.due_at", "must be an ISO 8601 string with timezone when present")
            if status == "pending":
                if not is_nonempty_string(event.get("trigger")) and due_time is None:
                    self.error(path, "pending event needs a non-empty trigger or due_at")
                if due_time is not None and now is not None and due_time <= now:
                    self.error(f"{path}.due_at", "pending event due_at must be later than world.clock")
            if not isinstance(event.get("hook"), bool):
                self.error(f"{path}.hook", "must be a boolean")
            elif event.get("hook") and kind != "far":
                self.error(f"{path}.hook", "hook events must have kind far")
            probability = event.get("probability")
            if kind == "probabilistic":
                if not isinstance(probability, (int, float)) or isinstance(probability, bool) or not 0 < probability <= 1:
                    self.error(f"{path}.probability", "probabilistic events require a number in (0, 1]")
            elif probability is not None:
                self.error(f"{path}.probability", "must be null unless kind is probabilistic")

    def validate_checkpoint(self, value: Any) -> None:
        data = self.mapping(value, "checkpoint")
        if data is None:
            return
        self.required(data, {"last_full_turn", "changed", "next_full_turn", "force_full", "force_reason", "invariants"}, "checkpoint")
        self.validate_turn(data.get("last_full_turn"), "checkpoint.last_full_turn")
        changed = self.sequence(data.get("changed"), "checkpoint.changed")
        if changed is not None:
            for index, value in enumerate(changed):
                path = f"checkpoint.changed[{index}]"
                change = self.mapping(value, path)
                if change is not None:
                    self.required(change, {"turn", "field", "reason"}, path)
                    self.validate_turn(change.get("turn"), f"{path}.turn")
                    self.required_text(change, ("field", "reason"), path)
        last_full = data.get("last_full_turn")
        if not is_int(data.get("next_full_turn")) or data.get("next_full_turn") < 0:
            self.error("checkpoint.next_full_turn", "must be a non-negative integer")
        elif is_int(last_full) and data["next_full_turn"] != last_full + 5:
            self.error("checkpoint.next_full_turn", "must equal last_full_turn + 5")
        force_full = data.get("force_full")
        if not isinstance(force_full, bool):
            self.error("checkpoint.force_full", "must be a boolean")
        if force_full and not is_nonempty_string(data.get("force_reason")):
            self.error("checkpoint.force_reason", "is required when force_full is true")
        if not force_full and data.get("force_reason") not in (None, ""):
            self.error("checkpoint.force_reason", "must be null unless force_full is true")
        invariants = self.mapping(data.get("invariants"), "checkpoint.invariants")
        if invariants is not None:
            names = {"age_verified", "player_control_preserved"}
            self.required(invariants, names, "checkpoint.invariants")
            for name in names:
                if invariants.get(name) is not True:
                    self.error(f"checkpoint.invariants.{name}", "must be true")

    def validate_resolved_summary(self, value: Any) -> None:
        items = self.sequence(value, "resolved_summary")
        if items is None:
            return
        for index, value in enumerate(items):
            path = f"resolved_summary[{index}]"
            summary = self.mapping(value, path)
            if summary is None:
                continue
            self.required(summary, {"event_id", "resolved_turn", "outcome"}, path)
            if not is_nonempty_string(summary.get("event_id")):
                self.error(f"{path}.event_id", "must be a non-empty event ID")
            self.validate_turn(summary.get("resolved_turn"), f"{path}.resolved_turn")
            if not is_nonempty_string(summary.get("outcome")):
                self.error(f"{path}.outcome", "must be a non-empty string")

    def validate_opening(self, data: dict[str, Any]) -> None:
        meta = data.get("meta")
        if isinstance(meta, dict):
            if meta.get("turn") != 1:
                self.error("meta.turn", "opening profile requires turn 1")
            if meta.get("safety_state") != "running":
                self.error("meta.safety_state", "opening profile requires running safety_state")
        events = data.get("events")
        if not isinstance(events, list):
            return
        required_top = {
            "save_version", "meta", "world", "boundaries", "consent", "player",
            "player_naming_audit", "npcs", "relationships", "events", "checkpoint",
            "resolved_summary", "current_node",
        }
        missing = required_top - data.keys()
        for field in sorted(missing):
            self.error(field, "opening profile requires C1-C14 structural field")
        kinds = {event.get("kind") for event in events if isinstance(event, dict)}
        for kind in ("immediate", "near", "far"):
            if kind not in kinds:
                self.error("events", f"opening profile requires an {kind} event")
        far_hooks = [event for event in events if isinstance(event, dict) and event.get("kind") == "far" and event.get("hook") is True]
        if not far_hooks:
            self.error("events", "opening profile requires a far hook event")
        relationships = data.get("relationships")
        if not isinstance(relationships, list) or not relationships:
            self.error("relationships", "opening profile requires relationship coverage")
        else:
            covered: set[tuple[str, str]] = set()
            for index, relationship in enumerate(relationships):
                opening = relationship.get("opening") if isinstance(relationship, dict) else None
                if not isinstance(opening, dict) or opening.get("status") is not True:
                    self.error(f"relationships[{index}].opening", "opening profile requires covered relationship edges")
                elif isinstance(relationship, dict):
                    source, target = relationship.get("source"), relationship.get("target")
                    covered.add((source, target))
            player_id = data.get("player", {}).get("id") if isinstance(data.get("player"), dict) else None
            npc_ids = getattr(self, "npc_ids", set())
            main_ids = getattr(self, "main_npc_ids", set())
            for npc_id in npc_ids:
                if (player_id, npc_id) not in covered and (npc_id, player_id) not in covered:
                    self.error("relationships", f"opening profile requires player relationship coverage for {npc_id}")
            ordered_main = sorted(main_ids)
            for left_index, left in enumerate(ordered_main):
                for right in ordered_main[left_index + 1:]:
                    if (left, right) not in covered and (right, left) not in covered:
                        self.error("relationships", f"opening profile requires main-main relationship coverage for {left}/{right}")
        if data.get("resolved_summary"):
            self.error("resolved_summary", "opening profile requires no resolved summaries")
        directives = data.get("directives")
        if isinstance(directives, list) and directives:
            self.error("directives", "new openings must not write directives")


def validate_data(data: Any, profile: str = "save") -> list[str]:
    return Validator(profile).validate(data)


def validate_text(text: str, profile: str = "save") -> list[str]:
    if yaml is None:
        return ["PyYAML is required; run: python -m pip install PyYAML"]
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"invalid YAML: {exc}"]
    return validate_data(data, profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save_file", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="save")
    args = parser.parse_args()
    if yaml is None:
        print("ERROR: PyYAML is required; run: python -m pip install PyYAML", file=sys.stderr)
        return 2
    try:
        text = args.save_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    errors = validate_text(text, args.profile)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.profile} invariants validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
