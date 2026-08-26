#!/usr/bin/env python3
"""把结构骰骨架填成可通过 opening profile 的完整 v3 状态。

1-14 步在这里程序化落地：起名、身份、处境、决策卡、亲密核心子集、
事件、当前节点、关系边。不写正文。失败视为脚本 bug，不得丢回模型手填。

文案模板与映射表全部是 scripts/data/ 下的数据本体：templates.yaml
（开场句式/处境模板/撤回信号/压力反应/反差台词/吸引取向/建议动作）、
character_meta.yaml（年龄段区间/社会位置关系）、pools.yaml（场景动作两桶）。
改文案、加处境模板不需要碰本文件。
"""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import random
import re
from pathlib import Path
from typing import Any

PROTOCOL = "opening-fill/v1"
MULTI_SEPARATOR = re.compile(r"[、，,]")


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


class FillError(RuntimeError):
    """填料无法完成（缺表、custom_required、或校验前结构损坏）。"""


def _load_yaml(name: str) -> Any:
    # 数据本体统一走 _common 的加载入口；缺依赖或文件问题统一为 CommonError。
    try:
        return _COMMON.load_data_yaml(name)
    except _COMMON.CommonError as exc:
        raise FillError(str(exc)) from exc


def rng_for(seed: int, label: str) -> random.Random:
    return random.Random(f"{seed}:{label}:{PROTOCOL}")


def split_multi(value: str) -> list[str]:
    return [part.strip() for part in MULTI_SEPARATOR.split(value or "") if part.strip()]


def pick(rng: random.Random, items: list[Any]) -> Any:
    if not items:
        raise FillError("cannot pick from an empty pool")
    return items[rng.randrange(len(items))]


def clock_for_seed(seed: int) -> dt.datetime:
    tz = dt.timezone(dt.timedelta(hours=8))
    base = dt.datetime(2026, 3, 20, 20, 0, tzinfo=tz)
    return base + dt.timedelta(minutes=int(seed) % 240)


