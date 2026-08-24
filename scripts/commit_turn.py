#!/usr/bin/env python3
"""回合提交器：应用小 patch，校验 save profile，写出活切片。

模型只提供 delta（时钟、未决、情绪、事件增删），不要重写整份 YAML。
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "saves" / "current_state.yaml"
PUBLIC_HINTS = ("走廊", "门厅", "大堂", "街道", "步道", "车站", "大厅", "连接处")
PRIVATE_HINTS = ("卧室", "浴室", "卫生间", "套房", "包厢", "起居室", "内间", "里间")


class CommitError(RuntimeError):
    pass


def _load_module(script: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise CommitError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_validator() -> Any:
    return _load_module(Path(__file__).with_name("validate_state.py"), "adult_tension_validate_state")


def load_live_slice() -> Any:
    return _load_module(Path(__file__).with_name("live_slice.py"), "adult_tension_live_slice")


def load_saves() -> Any:
    return _load_module(Path(__file__).with_name("manage_saves.py"), "adult_tension_manage_saves")


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise CommitError("PyYAML is required; run: python -m pip install PyYAML")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CommitError(f"cannot read {path}: {exc}") from exc
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
    consent = state["consent"]
    old_location = node.get("location")
    old_participants = list(node.get("participants") or [])
    new_location = location or old_location
    new_participants = list(participants or old_participants)
    changed = []
    if new_location == old_location and new_participants == old_participants:
        return changed
    old_scene = node.get("scene_id") or "scene-001"
    new_scene = next_id("scene", [old_scene])
    inherit = False
    safety = (state.get("meta") or {}).get("safety_state")
    if (
        new_participants == old_participants
        and safety != "paused"
        and adjacent_private(str(old_location), str(new_location))
    ):
        inherit = True
    new_grants = []
    if inherit:
        for grant in consent.get("grants") or []:
            if not isinstance(grant, dict) or grant.get("status") != "granted":
                continue
            scopes = [
                scope for scope in (grant.get("scope") or [])
                if isinstance(scope, dict) and scope.get("type") == "physical"
            ]
            if not scopes:
                continue
            new_grants.append({
                "id": next_id("consent", [item.get("id") for item in new_grants if isinstance(item, dict)] + [
                    g.get("id") for g in (consent.get("grants") or []) if isinstance(g, dict)
                ]),
                "scene_id": new_scene,
                "participants": list(new_participants),
                "scope": copy.deepcopy(scopes),
                "status": "granted",
                "granted_turn": turn,
                "withdrawn_turn": None,
                "last_checked_turn": turn,
                "inherited_from": grant.get("id"),
            })
    node["scene_id"] = new_scene
    node["location"] = new_location
    node["participants"] = new_participants
    consent["scene_id"] = new_scene
    consent["location"] = new_location
    consent["participants"] = new_participants
    # 旧场景的授予/撤回记录归档保存，不再随换场丢失（状态总结.md「另行归档」）。
    archive = consent.get("grants_archive")
    if not isinstance(archive, list):
        archive = []
        consent["grants_archive"] = archive
    for grant in consent.get("grants") or []:
        if isinstance(grant, dict):
            archive.append(grant)
    consent["grants"] = new_grants
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
        if delta.get("trust") is not None:
            current = relation.get("trust") if isinstance(relation.get("trust"), int) else 0
            # 正负整数视为增量并夹到 [-5,5]；绝对值大于 5 视为直接设定（同样夹到 [-5,5]）。
            change = int(delta["trust"])
            new_trust = max(-5, min(5, current + change)) if abs(change) <= 5 else max(-5, min(5, change))
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
        if raw.get("checked_turn_add"):
            checked = list(event.get("checked_turns") or [])
            if turn not in checked:
                checked.append(turn)
            event["checked_turns"] = checked
        touched.discard(target_id)

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


def apply_grants(state: dict[str, Any], additions: list[dict[str, Any]],
                 withdraw_ids: list[str], turn: int) -> None:
    if not additions and not withdraw_ids:
        return
    consent = state["consent"]
    grants = list(consent.get("grants") or [])
    withdraw = list(dict.fromkeys(withdraw_ids or []))
    known_ids = {g.get("id") for g in grants if isinstance(g, dict)}
    unknown = [gid for gid in withdraw if gid not in known_ids]
    if unknown:
        raise CommitError(f"grants_withdraw references unknown grant ids: {unknown}")
    updated = []
    for grant in grants:
        if not isinstance(grant, dict):
            continue
        if grant.get("id") in set(withdraw):
            grant = dict(grant)
            grant["status"] = "withdrawn"
            grant["withdrawn_turn"] = turn
            grant["last_checked_turn"] = turn
            # 换场景规则：当前 grants 只保留当前 scene。撤回后仍属当前 scene，可留着。
        updated.append(grant)
    existing = [g.get("id") for g in updated if isinstance(g, dict)]
    for raw in additions or []:
        if not isinstance(raw, dict):
            continue
        grant = dict(raw)
        grant.setdefault("id", next_id("consent", [str(i) for i in existing if i]))
        grant.setdefault("scene_id", consent.get("scene_id"))
        grant.setdefault("participants", list(consent.get("participants") or []))
        grant.setdefault("status", "granted")
        grant.setdefault("granted_turn", turn)
        grant.setdefault("withdrawn_turn", None)
        grant.setdefault("last_checked_turn", turn)
        if not grant.get("scope"):
            raise CommitError("grant requires scope")
        updated.append(grant)
        existing.append(grant["id"])
    consent["grants"] = updated


def apply_boundaries(state: dict[str, Any], additions: list[Any], revoke_topics: list[str],
                     turn: int) -> None:
    items = list(state.get("boundaries") or [])
    existing_ids = [b.get("id") for b in items if isinstance(b, dict)]
    revoke = set(revoke_topics or [])
    for boundary in items:
        if isinstance(boundary, dict) and boundary.get("topic") in revoke and boundary.get("status") == "active":
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


def apply_patch(state: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
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

    old_clock = parse_clock(world.get("clock"))
    delta_minutes = patch.get("delta_minutes")
    delta_seconds = patch.get("delta_seconds")
    if patch.get("clock"):
        new_clock = parse_clock(patch["clock"])
    elif delta_seconds is not None:
        new_clock = old_clock + dt.timedelta(seconds=int(delta_seconds))
    elif delta_minutes is not None:
        new_clock = old_clock + dt.timedelta(minutes=int(delta_minutes))
    elif advance:
        new_clock = old_clock + dt.timedelta(minutes=5)
    else:
        new_clock = old_clock
    if advance and new_clock <= old_clock:
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
    # 许可的撤回/授予先于换场处理：继承复制读取的是撤回后的最新同意状态，
    # 避免「同补丁内撤回＋换场」把刚收回的许可复活（SKILL.md 许可继承前提「无人撤回」）。
    apply_grants(data, list(patch.get("grants_add") or []), list(patch.get("grants_withdraw") or []), turn)
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
    maybe_full(
        data, turn,
        force=bool(patch.get("force_full")),
        scene_changed=scene_changed_actual or bool(
            patch.get("grants_add") or patch.get("grants_withdraw")
            or patch.get("boundaries_add") or patch.get("boundaries_revoke")
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
    try:
        state = load_yaml(args.state)
        patch = load_patch(args)
        updated = commit(state, patch)
    except (CommitError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    saves = load_saves()
    out = args.out or args.state
    saves.write_atomic(out, saves.yaml_text(updated))
    slice_mod = load_live_slice()
    payload = slice_mod.extract_live_slice(updated)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass
    raise SystemExit(main())
