#!/usr/bin/env python3
"""build_opening.py — 开局编排器：结构骰 → v3 骨架 → opening 校验。

把「完整开局」中可程序化推导的部分脚本化，模型只需填充内容字段、
跑 --check 直到通过，再进入正文。本脚本不写 roll 历史签名（避免污染
近期去重辅助），也不替模型生成叙事内容。

用法：
  python scripts/build_opening.py                             # 系统熵 roll，生成骨架
  python scripts/build_opening.py --seed 42                   # 确定性 roll
  python scripts/build_opening.py --lock 时代=当代都市        # 透传预锁（可重复）
  python scripts/build_opening.py --all-custom --custom 时代=X # 表外自定义
  python scripts/build_opening.py --roll-file roll.json       # 复用已有 roll JSON
  python scripts/build_opening.py --out saves/_opening_42.yaml
  python scripts/build_opening.py --request opens/req.yaml    # 顺带输出 opening_request
  python scripts/build_opening.py --check FILE                # 校验文件并列出待填/待修项

--check 输出即填充清单：exit 0 表示通过 opening profile 校验，
exit 1 表示仍有未填/非法字段（不进入正文）。
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


def _load_module(script: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_roll_opening() -> Any:
    return _load_module(Path(__file__).with_name("roll_opening.py"), "adult_tension_roll_opening")


def load_validator() -> Any:
    return _load_module(Path(__file__).with_name("validate_state.py"), "adult_tension_validate_state")


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
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def load_yaml_module() -> Any:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("ERROR: PyYAML is required; run: python -m pip install PyYAML") from exc
    return yaml


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=None, help="非负整数 seed")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check is not None:
        return check_file(args.check)

    if args.roll_file is not None:
        roll = roll_from_file(args.roll_file)
    else:
        locks = parse_pairs(args.lock, "lock")
        custom = parse_pairs(args.custom, "custom")
        roll = build_roll(args.seed, locks, custom, args.all_custom, args.force_table)
    seed = roll["seed"]

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
    print("下一步：按 references/开局流程.md 填充内容字段，然后反复运行")
    print(f"  python scripts/build_opening.py --check {out}")
    print("直到 exit 0 再进入正文。")

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