def iso(value: dt.datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def age_from_band(rng: random.Random, band: str, bands: dict[str, Any]) -> int:
    bounds = (bands or {}).get(band) or [28, 36]
    return rng.randint(int(bounds[0]), int(bounds[1]))


def position_relation(character_meta: dict[str, Any], position: str) -> tuple[str, str, int]:
    """社会位置 → 顶层关系边起点（type, channel, trust）；数据在 character_meta.yaml。"""
    row = ((character_meta or {}).get("社会位置关系") or {}).get(position)
    if not isinstance(row, dict):
        return ("acquaintance", "direct", 0)
    trust = row.get("trust")
    return (
        str(row.get("type") or "acquaintance"),
        str(row.get("channel") or "direct"),
        int(trust) if isinstance(trust, int) else 0,
    )


def trade_actions(pools: dict[str, Any]) -> set[str]:
    """交易摊牌桶的词条集合（数据在 pools.yaml）；用于判定开场是不是交易。"""
    scene = (pools or {}).get("场景动作") or {}
    return set(scene.get("交易摊牌") or [])


def load_tables() -> dict[str, Any]:
    return {
        "names": _load_yaml("names.yaml"),
        "identities": _load_yaml("identities.yaml"),
        "locations": _load_yaml("locations.yaml"),
        "pools": _load_yaml("pools.yaml"),
        "character_meta": _load_yaml("character_meta.yaml"),
        "templates": _load_yaml("templates.yaml"),
    }


def name_pool_for_era(names: dict, era: str) -> tuple[list, list]:
    """时代命中专属名池则用该池，否则回退顶层默认池。"""
    era_pools = names.get("eras") or {}
    pool = era_pools.get(str(era)) if isinstance(era_pools, dict) else None
    if isinstance(pool, dict):
        surnames = pool.get("surnames") or []
        givens = pool.get("given") or []
        if surnames and givens:
            return list(surnames), list(givens)
    return list(names.get("surnames") or []), list(names.get("given") or [])


def make_name(rng: random.Random, surnames: list[str], givens: list[str], used: set[str]) -> str:
    for _ in range(80):
        surname = pick(rng, surnames)
        given = pick(rng, givens)
        if given.startswith(surname):
            continue
        name = f"{surname}{given}"
        if name not in used and len(name) >= 2:
            used.add(name)
            return name
    raise FillError("name pool exhausted")


def naming_audit(role_ref: str, chosen: str, candidates: list[str],
                 era: str, place: str, social: str,
                 era_pool_hit: bool = False) -> dict[str, Any]:
    rows = []
    for name in candidates:
        if name == chosen:
            rows.append({"name": name, "reject_reason": None})
        else:
            # 如实标注：脚本路径只按池序取首候选，未选中项统一记「未选用」。
            rows.append({"name": name, "reject_reason": "未选用：按抽取顺序落在首选之后"})
    contemporary_markers = ("当代", "现代", "都市", "九十年代", "近未来", "架空")
    if era_pool_hit:
        # 时代命中专属名池：姓名与时代同源，直接记 pass。
        culture_match = "pass"
    else:
        culture_match = (
            "pass" if any(marker in str(era) for marker in contemporary_markers) else "warn"
        )
    return {
        "role_ref": role_ref,
        "mode": "standard",
        "name_profile": {
            "culture": "汉族都市",
            "region": place,
            "era": era,
            "social_context": social,
            "usage": "legal_name",
        },
        "candidates": rows,
        "chosen": chosen,
        "source": "角色设计.md",
        "approved_turn": 1,
        "checks": {
            "same_cast_duplicate": "pass",
            "phonetic_clash": "pass",
            "culture_match": culture_match,
            "natural_fit": "pass",
            "supporting_plainer": "n_a",
        },
        "recent_check": "unavailable",
        "locked_by_player": False,
    }


def appearance_text(entries: Any) -> str:
    if not isinstance(entries, list) or not entries:
        return "身形普通，夜里灯光把轮廓切得很清楚。"
    parts = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("item"):
            axis = entry.get("axis") or ""
            item = entry["item"]
            parts.append(f"{axis}{item}" if axis else str(item))
    return "、".join(parts) if parts else "身形普通。"


def expand_npc_identity(item: dict[str, str], family: str) -> dict[str, str]:
    hidden = item.get("hidden") or "—"
    return {
        "role": item["role"],
        "public_identity": item["role"],
        "actual_function": item["function"],
        "authority_source": item["authority"],
        "key_resource": item["resource"],
        "limitation": item["limitation"],
        "obligation": item["obligation"],
        "exposure_risk": item["exposure"],
        "hidden_mismatch": hidden,
    }


def player_identity_text(position_row: dict[str, Any], npc_role: str) -> str:
    base = str(position_row["identity"])
    if "对口" in base or "同一" in base:
        return f"{base}（对方公开身份是{npc_role}）"
    return base


def situation_bundle(kind: str, npc: str, pressure: str,
                     beats_map: dict[str, Any]) -> dict[str, str]:
    beat = beats_map.get(kind) or beats_map["今夜话没说完"]
    return {key: value.format(npc=npc, pressure=pressure) for key, value in beat.items()}


def voice_filter(roll: dict[str, Any], identity: str, templates: dict[str, Any]) -> str:
    flavor = roll.get("表层风味") or "—"
    quirk = roll.get("口癖") or "—"
    contrast = roll.get("反差轴") or ""
    flavor_bit = "按公开身份说话" if flavor in {"—", "", None} else f"带一点{flavor}"
    quirk_bit = "句子短、留白多" if quirk in {"—", "", None} else f"口吻上{quirk}"
    inner = (templates.get("contrast_line") or {}).get(str(contrast), "卸下外壳后直白，不绕。")
    return (
        f"表层语态：作为{identity}，{flavor_bit}，{quirk_bit}；"
        f"回避时改口程序和场面，压力下句短，不吐粗词。"
        f"里层语态：{inner}直白、索求不含糊；失控时用词先直，再碎到名字和气音。"
        f"切换触发：独处、酒意、疼痛或快感累积，或被明确要求别再装。"
    )


def sexuality_block(rng: random.Random, subset: dict[str, Any],
                    npc: str, player: str, position: str,
                    templates: dict[str, Any]) -> dict[str, Any]:
    subset = subset if isinstance(subset, dict) else {}
    intensity = subset.get("drive.intensity") or pick(rng, ["low", "medium", "high"])
    awareness = subset.get("drive.awareness") or pick(rng, ["unaware", "uncertain", "clear"])
    initiative = subset.get("preferences.initiative") or "responsive"
    pace = subset.get("preferences.pace") or "adaptive"
    style = subset.get("preferences.style") or "natural"
    directness = subset.get("expression.directness") or "natural"
    control = subset.get("regulation.self_control") or "variable"
    origin = subset.get("interest_origin.type") or "contextual"
    orientation = pick(rng, templates.get("orientations") or [])
    toward = (
        f"对{player}具备吸引前提与否，要看今夜是否被看见、以及{position}这条关系怎么落地；"
        f"同处一室本身不等于欲望成立。"
    )
    baseline = (
        f"欲望强度{intensity}、自我觉察{awareness}。"
        f"习惯{initiative}，节奏{pace}，风格{style}；表达{directness}，自控{control}。"
        f"来源是{origin}，不因压力或职级自动扩大许可。"
    )
    core = {
        "baseline": baseline,
        "drive": {"intensity": intensity, "awareness": awareness},
        "attraction": {"orientation": orientation, "toward_player": toward},
        "preferences": {"initiative": initiative, "pace": pace, "style": style},
        "expression": {"directness": directness},
        "regulation": {"self_control": control},
        "interest_origin": {
            "type": origin,
            "reason": f"{npc}平时把它压在工作里，只有情境对了才会承认身体先动。",
        },
    }
    snapshot = {
        "drive": f"{intensity}/{awareness}",
        "preference": f"{initiative}/{pace}/{style}",
        "expression": directness,
        "origin": origin,
    }
    return core, snapshot


def action_sentence(action: str, npc: str, trade: bool, templates: dict[str, Any]) -> str:
    table = (templates.get("trade_beats") or {}) if trade else (templates.get("near_beats") or {})
    fallback = templates.get("action_fallback_trade" if trade else "action_fallback_near")
    template = table.get(action) or fallback
    if not template:
        raise FillError("templates.yaml 缺少动作句式兜底（action_fallback_near/trade）")
    return template.format(npc=npc)


def suggested_actions(action: str, npc: str, player: str,
                      tables: dict[str, Any] | None = None) -> list[str]:
    tables = tables or load_tables()
    templates = tables["templates"]
    extras = [str(item).format(npc=npc) for item in templates.get("suggestion_extras") or []]
    first_map = templates.get("suggestion_player_first") or {}
    # Player-facing suggestions should be player actions.
    player_first = str(
        first_map.get(action)
        or templates.get("suggestion_default")
        or "先应{npc}刚才那一下，不把今夜写成交易。"
    ).format(npc=npc)
    picked = [player_first]
    for item in extras:
        if item not in picked:
            picked.append(item)
        if len(picked) == 3:
            break
    guard = str(templates.get("suggestion_nontrade_guard") or "把外套或杯子递回去，不先谈条件。")
    if action not in trade_actions(tables["pools"]) and not any(
            "交易" not in item and "条件" not in item for item in picked):
        picked[-1] = guard
    return picked[:3]


def require_roll_value(roll: dict[str, Any], key: str) -> str:
    value = roll.get(key)
    if value in (None, "", "custom_required"):
        raise FillError(f"roll field {key} is missing or custom_required")
    return str(value)


def fill_opening(skeleton: dict[str, Any], roll: dict[str, Any],
                 tables: dict[str, Any] | None = None) -> dict[str, Any]:
    """在骨架上填实 1-14 内容字段，返回新 dict。"""
    data = copy.deepcopy(skeleton)
    tables = tables or load_tables()
    seed = roll.get("seed")
    if not isinstance(seed, int) or seed < 0:
        raise FillError("roll.seed must be a non-negative integer")
    for key in ("时代", "地点", "社会规则", "压力来源", "身份族", "处境",
                "核心规则", "权力结构", "场景动作", "核心价值", "压力策略",
                "关系姿态", "玩家称谓", "玩家年龄段", "玩家社会位置"):
        require_roll_value(roll, key)

    era = roll["时代"]
    place = roll["地点"]
    rule = roll["社会规则"]
    pressure = roll["压力来源"]
    family = roll["身份族"]
    situation_kind = roll["处境"]
    core_rule = roll["核心规则"]
    value_axis = roll["核心价值"]
    strategy = roll["压力策略"]
    stance = roll["关系姿态"]
    contrast = roll.get("反差轴") or "外冷内热"
    appellation = roll["玩家称谓"]
    age_band = roll["玩家年龄段"]
    position = roll["玩家社会位置"]
    action = roll["场景动作"]
    engines = split_multi(str(roll.get("张力引擎") or ""))
    if not engines or any(item == "custom_required" for item in engines):
        raise FillError(
            "张力引擎缺失或仍为 custom_required：--all-custom 模式必须以 "
            "--lock 张力引擎=A、B 提供两项引擎，禁止占位符进入已提交状态"
        )
    if len(engines) < 2:
        raise FillError(f"张力引擎需要恰好两项，收到 {len(engines)} 项：{engines}")

    templates = tables["templates"]
    character_meta = tables["character_meta"]

    rng_names = rng_for(seed, "names")
    rng_body = rng_for(seed, "body")
    names_table = tables["names"]
    surnames, givens = name_pool_for_era(names_table, era)
    era_pool = (names_table.get("eras") or {}).get(str(era)) or {}
    era_pool_hit = bool(era_pool.get("surnames") and era_pool.get("given"))
    used: set[str] = set()
    player_candidates = [make_name(rng_names, surnames, givens, used) for _ in range(4)]
    npc_candidates = [make_name(rng_names, surnames, givens, used) for _ in range(4)]
    player_name = player_candidates[0]
    npc_name = npc_candidates[0]

    npc_pool = tables["identities"]["npc"].get(family)
    if not npc_pool:
        raise FillError(f"no identities for family {family!r}")
    npc_item = npc_pool[seed % len(npc_pool)]
    identity = expand_npc_identity(npc_item, family)
    position_row = tables["identities"]["player"].get(position)
    if not position_row:
        raise FillError(f"no player identity for position {position!r}")

    loc_pool = tables["locations"].get(place)
    if not loc_pool:
        # 地点表缺失必须响亮失败，禁止静默回退成错位拼接（如「新地点·室内·夜」）。
        raise FillError(
            f"locations.yaml 缺少地点 {place!r} 的细节条目；请同步 scripts/data/locations.yaml"
        )
    detail = loc_pool[seed % len(loc_pool)]
    location = f"{place}·{detail}"

    clock = clock_for_seed(seed)
    # 带死线的处境与压力来源（决定 near 事件是否带 due_at）；名单在 pools.yaml meta。
    pools_meta = tables["pools"].get("meta") or {}
    timed_situations = set(pools_meta.get("timed_situations")
                           or ["时限临门", "债务压身", "秘密将破", "审查将至"])
    timed_pressures = set(pools_meta.get("timed_pressures")
                          or ["时限逼近", "债务到期", "秘密即将暴露"])
    timed = situation_kind in timed_situations or pressure in timed_pressures
    deadline = clock + dt.timedelta(hours=8) if timed else None
    far_due = clock + dt.timedelta(days=7)

    player_age = age_from_band(rng_body, age_band, character_meta.get("年龄段区间"))
    npc_age = min(48, max(18, player_age + rng_body.randint(-6, 5)))
    if npc_age == player_age:
        npc_age = min(48, npc_age + 1)

    beats = situation_bundle(situation_kind, npc_name, pressure, templates.get("situation_beats") or {})
    trade = action in trade_actions(tables["pools"])
    unresolved = action_sentence(action, npc_name, trade, templates)
    last_result = f"门在身后合上。{location}里暂时只剩你们两个。"
    next_pressure = beats["near"]

    power_zh = {
        "player_high": "你在明面上更有位置",
        "npc_high": "她在明面上更有位置",
        "equal": "你们在明面上对等",
        "switchable": "明面上的位置今晚还可能倒转",
    }.get(str(roll["权力结构"]), "明面上的位置已经摆明")
    constants = [
        f"这座{place}里，{rule}。",
        f"{core_rule}不只是口号：今晚谁先破例，谁先付出能被看见的代价。",
        f"{power_zh}，这不推导把柄，也不等于今晚可以越界。",
    ]
    aesthetic = roll.get("美学基调")
    if isinstance(aesthetic, str) and aesthetic.strip() and aesthetic != "custom_required":
        # 开局流程步骤 1：美学基调进入 world.constants，作为本局质感基准。
        constants.append(f"{aesthetic}的质感贯穿这一夜：光线、声响和衣物细节都向它靠拢。")

    data["meta"]["turn"] = 1
    data["meta"]["safety_state"] = "running"
    data["meta"]["power_structure"] = roll["权力结构"]
    data["world"]["clock"] = iso(clock)
    data["world"]["previous_clock"] = iso(clock)
    data["world"]["delta_t"] = 0
    data["world"]["delta_human"] = ""
    data["world"]["constants"] = constants
    data["world"]["tension_engines"] = engines
    data["world"]["setting_shell"] = {
        "type": era, "place": place, "rule": rule, "pressure": pressure,
    }
    data["world"]["pressure_seeds"]["immediate"] = pressure

    player_id_text = player_identity_text(position_row, identity["role"])
    data["player"].update({
        "name": player_name,
        "age": player_age,
        "identity": player_id_text,
        "location": location,
        "baseline": f"{player_age}岁，别人称你{appellation}。{position_row['baseline']}",
        "resources": list(position_row["resources"]),
        "knowledge": [
            f"{npc_name}的公开身份是{identity['role']}。",
            f"今晚的压力来自{pressure}，场面停在{place}。",
        ],
        "reputation": position_row["reputation"],
        "appellation": appellation,
    })
    # 落档只保留最小三键（角色设计.md：候选名单与 checks 开局用完不进存档）。
    data["player_naming_audit"] = {
        "chosen": player_name,
        "source": "角色设计.md",
        "approved_turn": 1,
    }

    look = appearance_text(roll.get("外观·主NPC"))
    contrast_line = (templates.get("contrast_line") or {}).get(
        str(contrast), "公开场合端着，私下里会漏出另一层。")
    personality = (
        f"{contrast_line}核心要的是{value_axis}。"
        f"对人{stance}，压力下习惯{strategy}。"
    )
    pressure_map = templates.get("pressure_response") or {}
    responses = pressure_map.get(strategy) or pressure_map["正面解决"]
    goal = f"在{pressure}压过来之前守住{value_axis}，同时不把今夜写成自己认输"
    boundary = "不用身体换出路；不把未同意写成已经发生的交易"
    sex, sex_snap = sexuality_block(
        rng_body, roll.get("亲密画像核心子集") or {}, npc_name, player_name, position, templates,
    )

    npc = data["npcs"][0]
    npc.update({
        "name": npc_name,
        "age": npc_age,
        "role_level": "main",
        "identity": identity["role"],
        "location": location,
        "core_personality": personality,
        "pressure_strategy": strategy,
        "voice_filter": voice_filter(roll, identity["role"], templates),
        "goal": goal,
        "boundary": boundary,
        "withdrawal_signal": (templates.get("withdrawal") or {}).get(
            strategy, "改口此事到此，开始收拾东西。"),
        "emotion": f"表面还端着，{pressure}已经压到眼底。",
        "resources": [identity["key_resource"], identity["authority_source"]],
        "knowledge": [
            beats["trigger"],
            f"{player_name}今晚以{position}的位置出现在同一间屋子里。",
        ],
        "recent_memories": [
            f"进门前她在外面把{look.split('、')[0] if look else '自己'}重新整理过一次。",
            f"她决定先用{strategy}撑住场面。",
        ],
        "signature": f"{look}。压力下会先动手指，再动表情。",
        "autonomy": {"last_turn": None, "recent_turns": [], "cooldown_until": 0},
    })
    npc["identity_profile"] = identity
    npc["situation"] = {
        "type": situation_kind,
        "trigger": beats["trigger"],
        "pressure": pressure,
        "immediate_objective": beats["objective"],
        "deadline": iso(deadline) if deadline else None,
        "unresolved_choice": beats["choice"],
        "knowledge_gap": {
            "player_knows": [
                f"{npc_name}公开身份是{identity['role']}",
                f"今晚的压力与{pressure}有关",
            ],
            "npc_knows": [
                identity["limitation"],
                "她还没决定对你说哪一层",
            ],
            "both_mistake": [
                "双方都可能把今夜高估成已经有默契",
            ],
        },
        "exits": {
            "available": True,
            "cost": "任何一方都可以先离开；离开等于把未决交给外面的时点。",
            "blocked_by": None,
        },
        "consequence": {
            "immediate": beats["immediate"],
            "near_term": beats["near"],
        },
    }
    npc["decision_card"] = {
        "goal": goal,
        "stable_core": {
            "identity": identity["role"],
            "core_traits": [str(contrast), value_axis, stance],
            "hard_limits": [boundary, "不拿未同意当已经发生"],
        },
        "goals": {
            "primary": goal,
            "secondary": f"把{situation_kind}从人身条款里隔开",
            "hidden": f"想被认真对待，而不是被写成今晚的素材",
        },
        "knowledge": {
            "known": list(npc["knowledge"]),
            "unknown": [f"{player_name}手里到底有没有她不知道的那一层"],
            "mistaken_beliefs": ["只要把请求做成交易，就不会变成人情"],
        },
        "pressure_response": {
            "low": responses[0],
            "medium": responses[1],
            "high": responses[2],
            "critical": responses[3],
        },
        "action_preferences": {
            "prefer": [strategy, stance],
            "avoid": ["先开口认软", "在未得到态度前越界"],
            "never": ["用身体交换出手", "把拒绝当成还没听见"],
        },
        "sexuality_refs": {
            "profile": "sexuality_profile",
            "development": "sexuality_development",
        },
        # 决策卡不保存 autonomy 副本：顶层 autonomy 是唯一正式来源（SKILL.md）。
    }
    npc["sexuality_profile"] = sex
    npc["sexuality_development"] = {
        "baseline": sex_snap,
        "current": copy.deepcopy(sex_snap),
        "plasticity": "medium",
        "evidence": [],
        "trend": "stable",
    }
    npc["naming_audit"] = naming_audit(
        "main_npc", npc_name, npc_candidates, era, place, family,
        era_pool_hit=era_pool_hit,
    )

    # 配角未进场：丢掉骨架里可能出现的第二名。
    data["npcs"] = [npc]

    rel_type, rel_channel, trust = position_relation(character_meta, position)
    data["relationships"] = [{
        "source": "player-001",
        "target": "npc-001",
        "type": rel_type,
        "channel": rel_channel,
        "trust": trust,
        "last_updated_turn": 1,
        "opening": {"status": True, "covered_turn": 1},
    }]

    due_near = iso(deadline) if deadline else None
    data["events"] = [
        {
            "id": "evt-001",
            "semantic_key": f"opening-immediate-{situation_kind}",
            "source": "system:opening",
            "created_turn": 1,
            "kind": "immediate",
            "trigger": beats["trigger"],
            "due_at": None,
            "status": "pending",
            "consequence": beats["immediate"],
            "hook": False,
            "probability": None,
        },
        {
            "id": "evt-002",
            "semantic_key": f"opening-near-{pressure}",
            "source": "system:opening",
            "created_turn": 1,
            "kind": "near",
            "trigger": beats["near"],
            "due_at": due_near,
            "status": "pending",
            "consequence": beats["near"],
            "hook": False,
            "probability": None,
        },
        {
            "id": "evt-003",
            "semantic_key": f"opening-far-{engines[-1]}",
            "source": "system:opening",
            "created_turn": 1,
            "kind": "far",
            "trigger": f"{engines[-1]}还没有进这个房间，但已经在路上。",
            "due_at": iso(far_due),
            "status": "pending",
            "consequence": "那一层压力会改写你们今晚没谈完的部分。",
            "hook": True,
            "probability": None,
        },
    ]
    data["world"]["pressure_seeds"]["near_event_id"] = "evt-002"
    data["world"]["pressure_seeds"]["far_event_id"] = "evt-003"

    node_situation = {
        "trigger": beats["trigger"],
        "pressure": pressure,
        "immediate_objective": beats["objective"],
        "deadline": iso(deadline) if deadline else None,
        "unresolved_choice": beats["choice"],
        "knowledge_gap": copy.deepcopy(npc["situation"]["knowledge_gap"]),
        "exits": copy.deepcopy(npc["situation"]["exits"]),
        "consequence": copy.deepcopy(npc["situation"]["consequence"]),
    }
    data["current_node"].update({
        "scene_id": "scene-001",
        "location": location,
        "participants": ["player-001", "npc-001"],
        "situation": node_situation,
        "last_committed_result": last_result,
        "unresolved_action": unresolved,
        "natural_next_pressure": next_pressure,
    })
    data["consent"]["scene_id"] = "scene-001"
    data["consent"]["location"] = location
    data["consent"]["participants"] = ["player-001", "npc-001"]
    data["consent"]["grants"] = []
    data["boundaries"] = []
    data["resolved_summary"] = []
    data["checkpoint"] = {
        "last_full_turn": 1,
        "changed": [{"turn": 1, "field": "current_node", "reason": "opening commit"}],
        "next_full_turn": 6,
        "force_full": False,
        "force_reason": None,
        "invariants": {"age_verified": True, "player_control_preserved": True},
    }
    data.pop("directives", None)
    return data


def opening_suggestions(state: dict[str, Any], roll: dict[str, Any] | None = None,
                        tables: dict[str, Any] | None = None) -> list[str]:
    npc = (state.get("npcs") or [{}])[0]
    player = state.get("player") or {}
    action = (roll or {}).get("场景动作") or ""
    return suggested_actions(
        str(action), str(npc.get("name") or "她"), str(player.get("name") or "你"), tables)
