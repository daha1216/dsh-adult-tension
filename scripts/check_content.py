#!/usr/bin/env python3
"""内容体检：检查 scripts/data/ 下各数据文件之间的同步与完整。

只读不写。加完内容（新地点、新身份、新处境……）跑一句：

  python scripts/check_content.py

ERROR 会让开局直接报错或校验失败；WARNING 是有兜底、戏味打折。
全绿输出 OK 与检查项数。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scripts" / "data"

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


def check() -> Report:
    report = Report()
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

    # 6. 场景动作 ↔ 句式模板（有通用兜底，WARNING）
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
    report.ok(bool(names.get("surnames")) and bool(names.get("given")),
              "names.yaml 缺少姓氏或名字池")

    # 12. 时代分名池：era 键必须在时代池里，且每组 surnames/given 非空
    era_pool_table = names.get("eras") or {}
    era_names = set(pools.get("时代与地点", {}).get("时代") or [])
    for era_name, pool in era_pool_table.items():
        report.ok(str(era_name) in era_names,
                  f"names.yaml eras「{era_name}」不在时代池里（永远抽不到）")
        report.ok(isinstance(pool, dict) and bool(pool.get("surnames")) and bool(pool.get("given")),
                  f"names.yaml eras「{era_name}」的 surnames/given 必须非空")

    # 13. 双语态格式契约：主 NPC 语态字段必须同时带「表层语态：」「里层语态：」两个标记。
    # live_slice 按「里层」首次出现处切分（角色设计.md「书写格式」），缺任一标记，
    # 里层台词会被整段当表层输出。这里直接验证生成器 fill_opening.voice_filter 的产物。
    try:
        spec = importlib.util.spec_from_file_location(
            "adult_tension_check_fill", ROOT / "scripts" / "fill_opening.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load fill_opening.py")
        fill_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fill_mod)
        for flavor, quirk in (("—", "—"), ("冷淡疏离", "话留半句")):
            text = fill_mod.voice_filter(
                {"表层风味": flavor, "口癖": quirk, "反差轴": ""}, "测试身份", templates)
            report.ok("表层语态：" in text and "里层语态：" in text,
                      "fill_opening.voice_filter 产物缺少「表层语态：/里层语态：」标记"
                      "（live_slice 会把里层台词当表层输出）")
    except Exception as exc:  # noqa: BLE001 - 加载失败本身就是体检要抓的问题
        report.checks += 1
        report.error(f"双语态标记检查无法执行：{exc}")

    return report


def main() -> int:
    report = check()
    for message in report.errors:
        print(f"ERROR: {message}")
    for message in report.warnings:
        print(f"WARNING: {message}")
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
