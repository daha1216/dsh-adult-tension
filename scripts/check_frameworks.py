"""Validate world packages without running a narrative or rewriting the data."""
from __future__ import annotations

from string import Formatter


def check_frameworks(registry, pools, categories, identity_profiles, report):
    def error(path, message):
        report.error(f"world_frameworks.{path}: {message}")

    def mapping(value, path):
        if not isinstance(value, dict) or not value:
            error(path, "必须为非空映射")
            return {}
        return value

    def text(value, path, placeholders=()):
        report.checks += 1
        if not isinstance(value, str) or not value.strip():
            error(path, "必须为非空字符串")
            return
        try:
            for _, field, spec, conversion in Formatter().parse(value):
                if field is not None and (field not in placeholders or spec or conversion):
                    error(path, "包含非法占位符")
        except ValueError:
            error(path, "模板格式非法")

    def strings(value, path, allowed=None):
        if not isinstance(value, list) or not value:
            error(path, "必须为非空列表")
            return []
        for index, item in enumerate(value):
            text(item, f"{path}[{index}]")
            if allowed is not None and isinstance(item, str) and item not in allowed:
                error(path, f"引用不存在或不兼容的素材：{item}")
        if len({str(item) for item in value}) != len(value):
            error(path, "重复条目")
        return [x for x in value if isinstance(x, str) and x]

    def beats(value, path):
        for key in ("trigger", "objective", "choice", "immediate", "near"):
            text(mapping(value, path).get(key), f"{path}.{key}", ("npc", "pressure"))

    if not isinstance(registry, dict):
        error("", "顶层必须为映射")
        return
    if type(registry.get("version")) is not int or registry["version"] != 1:
        error("version", "仅支持版本 1")
    if type(registry.get("legacy_weight")) is not int or registry["legacy_weight"] < 1:
        error("legacy_weight", "须为正整数")
    frameworks = mapping(registry.get("frameworks"), "frameworks")
    for name, package in frameworks.items():
        text(name, "name")
        package = mapping(package, str(name))
        eras = strings(package.get("eras"), f"{name}.eras", pools["时代与地点"]["时代"])
        aesthetics = strings(package.get("aesthetics"), f"{name}.aesthetics", pools["美学基调"])
        aesthetic_eras = pools.get("meta", {}).get("aesthetic_eras", {})
        for aesthetic in aesthetics:
            allowed = aesthetic_eras.get(aesthetic)
            if allowed and any(era not in allowed for era in eras):
                error(str(name), f"美学 {aesthetic} 不兼容所选时代")
        for key in ("rule", "social_rule"):
            text(package.get(key), f"{name}.{key}")
        strings(package.get("customs"), f"{name}.customs")
        places = mapping(package.get("places"), f"{name}.places")
        for place, row in places.items():
            row = mapping(row, f"{name}.{place}")
            strings(row.get("details"), f"{name}.{place}.details")
            profile = mapping(row.get("profile"), f"{name}.{place}.profile")
            for key in ("privacy", "visibility"):
                text(profile.get(key), f"{name}.{place}.{key}")
            for key in ("exits", "witnesses", "affordances", "pressure_modifiers"):
                strings(profile.get(key), f"{name}.{place}.{key}")
        pairs = package.get("pairs")
        if not isinstance(pairs, list) or not pairs:
            error(f"{name}.pairs", "须有角色搭配")
            pairs = []
        for index, pair in enumerate(pairs):
            path = f"{name}.pairs[{index}]"
            pair = mapping(pair, path)
            if pair.get("family") not in identity_profiles:
                error(path, "身份族没有行为画像")
            if pair.get("position") not in pools["玩家化身轴"]["社会位置"]:
                error(path, "玩家社会位置不存在")
            strings(pair.get("appellations"), path + ".appellations", pools["玩家化身轴"]["称谓"])
            text(pair.get("relationship_reason"), path + ".relationship_reason")
            npc = mapping(pair.get("npc"), path + ".npc")
            for key in ("role", "function", "authority", "resource", "limitation", "obligation", "exposure"):
                text(npc.get(key), path + ".npc." + key)
            player = mapping(pair.get("player"), path + ".player")
            for key in ("identity", "baseline", "reputation"):
                text(player.get(key), path + ".player." + key)
            strings(player.get("resources"), path + ".player.resources")
        covered_places, covered_pairs = set(), set()
        for label, activity in mapping(package.get("activities"), f"{name}.activities").items():
            path = f"{name}.activities.{label}"
            text(label, path)
            activity = mapping(activity, path)
            covered_places.update(strings(activity.get("places"), path + ".places", places))
            indices = activity.get("pairs")
            if not isinstance(indices, list) or not indices:
                error(path, "缺少配套人物索引")
            else:
                for index in indices:
                    if type(index) is not int or not 0 <= index < len(pairs):
                        error(path, "配套人物索引越界")
                    else:
                        covered_pairs.add(index)
            if activity.get("category") not in categories:
                error(path, "动作分类不存在")
            text(activity.get("action"), path + ".action", ("npc",))
            beats(activity.get("beats"), path + ".beats")
        if set(places) - covered_places:
            error(str(name), "存在没有活动入口的地点")
        if set(range(len(pairs))) - covered_pairs:
            error(str(name), "存在无法抽到的人物搭配")
        for label, pressure in mapping(package.get("pressures"), f"{name}.pressures").items():
            path = f"{name}.pressures.{label}"
            pressure = mapping(pressure, path)
            text(pressure.get("source"), path + ".source")
            engines = strings(pressure.get("engines"), path + ".engines", pools["张力引擎"])
            if len(engines) != 2:
                error(path, "压力模式须有两个不同引擎")
            beats(pressure.get("beats"), path + ".beats")
            for key in ("far_trigger", "far_consequence"):
                text(pressure.get(key), path + "." + key)
