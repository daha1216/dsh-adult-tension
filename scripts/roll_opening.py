#!/usr/bin/env python3
"""roll_opening.py — 沉浸叙事引擎的开局结构骰与中期转折抽取。

本脚本实时解析 references/角色设计.md、references/素材库.md 与
references/世界运转.md 中的锚点小节；锚点改名、清空或格式破坏会使脚本报错，
这正是维护契约要求的自检能力（见各文档内的维护契约注释）。

用法：
  python scripts/roll_opening.py                     # 完整结构骰（系统熵 seed）
  python scripts/roll_opening.py --seed 42           # 确定性完整结构骰
  python scripts/roll_opening.py --seed 1 --no-history   # 维护自检（不写历史）
  python scripts/roll_opening.py --twist             # 2-3 个中期转折方向
  python scripts/roll_opening.py --all-custom        # 表外模式：允许自定义的核心字段标记为待补齐
  python scripts/roll_opening.py --force-table       # 强制表内模式
  python scripts/roll_opening.py --lock 时代=当代都市 --lock 地点=写字楼
  python scripts/roll_opening.py --format json       # JSON 输出
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
CHAR_DOC = REFERENCES / "角色设计.md"
MATERIAL_DOC = REFERENCES / "素材库.md"
WORLD_DOC = REFERENCES / "世界运转.md"
HISTORY_FILE = "adult_tension_narrative_roll_history.jsonl"
HISTORY_RETRY_LIMIT = 32
PROTOCOL_VERSION = "opening-roll/v3"
# This is the compatibility contract: changing order requires a protocol bump.
DRAW_PLAN = (
    "美学基调", "核心规则", "权力结构", "张力引擎", "时代", "地点",
    "社会规则", "压力来源", "场景动作", "身份族", "处境", "核心价值",
    "压力策略", "关系姿态", "反差轴", "表层风味", "口癖", "外观·主NPC",
    "外观·配角", "生成倾向", "配角功能", "亲密画像核心子集",
    "场景动作·对照", "玩家称谓", "玩家年龄段", "玩家社会位置",
)
LEVERAGE_ENGINES = {"债务压力", "秘密暴露倒计时", "第三方施压"}
SITUATION_LEVERAGE = {"债务压身", "秘密将破", "时限临门"}
IDENTITY_WEIGHTS = {
    "侍奉与身契": 7,
    "成人行业与感官服务": 7,
    "私密撮合与契约中介": 6,
    "权力与治理": 5,
    "商业与产业": 5,
    "学术与专业": 8,
    "秩序与执法": 6,
    "艺术与传播": 12,
    "医疗与照护": 12,
    "地下与灰色地带": 7,
    "家族与继承": 12,
    "服务与手艺": 13,
}
GOLDEN_MAPPING = {"protocol_version": PROTOCOL_VERSION, "seed": 7}

GATE_AESTHETICS = {"青年漫写实", "写实文学"}
CUSTOM_KEYS = {
    "核心规则", "张力引擎", "时代", "地点", "社会规则", "压力来源",
    "场景动作", "身份族", "处境", "核心价值", "压力策略", "关系姿态",
}
LOCKABLE_KEYS = set(CUSTOM_KEYS) | {
    "美学基调", "权力结构", "反差轴", "配角功能",
    "玩家称谓", "玩家年龄段", "玩家社会位置",
}
# 多值字段：lock/custom 值允许顿号或逗号分隔多项，每项必须来自对应解析池；
# 少于规定数量时自动从池中补抽，保证最终数量与互不相同（如张力引擎恒为两项）。
MULTI_LOCK_KEYS = {"张力引擎"}
MULTI_SEPARATOR = re.compile(r"[、，,]")
MODE_LABELS = {"table": "表内", "all_custom": "表外全随机", "force_table": "强制表内"}
POWER_STRUCTURES = {"player_high", "npc_high", "equal", "switchable"}
TWIST_CATEGORIES = ("信息类", "人事类", "资源类", "制度类", "时限类", "关系类", "意外类")

DEFAULT_WEIGHTS = {
    "ordinary_natural": 35,
    "reserved_sensitive": 15,
    "inexperienced": 12,
    "experienced_restrained": 10,
    "open_active": 8,
    "playful": 8,
    "conflicted": 7,
    "low_desire": 5,
}

INTENSITY = ["low", "medium", "high"]
AWARENESS = ["unaware", "uncertain", "clear"]
INITIATIVE = ["follow", "responsive", "lead", "switch"]
PACE = ["gradual", "adaptive", "direct"]
STYLE = ["tender", "natural", "playful", "intense", "experimental", "mixed"]
DIRECTNESS = ["reserved", "natural", "direct", "uninhibited"]
SELF_CONTROL = ["stable", "variable", "poor"]
INTEREST_ORIGIN = ["stable", "contextual", "unexplored", "defensive", "target_specific"]


class AnchorError(Exception):
    """锚点缺失、清空或格式违反维护契约。"""


def split_items(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[、，,]", text) if part.strip()]


def read_doc(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _heading_level(line: str) -> int:
    match = re.match(r"^(#+)\s", line)
    return len(match.group(1)) if match else 0


def section(title: str, text: str) -> list[str]:
    """返回标题之后、下一个同级或更高级标题之前的行。"""
    lines = text.splitlines()
    title_level = _heading_level(title)
    start = None
    for index, line in enumerate(lines):
        if line.strip() == title:
            start = index
            break
    if start is None:
        raise AnchorError(f"缺失锚点小节：{title}")
    body: list[str] = []
    for line in lines[start + 1:]:
        level = _heading_level(line)
        if level and level <= title_level:
            break
        body.append(line)
    return body


def _grouped(lines: list[str]) -> dict[str, list[str]]:
    """解析 `- 组名：项、项` 分组行。"""
    groups: dict[str, list[str]] = {}
    for line in lines:
        match = re.match(r"^\s*-\s*([^：:]+)[：:]\s*(.+)$", line)
        if not match:
            continue
        name = match.group(1).strip()
        groups.setdefault(name, []).extend(split_items(match.group(2)))
    return groups


def _union_pool(lines: list[str], *, name: str, max_len: int | None = None) -> list[str]:
    pool: list[str] = []
    for items in _grouped(lines).values():
        for item in items:
            if max_len is not None and len(item) > max_len:
                continue
            if item not in pool:
                pool.append(item)
    if not pool:
        raise AnchorError(f"{name} 池为空（检查锚点与 `- 组名：项、项` 格式）")
    return pool


def _appearance_pool(lines: list[str]) -> dict[str, dict[str, list[str]]]:
    axes: dict[str, dict[str, list[str]]] = {}
    current: str | None = None
    for line in lines:
        stripped = line.strip()
        top = re.match(r"^- ([^：:]+)$", stripped)
        group = re.match(r"^\s{2,}- ([^：:]+)[：:]\s*(.+)$", line)
        if top:
            current = top.group(1).strip()
            axes[current] = {}
        elif group and current:
            axes[current].setdefault(group.group(1).strip(), []).extend(
                split_items(group.group(2)))
        elif re.match(r"^-", stripped):
            raise AnchorError(f"外观与气质轴子轴格式违反维护契约：{stripped!r}")
    if not axes:
        raise AnchorError("外观与气质轴池为空（检查子轴与两空格缩进分组行）")
    return axes


def _decision_axes(lines: list[str]) -> dict[str, list[str]]:
    groups = _grouped(lines)
    for name in ("核心价值", "压力策略", "关系姿态"):
        if name not in groups or len(groups[name]) < 2:
            raise AnchorError(f"人物决策轴缺少合格轴 {name}（需 `- 轴名：项、项` 且至少两项）")
    return groups


def _weights(lines: list[str]) -> dict[str, int]:
    parsed: dict[str, int] = {}
    inside = False
    saw_content = False
    for line in lines:
        stripped = line.strip()
        if not inside:
            if stripped in {"```yaml", "```yml"}:
                inside = True
            continue
        if stripped == "```":
            break
        if stripped and not stripped.startswith("#"):
            if re.match(r"^[A-Za-z_]+:\s*$", stripped):
                continue
            saw_content = True
            match = re.match(r"^\s{2}([A-Za-z_]+):\s*(\d+)\s*$", line)
            if not match:
                raise AnchorError(f"人物生成倾向权重格式损坏：{line.strip()!r}")
            parsed[match.group(1)] = int(match.group(2))
    if not saw_content:
        raise AnchorError("人物生成倾向权重代码块为空")
    missing = set(DEFAULT_WEIGHTS) - set(parsed)
    extra = set(parsed) - set(DEFAULT_WEIGHTS)
    if missing or extra or any(value <= 0 for value in parsed.values()):
        raise AnchorError(f"人物生成倾向权重键缺失或数值非法：missing={sorted(missing)}, extra={sorted(extra)}")
    if sum(parsed.values()) != 100:
        raise AnchorError(f"人物生成倾向权重总和必须为 100，实际为 {sum(parsed.values())}")
    return parsed


def _supporting_functions(lines: list[str]) -> list[str]:
    for line in lines:
        if line.strip().startswith("配角功能独立生成") and line.strip().endswith("。"):
            match = re.search(r"生成[：:]\s*(.*?)。", line)
            if match:
                return split_items(match.group(1))
    raise AnchorError("「配角功能独立生成：…。」句式缺失或已改动")


def _twist_pool(lines: list[str]) -> dict[str, list[str]]:
    pools: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        heading = re.match(r"^###\s+(.+)$", line)
        if heading:
            current = heading.group(1).strip()
            pools[current] = []
            continue
        if current is None:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "硬规则：" or re.match(r"^\d+\.\s", stripped):
            break
        pools[current].extend(split_items(line))
    if tuple(pools) != TWIST_CATEGORIES:
        raise AnchorError(f"中期剧情转折池必须严格包含七类：{TWIST_CATEGORIES}")
    if any(not items for items in pools.values()):
        raise AnchorError("中期剧情转折池存在空类（检查七个「### X类」小节）")
    return pools


def load_pools() -> dict[str, Any]:
    char_text = read_doc(CHAR_DOC)
    material_text = read_doc(MATERIAL_DOC)
    world_text = read_doc(WORLD_DOC)

    pools: dict[str, Any] = {}
    pools["表层风味"] = _union_pool(section("### 表层风味", char_text), name="表层风味", max_len=8)
    pools["口癖"] = _union_pool(section("### 口癖与语感", char_text), name="口癖", max_len=8)
    pools["外观轴"] = _appearance_pool(section("### 外观与气质轴", char_text))
    pools["决策轴"] = _decision_axes(section("## 人物决策轴", char_text))
    pools["人物生成倾向"] = _weights(section("## 人物生成原则", char_text))
    pools["配角功能"] = _supporting_functions(section("## 配角", char_text))
    if not pools["配角功能"]:
        raise AnchorError("配角功能池为空")

    pools["核心规则"] = _union_pool(section("## 核心规则", material_text), name="核心规则")
    pools["美学基调"] = _union_pool(section("## 美学基调", material_text), name="美学基调")
    pools["权力结构"] = _union_pool(section("## 权力结构", material_text), name="权力结构")
    pools["张力引擎"] = _union_pool(section("## 张力引擎", material_text), name="张力引擎")
    era_place = _grouped(section("## 时代与地点", material_text))
    if not era_place.get("时代") or not era_place.get("地点"):
        raise AnchorError("「时代与地点」缺少「时代」或「地点」分组")
    pools["时代与地点"] = era_place
    pools["社会规则"] = _union_pool(section("## 社会规则", material_text), name="社会规则")
    pools["压力来源"] = _union_pool(section("## 压力来源", material_text), name="压力来源")
    scene_groups = _grouped(section("## 场景动作", material_text))
    if not scene_groups.get("交易摊牌") or not scene_groups.get("非交易靠近"):
        raise AnchorError("「场景动作」缺少「交易摊牌」或「非交易靠近」分组")
    pools["场景动作·交易"] = list(dict.fromkeys(scene_groups["交易摊牌"]))
    pools["场景动作·靠近"] = list(dict.fromkeys(scene_groups["非交易靠近"]))
    pools["场景动作"] = list(dict.fromkeys(pools["场景动作·交易"] + pools["场景动作·靠近"]))
    pools["身份侧"] = _union_pool(section("## 身份侧", material_text), name="身份侧")
    pools["处境侧"] = _union_pool(section("## 处境侧", material_text), name="处境侧")
    pools["反差轴"] = _union_pool(section("## 反差轴", material_text), name="反差轴")
    player_axes = _grouped(section("## 玩家化身轴", material_text))
    for axis in ("称谓", "年龄段", "社会位置"):
        if not player_axes.get(axis):
            raise AnchorError(f"「玩家化身轴」缺少「{axis}」分组")
    pools["玩家化身轴"] = {key: list(dict.fromkeys(items)) for key, items in player_axes.items()}

    pools["转折池"] = _twist_pool(section("## 中期剧情转折", world_text))
    if not set(pools["权力结构"]).issubset(POWER_STRUCTURES):
        raise AnchorError("权力结构条目与 validate_state 枚举不一致")
    return pools


def _realistic(axis: str, group: str, item: str) -> bool:
    if axis == "发色":
        return group == "自然发色"
    if axis == "瞳与面部" and group == "瞳色":
        return item != "异色瞳"
    return True


def _appearance_items(pools: dict[str, Any], gate: bool) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for axis, groups in pools["外观轴"].items():
        for group, items in groups.items():
            for item in items:
                if gate and not _realistic(axis, group, item):
                    continue
                entries.append({"axis": axis, "group": group, "item": item})
    return entries


def _draw_distinct(rng: random.Random, entries: list[dict[str, str]],
                   count: int) -> list[dict[str, str]]:
    picks: list[dict[str, str]] = []
    pool = list(entries)
    for _ in range(count):
        if not pool:
            break
        pick = rng.choice(pool)
        picks.append(pick)
        pool = [entry for entry in pool if entry != pick]
    return picks


def _weighted_choice(rng: random.Random, items: list[str], weights: dict[str, int]) -> str:
    values = [max(1, int(weights.get(item, 8))) for item in items]
    return rng.choices(items, weights=values, k=1)[0]


def _combine_multi(key: str, raw: str, pool: list[str], count: int,
                   rng: random.Random) -> str:
    """把多值字段（如张力引擎）的 lock/custom 值规范化为恰好 count 项。

    - 值按顿号/逗号拆分；
    - 超过 count 项或含重复项报错；
    - 少于 count 项时，从池中排除已锁定项后补抽到 count，保证互不相同。
    """
    items = [part.strip() for part in MULTI_SEPARATOR.split(raw) if part.strip()]
    if not items:
        raise AnchorError(f"{key} 的值不能为空：{raw!r}")
    if len(items) > count:
        raise AnchorError(f"{key} 最多 {count} 项，收到 {len(items)} 项")
    if len(set(items)) != len(items):
        raise AnchorError(f"{key} 的取值不能重复：{raw!r}")
    if len(items) == count:
        return "、".join(items)
    remaining = [item for item in pool if item not in items]
    picks = items + rng.sample(remaining, count - len(items))
    return "、".join(picks)


def build_roll(pools: dict[str, Any], seed: int, mode: str = "table",
               locks: dict[str, str] | None = None,
               custom: dict[str, str] | None = None) -> dict[str, Any]:
    """按 protocol_version/DRAW_PLAN 固定消费顺序生成结构骰。"""
    locks = dict(locks or {})
    custom = dict(custom or {})
    if mode not in MODE_LABELS:
        raise AnchorError(f"未知模式：{mode}")
    unknown = set(locks) - LOCKABLE_KEYS
    if unknown:
        raise AnchorError(f"未知 lock 字段：{sorted(unknown)}")
    if any(not key or not value.strip() for key, value in locks.items()):
        raise AnchorError("lock 字段和值不能为空")
    if custom and mode != "all_custom":
        raise AnchorError("--custom 仅可与 --all-custom 一起使用")
    if set(custom) - CUSTOM_KEYS:
        raise AnchorError(f"--custom 包含不可自拟字段：{sorted(set(custom) - CUSTOM_KEYS)}")
    valid_lock_values = {
        "美学基调": pools["美学基调"],
        "核心规则": pools["核心规则"],
        "权力结构": pools["权力结构"],
        "张力引擎": pools["张力引擎"],
        "时代": pools["时代与地点"]["时代"],
        "地点": pools["时代与地点"]["地点"],
        "社会规则": pools["社会规则"],
        "压力来源": pools["压力来源"],
        "场景动作": pools["场景动作"],
        "身份族": pools["身份侧"],
        "处境": pools["处境侧"],
        "核心价值": pools["决策轴"]["核心价值"],
        "压力策略": pools["决策轴"]["压力策略"],
        "关系姿态": pools["决策轴"]["关系姿态"],
        "反差轴": pools["反差轴"],
        "配角功能": pools["配角功能"],
        "玩家称谓": pools["玩家化身轴"]["称谓"],
        "玩家年龄段": pools["玩家化身轴"]["年龄段"],
        "玩家社会位置": pools["玩家化身轴"]["社会位置"],
    }
    if mode in {"table", "force_table"}:
        for key, value in locks.items():
            if key in MULTI_LOCK_KEYS:
                parts = [part.strip() for part in MULTI_SEPARATOR.split(value) if part.strip()]
                if not parts:
                    raise AnchorError(f"lock 字段 {key} 的值不能为空：{value!r}")
                for part in parts:
                    if part not in valid_lock_values[key]:
                        raise AnchorError(f"lock 值不在解析后的 {key} 表内：{part!r}")
            elif value not in valid_lock_values[key]:
                raise AnchorError(f"lock 值不在解析后的 {key} 表内：{value!r}")
    rng = random.Random(seed)
    roll: dict[str, Any] = {"protocol_version": PROTOCOL_VERSION, "seed": seed, "mode": mode}

    def draw(key: str, pool: list[str]) -> None:
        if key in locks:
            roll[key] = locks[key]
            return
        if mode == "all_custom" and key in CUSTOM_KEYS:
            roll[key] = custom.get(key, "custom_required")
            return
        roll[key] = rng.choice(pool)

    def draw_many(key: str, pool: list[str], count: int) -> None:
        if key in locks:
            roll[key] = _combine_multi(key, locks[key], pool, count, rng)
            return
        if mode == "all_custom" and key in CUSTOM_KEYS:
            raw = custom.get(key, "custom_required")
            if raw == "custom_required":
                roll[key] = raw
            else:
                roll[key] = _combine_multi(key, raw, pool, count, rng)
            return
        picks = rng.sample(pool, min(count, len(pool)))
        roll[key] = "、".join(picks)

    draw("美学基调", pools["美学基调"])
    draw("核心规则", pools["核心规则"])
    draw("权力结构", pools["权力结构"])
    draw_many("张力引擎", pools["张力引擎"], 2)
    draw("时代", pools["时代与地点"]["时代"])
    draw("地点", pools["时代与地点"]["地点"])
    draw("社会规则", pools["社会规则"])
    draw("压力来源", pools["压力来源"])
    if "场景动作" in locks or (mode == "all_custom" and "场景动作" in CUSTOM_KEYS):
        draw("场景动作", pools["场景动作"])
    else:
        roll["场景动作"] = rng.choice(pools["场景动作·靠近"])
    if "身份族" in locks or (mode == "all_custom" and "身份族" in CUSTOM_KEYS):
        draw("身份族", pools["身份侧"])
    else:
        roll["身份族"] = _weighted_choice(rng, pools["身份侧"], IDENTITY_WEIGHTS)
    draw("处境", pools["处境侧"])
    draw("核心价值", pools["决策轴"]["核心价值"])
    draw("压力策略", pools["决策轴"]["压力策略"])
    draw("关系姿态", pools["决策轴"]["关系姿态"])
    draw("反差轴", pools["反差轴"])

    if roll["权力结构"] not in POWER_STRUCTURES:
        raise AnchorError(f"权力结构值不在枚举中：{roll['权力结构']!r}")
    if "张力引擎" not in locks and not (
            mode == "all_custom" and roll.get("张力引擎") == "custom_required"):
        engines = [part.strip() for part in MULTI_SEPARATOR.split(str(roll.get("张力引擎", ""))) if part.strip()]
        if len(engines) >= 2 and set(engines) <= LEVERAGE_ENGINES:
            remaining = [item for item in pools["张力引擎"] if item not in engines and item not in LEVERAGE_ENGINES]
            if not remaining:
                remaining = [item for item in pools["张力引擎"] if item not in engines]
            if remaining:
                engines[1] = rng.choice(remaining)
                roll["张力引擎"] = "、".join(engines)
    if "处境" not in locks and not (
            mode == "all_custom" and roll.get("处境") == "custom_required"):
        if roll.get("权力结构") == "player_high" and roll.get("处境") in SITUATION_LEVERAGE:
            remaining = [item for item in pools["处境侧"] if item not in SITUATION_LEVERAGE]
            if remaining:
                roll["处境"] = rng.choice(remaining)
    trade_pool = [item for item in pools["场景动作·交易"] if item != roll.get("场景动作")]
    if trade_pool:
        roll["场景动作·对照"] = rng.choice(trade_pool)
    else:
        roll["场景动作·对照"] = rng.choice(pools["场景动作·交易"]) if pools["场景动作·交易"] else "—"
    gate = roll["美学基调"] in GATE_AESTHETICS
    if gate:
        roll["表层风味"] = "—"
        roll["口癖"] = "—"
    else:
        draw("表层风味", pools["表层风味"])
        draw("口癖", pools["口癖"])

    appearance = _appearance_items(pools, gate)
    main_picks = _draw_distinct(rng, appearance, 2)
    rest = [entry for entry in appearance if entry not in main_picks]
    support_picks = _draw_distinct(rng, rest, 1)
    roll["外观·主NPC"] = main_picks
    roll["外观·配角"] = support_picks

    weights = pools["人物生成倾向"]
    tendency = rng.choices(list(weights), weights=list(weights.values()), k=1)[0]
    roll["生成倾向"] = f"{tendency}（权重 {weights[tendency]}）"
    draw("配角功能", pools["配角功能"])

    roll["亲密画像核心子集"] = {
        "drive.intensity": rng.choice(INTENSITY),
        "drive.awareness": rng.choice(AWARENESS),
        "attraction.orientation": "unspecified（自拟）",
        "preferences.initiative": rng.choice(INITIATIVE),
        "preferences.pace": rng.choice(PACE),
        "preferences.style": rng.choice(STYLE),
        "expression.directness": rng.choice(DIRECTNESS),
        "regulation.self_control": rng.choice(SELF_CONTROL),
        "interest_origin.type": rng.choice(INTEREST_ORIGIN),
    }
    draw("玩家称谓", pools["玩家化身轴"]["称谓"])
    draw("玩家年龄段", pools["玩家化身轴"]["年龄段"])
    draw("玩家社会位置", pools["玩家化身轴"]["社会位置"])
    roll["开局约束"] = "权力结构不自动等于把柄；处境不得推导同意；未决动作须落在非交易靠近"
    return roll


def draw_twists(pools: dict[str, Any], seed: int) -> list[tuple[str, str]]:
    if tuple(pools["转折池"]) != TWIST_CATEGORIES:
        raise AnchorError("中期剧情转折池类别不符合严格七类契约")
    rng = random.Random(seed)
    entries = [(category, item)
               for category, items in pools["转折池"].items() for item in items]
    count = min(rng.choice([2, 3]), len(entries))
    return rng.sample(entries, count)


def _roll_signature(roll: dict[str, Any]) -> str:
    payload = {key: roll.get(key) for key in DRAW_PLAN}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _roll_triple(roll: dict[str, Any]) -> str:
    return f"{roll.get('时代')}|{roll.get('地点')}|{roll.get('张力引擎')}"


def history_path() -> Path:
    return Path(tempfile.gettempdir()) / HISTORY_FILE


def recent_signatures(limit: int = 20) -> set[str]:
    path = history_path()
    if not path.exists():
        return set()
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("signature"):
                records.append(record)
    except OSError as exc:
        print(f"warning: could not read roll history: {exc}", file=sys.stderr)
    return {record["signature"] for record in records}


def recent_triples(limit: int = 20) -> set[str]:
    path = history_path()
    if not path.exists():
        return set()
    triples: set[str] = set()
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("triple"):
                triples.add(record["triple"])
    except OSError as exc:
        print(f"warning: could not read roll history: {exc}", file=sys.stderr)
    return triples


def append_history(roll: dict[str, Any]) -> None:
    try:
        record = {
            "protocol_version": PROTOCOL_VERSION,
            "seed": roll["seed"],
            "mode": roll["mode"],
            "signature": _roll_signature(roll),
            "triple": _roll_triple(roll),
            "at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        with history_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # 历史只用于近期去重辅助，写失败不阻断开局
        print(f"warning: could not record roll history: {exc}", file=sys.stderr)


def print_roll(roll: dict[str, Any]) -> None:
    print(f"seed: {roll['seed']}")
    print(f"模式: {MODE_LABELS.get(roll['mode'], roll['mode'])}")
    for key, value in roll.items():
        if key in ("seed", "mode"):
            continue
        if isinstance(value, dict):
            print(f"{key}:")
            for sub, sub_value in value.items():
                print(f"  {sub}: {sub_value}")
        elif isinstance(value, list):
            names = "、".join(entry["item"] for entry in value)
            print(f"{key}: {names}")
        else:
            print(f"{key}: {value}")
    print("提示：结构骰只用于后台生成，正文不得暴露字段名或骰子结果。")
    if roll["mode"] == "force_table":
        print("强制表内：具体身份须由身份族条目推导，不得自拟。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None,
                        help="非负整数 seed；缺省用系统熵，实际 seed 显示在输出首行")
    parser.add_argument("--no-history", action="store_true",
                        help="不写近期抽取历史（维护自检时使用）")
    parser.add_argument("--twist", action="store_true",
                        help="抽取 2-3 个中期转折方向后退出")
    parser.add_argument("--all-custom", action="store_true",
                        help="表外全随机：核心规则、引擎、壳、动作、身份、处境和人物决策轴自拟")
    parser.add_argument("--force-table", action="store_true",
                        help="强制表内模式")
    parser.add_argument("--lock", action="append", default=[], metavar="KEY=VALUE",
                        help="预锁字段，可重复（如 --lock 时代=当代都市）")
    parser.add_argument("--custom", action="append", default=[], metavar="KEY=VALUE",
                        help="表外自定义值，仅与 --all-custom 一起使用")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    if args.seed is not None and args.seed < 0:
        print("ERROR: --seed must be a non-negative integer", file=sys.stderr)
        return 2
    def parse_pairs(entries: list[str], label: str) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for entry in entries:
            if "=" not in entry:
                raise AnchorError(f"--{label} expects KEY=VALUE, got {entry!r}")
            key, value = (part.strip() for part in entry.split("=", 1))
            if not key or not value:
                raise AnchorError(f"--{label} 不允许空字段或空值")
            if key in pairs:
                raise AnchorError(f"重复 {label} 字段：{key}")
            pairs[key] = value
        return pairs

    try:
        locks = parse_pairs(args.lock, "lock")
        custom = parse_pairs(args.custom, "custom")
    except AnchorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        pools = load_pools()
    except AnchorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(0, 2 ** 31)
    if args.all_custom and args.force_table:
        print("ERROR: --all-custom 与 --force-table 互斥", file=sys.stderr)
        return 2
    mode = "all_custom" if args.all_custom else ("force_table" if args.force_table else "table")
    try:
        if mode == "force_table" and custom:
            raise AnchorError("强制表内禁止 --custom")
        if mode != "all_custom" and custom:
            raise AnchorError("--custom 仅可与 --all-custom 一起使用")
        unknown = set(locks) - LOCKABLE_KEYS
        if unknown:
            raise AnchorError(f"未知 lock 字段：{sorted(unknown)}")
    except AnchorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.twist:
        picks = draw_twists(pools, seed)
        if args.format == "json":
            payload = {
                "protocol_version": PROTOCOL_VERSION,
                "seed": seed,
                "mode": mode,
                "twists": [f"{category}｜{item}" for category, item in picks],
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"seed: {seed}")
            print("转折方向（2-3 个，仅提供方向，不直接改写剧情或状态）：")
            for category, item in picks:
                print(f"- {category}｜{item}")
        return 0

    try:
        recent = set() if args.no_history else recent_signatures()
        recent_t = set() if args.no_history else recent_triples()
        roll = build_roll(pools, seed, mode, locks, custom)
        signature = _roll_signature(roll)
        triple = _roll_triple(roll)
        if args.seed is None:
            attempts = 0
            entropy = random.SystemRandom()
            while (signature in recent or triple in recent_t) and attempts < HISTORY_RETRY_LIMIT:
                seed = entropy.randrange(0, 2 ** 31)
                roll = build_roll(pools, seed, mode, locks, custom)
                signature = _roll_signature(roll)
                triple = _roll_triple(roll)
                attempts += 1
            if signature in recent or triple in recent_t:
                print("warning: 无法在历史去重上限内生成新结构骰", file=sys.stderr)
        elif signature in recent or triple in recent_t:
            print("warning: 本次结构骰与近期历史签名或三元组重复（显式 seed 保持确定性）", file=sys.stderr)
    except AnchorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not args.no_history:
        append_history(roll)
    if args.format == "json":
        print(json.dumps(roll, ensure_ascii=False, indent=2))
    else:
        print_roll(roll)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    raise SystemExit(main())
