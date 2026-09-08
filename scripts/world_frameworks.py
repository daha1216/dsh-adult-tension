"""Select a coherent world package before the unchanged legacy draw pipeline."""
from __future__ import annotations

import copy
import random


class FrameworkError(ValueError):
    pass


def candidates(package, locks, custom, opening_mode):
    given = {**custom, **locks}
    if any(key in given and given[key] not in package[field]
           for key, field in (("时代", "eras"), ("美学基调", "aesthetics"), ("地点", "places"))):
        return []
    if given.get("核心规则", package["rule"]) != package["rule"] or given.get("社会规则", package["social_rule"]) != package["social_rule"]:
        return []
    results = []
    for activity_name, activity in package["activities"].items():
        if given.get("场景动作", activity_name) != activity_name:
            continue
        for place in activity["places"]:
            if given.get("地点", place) != place:
                continue
            for index in activity["pairs"]:
                pair = package["pairs"][index]
                if any(key in given and given[key] != pair[field]
                       for key, field in (("身份族", "family"), ("玩家社会位置", "position"))):
                    continue
                if given.get("玩家称谓", pair["appellations"][0]) not in pair["appellations"]:
                    continue
                if opening_mode == "daily":
                    if given.get("压力来源") or given.get("处境", activity_name) != activity_name:
                        continue
                    results.append((activity_name, place, index, None))
                else:
                    for pressure_name, pressure in package["pressures"].items():
                        if given.get("压力来源", pressure["source"]) != pressure["source"] or given.get("处境", pressure_name) != pressure_name:
                            continue
                        engines = str(given.get("张力引擎", "")).replace(",", "、").replace("，", "、").split("、")
                        if any(x and x not in pressure["engines"] for x in engines):
                            continue
                        results.append((activity_name, place, index, pressure_name))
    return results


def build(roll_module, pools, seed, mode, locks, custom, recent, opening_mode, requested):
    if opening_mode not in ("daily", "pressure"):
        raise FrameworkError("未知 opening_mode")
    registry = pools.get("世界框架") or {}
    locks = dict(locks or {})
    custom = dict(custom or {})
    locked = locks.pop("世界框架", None)
    if locked:
        if requested not in (None, "auto", locked):
            raise FrameworkError("--framework 与锁定的世界框架不一致")
        requested = locked
    if requested in (None, "legacy"):
        return roll_module(pools, seed, mode, locks, custom, recent, opening_mode)
    if requested != "auto" and requested not in registry:
        raise FrameworkError(f"未知世界框架：{requested}")
    eligible = {name: candidates(package, locks, custom, opening_mode)
                for name, package in registry.items() if requested == "auto" or name == requested}
    eligible = {name: rows for name, rows in eligible.items() if rows}
    rng = random.Random(f"{seed}:world-framework/v1")
    if requested == "auto":
        choices = [None] * pools.get("世界框架旧池权重", 10) + list(eligible)
        requested = rng.choice(choices)
        if requested is None:
            return roll_module(pools, seed, mode, locks, custom, recent, opening_mode)
    if requested not in eligible:
        raise FrameworkError("该世界框架与所选素材不兼容；请调整锁定值或使用 --framework legacy，不会静默替换用户选择")
    package = registry[requested]
    activity_name, place, pair_index, pressure_name = rng.choice(eligible[requested])
    pair = package["pairs"][pair_index]
    activity = package["activities"][activity_name]
    pressure = package["pressures"].get(pressure_name)
    scoped = copy.deepcopy(pools)
    scoped["时代与地点"] = {"时代": list(package["eras"]), "地点": [place]}
    scoped["美学基调"] = list(package["aesthetics"])
    scoped["核心规则"] = [package["rule"]]
    scoped["社会规则"] = [package["social_rule"]]
    scoped["身份侧"] = [pair["family"]]
    scoped["玩家化身轴"]["社会位置"] = [pair["position"]]
    scoped["玩家化身轴"]["称谓"] = list(pair["appellations"])
    scoped["场景动作"] = [activity_name]
    scoped["场景动作·靠近"] = [activity_name]
    scoped["场景动作·交易"] = []
    scoped["表层风味"] = ["直率", "沉静", "耐心", "爽朗"]
    scoped["口癖"] = ["说话简短", "先问来意", "爱举例子", "偶尔自嘲"]
    scoped["场景动作分类"] = {activity["category"]: [activity_name]}
    scoped["处境侧"] = [pressure_name or activity_name]
    if pressure:
        scoped["压力来源"] = [pressure["source"]]
        scoped["张力引擎"] = list(pressure["engines"])
    meta = scoped["meta"]
    # The package is a closed compatibility set; it is not the global material pool.
    meta["location_eras"] = {place: list(package["eras"])}
    meta["aesthetic_eras"] = {x: list(package["eras"]) for x in package["aesthetics"]}
    meta["material_compatibility"] = {}
    meta["daily_opening"] = {"核心规则": [package["rule"]], "社会规则": [package["social_rule"]],
                             "张力引擎": list(pools["meta"]["daily_opening"]["张力引擎"]),
                             "场景动作": [activity_name], "处境": {activity_name: activity["beats"]}}
    if mode == "all_custom":
        defaults = {"时代": rng.choice(package["eras"]), "地点": place, "核心规则": package["rule"],
                    "社会规则": package["social_rule"], "身份族": pair["family"], "场景动作": activity_name,
                    "处境": pressure_name or activity_name}
        if pressure:
            defaults.update({"压力来源": pressure["source"], "张力引擎": "、".join(pressure["engines"])})
        custom = {**defaults, **custom}
    roll = roll_module(scoped, seed, mode, locks, custom, recent, opening_mode)
    if "场景动作·对照" in roll:
        roll.pop("场景动作·对照")
    roll["世界框架"] = requested
    roll["框架选择"] = {"version": 1, "activity": activity_name, "pair": pair_index,
                         "pressure": pressure_name, "custom": rng.randrange(len(package["customs"]))}
    roll["兼容性"] = {"status": "pass", "reasons": [], "primary_theme": "community",
                      "secondary_theme": "", "bridge_points": []}
    return roll


