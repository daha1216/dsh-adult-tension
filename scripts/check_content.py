#!/usr/bin/env python3
"""内容体检：检查 scripts/data/ 下各数据文件之间的同步与完整。

只读不写。加完内容（新地点、新身份、新处境……）跑一句：

  python scripts/check_content.py

ERROR 会让开局直接报错或校验失败；WARNING 是有兜底、戏味打折。
默认只读；可用 --fingerprint 输出当前素材指纹。
"""

from __future__ import annotations

import importlib.util
import hashlib
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scripts" / "data"
DATA_FILES = (
    "pools.yaml",
    "character_meta.yaml",
    "twists.yaml",
    "templates.yaml",
    "names.yaml",
    "identities.yaml",
    "locations.yaml",
    "character_pools.yaml",
    "location_profiles.yaml",
    "action_categories.yaml",
    "action_metadata.yaml",
    "identity_profiles.yaml",
    "twist_profiles.yaml",
)

POOL_TABLES = ("核心规则", "美学基调", "权力结构", "张力引擎", "社会规则",
               "压力来源", "身份侧", "处境侧", "反差轴")
TWIST_CATEGORIES = ("信息类", "人事类", "资源类", "制度类", "时限类", "关系类", "意外类")
SITUATION_BEAT_KEYS = ("trigger", "objective", "choice", "immediate", "near")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks = 0

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def ok(self, condition: bool, message: str, *, warn: bool = False) -> None:
        self.checks += 1
        if not condition:
            (self.warn if warn else self.error)(message)


