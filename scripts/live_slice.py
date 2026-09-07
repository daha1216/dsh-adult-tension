#!/usr/bin/env python3
"""从完整 v3 状态抽出运行时活切片 / opening_brief / 人话状态。

普通回合只把本脚本的输出放进上下文，不要重读整份 YAML。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _load(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise SystemExit("ERROR: PyYAML is required; run: python -m pip install PyYAML")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SystemExit(f"ERROR: cannot read {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: state is not a mapping: {path}")
    return data


# 活切片上限：防长线膨胀（pending 按到期/创建排序取前 N，knowledge 保留最新 M 条；
# relationships 全量保留——量小且是关系传播的正式来源）。
PENDING_EVENTS_LIMIT = 10
KNOWLEDGE_LIMIT = 8


def _trim_npc(npc: dict[str, Any]) -> dict[str, Any]:
    situation = npc.get("situation") if isinstance(npc.get("situation"), dict) else {}
    sex = npc.get("sexuality_profile") if isinstance(npc.get("sexuality_profile"), dict) else {}
    identity = npc.get("identity_profile") if isinstance(npc.get("identity_profile"), dict) else {}
    decision = npc.get("decision_card") if isinstance(npc.get("decision_card"), dict) else {}
    return {
        "id": npc.get("id"),
        "name": npc.get("name"),
        "age": npc.get("age"),
        "role_level": npc.get("role_level"),
        "identity": npc.get("identity"),
        "location": npc.get("location"),
        "core_personality": npc.get("core_personality"),
        "pressure_strategy": npc.get("pressure_strategy"),
        "voice_filter": npc.get("voice_filter"),
        "goal": npc.get("goal") or decision.get("goal"),
        "boundary": npc.get("boundary"),
        "withdrawal_signal": npc.get("withdrawal_signal"),
        "emotion": npc.get("emotion"),
        "resources": npc.get("resources") or [],
        "knowledge": (npc.get("knowledge") or [])[-KNOWLEDGE_LIMIT:],
        "recent_memories": (npc.get("recent_memories") or [])[-2:],
        "signature": npc.get("signature"),
        "autonomy": npc.get("autonomy"),
        "active_voice_mode": npc.get("active_voice_mode") or "surface",
        "identity_role": identity.get("role") or npc.get("identity"),
        "identity_behavior": identity.get("behavior") or {},
        "situation_type": situation.get("type"),
        "situation_pressure": situation.get("pressure"),
        "sexuality_baseline": sex.get("baseline"),
    }


def _pending_events(events: Any) -> list[dict[str, Any]]:
    rows: list[tuple[tuple, dict[str, Any]]] = []
    if not isinstance(events, list):
        return []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("status") != "pending":
            continue
        due = event.get("due_at")
        try:
            created = int(event.get("created_turn") or 0)
        except (TypeError, ValueError):
            created = 0
        order = (due is None, str(due or ""), created, str(event.get("id") or ""))
        rows.append((order, {
            "id": event.get("id"),
            "kind": event.get("kind"),
            "trigger": event.get("trigger"),
            "due_at": event.get("due_at"),
            "consequence": event.get("consequence"),
            "hook": event.get("hook"),
            "semantic_key": event.get("semantic_key"),
            "source": event.get("source"),
            "probability": event.get("probability"),
            "last_roll": event.get("last_roll"),
        }))
    rows.sort(key=lambda row: row[0])
    kept = [row[1] for row in rows[:PENDING_EVENTS_LIMIT]]
    omitted = len(rows) - len(kept)
    if omitted > 0:
        kept.append({"summary": f"另有 {omitted} 条未列出"})
    return kept


def extract_live_slice(state: dict[str, Any]) -> dict[str, Any]:
    """运行时活切片：按运行状态速览白名单保留普通回合所需字段。"""
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    world = state.get("world") if isinstance(state.get("world"), dict) else {}
    player = state.get("player") if isinstance(state.get("player"), dict) else {}
    node = state.get("current_node") if isinstance(state.get("current_node"), dict) else {}
    checkpoint = state.get("checkpoint") if isinstance(state.get("checkpoint"), dict) else {}
    participants = set(node.get("participants") or [])
    npcs = []
    for npc in state.get("npcs") or []:
        if not isinstance(npc, dict):
            continue
        if npc.get("id") in participants or npc.get("role_level") == "main":
            npcs.append(_trim_npc(npc))
    boundaries = []
    for boundary in state.get("boundaries") or []:
        if isinstance(boundary, dict) and boundary.get("status") == "active":
            boundaries.append({"id": boundary.get("id"), "topic": boundary.get("topic")})
    return {
        "turn": meta.get("turn"),
        "mode": meta.get("mode"),
        "safety_state": meta.get("safety_state"),
        "power_structure": meta.get("power_structure"),
        "simulation": meta.get("simulation"),
        "voyeur_pov": meta.get("voyeur_pov") or "off",
        "clock": world.get("clock"),
        "delta_t": world.get("delta_t"),
        "delta_human": world.get("delta_human"),
        "setting_shell": world.get("setting_shell"),
        "tension_engines": world.get("tension_engines"),
        # 世界常量不可压缩，切片不截断（状态总结.md 把常量列入禁删清单）。
        "constants": list(world.get("constants") or []),
        "pressure_immediate": (world.get("pressure_seeds") or {}).get("immediate")
        if isinstance(world.get("pressure_seeds"), dict) else None,
        "twist_state": world.get("twist_state"),
        "location": node.get("location"),
        "participants": node.get("participants"),
        "unresolved_action": node.get("unresolved_action"),
        "last_committed_result": node.get("last_committed_result"),
        "natural_next_pressure": node.get("natural_next_pressure"),
        "scene_id": node.get("scene_id"),
        "scene_profile": node.get("scene_profile"),
        "action_category": node.get("action_category"),
        "action_metadata": node.get("action_metadata") or {},
        "node_situation": node.get("situation"),
        "boundaries": boundaries,
        "player": {
            "id": player.get("id"),
            "name": player.get("name"),
            "age": player.get("age"),
            "identity": player.get("identity"),
            "location": player.get("location"),
            "baseline": player.get("baseline"),
            "resources": player.get("resources") or [],
            "knowledge": (player.get("knowledge") or [])[-KNOWLEDGE_LIMIT:],
            "reputation": player.get("reputation"),
            "appellation": player.get("appellation"),
        },
        "npcs": npcs,
        "relationships": state.get("relationships") or [],
        "pending_events": _pending_events(state.get("events")),
        "checkpoint": {
            "last_full_turn": checkpoint.get("last_full_turn"),
            "next_full_turn": checkpoint.get("next_full_turn"),
            "force_full": checkpoint.get("force_full"),
            "changed": checkpoint.get("changed") or [],
        },
    }


def _surface_voice(voice_filter: Any) -> str:
    """取开局简介使用的表层语态；兼容旧版字符串格式。"""
    if isinstance(voice_filter, dict):
        return str(voice_filter.get("surface") or "").strip()
    text = str(voice_filter or "")
    index = text.find("里层")
    if index <= 0:
        return text.strip("。； ")
    text = text[:index].strip("。； ")
    return text.removeprefix("表层语态：").strip()


def opening_brief(state: dict[str, Any]) -> dict[str, Any]:
    slice_ = extract_live_slice(state)
    player = slice_["player"]
    npc = (slice_["npcs"] or [{}])[0]
    shell = slice_.get("setting_shell") or {}
    return {
        "seed_clock": slice_.get("clock"),
        "world": {
            "era": shell.get("type"),
            "place": shell.get("place"),
            "rule": shell.get("rule"),
            "pressure": shell.get("pressure"),
            "engines": slice_.get("tension_engines"),
            "constants": slice_.get("constants"),
        },
        "player": {
            "name": player.get("name"),
            "appellation": player.get("appellation") or player.get("name"),
            "identity": player.get("identity"),
            "why_here": player.get("baseline"),
        },
        "npc": {
            "name": npc.get("name"),
            "identity": npc.get("identity"),
            "stuck_on": (slice_.get("node_situation") or {}).get("unresolved_choice")
            or npc.get("situation_pressure"),
            "surface_voice": _surface_voice(npc.get("voice_filter")),
        },
        "location": slice_.get("location"),
        "unresolved": slice_.get("unresolved_action"),
        "last_beat": slice_.get("last_committed_result"),
        "next_pressure": slice_.get("natural_next_pressure"),
        # 三段式模板（SKILL.md「完整开局」）不消费建议/安全提醒，孤儿键已删。
        "turn": 1,
    }


def opening_brief_compact(state: dict[str, Any]) -> dict[str, Any]:
    """玩家侧最小开局信息；完整 brief 仍供模型后台使用。"""
    brief = opening_brief(state)
    npc = brief["npc"]
    return {
        "scene": f"{brief['world']['era']}·{brief['location']}",
        "pressure": brief["world"]["pressure"],
        "player": brief["player"]["why_here"],
        "npc": f"{npc['name']}（{npc['identity']}）",
        "situation": npc["stuck_on"],
        "action": brief["unresolved"],
        "turn": brief["turn"],
    }


def _presence_names(slice_: dict[str, Any]) -> list[str]:
    """「在场」只列当前场景参与者：player + 参与者集合里的 NPC，不混入离场 main NPC。"""
    player = slice_.get("player") or {}
    name_by_id = {player.get("id"): str(player.get("name") or "你")}
    for npc in slice_.get("npcs") or []:
        if npc.get("id"):
            name_by_id[str(npc["id"])] = str(npc.get("name") or npc["id"])
    names = []
    for participant in slice_.get("participants") or []:
        pid = str(participant)
        if pid == str(player.get("id")):
            names.append(str(player.get("name") or "你"))
        else:
            names.append(name_by_id.get(pid, pid))
    return names or [str(player.get("name") or "你")]


def human_status(state: dict[str, Any]) -> str:
    slice_ = extract_live_slice(state)
    names = _presence_names(slice_)
    paused = "是" if slice_.get("safety_state") == "paused" else "否"
    return "\n".join([
        f"地点：{slice_.get('location') or '未知'}",
        f"在场：{'、'.join(names)}",
        f"暂停：{paused}",
        f"当前压力：{slice_.get('pressure_immediate') or slice_.get('natural_next_pressure') or '无'}",
        "同意：由模型根据当前互动、NPC反应和撤回信号判断",
        f"可接：{slice_.get('unresolved_action') or '停在你能接手处'}",
    ])


def dump(data: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if yaml is None:
        return json.dumps(data, ensure_ascii=False, indent=2)
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("--human", action="store_true", help="状态命令用人话，不暴露字段名")
    parser.add_argument("--brief", action="store_true", help="开局 brief")
    parser.add_argument("--compact", action="store_true", help="最小开局 brief")
    parser.add_argument("--format", choices=("yaml", "json"), default="yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state = _load(args.state)
    if args.human:
        print(human_status(state))
        return 0
    payload: Any
    if args.compact:
        payload = opening_brief_compact(state)
    elif args.brief:
        payload = opening_brief(state)
    else:
        payload = extract_live_slice(state)
    print(dump(payload, args.format), end="" if str(args.format) == "yaml" else "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass
    raise SystemExit(main())
