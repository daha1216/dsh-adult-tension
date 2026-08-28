#!/usr/bin/env python3
"""roll_opening.py — 沉浸叙事引擎的开局结构骰与中期转折抽取。

数据本体全部在 scripts/data/ 下的 yaml：pools.yaml（开局素材池＋meta 行为开关）、
character_meta.yaml（决策轴/生成权重/配角功能）、twists.yaml（转折池）、
character_pools.yaml（角色三池）。references/ 下的文档只承载语义说明，
本脚本不再解析任何 markdown。数据缺漏即 AnchorError 响亮失败。

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
import importlib.util
import json
import random
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "scripts" / "data"
POOLS_FILE = DATA_DIR / "pools.yaml"
CHAR_META_FILE = DATA_DIR / "character_meta.yaml"
TWISTS_FILE = DATA_DIR / "twists.yaml"
CHAR_POOLS_FILE = DATA_DIR / "character_pools.yaml"
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

INTENSITY = ["low", "medium", "high"]
AWARENESS = ["unaware", "uncertain", "clear"]
INITIATIVE = ["follow", "responsive", "lead", "switch"]
PACE = ["gradual", "adaptive", "direct"]
STYLE = ["tender", "natural", "playful", "intense", "experimental", "mixed"]
DIRECTNESS = ["reserved", "natural", "direct", "uninhibited"]
SELF_CONTROL = ["stable", "variable", "poor"]
INTEREST_ORIGIN = ["stable", "contextual", "unexplored", "defensive", "target_specific"]


class AnchorError(Exception):
    """数据文件缺失、键缺失或内容违反契约。"""


def split_items(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[、，,]", text) if part.strip()]


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


def _read_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        data = _COMMON.load_yaml_file(path)
    except _COMMON.CommonError as exc:
        raise AnchorError(f"无法读取{label}（{path}）：{exc}") from exc
    if not isinstance(data, dict) or not data:
        raise AnchorError(f"{label}为空或顶层不是映射：{path}")
    return data


def _flat(value: Any, name: str) -> list[str]:
    """校验字符串列表：去重保序、过滤空项；为空即报错。"""
    if not isinstance(value, list):
        raise AnchorError(f"{name} 必须是字符串列表")
    pool: list[str] = []
    for raw in value:
        item = str(raw).strip()
        if item and item not in pool:
            pool.append(item)
    if not pool:
        raise AnchorError(f"{name} 池为空")
    return pool


def _flat_groups(value: Any, name: str, required: tuple[str, ...]) -> dict[str, list[str]]:
    """校验分组表：必需的组名都在且每组非空。"""
    if not isinstance(value, dict):
        raise AnchorError(f"{name} 必须是 组名→列表 映射")
    groups: dict[str, list[str]] = {}
    for group in required:
        groups[group] = _flat(value.get(group), f"{name}·{group}")
    return groups


def _parse_meta(raw: dict[str, Any]) -> dict[str, Any]:
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        raise AnchorError("pools.yaml 缺少 meta 节")
    for key in ("leverage_engines", "situation_leverage", "gate_aesthetics"):
        meta[key] = _flat(meta.get(key), f"meta.{key}")
    weights = meta.get("identity_weights")
    if not isinstance(weights, dict) or not weights:
        raise AnchorError("meta.identity_weights 必须是 身份族→权重 映射")
    for family, weight in weights.items():
        if not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0:
            raise AnchorError(f"meta.identity_weights.{family} 必须是正整数")
    # location_eras 是可选键（地点→配套时代列表）：测试合成 fixture 可能没有这个键，
    # 缺失时直接跳过、不注入；存在则必须是 地点→非空时代列表 映射（形状与 _flat 契约）。
    era_map = meta.get("location_eras")
    if era_map is not None:
        if not isinstance(era_map, dict) or not era_map:
            raise AnchorError("meta.location_eras 必须是 地点→非空时代列表 映射")
        meta["location_eras"] = {
            place: _flat(eras, f"meta.location_eras.{place}")
            for place, eras in era_map.items()
        }
    return meta


# 行为开关（pools.yaml 的 meta 节）与原始素材池改为首次使用时加载：
# 模块导入不再读任何数据文件；进程内每个文件只解析一次。
_RAW_POOLS_CACHE: dict[str, Any] | None = None
_META_CACHE: dict[str, Any] | None = None


def _raw_pools_once() -> dict[str, Any]:
    global _RAW_POOLS_CACHE
    if _RAW_POOLS_CACHE is None:
        _RAW_POOLS_CACHE = _read_yaml(POOLS_FILE, "开局素材池")
    return _RAW_POOLS_CACHE


def _module_meta() -> dict[str, Any]:
    global _META_CACHE
    if _META_CACHE is None:
        _META_CACHE = _parse_meta(_raw_pools_once())
    return _META_CACHE


def leverage_engines() -> frozenset[str]:
    return frozenset(_module_meta()["leverage_engines"])


def situation_leverage() -> frozenset[str]:
    return frozenset(_module_meta()["situation_leverage"])


def gate_aesthetics() -> frozenset[str]:
    return frozenset(_module_meta()["gate_aesthetics"])


def identity_weights() -> dict[str, int]:
    return dict(_module_meta()["identity_weights"])


def __getattr__(name: str) -> Any:
    # 兼容旧的全大写常量属性访问（外部消费者/测试按属性读取时兜底；
    # 模块内部一律用上面的取值函数）。
    lazy = {
        "LEVERAGE_ENGINES": leverage_engines,
        "SITUATION_LEVERAGE": situation_leverage,
        "GATE_AESTHETICS": gate_aesthetics,
        "IDENTITY_WEIGHTS": identity_weights,
        "_MODULE_META": _module_meta,
    }
    if name in lazy:
        return lazy[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _load_character_pools() -> dict[str, Any]:
    """加载角色三池 yaml（表层风味/口癖/外观轴），缺失或为空即报错。"""
    data = _read_yaml(CHAR_POOLS_FILE, "角色三池")
    for key in ("表层风味", "口癖", "外观轴"):
        value = data.get(key)
        if not isinstance(value, dict) or not value:
            raise AnchorError(f"character_pools.yaml 缺失或为空：{key}")
    return data


def _flatten_grouped(groups: Any, *, name: str, max_len: int | None = None) -> list[str]:
    """把 {组名: [条目]} 展平为去重池；max_len 过滤超长条目。"""
    if not isinstance(groups, dict):
        raise AnchorError(f"{name} 必须是 组名→列表 映射")
    pool: list[str] = []
    for items in groups.values():
        if not isinstance(items, list):
            raise AnchorError(f"{name} 的每个组必须是列表")
        for raw in items:
            item = str(raw).strip()
            if not item or (max_len is not None and len(item) > max_len):
                continue
            if item not in pool:
                pool.append(item)
    if not pool:
        raise AnchorError(f"{name} 池为空（检查 character_pools.yaml）")
    return pool


def _appearance_from_yaml(axes: Any) -> dict[str, dict[str, list[str]]]:
    """校验外观轴两层结构 {轴名: {组名: [条目]}}，键名被写实门控按名引用。"""
    if not isinstance(axes, dict) or not axes:
        raise AnchorError("外观与气质轴池为空（检查 character_pools.yaml）")
    validated: dict[str, dict[str, list[str]]] = {}
    for axis, groups in axes.items():
        if not isinstance(groups, dict) or not groups:
            raise AnchorError(f"外观轴 {axis} 缺少分组条目")
        cleaned: dict[str, list[str]] = {}
        for group, items in groups.items():
            if not isinstance(items, list):
                raise AnchorError(f"外观轴 {axis}/{group} 必须是列表")
            entries = [str(item).strip() for item in items if str(item).strip()]
            if entries:
                cleaned[str(group)] = entries
        if not cleaned:
            raise AnchorError(f"外观轴 {axis} 缺少分组条目")
        validated[str(axis)] = cleaned
    return validated


def _decision_axes(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise AnchorError("决策轴必须是 轴名→列表 映射")
    axes: dict[str, list[str]] = {}
    for name in ("核心价值", "压力策略", "关系姿态"):
        items = _flat(value.get(name), f"决策轴·{name}")
        if len(items) < 2:
            raise AnchorError(f"决策轴·{name} 至少需要两项")
        axes[name] = items
    return axes


def _profile_weights(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise AnchorError("人物生成倾向必须是 倾向→权重 映射")
    weights: dict[str, int] = {}
    for key, weight in value.items():
        if not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0:
            raise AnchorError(f"人物生成倾向.{key} 必须是正整数")
        weights[str(key)] = weight
    if sum(weights.values()) != 100:
        raise AnchorError(f"人物生成倾向权重总和必须为 100，实际为 {sum(weights.values())}")
    return weights


def _twist_pool(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict) or tuple(value.keys()) != TWIST_CATEGORIES:
        raise AnchorError(f"转折池必须严格包含七类且顺序不变：{TWIST_CATEGORIES}")
    pools = {category: _flat(value.get(category), f"转折池·{category}") for category in TWIST_CATEGORIES}
    return pools


def load_pools() -> dict[str, Any]:
    raw = _raw_pools_once()
    meta = _parse_meta(raw)
    char_meta = _read_yaml(CHAR_META_FILE, "人物生成元数据")
    twists = _read_yaml(TWISTS_FILE, "转折池")
    char_pools = _load_character_pools()

    pools: dict[str, Any] = {}
    pools["表层风味"] = _flatten_grouped(char_pools["表层风味"], name="表层风味", max_len=8)
    pools["口癖"] = _flatten_grouped(char_pools["口癖"], name="口癖", max_len=8)
    pools["外观轴"] = _appearance_from_yaml(char_pools["外观轴"])
    pools["决策轴"] = _decision_axes(char_meta.get("决策轴"))
    pools["人物生成倾向"] = _profile_weights(char_meta.get("人物生成倾向"))
    pools["配角功能"] = _flat(char_meta.get("配角功能"), "配角功能")

    for key in ("核心规则", "美学基调", "权力结构", "张力引擎", "社会规则",
                "压力来源", "身份侧", "处境侧", "反差轴"):
        pools[key] = _flat(raw.get(key), key)
    pools["时代与地点"] = _flat_groups(raw.get("时代与地点"), "时代与地点", ("时代", "地点"))
    scene = _flat_groups(raw.get("场景动作"), "场景动作", ("交易摊牌", "非交易靠近"))
    pools["场景动作·交易"] = scene["交易摊牌"]
    pools["场景动作·靠近"] = scene["非交易靠近"]
    pools["场景动作"] = list(dict.fromkeys(pools["场景动作·交易"] + pools["场景动作·靠近"]))
    pools["玩家化身轴"] = _flat_groups(raw.get("玩家化身轴"), "玩家化身轴", ("称谓", "年龄段", "社会位置"))
    pools["转折池"] = _twist_pool(twists)

    if not set(pools["权力结构"]).issubset(POWER_STRUCTURES):
        raise AnchorError("权力结构条目与 validate_state 枚举不一致")
    for name in meta["leverage_engines"]:
        if name not in pools["张力引擎"]:
            raise AnchorError(f"meta.leverage_engines 引用了不存在的张力引擎：{name!r}")
    for name in meta["situation_leverage"]:
        if name not in pools["处境侧"]:
            raise AnchorError(f"meta.situation_leverage 引用了不存在的处境：{name!r}")
    for name in meta["gate_aesthetics"]:
        if name not in pools["美学基调"]:
            raise AnchorError(f"meta.gate_aesthetics 引用了不存在的美学基调：{name!r}")
    for family in meta["identity_weights"]:
        if family not in pools["身份侧"]:
            raise AnchorError(f"meta.identity_weights 引用了不存在的身份族：{family!r}")
    for place, eras in (meta.get("location_eras") or {}).items():
        if place not in pools["时代与地点"]["地点"]:
            raise AnchorError(f"meta.location_eras 引用了不存在的地点：{place!r}")
        for era in eras:
            if era not in pools["时代与地点"]["时代"]:
                raise AnchorError(f"meta.location_eras.{place} 引用了不存在的时代：{era!r}")
    pools["meta"] = meta
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
                   rng: random.Random, avoid: set[str] | None = None) -> str:
    """把多值字段（如张力引擎）的 lock/custom 值规范化为恰好 count 项。

    - 值按顿号/逗号拆分；
    - 超过 count 项或含重复项报错；
    - 少于 count 项时，从池中排除已锁定项（以及 avoid 集合，除非玩家显式
      锁定了多项）后补抽到 count，保证互不相同且不塌缩成被禁组合。
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
    # 玩家只显式锁定一项且落在 avoid 组（杠杆引擎）时，补抽不得再落入同组；
    # 玩家显式锁满两项则视为有意叠加，不受此限。
    if avoid and len(items) < count and not any(item in avoid for item in items[1:]):
        filtered = [item for item in remaining if item not in avoid]
        if filtered:
            remaining = filtered
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
            locked_parts = [part.strip() for part in MULTI_SEPARATOR.split(locks[key]) if part.strip()]
            # 单锁一项杠杆引擎时，补抽不得再叠出第二项杠杆引擎（双杠杆防塌缩）。
            leverage_switch = leverage_engines()
            avoid = leverage_switch if (key == "张力引擎" and len(locked_parts) == 1
                                        and locked_parts[0] in leverage_switch) else None
            roll[key] = _combine_multi(key, locks[key], pool, count, rng, avoid=avoid)
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
    # 时代×地点和解（meta.location_eras，pools.yaml 契约第 4 条）：
    # 表抽值才让路；玩家给定值（--lock / all_custom 自拟 / custom_required 占位）一律不动。
    player_era = "时代" in locks or (mode == "all_custom" and "时代" in CUSTOM_KEYS)
    player_place = "地点" in locks or (mode == "all_custom" and "地点" in CUSTOM_KEYS)
    era_map = (pools.get("meta") or {}).get("location_eras") or {}
    compat = era_map.get(roll["地点"])
    if compat and roll["时代"] not in compat:
        if player_era and player_place:
            print(f"WARNING: 玩家给定组合「{roll['时代']}×{roll['地点']}」跨越 location_eras，按玩家意愿保留。",
                  file=sys.stderr)
        elif player_era:
            # 时代是玩家给定：重抽地点，只从「不在 location_eras 的地点 ∪ 兼容该时代的地点」里挑
            candidates = [p for p in pools["时代与地点"]["地点"]
                          if p not in era_map or roll["时代"] in era_map[p]]
            if candidates:
                roll["地点"] = rng.choice(candidates)
            else:
                print(f"WARNING: 时代「{roll['时代']}」无可换地点，保留「{roll['地点']}」。",
                      file=sys.stderr)
        else:
            # 时代是表抽值：时代让路（硬锁地点是稀缺签），从配套名单重抽
            roll["时代"] = rng.choice(compat)
    draw("社会规则", pools["社会规则"])
    draw("压力来源", pools["压力来源"])
    if "场景动作" in locks or (mode == "all_custom" and "场景动作" in CUSTOM_KEYS):
        draw("场景动作", pools["场景动作"])
    else:
        roll["场景动作"] = rng.choice(pools["场景动作·靠近"])
    if "身份族" in locks or (mode == "all_custom" and "身份族" in CUSTOM_KEYS):
        draw("身份族", pools["身份侧"])
    else:
        roll["身份族"] = _weighted_choice(rng, pools["身份侧"], identity_weights())
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
        leverage_switch = leverage_engines()
        if len(engines) >= 2 and set(engines) <= leverage_switch:
            remaining = [item for item in pools["张力引擎"] if item not in engines and item not in leverage_switch]
            if not remaining:
                remaining = [item for item in pools["张力引擎"] if item not in engines]
            if remaining:
                engines[1] = rng.choice(remaining)
                roll["张力引擎"] = "、".join(engines)
    if "处境" not in locks and not (
            mode == "all_custom" and roll.get("处境") == "custom_required"):
        situation_leverage_set = situation_leverage()
        if roll.get("权力结构") == "player_high" and roll.get("处境") in situation_leverage_set:
            remaining = [item for item in pools["处境侧"] if item not in situation_leverage_set]
            if remaining:
                roll["处境"] = rng.choice(remaining)
    trade_pool = [item for item in pools["场景动作·交易"] if item != roll.get("场景动作")]
    if trade_pool:
        roll["场景动作·对照"] = rng.choice(trade_pool)
    else:
        roll["场景动作·对照"] = rng.choice(pools["场景动作·交易"]) if pools["场景动作·交易"] else "—"
    gate = roll["美学基调"] in gate_aesthetics()
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


def _nonneg_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be an integer, got {text!r}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=_nonneg_int, default=None,
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