def _load(name: str) -> Any:
    if yaml is None:
        raise SystemExit("ERROR: PyYAML is required; run: python -m pip install PyYAML")
    path = DATA / name
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SystemExit(f"ERROR: cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise SystemExit(f"ERROR: {path} 为空或顶层不是映射")
    return data


def _keys(items: Any) -> set[str]:
    return {str(k) for k in items} if isinstance(items, (dict, list)) else set()


def check_daily_opening(pools: dict[str, Any], report: Report) -> None:
    rules = (pools.get("meta") or {}).get("daily_opening")
    if not isinstance(rules, dict):
        report.error("meta.daily_opening 必须是映射")
        return
    sources = {"核心规则": pools.get("核心规则", []), "社会规则": pools.get("社会规则", []),
               "张力引擎": pools.get("张力引擎", []), "处境": pools.get("处境侧", []),
               "场景动作": (pools.get("场景动作") or {}).get("非交易靠近", [])}
    for field, source in sources.items():
        entries = rules.get(field)
        expected = dict if field == "处境" else list
        if not isinstance(entries, expected) or not entries:
            report.error(f"daily_opening.{field} 必须是非空{expected.__name__}")
            continue
        for name in entries:
            report.ok(isinstance(name, str) and name in source,
                      f"daily_opening.{field} 引用了不存在的旧素材：{name}")
        if isinstance(entries, list):
            report.ok(len(entries) == len(set(str(x) for x in entries)), f"daily_opening.{field} 有重复值")
    situations = rules.get("处境")
    if isinstance(situations, dict):
        for name, beats in situations.items():
            if not isinstance(beats, dict):
                report.error(f"daily_opening.处境.{name} 必须是映射")
                continue
            for field in SITUATION_BEAT_KEYS:
                value = beats.get(field)
                if not isinstance(value, str) or not value.strip():
                    report.error(f"daily_opening.处境.{name}.{field} 缺少文案")
                    continue
                try:
                    value.format(npc="NPC", pressure="")
                except (KeyError, ValueError, IndexError, AttributeError):
                    report.error(f"daily_opening.处境.{name}.{field} 占位符非法")


def check() -> Report:
    report = Report()
    commands_path = ROOT / "commands.yaml"
    report.ok(commands_path.exists(), "根目录缺少 commands.yaml")
    if commands_path.exists():
        try:
            commands_data = yaml.safe_load(commands_path.read_text(encoding="utf-8")) if yaml else None
            report.ok(isinstance(commands_data, dict) and bool(commands_data.get("command_categories")),
                      "commands.yaml 为空或缺少 command_categories 结构")
        except Exception as exc:
            report.error(f"commands.yaml YAML 语法解析失败：{exc}")

    pools = _load("pools.yaml")
    character_meta = _load("character_meta.yaml")
    twists = _load("twists.yaml")
    templates = _load("templates.yaml")
    names = _load("names.yaml")
    identities = _load("identities.yaml")
    locations = _load("locations.yaml")
    char_pools = _load("character_pools.yaml")
    meta = pools.get("meta") or {}

    # 1. 素材池 12 张表非空
    for table in POOL_TABLES:
        report.ok(bool(pools.get(table)), f"pools.yaml 缺少或非空：{table}")
    for table, groups in (("时代与地点", ("时代", "地点")),
                          ("场景动作", ("交易摊牌", "非交易靠近")),
                          ("玩家化身轴", ("称谓", "年龄段", "社会位置"))):
        node = pools.get(table) or {}
        for group in groups:
            report.ok(bool(node.get(group)), f"pools.yaml「{table}」缺少组：{group}")

    places = set(pools.get("时代与地点", {}).get("地点") or [])
    families = set(pools.get("身份侧") or [])
    situations = set(pools.get("处境侧") or [])
    positions = set(pools.get("玩家化身轴", {}).get("社会位置") or [])
    age_bands = set(pools.get("玩家化身轴", {}).get("年龄段") or [])
    scene_trade = set(pools.get("场景动作", {}).get("交易摊牌") or [])
    scene_near = set(pools.get("场景动作", {}).get("非交易靠近") or [])

    # 2. 地点 ↔ locations.yaml
    for place in sorted(places - _keys(locations)):
        report.error(f"地点「{place}」在 locations.yaml 没有房间细节（开局会报错）")
    report.checks += 1
    for place in sorted(_keys(locations) - places):
        report.warn(f"locations.yaml 的「{place}」不在地点池里（永远抽不到）")
    report.checks += 1

    # 3. 身份族 ↔ identities.yaml
    npc_identities = identities.get("npc") or {}
    for family in sorted(families - _keys(npc_identities)):
        report.error(f"身份族「{family}」在 identities.yaml 没有具体身份（开局会报错）")
    report.checks += 1
    for family in sorted(_keys(npc_identities) - families):
        report.warn(f"identities.yaml 的「{family}」不在身份族池里（永远抽不到）")
    report.checks += 1

    # 4. 处境 ↔ templates.situation_beats（缺模板会静默套用通用模板，戏味打折）
    beats = templates.get("situation_beats") or {}
    for kind in sorted(situations - _keys(beats)):
        report.error(f"处境「{kind}」在 templates.yaml 没有剧情模板（会静默套用「今夜话没说完」）")
    report.checks += 1
    for kind in sorted(_keys(beats) - situations):
        report.warn(f"templates.yaml 的处境模板「{kind}」不在处境池里（永远用不到）")
    report.checks += 1
    report.ok("今夜话没说完" in beats, "templates.yaml 缺少兜底处境模板「今夜话没说完」")
    for kind, beat in beats.items():
        if isinstance(beat, dict):
            missing = [key for key in SITUATION_BEAT_KEYS if not beat.get(key)]
            report.ok(not missing, f"处境模板「{kind}」缺键：{missing}")

    # 5. 玩家化身轴 ↔ 映射表
    player_identities = identities.get("player") or {}
    relations = character_meta.get("社会位置关系") or {}
    band_map = character_meta.get("年龄段区间") or {}
    for position in sorted(positions - _keys(player_identities)):
        report.error(f"社会位置「{position}」在 identities.yaml 没有玩家身份条目（开局会报错）")
    report.checks += 1
    for position in sorted(positions - _keys(relations)):
        report.warn(f"社会位置「{position}」在 character_meta.yaml 没有关系起点（按陌生直连兜底）")
    report.checks += 1
    for band in sorted(age_bands - _keys(band_map)):
        report.warn(f"年龄段「{band}」在 character_meta.yaml 没有区间（按 28-36 兜底）")
    report.checks += 1

    # 6. 场景动作 ↔ 句式模板（新增动作允许运行时通用兜底）
    near_beats = templates.get("near_beats") or {}
    trade_beats = templates.get("trade_beats") or {}
    for action in sorted(scene_near - _keys(near_beats)):
        report.warn(f"非交易靠近「{action}」在 templates.yaml 没有专属句式（用兜底句）")
    report.checks += 1
    for action in sorted(scene_trade - _keys(trade_beats)):
        report.warn(f"交易摊牌「{action}」在 templates.yaml 没有专属句式（用兜底句）")
    report.checks += 1
    report.ok(bool(templates.get("action_fallback_near")) and bool(templates.get("action_fallback_trade")),
              "templates.yaml 缺少动作句式兜底（action_fallback_near/trade）")
    report.ok(bool(templates.get("suggestion_default")) and bool(templates.get("suggestion_extras")),
              "templates.yaml 缺少建议动作模板（suggestion_default/suggestion_extras）")
    # suggestion_player_first 按键名精确匹配场景动作（fill_opening.suggested_actions 的
    # first_map.get(action)）：死键=改名/删条目后留下的旧键，静默失去命中；镜像方向是
    # 池内动作缺玩家优先建议，缺失走 suggestion_default。两向都是 WARNING（有兜底，戏味打折）。
    player_first = templates.get("suggestion_player_first") or {}
    for action in sorted(_keys(player_first) - (scene_near | scene_trade)):
        report.warn(f"suggestion_player_first 的「{action}」不在场景动作两桶里（死键，永远命中不到）")
    report.checks += 1
    for action in sorted(scene_near - _keys(player_first)):
        report.warn(f"非交易靠近「{action}」没有玩家优先建议（走 suggestion_default 兜底）")
    report.checks += 1

    # 7. 压力策略 / 反差轴 ↔ 文案
    axes = character_meta.get("决策轴") or {}
    strategies = set(axes.get("压力策略") or [])
    withdrawal = templates.get("withdrawal") or {}
    responses = templates.get("pressure_response") or {}
    for strategy in sorted(strategies - _keys(withdrawal)):
        report.warn(f"压力策略「{strategy}」在 templates.yaml 没有撤回信号（用通用撤回）")
    report.checks += 1
    for strategy in sorted(strategies - _keys(responses)):
        report.warn(f"压力策略「{strategy}」在 templates.yaml 没有压力反应（按「正面解决」兜底）")
    report.checks += 1
    for name, entry in responses.items():
        report.ok(isinstance(entry, list) and len(entry) == 4,
                  f"pressure_response「{name}」必须恰好四句（低/中/高/临界）")
    contrasts = set(pools.get("反差轴") or [])
    contrast_line = templates.get("contrast_line") or {}
    for item in sorted(contrasts - _keys(contrast_line)):
        report.warn(f"反差轴「{item}」在 templates.yaml 没有专属台词（用通用句）")
    report.checks += 1
    report.ok(bool(templates.get("orientations")), "templates.yaml 缺少吸引取向清单（orientations）")

    check_daily_opening(pools, report)

    # 8. meta 行为开关引用合法
    engines = set(pools.get("张力引擎") or [])
    for name in meta.get("leverage_engines") or []:
        report.ok(name in engines, f"meta.leverage_engines 引用了不存在的张力引擎：{name}")
    for name in meta.get("situation_leverage") or []:
        report.ok(name in situations, f"meta.situation_leverage 引用了不存在的处境：{name}")
    for name in meta.get("gate_aesthetics") or []:
        report.ok(name in set(pools.get("美学基调") or []),
                  f"meta.gate_aesthetics 引用了不存在的美学基调：{name}")
    for name in meta.get("timed_situations") or []:
        report.ok(name in situations, f"meta.timed_situations 引用了不存在的处境：{name}")
    for name in meta.get("timed_pressures") or []:
        report.ok(name in set(pools.get("压力来源") or []),
                  f"meta.timed_pressures 引用了不存在的压力来源：{name}")
    weights = meta.get("identity_weights") or {}
    for name in sorted(_keys(weights) - families):
        report.error(f"meta.identity_weights 引用了不存在的身份族：{name}（疑似笔误）")
    report.checks += 1
    for name in sorted(families - _keys(weights)):
        report.warn(f"身份族「{name}」没配抽取权重（按 8 计）")
    report.checks += 1

    # 8b. location_eras 和解名单引用合法（形状=地点→非空时代列表；与 roll_opening 的
    # 运行时校验同规约，把事故前移到体检层。只能抓错拼，抓不到漏登——漏登靠测试兜底）。
    era_map = meta.get("location_eras")
    eras_pool = set(pools.get("时代与地点", {}).get("时代") or [])
    report.ok(era_map is None or isinstance(era_map, dict),
              "meta.location_eras 必须是 地点→非空时代列表 映射")
    if isinstance(era_map, dict):
        for place, era_list in sorted(era_map.items()):
            report.ok(place in places,
                      f"meta.location_eras 引用了不存在的地点：{place}")
            report.ok(isinstance(era_list, list) and bool(era_list)
                      and all(str(era) in eras_pool for era in era_list),
                      f"meta.location_eras.{place} 必须是全部存在于时代池的非空列表")

    # 8c. 三表两两互斥：张力引擎/压力来源/处境侧不得逐字重名（改名后防再生）。
    # 撞名冗余会进已提交状态（引擎→world.tension_engines、压力→pressure_seeds.immediate
    # ＋player.knowledge、far 事件 semantic_key 内嵌引擎名），near+far 描述同一件事且
    # 语义键不同、无法去重；分层用近义词区分（引擎=动态推到极点/压力=外力逼近/处境=当下状态）。
    pressures = set(pools.get("压力来源") or [])
    for label, left, right in (("张力引擎×压力来源", engines, pressures),
                               ("张力引擎×处境侧", engines, situations),
                               ("压力来源×处境侧", pressures, situations)):
        for word in sorted(left & right):
            report.error(f"三表互斥违反：{label} 逐字重名「{word}」（分层请用近义词区分）")
    report.checks += 1

    # 9. 人物生成元数据
    tendency = character_meta.get("人物生成倾向") or {}
    report.ok(bool(tendency) and all(isinstance(v, int) and v > 0 for v in tendency.values())
              and sum(tendency.values()) == 100,
              f"人物生成倾向权重必须全为正整数且总和为 100（当前 {sum(tendency.values()) or '空'}）")
    for axis in ("核心价值", "压力策略", "关系姿态"):
        report.ok(len(axes.get(axis) or []) >= 2, f"决策轴「{axis}」至少需要两项")
    report.ok(bool(character_meta.get("配角功能")), "character_meta.yaml 缺少配角功能清单")

    # 10. 转折池七类
    report.ok(tuple(twists.keys()) == TWIST_CATEGORIES,
              f"twists.yaml 必须严格七类且顺序不变：{TWIST_CATEGORIES}")
    for category in TWIST_CATEGORIES:
        report.ok(bool(twists.get(category)), f"转折池「{category}」为空")

    # 11. 角色三池与起名池
    for key in ("表层风味", "口癖"):
        for group, items in (char_pools.get(key) or {}).items():
            for item in items or []:
                report.ok(len(str(item)) <= 8, f"{key}「{item}」超过 8 字会被加载器筛掉")
    report.ok(bool(char_pools.get("外观轴")), "character_pools.yaml 缺少外观轴")
    report.ok(bool(names.get("surnames")) and bool(names.get("given_male")) and bool(names.get("given_female")),
              "names.yaml 缺少姓氏、男名池（given_male）或女名池（given_female）")

    # 12. 体验层体检：重复率、权重偏斜、地点覆盖和动作分布只报警，不阻断加载。
    def _all_strings(value: Any):
        if isinstance(value, dict):
            for child in value.values():
                yield from _all_strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from _all_strings(child)
        elif isinstance(value, str) and value.strip():
            yield value.strip()

    for filename, data in (("names.yaml", names), ("pools.yaml", pools)):
        values = list(_all_strings(data))
        duplicates = len(values) - len(set(values))
        report.ok(duplicates >= 0, f"{filename} 重复值统计完成：{duplicates}（跨池复用不再作为错误）")
    location_values = locations
    if isinstance(location_values, dict):
        counts = [len(items) for items in location_values.values() if isinstance(items, list)]
        report.ok(all(isinstance(items, list) and items for items in location_values.values()),
                  "locations.yaml 每个地点族至少有一个具体变体")
    profiles = _load("location_profiles.yaml") if (DATA / "location_profiles.yaml").exists() else {}
    report.ok(set(profiles) == places,
              f"location_profiles.yaml 必须覆盖全部地点族（缺少 {sorted(places - set(profiles))}，多出 {sorted(set(profiles) - places)}）")
    for place, profile in profiles.items():
        report.ok(isinstance(profile, dict) and all(profile.get(key) for key in ("privacy", "visibility", "exits", "witnesses", "affordances", "pressure_modifiers")),
                  f"地点画像「{place}」缺少 privacy/visibility/exits/witnesses/affordances/pressure_modifiers")
    if weights:
        total_weight = sum(int(value) for value in weights.values())
        report.ok(total_weight > 0, f"身份族权重总和为 {total_weight}，抽取层已启用近期冷却")
    action_categories_path = DATA / "action_categories.yaml"
    action_categories = _load("action_categories.yaml") if action_categories_path.exists() else {}
    classified_actions = {item for items in action_categories.values() if isinstance(items, list) for item in items}
    report.ok(classified_actions == scene_near,
              f"action_categories.yaml 必须逐项覆盖非交易靠近动作（缺少 {sorted(scene_near - classified_actions)}，多出 {sorted(classified_actions - scene_near)}）")
    report.checks += 1
    action_total = len(scene_trade) + len(scene_near)
    category_sizes = [len(items) for items in action_categories.values() if isinstance(items, list)]
    report.ok(len(category_sizes) >= 4 and all(size > 0 for size in category_sizes),
              "场景动作分类至少覆盖四类且每类非空")
    action_metadata = _load("action_metadata.yaml")
    report.ok(set(action_categories) <= set(action_metadata),
              "action_metadata.yaml 必须覆盖所有场景动作分类")
    for category in action_categories:
        profile = action_metadata.get(category) or {}
        report.ok(all(profile.get(key) for key in ("function", "visibility", "escalation")),
                  f"场景动作元数据「{category}」缺少 function/visibility/escalation")
    identity_profiles = _load("identity_profiles.yaml")
    report.ok(families <= set(identity_profiles),
              "identity_profiles.yaml 必须覆盖所有身份族")
    for family in families:
        report.ok(all((identity_profiles.get(family) or {}).get(key)
                      for key in ("negotiation_style", "conflict_response", "repair_style",
                                  "public_private_shift", "follow_up_style", "exit_preference",
                                  "evidence_habit")),
                  f"身份行为画像「{family}」字段不完整")
    twist_profiles = _load("twist_profiles.yaml")
    report.ok(set(TWIST_CATEGORIES) <= set(twist_profiles),
              "twist_profiles.yaml 必须覆盖七个转折类别")
    for category in TWIST_CATEGORIES:
        profile = twist_profiles.get(category) or {}
        report.ok(all(key in profile for key in ("affects", "escalation", "opens_exit", "introduces_third_party")),
                  f"转折画像「{category}」字段不完整")

    # 13. 时代分名池：era 键必须在时代池里，且每组 surnames/given_male/given_female 非空
    era_pool_table = names.get("eras") or {}
    era_names = set(pools.get("时代与地点", {}).get("时代") or [])
    for era_name, pool in era_pool_table.items():
        report.ok(str(era_name) in era_names,
                  f"names.yaml eras「{era_name}」不在时代池里（永远抽不到）")
        report.ok(isinstance(pool, dict) and bool(pool.get("surnames")) and bool(pool.get("given_male")) and bool(pool.get("given_female")),
                  f"names.yaml eras「{era_name}」的 surnames/given_male/given_female 必须非空")

    # 13. 双语态结构契约：生成器必须输出 surface / inner / switch_conditions 三键。
    # live_slice 只读取 surface，避免依赖长字符串中的中文标记切分。
    try:
        spec = importlib.util.spec_from_file_location(
            "adult_tension_check_fill", ROOT / "scripts" / "fill_opening.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load fill_opening.py")
        fill_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fill_mod)
        for flavor, quirk in (("—", "—"), ("冷淡疏离", "话留半句")):
            voice = fill_mod.voice_filter(
                {"表层风味": flavor, "口癖": quirk, "反差轴": ""}, "测试身份", templates)
            report.ok(
                isinstance(voice, dict)
                and set(("surface", "inner", "switch_conditions")) <= set(voice)
                and all(isinstance(voice.get(key), str) and voice.get(key).strip() for key in ("surface", "inner"))
                and isinstance(voice.get("switch_conditions"), list)
                and bool(voice.get("switch_conditions")),
                "fill_opening.voice_filter 必须输出完整的结构化双语态",
            )
    except Exception as exc:  # noqa: BLE001 - 加载失败本身就是体检要抓的问题
        report.checks += 1
        report.error(f"双语态标记检查无法执行：{exc}")

    return report


def content_fingerprint() -> str:
    digest = hashlib.sha256()
    for name in DATA_FILES:
        digest.update(name.encode("utf-8"))
        digest.update((DATA / name).read_bytes())
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fingerprint", action="store_true", help="输出 scripts/data 的当前指纹")
    args = parser.parse_args(argv)
    report = check()
    for message in report.errors:
        print(f"ERROR: {message}")
    for message in report.warnings:
        print(f"WARNING: {message}")
    if args.fingerprint:
        print(f"CONTENT_FINGERPRINT: {content_fingerprint()}")
    if report.errors:
        print(f"\n未通过：{len(report.errors)} 个 ERROR、{len(report.warnings)} 个 WARNING"
              f"（共 {report.checks} 项检查）")
        return 1
    suffix = f"，{len(report.warnings)} 个 WARNING" if report.warnings else ""
    print(f"OK: 内容数据同步完好（{report.checks} 项检查{suffix}）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover
        pass
    raise SystemExit(main())
