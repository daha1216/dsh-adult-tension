#!/usr/bin/env python3
"""回合提交器：应用小 patch，校验 save profile，写出活切片。

模型只提供 delta（时钟、未决、情绪、事件增删），不要重写整份 YAML。
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "saves" / "current_state.yaml"
PUBLIC_HINTS = ("走廊", "门厅", "大堂", "街道", "步道", "车站", "大厅", "连接处")
PRIVATE_HINTS = ("卧室", "浴室", "卫生间", "套房", "包厢", "起居室", "内间", "里间")
ORDINARY_TURN_MAX_SECONDS = 15 * 60
SHORT_FAST_FORWARD_MAX_SECONDS = 60 * 60


def _load_common() -> Any:
    """按路径加载同目录 _common.py（不依赖 sys.path，见该模块 docstring）。"""
    spec = importlib.util.spec_from_file_location(
        "adult_tension_common", Path(__file__).with_name("_common.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load _common.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_COMMON = _load_common()


class CommitError(RuntimeError):
    pass


def load_validator() -> Any:
    return _COMMON.load_sibling("validate_state")


def load_live_slice() -> Any:
    return _COMMON.load_sibling("live_slice")


def load_saves() -> Any:
    return _COMMON.load_sibling("manage_saves")


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = _COMMON.load_yaml_file(path)
    except _COMMON.CommonError as exc:
        raise CommitError(str(exc)) from exc
    if not isinstance(data, dict):
        raise CommitError(f"state is not a mapping: {path}")
    return data


def parse_clock(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise CommitError("world.clock missing")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise CommitError(f"invalid clock: {value}") from exc
    if parsed.tzinfo is None:
        raise CommitError("clock must include timezone")
    return parsed


def iso(value: dt.datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def requested_clock(state: dict[str, Any], patch: dict[str, Any], advance: bool) -> tuple[dt.datetime, dt.datetime]:
    world = state.get("world") if isinstance(state.get("world"), dict) else {}
    old_clock = parse_clock(world.get("clock"))
    if patch.get("clock"):
        return old_clock, parse_clock(patch["clock"])
    if patch.get("delta_seconds") is not None and patch.get("delta_minutes") is not None:
        raise CommitError("delta_seconds and delta_minutes cannot be used together")
    if patch.get("delta_seconds") is not None:
        delta = patch["delta_seconds"]
        if isinstance(delta, bool) or not isinstance(delta, int) or delta < 0:
            raise CommitError("delta_seconds must be a non-negative integer")
        return old_clock, old_clock + dt.timedelta(seconds=delta)
    if patch.get("delta_minutes") is not None:
        delta = patch["delta_minutes"]
        if isinstance(delta, bool) or not isinstance(delta, int) or delta < 0:
            raise CommitError("delta_minutes must be a non-negative integer")
        return old_clock, old_clock + dt.timedelta(minutes=delta)
    return old_clock, old_clock + dt.timedelta(minutes=5 if advance else 0)


def elapsed_seconds(state: dict[str, Any], patch: dict[str, Any]) -> int:
    old_clock, new_clock = requested_clock(state, patch, patch.get("advance_turn", True) is not False)
    return int((new_clock - old_clock).total_seconds())


def deterministic_event_roll(event_id: str, turn: int, seed: Any = 0) -> float:
    token = f"{seed}:{event_id}:{turn}".encode("utf-8")
    value = int.from_bytes(hashlib.sha256(token).digest()[:8], "big")
    return value / float(2**64)


def enforce_simulation_gate(state: dict[str, Any], patch: dict[str, Any]) -> None:
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    simulation = patch.get("simulation") if isinstance(patch.get("simulation"), bool) else meta.get("simulation")
    if simulation is not False:
        return
    violations: list[str] = []
    for npc_id, update in (patch.get("npc_updates") or {}).items():
        if isinstance(update, dict) and update.get("autonomy_now"):
            violations.append(f"npc_updates.{npc_id}.autonomy_now")
    for event in patch.get("events_add") or []:
        if not isinstance(event, dict):
            continue
        source = str(event.get("source") or "")
        if event.get("offline") is True or source.startswith("world:"):
            violations.append("events_add.offline")
    relation_delta = patch.get("relationship_delta")
    entries = relation_delta if isinstance(relation_delta, list) else [relation_delta]
    for entry in entries:
        if isinstance(entry, dict) and (entry.get("offline") is True or entry.get("propagation") is True):
            violations.append("relationship_delta.offline")
    if patch.get("twist_generate") is not None:
        violations.append("twist_generate")
    if violations:
        raise CommitError("simulation=false blocks offline/world effects: " + ", ".join(violations))


def apply_twist_generation(state: dict[str, Any], request: Any, turn: int, crossed_day: bool) -> None:
    if request is None:
        return
    if not isinstance(request, dict):
        raise CommitError("twist_generate must be a mapping")
    reason = request.get("reason")
    if reason not in {"first_cross_day", "player_requested"}:
        raise CommitError("twist_generate.reason must be first_cross_day or player_requested")
    world = state.setdefault("world", {})
    current = world.get("twist_state") if isinstance(world.get("twist_state"), dict) else {}
    count = current.get("generated_count", 0)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise CommitError("world.twist_state.generated_count must be a non-negative integer")
    if reason == "first_cross_day" and count > 0:
        raise CommitError("first_cross_day twist has already been generated")
    if reason == "first_cross_day" and not crossed_day:
        raise CommitError("first_cross_day twist requires a calendar day change")
    world["twist_state"] = {
        "generated_count": count + 1,
        "last_generated_turn": turn,
        "last_reason": reason,
    }


def next_id(prefix: str, existing: list[str], reserved: list[str] | None = None) -> str:
    numbers = []
    token = prefix + "-"
    pool = list(existing) + [item for item in (reserved or []) if item]
    for item in pool:
        if isinstance(item, str) and item.startswith(token):
            tail = item[len(token):]
            if tail.isdigit():
                numbers.append(int(tail))
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def location_root(location: str) -> str:
    return (location or "").split("·")[0]


def is_public(location: str) -> bool:
    return any(hint in (location or "") for hint in PUBLIC_HINTS)


def adjacent_private(old: str, new: str) -> bool:
    if not old or not new or old == new:
        return False
    if is_public(old) or is_public(new):
        return False
    if location_root(old) != location_root(new):
        return False
    # 继承方向只看新地点：必须是相邻私密空间才继承（范围不扩大）。
    return any(hint in new for hint in PRIVATE_HINTS)


def npc_by_id(state: dict[str, Any], npc_id: str) -> dict[str, Any] | None:
    for npc in state.get("npcs") or []:
        if isinstance(npc, dict) and npc.get("id") == npc_id:
            return npc
    return None


def apply_scene(state: dict[str, Any], location: str | None, participants: list[str] | None,
                turn: int) -> list[dict[str, str]]:
    node = state["current_node"]
    # Consent is inferred by the model from the live narrative; no grant ledger is stored.
    old_location = node.get("location")
    old_participants = list(node.get("participants") or [])
    new_location = location or old_location
    new_participants = list(participants or old_participants)
    changed = []
    if new_location == old_location and new_participants == old_participants:
        return changed
    old_scene = node.get("scene_id") or "scene-001"
    new_scene = next_id("scene", [old_scene])
    node["scene_id"] = new_scene
    node["location"] = new_location
    node["participants"] = new_participants
    player = state.get("player")
    if isinstance(player, dict):
        player["location"] = new_location
    for npc_id in new_participants:
        npc = npc_by_id(state, npc_id)
        if npc is not None:
            npc["location"] = new_location
    changed.append({"turn": turn, "field": "current_node.location", "reason": "scene change"})
    return changed


def apply_npc_updates(state: dict[str, Any], updates: dict[str, Any], turn: int) -> None:
    for npc_id, patch in (updates or {}).items():
        if not isinstance(patch, dict):
            continue
        npc = npc_by_id(state, npc_id)
        if npc is None:
            raise CommitError(f"unknown npc id: {npc_id}")
        for key in ("emotion", "location"):
            if patch.get(key):
                npc[key] = patch[key]
        if patch.get("active_voice_mode") in {"surface", "inner"}:
            npc["active_voice_mode"] = patch["active_voice_mode"]
        memory = patch.get("memory")
        if memory:
            recent = list(npc.get("recent_memories") or [])
            recent.append(str(memory))
            npc["recent_memories"] = recent[-4:]
        extra = patch.get("knowledge_add") or []
        if extra:
            knowledge = list(npc.get("knowledge") or [])
            for item in extra:
                if item and item not in knowledge:
                    knowledge.append(item)
            npc["knowledge"] = knowledge
        if patch.get("autonomy_now"):
            recent = list((npc.get("autonomy") or {}).get("recent_turns") or [])
            if turn not in recent:
                recent.append(turn)
            npc["autonomy"] = {
                "last_turn": turn,
                "recent_turns": recent,
                "cooldown_until": turn + 3,
            }
            # 决策卡不保存 autonomy 副本：顶层 autonomy 是唯一正式来源
            # （SKILL.md「角色卡不得保存覆盖顶层的关系数值/自主状态」）。


def _apply_relationship_edge(state: dict[str, Any], delta: dict[str, Any], turn: int) -> None:
    if not isinstance(delta, dict):
        raise CommitError("relationship_delta entries must be mappings")
    npcs = [n for n in state.get("npcs") or [] if isinstance(n, dict)]
    source = delta.get("source")
    target = delta.get("target")
    if not source or not target:
        # 仅当场上恰好一名 NPC 时才允许省写边端点，避免多 NPC 局静默指错边。
        if len(npcs) == 1:
            player_id = (state.get("player") or {}).get("id") if isinstance(state.get("player"), dict) else None
            source = source or player_id or "player-001"
            target = target or npcs[0].get("id")
        else:
            raise CommitError("relationship_delta 需要 source/target（场上不止一名 NPC 时不可省写）")
    changed = False
    for relation in state.get("relationships") or []:
        if not isinstance(relation, dict):
            continue
        if {relation.get("source"), relation.get("target")} != {source, target}:
            continue
        if delta.get("trust_set") is not None:
            value = delta["trust_set"]
            if isinstance(value, bool) or not isinstance(value, int):
                raise CommitError("relationship_delta trust_set must be an integer")
            new_trust = max(-5, min(5, value))
            if new_trust != relation.get("trust"):
                relation["trust"] = new_trust
                changed = True
        elif delta.get("trust") is not None:
            current = relation.get("trust") if isinstance(relation.get("trust"), int) else 0
            change = delta["trust"]
            if isinstance(change, bool) or not isinstance(change, int):
                raise CommitError("relationship_delta trust must be an integer delta")
            new_trust = max(-5, min(5, current + change))
            if new_trust != current:
                relation["trust"] = new_trust
                changed = True
        if delta.get("type") and delta["type"] != relation.get("type"):
            relation["type"] = delta["type"]
            changed = True
        if delta.get("channel") and delta["channel"] != relation.get("channel"):
            relation["channel"] = delta["channel"]
            changed = True
        if changed:
            relation["last_updated_turn"] = turn
        return
    raise CommitError(f"no relationship edge for {source}/{target}")


def apply_relationship(state: dict[str, Any], delta: dict[str, Any] | list[Any] | None,
                       turn: int) -> None:
    if delta is None:
        return
    entries = delta if isinstance(delta, list) else [delta]
    for entry in entries:
        _apply_relationship_edge(state, entry, turn)


EVENT_IMMUTABLE_FIELDS = ("id", "semantic_key", "kind", "source", "created_turn")

def _event_index(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for event in state.get("events") or []:
        if isinstance(event, dict) and isinstance(event.get("id"), str):
            index[event["id"]] = event
    return index


def repoint_pressure_seeds(state: dict[str, Any], affected_ids: set[str]) -> None:
    """种子引用的事件被解决/取消后，重指到同类 pending 事件；没有就置空。

    校验器（save profile）允许空种子，但只要非空就必须指向现存 pending 事件。
    """
    world = state.get("world")
    seeds = world.get("pressure_seeds") if isinstance(world, dict) else None
    if not isinstance(seeds, dict) or not affected_ids:
        return
    for field, kind in (("near_event_id", "near"), ("far_event_id", "far")):
        if seeds.get(field) not in affected_ids:
            continue
        replacement = None
        for event in state.get("events") or []:
            if not isinstance(event, dict):
                continue
            if event.get("status") != "pending" or event.get("id") in affected_ids:
                continue
            if event.get("kind") != kind:
                continue
            if kind == "far" and event.get("hook") is not True:
                continue
            replacement = event.get("id")
            break
        seeds[field] = replacement


def apply_events(state: dict[str, Any], resolve_ids: list[str], additions: list[dict[str, Any]],
                 turn: int, outcome_default: str, updates: list[Any] | None = None,
                 cancel_ids: list[str] | None = None) -> None:
    events = state.get("events") or []
    resolved = list(state.get("resolved_summary") or [])
    index = _event_index(state)
    # 已解决/已取消事件保留在队列中（世界运转.md：不得删除后重建同一含义事件）。
    resolve_list = list(dict.fromkeys(resolve_ids or []))
    unknown = [eid for eid in resolve_list if eid not in index]
    if unknown:
        raise CommitError(f"events_resolve references unknown event ids: {unknown}")
    touched: set[str] = set()
    for eid in resolve_list:
        event = index[eid]
        status = event.get("status")
        if status == "resolved":
            continue
        if status == "cancelled":
            raise CommitError(f"event {eid} is cancelled and cannot be resolved")
        event["status"] = "resolved"
        resolved.append({
            "event_id": eid,
            "resolved_turn": turn,
            "outcome": outcome_default or event.get("consequence") or "已在本回合落地",
        })
        touched.add(eid)

    cancel_list = list(dict.fromkeys(cancel_ids or []))
    unknown_cancel = [cid for cid in cancel_list if cid not in index]
    if unknown_cancel:
        raise CommitError(f"events_cancel references unknown event ids: {unknown_cancel}")
    for cid in cancel_list:
        event = index[cid]
        status = event.get("status")
        if status == "cancelled":
            continue
        if status == "resolved":
            raise CommitError(f"event {cid} is already resolved and cannot be cancelled")
        event["status"] = "cancelled"
        touched.add(cid)

    for raw in updates or []:
        if not isinstance(raw, dict):
            raise CommitError("events_update entries must be mappings")
        target_id = raw.get("id")
        if not target_id:
            raise CommitError("events_update entry missing id")
        if target_id not in index:
            raise CommitError(f"events_update references unknown event id: {target_id}")
        event = index[target_id]
        immutable_violation = [key for key in EVENT_IMMUTABLE_FIELDS
                               if key in raw and key != "id" and raw[key] != event.get(key)]
        if immutable_violation:
            raise CommitError(f"events_update cannot modify immutable fields: {immutable_violation}")
        for key in ("trigger", "due_at", "consequence", "probability"):
            if key in raw:
                event[key] = raw[key]
        if "hook" in raw:
            if not isinstance(raw["hook"], bool):
                raise CommitError("events_update hook must be a boolean")
            event["hook"] = raw["hook"]
        if raw.get("roll"):
            if raw.get("checked_turn_add"):
                raise CommitError("events_update roll cannot be combined with checked_turn_add")
            if event.get("kind") != "probabilistic":
                raise CommitError("event roll requires a probabilistic event")
            if event.get("status") != "pending":
                raise CommitError("only pending events can be rolled")
            checked = list(event.get("checked_turns") or [])
            if turn in checked:
                raise CommitError(f"event {target_id} was already checked on turn {turn}")
            probability = event.get("probability")
            if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not 0 < probability <= 1:
                raise CommitError("probabilistic event probability must be in (0, 1]")
            meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
            roll_value = deterministic_event_roll(target_id, turn, meta.get("event_seed", 0))
            hit = roll_value < float(probability)
            event["last_roll"] = {
                "turn": turn,
                "value": roll_value,
                "outcome": "hit" if hit else "miss",
            }
            if hit:
                event["status"] = "resolved"
                resolved.append({
                    "event_id": target_id,
                    "resolved_turn": turn,
                    "outcome": raw.get("roll_outcome") or event.get("consequence") or "概率事件已命中",
                })
                touched.add(target_id)
            else:
                checked.append(turn)
                event["checked_turns"] = checked
        if raw.get("checked_turn_add"):
            checked = list(event.get("checked_turns") or [])
            if turn not in checked:
                checked.append(turn)
            event["checked_turns"] = checked
        # 注意：这里不再把 target_id 移出 touched——同一事件在同补丁内被解决/取消
        # 又被更新时，仍按解决/取消语义重指或置空压力种子（events_update 不吞重指）。

    all_event_ids = [event.get("id") for event in events if isinstance(event, dict)]
    summary_ids = [item.get("event_id") for item in resolved if isinstance(item, dict)]
    existing_keys = {event.get("semantic_key") for event in events if isinstance(event, dict)}
    for raw in additions or []:
        if not isinstance(raw, dict):
            continue
        event = dict(raw)
        event.setdefault("id", next_id("evt", [str(i) for i in all_event_ids if i], summary_ids))
        if event["id"] in all_event_ids:
            raise CommitError(f"duplicate event id {event['id']}")
        event.setdefault("source", f"turn:{turn}")
        event.setdefault("created_turn", turn)
        event.setdefault("kind", "timed")
        event.setdefault("status", "pending")
        event.setdefault("hook", False)
        event.setdefault("probability", None)
        event.setdefault("due_at", None)
        event.setdefault("trigger", event.get("trigger") or "本回合新增的未决")
        event.setdefault("consequence", event.get("consequence") or "将改变后续窗口")
        event.setdefault("semantic_key", event.get("semantic_key") or f"turn-{turn}-{event['id']}")
        if event["semantic_key"] in existing_keys:
            raise CommitError(f"duplicate semantic_key {event['semantic_key']}")
        events.append(event)
        all_event_ids.append(event["id"])
        existing_keys.add(event["semantic_key"])
    state["events"] = events
    state["resolved_summary"] = resolved
    if touched:
        repoint_pressure_seeds(state, touched)


def expire_due_events(state: dict[str, Any], now: dt.datetime, turn: int) -> None:
    due_ids = []
    for event in state.get("events") or []:
        if not isinstance(event, dict) or event.get("status") != "pending":
            continue
        due = event.get("due_at")
        if not due:
            continue
        try:
            due_time = dt.datetime.fromisoformat(str(due))
        except ValueError:
            continue
        if due_time.tzinfo is None:
            continue
        if due_time <= now:
            due_ids.append(event.get("id"))
    if due_ids:
        apply_events(state, [str(i) for i in due_ids if i], [], turn, "时限已到，尚未在场上兑现")


def apply_boundaries(state: dict[str, Any], additions: list[Any], revoke_topics: list[str],
                     turn: int) -> None:
    items = list(state.get("boundaries") or [])
    existing_ids = [b.get("id") for b in items if isinstance(b, dict)]
    revoke = list(dict.fromkeys(revoke_topics or []))
    # 话题对不上任何边界记录（无论 active/revoked）
    # 就报错退出，不静默无操作。
    known_topics = {b.get("topic") for b in items if isinstance(b, dict)}
    unknown = [topic for topic in revoke if topic not in known_topics]
    if unknown:
        raise CommitError(f"boundaries_revoke references unknown boundary topics: {unknown}")
    revoke_set = set(revoke)
    for boundary in items:
        if isinstance(boundary, dict) and boundary.get("topic") in revoke_set and boundary.get("status") == "active":
            boundary["status"] = "revoked"
            boundary["revoked_turn"] = turn
    for raw in additions or []:
        topic = raw if isinstance(raw, str) else (raw.get("topic") if isinstance(raw, dict) else None)
        if not topic:
            continue
        items.append({
            "id": next_id("boundary", [str(i) for i in existing_ids if i]),
            "topic": topic,
            "status": "active",
            "created_turn": turn,
            "revoked_turn": None,
        })
        existing_ids.append(items[-1]["id"])
    state["boundaries"] = items


def apply_npcs_add(state: dict[str, Any], additions: list[Any]) -> None:
    if not additions:
        return
    npcs = state.setdefault("npcs", [])
    existing_ids = {n.get("id") for n in npcs if isinstance(n, dict)}
    node = state.get("current_node") if isinstance(state.get("current_node"), dict) else {}
    for raw in additions or []:
        if not isinstance(raw, dict):
            raise CommitError("npcs_add entries must be mappings")
        npc_id = raw.get("id")
        if not isinstance(npc_id, str) or not npc_id.strip():
            raise CommitError("npcs_add entry missing id")
        if npc_id in existing_ids:
            raise CommitError(f"duplicate npc id: {npc_id}")
        npc = copy.deepcopy(raw)
        npc.setdefault("location", node.get("location") or "")
        npc.setdefault("resources", [])
        npc.setdefault("knowledge", [])
        npc.setdefault("recent_memories", [])
        autonomy = npc.get("autonomy")
        if not isinstance(autonomy, dict):
            npc["autonomy"] = {"last_turn": None, "recent_turns": [], "cooldown_until": 0}
        npcs.append(npc)
        existing_ids.add(npc_id)


def maybe_full(state: dict[str, Any], turn: int, force: bool,
               scene_changed: bool) -> None:
    checkpoint = state.setdefault("checkpoint", {})
    due = False
    next_full = checkpoint.get("next_full_turn")
    if isinstance(next_full, int) and turn >= next_full:
        due = True
    if force or scene_changed or due:
        checkpoint["last_full_turn"] = turn
        checkpoint["next_full_turn"] = turn + 5
        checkpoint["force_full"] = False
        checkpoint["force_reason"] = None
        if "invariants" not in checkpoint:
            checkpoint["invariants"] = {"age_verified": True, "player_control_preserved": True}


def classify_turn(state: dict[str, Any], patch: dict[str, Any]) -> tuple[str, list[str]]:
    """Resolve the model's turn judgment, applying only hard escalations."""
    if patch.get("advance_turn", True) is False:
        return "meta", ["advance_turn=false"]

    requested = patch.get("turn_mode", "fast")
    if requested not in {"fast", "deep"}:
        raise CommitError("turn_mode must be fast or deep")
    reasons: list[str] = [f"model requested {requested}"]
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    world = state.get("world") if isinstance(state.get("world"), dict) else {}
    node = state.get("current_node") if isinstance(state.get("current_node"), dict) else {}
    checkpoint = state.get("checkpoint") if isinstance(state.get("checkpoint"), dict) else {}
    if patch.get("force_full") or patch.get("full"):
        reasons.append("explicit force_full")
    if patch.get("location") is not None and patch.get("location") != node.get("location"):
        reasons.append("scene location changed")
    if patch.get("participants") is not None:
        if list(patch.get("participants") or []) != list(node.get("participants") or []):
            reasons.append("scene participants changed")
    if any(patch.get(key) for key in (
        "boundaries_add", "boundaries_revoke",
        "events_add", "events_resolve", "events_cancel", "events_update", "npcs_add",
        "twist_generate",
    )):
        reasons.append("structural state changed")
    if any(isinstance(update, dict) and update.get("autonomy_now")
           for update in (patch.get("npc_updates") or {}).values()):
        reasons.append("NPC autonomous action")
    if patch.get("retcon_add") or patch.get("safety_state") in {"paused", "running"}:
        reasons.append("safety or continuity control changed")
    span = elapsed_seconds(state, patch)
    if span > ORDINARY_TURN_MAX_SECONDS:
        if span >= SHORT_FAST_FORWARD_MAX_SECONDS:
            reasons.append("large time jump")
        else:
            reasons.append("short fast-forward")
    if span < 0:
        reasons.append("clock moved backwards")
    try:
        old_clock, new_clock = requested_clock(state, patch, patch.get("advance_turn", True) is not False)
        if old_clock.date() != new_clock.date():
            reasons.append("calendar day changed")
    except (CommitError, TypeError, ValueError, OverflowError):
        reasons.append("clock requires full validation")
    current_turn = int(meta.get("turn") or 0) + 1
    next_full = checkpoint.get("next_full_turn")
    if isinstance(next_full, int) and current_turn >= next_full:
        reasons.append("scheduled deep calibration")
    if len(reasons) > 1:
        reasons.append("script hard escalation")
        return "deep", reasons
    reasons.append("ordinary local turn")
    return requested, reasons