def selection(tables, roll):
    name = roll.get("世界框架")
    if name is None:
        return None
    registry = tables["frameworks"]["frameworks"]
    if not isinstance(name, str) or name not in registry:
        raise FrameworkError("未知或已移除的世界框架；不能用另一框架替换旧抽取记录")
    package = registry[name]
    record = roll.get("框架选择")
    if not isinstance(record, dict) or record.get("version") != 1:
        raise FrameworkError("缺少合法框架选择记录")
    index, custom_index = record.get("pair"), record.get("custom")
    if type(index) is not int or not 0 <= index < len(package["pairs"]):
        raise FrameworkError("框架人物搭配索引非法")
    if type(custom_index) is not int or not 0 <= custom_index < len(package["customs"]):
        raise FrameworkError("框架地方细节索引非法")
    expected = (record.get("activity"), roll.get("地点"), index, record.get("pressure"))
    relevant = {key: roll[key] for key in ("时代", "美学基调", "地点", "身份族", "玩家社会位置", "玩家称谓", "核心规则", "社会规则", "场景动作", "处境", "压力来源", "张力引擎") if key in roll}
    if expected not in candidates(package, relevant, {}, roll.get("opening_mode", "pressure")):
        raise FrameworkError("框架选择与结构骰不一致，拒绝错误拼接")
    return package, record


def prepare_tables(tables, roll):
    selected = selection(tables, roll)
    if selected is None:
        return tables
    package, record = selected
    tables = copy.deepcopy(tables)
    pair = package["pairs"][record["pair"]]
    activity_name = record["activity"]
    activity = package["activities"][activity_name]
    tables["identities"]["npc"][pair["family"]] = [pair["npc"]]
    tables["identities"]["player"][pair["position"]] = pair["player"]
    for place, row in package["places"].items():
        tables["locations"][place] = row["details"]
        tables["location_profiles"][place] = row["profile"]
    tables["templates"]["near_beats"][activity_name] = activity["action"]
    tables["templates"].setdefault("suggestion_player_first", {})[activity_name] = activity["beats"]["choice"]
    tables["pools"]["meta"]["daily_opening"].update({"核心规则": [package["rule"]],
        "社会规则": [package["social_rule"]], "场景动作": [activity_name], "处境": {activity_name: activity["beats"]}})
    if record["pressure"]:
        pressure = package["pressures"][record["pressure"]]
        tables["templates"]["situation_beats"][record["pressure"]] = pressure["beats"]
    return tables


def decorate(state, roll, tables):
    selected = selection(tables, roll)
    if selected is None:
        return state
    package, record = selected
    pair = package["pairs"][record["pair"]]
    snapshot = {"name": roll["世界框架"], "rule": package["rule"],
                "custom": package["customs"][record["custom"]],
                "activity": record["activity"], "relationship_reason": pair["relationship_reason"]}
    state["world"]["framework"] = snapshot
    state["world"]["constants"].extend([snapshot["rule"], snapshot["custom"]])
    state["npcs"][0]["recent_memories"].append(snapshot["relationship_reason"])
    if record["pressure"]:
        pressure = package["pressures"][record["pressure"]]
        for event in state["events"]:
            if event["kind"] == "far":
                event.update(trigger=pressure["far_trigger"], consequence=pressure["far_consequence"])
    return state
