#!/usr/bin/env python3
"""build_opening.py — 开局编排器：结构骰 → v3 骨架 → opening 校验。

默认开局走 --complete：结构骰 + 1-14 填料 + opening 校验一次做完，
stdout 给出 opening_brief，模型只写四块玩家可见正文。--complete 成功后会
把本局签名追加进临时历史（与 roll_opening 同一份），重复三元组只发
warning 不阻断；本脚本也不替模型生成叙事正文。

用法：
  python scripts/build_opening.py --complete                  # 一次生成可开场状态
  python scripts/build_opening.py --complete --seed 42
  python scripts/build_opening.py --complete --lock 时代=当代都市
  python scripts/build_opening.py --complete --slot 本局
  python scripts/build_opening.py                             # 仅骨架（维护/测试）
  python scripts/build_opening.py --roll-file roll.json --out saves/_opening_42.yaml
  python scripts/build_opening.py --request opens/req.yaml
  python scripts/build_opening.py --check FILE                # 校验已有文件

--complete 失败视为脚本 bug，不得改由模型手填 YAML。
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "saves"
PROTOCOL_VERSION = "opening-roll/v3"
MULTI_SEPARATOR = re.compile(r"[、，,]")


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location(
        "adult_tension_common", Path(__file__).with_name("_common.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load _common.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_COMMON = _load_common()


def load_roll_opening() -> Any:
    return _COMMON.load_sibling("roll_opening")


def load_validator() -> Any:
    return _COMMON.load_sibling("validate_state")


def load_fill_opening() -> Any:
    return _COMMON.load_sibling("fill_opening")


def load_live_slice() -> Any:
    return _COMMON.load_sibling("live_slice")


def load_saves() -> Any:
    return _COMMON.load_sibling("manage_saves")


def parse_pairs(entries: list[str], label: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise argparse.ArgumentTypeError(f"--{label} expects KEY=VALUE, got {entry!r}")
        key, value = (part.strip() for part in entry.split("=", 1))
        if not key or not value:
            raise argparse.ArgumentTypeError(f"--{label} 不允许空字段或空值")
        if key in pairs:
            raise argparse.ArgumentTypeError(f"重复 {label} 字段：{key}")
        pairs[key] = value
    return pairs


def build_roll(seed: int | None, locks: dict[str, str], custom: dict[str, str],
               all_custom: bool, force_table: bool) -> dict[str, Any]:
    roll_mod = load_roll_opening()
    pools = roll_mod.load_pools()
    if all_custom and force_table:
        raise SystemExit("ERROR: --all-custom 与 --force-table 互斥")
    mode = "all_custom" if all_custom else ("force_table" if force_table else "table")
    actual_seed = seed if seed is not None else roll_mod.random.SystemRandom().randrange(0, 2 ** 31)
    return roll_mod.build_roll(pools, actual_seed, mode, locks, custom)


def roll_from_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read roll JSON {path}: {exc}")
    if not isinstance(data, dict) or data.get("protocol_version") != PROTOCOL_VERSION:
        raise SystemExit(f"ERROR: roll JSON 缺少或版本不符（需要 {PROTOCOL_VERSION}）：{path}")
    if not isinstance(data.get("seed"), int) or data["seed"] < 0:
        raise SystemExit(f"ERROR: roll JSON 的 seed 必须是非负整数：{path}")
    return data


def split_multi(value: str) -> list[str]:
    return [part.strip() for part in MULTI_SEPARATOR.split(value) if part.strip()]


def utc_clock() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def build_skeleton(roll: dict[str, Any]) -> dict[str, Any]:
    """从结构骰生成 v3 骨架：结构字段、ID、时钟、事件与 checkpoint 就位，
    内容字段留空/占位，由模型按 1-14 流程填充。开局提交点即回合 1：
    所有 created/approved/last_updated/covered 回合字段统一从 1 起算。"""
    clock = utc_clock()
    engines = split_multi(roll.get("张力引擎", ""))
    if not engines:
        engines = ["", ""]
    return {
        "save_version": 3,
        "meta": {
            "turn": 1,
            "mode": "reliable",
            "tier": 1,
            "simulation": True,
            "safety_state": "running",
            "power_structure": roll.get("权力结构", "equal"),
        },
        "world": {
            "clock": clock,
            "previous_clock": clock,
            "delta_t": 0,
            "delta_human": "",
            "constants": [],
            "tension_engines": engines,
            "setting_shell": {
                "type": roll.get("时代", ""),
                "place": roll.get("地点", ""),
                "rule": roll.get("社会规则", ""),
                "pressure": roll.get("压力来源", ""),
            },
            "pressure_seeds": {
                "immediate": roll.get("压力来源", ""),
                "near_event_id": "evt-002",
                "far_event_id": "evt-003",
            },
        },
        "boundaries": [],
        "consent": {
            "scene_id": "scene-001",
            "location": "",
            "participants": ["player-001", "npc-001"],
            "grants": [],
        },
        "player": {
            "id": "player-001",
            "name": "",
            "age": None,
            "identity": "",
            "location": "",
            "baseline": "",
            "resources": [],
            "knowledge": [],
            "reputation": "",
            "appellation": roll.get("玩家称谓") or "",
        },
        "player_naming_audit": {
            "chosen": "",
            "source": "角色设计.md",
            "approved_turn": 1,
        },
        "npcs": [
            {
                "id": "npc-001",
                "name": "",
                "age": None,
                "role_level": "main",
                "identity": "",
                "location": "",
                "core_personality": "",
                "pressure_strategy": roll.get("压力策略", ""),
                "voice_filter": "",
                "goal": "",
                "boundary": "",
                "withdrawal_signal": "",
                "emotion": "",
                "resources": [],
                "knowledge": [],
                "recent_memories": [],
                "signature": "",
                "autonomy": {"last_turn": None, "recent_turns": [], "cooldown_until": 0},
                "identity_profile": {"role": ""},
                "situation": {"type": roll.get("处境", "")},
                "decision_card": {"goal": ""},
                "sexuality_profile": {"baseline": ""},
                "sexuality_development": {"trend": "stable"},
                "naming_audit": {"chosen": "", "source": "角色设计.md", "approved_turn": 1},
            }
        ],
        "relationships": [
            {
                "source": "player-001",
                "target": "npc-001",
                "type": "",
                "channel": "",
                "trust": 0,
                "last_updated_turn": 1,
                "opening": {"status": True, "covered_turn": 1},
            }
        ],
        "events": [
            {"id": "evt-001", "semantic_key": "", "source": "system:opening", "created_turn": 1,
             "kind": "immediate", "trigger": "", "due_at": None, "status": "pending",
             "consequence": "", "hook": False, "probability": None},
            {"id": "evt-002", "semantic_key": "", "source": "system:opening", "created_turn": 1,
             "kind": "near", "trigger": "", "due_at": None, "status": "pending",
             "consequence": "", "hook": False, "probability": None},
            {"id": "evt-003", "semantic_key": "", "source": "system:opening", "created_turn": 1,
             "kind": "far", "trigger": "", "due_at": None, "status": "pending",
             "consequence": "", "hook": True, "probability": None},
        ],
        "checkpoint": {
            "last_full_turn": 1,
            "changed": [],
            "next_full_turn": 6,
            "force_full": False,
            "force_reason": None,
            "invariants": {"age_verified": True, "player_control_preserved": True},
        },
        "resolved_summary": [],
        "current_node": {
            "scene_id": "scene-001",
            "location": "",
            "participants": ["player-001", "npc-001"],
            "situation": {
                "trigger": "",
                "pressure": roll.get("压力来源", ""),
                "immediate_objective": "",
                "deadline": None,
                "unresolved_choice": "",
                "knowledge_gap": {"player_knows": [], "npc_knows": [], "both_mistake": []},
                "exits": {"available": True, "cost": None, "blocked_by": None},
                "consequence": {"immediate": "", "near_term": ""},
            },
            "last_committed_result": "",
            "unresolved_action": "",
            "natural_next_pressure": "",
        },
    }


def write_atomic(path: Path, text: str) -> None:
    _COMMON.write_atomic(path, text)


def load_yaml_module() -> Any:
    try:
        return _COMMON.load_yaml_module()
    except _COMMON.CommonError as exc:  # pragma: no cover
        raise SystemExit(f"ERROR: {exc}") from exc


def dump_yaml(data: dict[str, Any]) -> str:
    return _COMMON.yaml_text(data)


def resolve_roll(args: argparse.Namespace) -> dict[str, Any]:
    if args.roll_file is not None:
        return roll_from_file(args.roll_file)
    locks = parse_pairs(args.lock, "lock")
    custom = parse_pairs(args.custom, "custom")
    return build_roll(args.seed, locks, custom, args.all_custom, args.force_table)


def complete_opening(args: argparse.Namespace) -> int:
    print("正在抽这一局的世界…")
    roll_mod = load_roll_opening()
    try:
        roll = resolve_roll(args)
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            return 1
        if exc.code not in (None, 0):
            return int(exc.code) if isinstance(exc.code, int) else 1
        raise
    except (roll_mod.AnchorError, argparse.ArgumentTypeError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    seed = roll["seed"]
    print("正在写人物…")
    fill_mod = load_fill_opening()
    try:
        filled = fill_mod.fill_opening(build_skeleton(roll), roll)
    except fill_mod.FillError as exc:
        print(f"ERROR: opening fill failed: {exc}", file=sys.stderr)
        return 1
    print("正在核对能否开场…")
    validator = load_validator()
    errors = validator.validate_data(filled, "opening")
    if errors:
        print("ERROR: --complete 未通过 opening 校验（填料 bug，不要改由模型手填）：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    text = dump_yaml(filled)
    # 近期结构去重（SKILL.md：连续局重复三元组只 warning 不阻断）。
    try:
        signature = roll_mod._roll_signature(roll)
        triple = roll_mod._roll_triple(roll)
        if signature in roll_mod.recent_signatures() or triple in roll_mod.recent_triples():
            print("warning: 本局「时代×地点×张力引擎」或完整结构与近期开局重复（不阻断）",
                  file=sys.stderr)
        roll_mod.append_history(roll)
    except Exception as exc:  # noqa: BLE001 - 历史是辅助机制，失败不影响开局
        print(f"warning: roll 历史记录不可用：{exc}", file=sys.stderr)
    out = args.out or (DEFAULT_OUT_DIR / f"_opening_{seed}.yaml")
    if out.exists() and not args.force:
        print(f"ERROR: 输出已存在，不覆盖（换 seed、指定 --out 或加 --force）：{out}", file=sys.stderr)
        return 1
    write_atomic(out, text)
    if args.no_working:
        working = None
    elif args.working is not None:
        working = args.working
    elif args.out is None:
        working = DEFAULT_OUT_DIR / "current_state.yaml"
    else:
        working = None
    if working is not None:
        write_atomic(working, text)

    slot_info = None
    if args.slot:
        saves = load_saves()
        store = saves.SaveStore(DEFAULT_OUT_DIR)
        try:
            slot_info = store.init_slot(args.slot, out)
        except saves.SaveError as exc:
            print(f"WARNING: 槽位未写入（状态文件已生成）：{exc}", file=sys.stderr)

    if args.request is not None:
        request_locks = parse_pairs(args.lock, "lock") if args.lock else {}
        request_custom = parse_pairs(args.custom, "custom") if args.custom else {}
        request = {
            "seed": seed,
            "protocol_version": PROTOCOL_VERSION,
            "mode": roll.get("mode", "table"),
            "locks": request_locks,
            "custom": request_custom,
            "history_used": False,
            "state": str(out),
            "validation": {"passed": True, "checked_at": utc_clock()},
        }
        write_atomic(args.request, dump_yaml(request))

    live = load_live_slice()
    suggestions = fill_mod.opening_suggestions(filled, roll)
    brief = live.opening_brief(filled, suggestions)
    brief["state_path"] = str(working or out)
    brief["archive_path"] = str(out)
    if slot_info:
        brief["slot"] = slot_info.get("slot")
    print("---opening_brief---")
    print(dump_yaml(brief), end="")
    print("---end---")
    return 0


def check_file(path: Path) -> int:
    yaml = load_yaml_module()
    validator = load_validator()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"ERROR: cannot read YAML {path}: {exc}", file=sys.stderr)
        return 2
    errors = validator.validate_data(data, "opening")
    if not errors:
        print(f"OK: opening invariants validated ({path})")
        return 0
    print(f"未通过 opening 校验（{path}）。以下为待填/待修项，全部消除后方可进入正文：")
    for error in errors:
        print(f"- {error}")
    return 1


def _nonneg_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be an integer, got {text!r}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=_nonneg_int, default=None, help="非负整数 seed")
    parser.add_argument("--lock", action="append", default=[], metavar="KEY=VALUE",
                        help="预锁字段，可重复（如 --lock 时代=当代都市；张力引擎支持 A 或 A、B）")
    parser.add_argument("--custom", action="append", default=[], metavar="KEY=VALUE",
                        help="表外自定义值，仅与 --all-custom 一起使用")
    parser.add_argument("--all-custom", action="store_true", help="表外全随机模式")
    parser.add_argument("--force-table", action="store_true", help="强制表内模式")
    parser.add_argument("--roll-file", type=Path, default=None,
                        help="复用已有 roll JSON（roll_opening.py --format json 输出）")
    parser.add_argument("--out", type=Path, default=None, help="骨架输出路径（默认 saves/_opening_<seed>.yaml）")
    parser.add_argument("--request", type=Path, default=None,
                        help="顺带输出 opening_request YAML（seed/协议/模式/锁/校验状态）")
    parser.add_argument("--check", type=Path, default=None, metavar="FILE",
                        help="校验已生成骨架/填充文件并列出待填项")
    parser.add_argument("--complete", action="store_true",
                        help="一次生成可通过 opening 校验的完整开局，并打印 opening_brief")
    parser.add_argument("--working", type=Path, default=None,
                        help="额外写入的当前活档（默认 saves/current_state.yaml）")
    parser.add_argument("--no-working", action="store_true", help="不写 current_state.yaml")
    parser.add_argument("--slot", default=None, help="可选：初始化命名存档槽")
    parser.add_argument("--force", action="store_true", help="允许覆盖 --out 已存在文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check is not None:
        return check_file(args.check)
    if args.complete:
        return complete_opening(args)

    try:
        roll = resolve_roll(args)
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            return 1
        if exc.code not in (None, 0):
            return int(exc.code) if isinstance(exc.code, int) else 1
        raise
    except (argparse.ArgumentTypeError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    roll_mod = load_roll_opening()
    try:
        seed = int(roll["seed"])
    except (KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: roll JSON 的 seed 缺失或非法：{exc}", file=sys.stderr)
        return 1
    if seed < 0:
        print("ERROR: --seed 必须是非负整数", file=sys.stderr)
        return 1

    skeleton = build_skeleton(roll)
    yaml = load_yaml_module()
    text = yaml.safe_dump(skeleton, allow_unicode=True, sort_keys=False, default_flow_style=False)

    out = args.out or (DEFAULT_OUT_DIR / f"_opening_{seed}.yaml")
    if out.exists():
        print(f"ERROR: 输出已存在，不覆盖（换 seed 或指定 --out）：{out}", file=sys.stderr)
        return 1
    write_atomic(out, text)
    print(f"骨架已写入：{out}")
    print(f"seed: {seed}  模式: {roll.get('mode', 'table')}")
    print("仅限维护/测试路径（生产开局必须走 --complete，见 SKILL.md）：")
    print("按 references/开局流程.md 填充内容字段，然后运行")
    print(f"  python scripts/build_opening.py --check {out}")
    print("全部待填项消除后，本骨架才可用于维护自检。")

    if args.request is not None:
        request_locks = parse_pairs(args.lock, "lock") if args.lock else {}
        request_custom = parse_pairs(args.custom, "custom") if args.custom else {}
        request = {
            "seed": seed,
            "protocol_version": PROTOCOL_VERSION,
            "mode": roll.get("mode", "table"),
            "locks": request_locks,
            "custom": request_custom,
            "history_used": False,
            "skeleton": str(out),
            "validation": {"passed": False, "checked_at": utc_clock()},
        }
        write_atomic(args.request, yaml.safe_dump(request, allow_unicode=True, sort_keys=False, default_flow_style=False))
        print(f"opening_request 已写入：{args.request}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass
    raise SystemExit(main())