def apply_patch(state: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    enforce_simulation_gate(state, patch)
    data = copy.deepcopy(state)
    meta = data.setdefault("meta", {})
    world = data.setdefault("world", {})
    node = data.setdefault("current_node", {})
    advance = patch.get("advance_turn", True)
    old_turn = meta.get("turn") if isinstance(meta.get("turn"), int) else 0
    turn = old_turn + 1 if advance else old_turn
    if advance:
        meta["turn"] = turn
    if patch.get("safety_state") in {"running", "paused"}:
        meta["safety_state"] = patch["safety_state"]
    if isinstance(patch.get("simulation"), bool):
        meta["simulation"] = patch["simulation"]
    if patch.get("voyeur_pov") in {"on", "off"}:
        meta["voyeur_pov"] = patch["voyeur_pov"]

    old_clock, new_clock = requested_clock(data, patch, advance)
    if new_clock < old_clock:
        raise CommitError("clock cannot move backwards")
    if advance and new_clock == old_clock:
        raise CommitError("advancing turns must move the clock")
    if new_clock != old_clock:
        world["previous_clock"] = iso(old_clock)
        world["clock"] = iso(new_clock)
        world["delta_t"] = int((new_clock - old_clock).total_seconds())
        minutes = world["delta_t"] // 60
        world["delta_human"] = f"{minutes} 分钟" if minutes else f"{world['delta_t']} 秒"
    elif not advance:
        world["delta_t"] = 0
        world["delta_human"] = world.get("delta_human") or ""

    changes = []
    if patch.get("location") is not None or patch.get("participants") is not None:
        changes.extend(apply_scene(data, patch.get("location"), patch.get("participants"), turn))
    scene_changed_actual = any(
        isinstance(change, dict) and change.get("field") == "current_node.location"
        for change in changes
    )
    if patch.get("last_committed_result"):
        node["last_committed_result"] = patch["last_committed_result"]
        changes.append({"turn": turn, "field": "current_node.last_committed_result", "reason": "turn commit"})
    if patch.get("unresolved_action"):
        node["unresolved_action"] = patch["unresolved_action"]
    if patch.get("natural_next_pressure"):
        node["natural_next_pressure"] = patch["natural_next_pressure"]
    sit = node.get("situation") if isinstance(node.get("situation"), dict) else {}
    if patch.get("situation_update") and isinstance(patch["situation_update"], dict):
        sit.update(patch["situation_update"])
        node["situation"] = sit

    player_updates = patch.get("player_updates") or {}
    if isinstance(player_updates, dict):
        player = data.get("player") if isinstance(data.get("player"), dict) else {}
        extra = player_updates.get("knowledge_add") or []
        knowledge = list(player.get("knowledge") or [])
        for item in extra:
            if item and item not in knowledge:
                knowledge.append(item)
        player["knowledge"] = knowledge
        if player_updates.get("location"):
            player["location"] = player_updates["location"]

    apply_npc_updates(data, patch.get("npc_updates") or {}, turn)
    apply_npcs_add(data, list(patch.get("npcs_add") or []))
    apply_relationship(data, patch.get("relationship_delta"), turn)
    apply_twist_generation(data, patch.get("twist_generate"), turn, old_clock.date() != new_clock.date())
    if patch.get("twist_generate") is not None:
        changes.append({"turn": turn, "field": "world.twist_state", "reason": "twist generation recorded"})
    if patch.get("retcon_add"):
        entry = patch["retcon_add"]
        note = entry.get("note") if isinstance(entry, dict) else str(entry)
        retcons = data.setdefault("retcons", [])
        if not isinstance(retcons, list):
            retcons = []
            data["retcons"] = retcons
        retcons.append({"turn": turn, "note": str(note)})
        changes.append({"turn": turn, "field": "retcons", "reason": "retcon recorded"})
    apply_events(
        data,
        list(patch.get("events_resolve") or []),
        list(patch.get("events_add") or []),
        turn,
        str(patch.get("resolve_outcome") or ""),
        updates=list(patch.get("events_update") or []),
        cancel_ids=list(patch.get("events_cancel") or []),
    )
    expire_due_events(data, parse_clock(data["world"]["clock"]), turn)
    apply_boundaries(data, list(patch.get("boundaries_add") or []), list(patch.get("boundaries_revoke") or []), turn)

    if changes:
        data.setdefault("checkpoint", {})["changed"] = changes
    elif advance:
        data.setdefault("checkpoint", {})["changed"] = [
            {"turn": turn, "field": "world.clock", "reason": "turn advance"}
        ]
    elapsed = int((new_clock - old_clock).total_seconds())
    maybe_full(
        data, turn,
        force=bool(patch.get("force_full")) or elapsed >= 3600 or old_clock.date() != new_clock.date(),
        scene_changed=scene_changed_actual or bool(
            patch.get("boundaries_add") or patch.get("boundaries_revoke")
        ),
    )
    return data


def commit(state: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    updated = apply_patch(state, patch)
    validator = load_validator()
    errors = validator.validate_data(updated, "save")
    if errors:
        raise CommitError("save validation failed: " + "; ".join(errors))
    return updated


def load_patch(args: argparse.Namespace) -> dict[str, Any]:
    if args.patch_file:
        text = Path(args.patch_file).read_text(encoding="utf-8")
        data = json.loads(text)
    elif args.patch:
        data = json.loads(args.patch)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        data = json.loads(raw) if raw else {}
    else:
        data = {}
    if not isinstance(data, dict):
        raise CommitError("patch must be a JSON object")
    if args.delta_minutes is not None:
        data["delta_minutes"] = args.delta_minutes
    if args.full:
        data["force_full"] = True
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--patch", default=None, help="patch JSON string")
    parser.add_argument("--patch-file", type=Path, default=None)
    parser.add_argument("--delta-minutes", type=int, default=None)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--format", choices=("yaml", "json"), default="yaml")
    parser.add_argument("--out", type=Path, default=None, help="defaults to --state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = args.out or args.state
    try:
        lock = _COMMON.FileLock(_COMMON.lock_path(args.state))
        lock.__enter__()
    except _COMMON.CommonError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    try:
        state = load_yaml(args.state)
        patch = load_patch(args)
        turn_mode, turn_reasons = classify_turn(state, patch)
        updated = commit(state, patch)
        saves = load_saves()
        saves.write_atomic(out, saves.yaml_text(updated))
    except (CommitError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        lock.__exit__(None, None, None)
    slice_mod = load_live_slice()
    payload = slice_mod.extract_live_slice(updated)
    payload["turn_mode"] = turn_mode
    payload["turn_reasons"] = turn_reasons
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_COMMON.yaml_text(payload))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass
    raise SystemExit(main())
