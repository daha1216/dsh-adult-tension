#!/usr/bin/env python3
"""Roll all structural dice for a new opening.

Parses references/素材库.md and references/角色设计.md at runtime, so the
markdown files stay the single source of truth: edit the tables and the
next roll picks up the changes. Output is a human-readable dice sheet the
model copies into the opening draft; fit/adjudication stays with the
model per references/开局流程.md「随机性与多样性协议」.

Usage:
    python scripts/roll_opening.py [--seed N] [--genre 大类] [--lock 字段=值]
                                   [--no-custom] [--no-history]
                                   [--mains N] [--twist]
                                   [--list-genres]

The script reads the material tables at runtime; ``--list-genres`` only lists
the supported genre axes and does not write opening history.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

CUSTOM = "【系统自拟：现场创造，不复用近期用过的设定】"

DANG_REAL = "现实"
DANG_HALF = "半架空"
DANG_FULL = "强架空"
SUPPLEMENT_TITLES = {DANG_HALF + "增补": DANG_HALF, DANG_FULL + "增补": DANG_FULL}

TONE_AXES = ["时代与技术", "地域气质", "社会形态", "叙事基调", "美学基调"]
WORLD_RULE_AXES = ["核心规则来源", "掌握范围", "生效代价", "变化阶段"]
DECISION_AXES = ["核心价值", "压力策略", "关系姿态"]
HISTORY_LIMIT = 30
HISTORY_RECENT_LIMIT = 5
HISTORY_CANDIDATE_LIMIT = 16
HISTORY_DIMENSIONS = (
    "dang", "world_rule", "genre", "engine", "shell", "action",
    "identity", "situation", "relation", "value", "strategy", "stance",
)
HISTORY_PAIRS = (
    ("dang", "world_rule"), ("genre", "world_rule"),
    ("engine", "shell"), ("shell", "action"),
    ("identity", "situation"), ("identity", "strategy"),
    ("value", "strategy"), ("relation", "stance"),
)

LOCK_ALIASES = {
    "世界观档": "dang", "档位": "dang",
    "时代与技术": "era", "地域气质": "region", "社会形态": "society",
    "叙事基调": "tone", "美学基调": "aesthetic",
    "核心规则来源": "world_rule", "世界规则": "world_rule",
    "掌握范围": "world_reach", "生效代价": "world_cost", "变化阶段": "world_phase",
    "大类": "genre", "题材": "genre",
    "主引擎": "engine", "副引擎": "sub_engine", "咬合": "mesh",
    "壳": "shell", "制度与场合壳": "shell",
    "tier": "tier",
    "模式": "mode", "运行模式": "mode",
    "权力结构": "power", "权力": "power",
    "配角数": "cast",
    "主npc身份": "identity", "身份": "identity",
    "主npc处境": "situation", "处境": "situation",
    "开场动作": "action", "动作": "action",
    "关系阶段": "relation_stage", "反差轴": "contrast",
    "核心价值": "core_value", "压力策略": "pressure_strategy",
    "关系姿态": "relationship_stance",
}

AXIS_LOCK_KEYS = {"时代与技术": "era", "地域气质": "region", "社会形态": "society",
                  "叙事基调": "tone", "美学基调": "aesthetic"}
WORLD_RULE_LOCK_KEYS = {
    "核心规则来源": "world_rule", "掌握范围": "world_reach",
    "生效代价": "world_cost", "变化阶段": "world_phase",
}
DECISION_LOCK_KEYS = {
    "核心价值": "core_value", "压力策略": "pressure_strategy",
    "关系姿态": "relationship_stance",
}

MODE_LABELS = ["可靠 (reliable)", "沉浸 (immersive)"]
POWER_LABELS = ["玩家高位 (player_high)", "NPC高位 (npc_high)", "对等 (equal)", "可切换 (switchable)"]
MESH_LABELS = ["单引擎", "双引擎"]
MODE_LOCK_VALUES = set(MODE_LABELS) | {"可靠", "沉浸", "reliable", "immersive"}
POWER_LOCK_VALUES = set(POWER_LABELS) | {
    "玩家高位", "NPC高位", "对等", "可切换",
    "player_high", "npc_high", "equal", "switchable",
}


# ---------------------------------------------------------------- parsing

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def headings(lines: list[str]) -> list[tuple[int, int, str]]:
    out = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def section(lines: list[str], title_prefix: str, level: int = 2) -> list[str]:
    """Lines of the section whose heading starts with title_prefix."""
    heads = headings(lines)
    for idx, (i, lv, title) in enumerate(heads):
        if lv == level and title.startswith(title_prefix):
            end = len(lines)
            for j, jlv, _ in heads[idx + 1:]:
                if jlv <= level:
                    end = j
                    break
            return lines[i + 1:end]
    return []


def subsections(lines: list[str], level: int = 3) -> list[tuple[str, list[str]]]:
    heads = [(i, lv, t) for i, lv, t in headings(lines) if lv == level]
    out = []
    for idx, (i, _, title) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        out.append((title, lines[i + 1:end]))
    return out


def before_subsections(lines: list[str], level: int = 3) -> list[str]:
    marker = "#" * level + " "
    for index, line in enumerate(lines):
        if line.startswith(marker):
            return lines[:index]
    return lines


def strip_paren(text: str) -> str:
    return re.sub(r"（[^）]*）\s*$", "", text.strip()).strip()


def parse_axes(lines: list[str]) -> dict[str, list[str]]:
    """Bullets of form `- 轴名：项、项、项`."""
    axes: dict[str, list[str]] = {}
    for line in lines:
        m = re.match(r"^-\s*([^：]+)：(.+)$", line.strip())
        if not m or "、" not in m.group(2):
            continue
        options = [strip_paren(x) for x in m.group(2).split("、") if strip_paren(x)]
        if len(options) >= 2:
            axes[m.group(1).strip()] = options
    return axes


def parse_table(lines: list[str]) -> list[tuple[str, str]]:
    rows = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        rows.append((cells[0], cells[1]))
    return [(a, b) for a, b in rows
            if a not in {"壳类", "族", "类型", "档位", "序", "项目", "大类", "动作族"}]


def parse_exclusions(lines: list[str]) -> dict[str, set[str]]:
    exclusions: dict[str, set[str]] = {}
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "池" or re.fullmatch(r":?-+:?", cells[0]):
            continue
        exclusions[cells[0]] = {item.strip() for item in cells[1].split("、") if item.strip()}
    return exclusions


def parse_numbered(lines: list[str]) -> list[str]:
    return [m.group(1).strip() for line in lines
            if (m := re.match(r"^\d+\.\s+(.+)$", line.strip()))]


def parse_dun_list(lines: list[str], min_items: int = 3,
                   max_item_len: int | None = None) -> list[str]:
    for line in lines:
        s = line.strip()
        if s.startswith(("|", "#", "-", ">", "`")) or s.endswith("：") or "、" not in s:
            continue
        items = [x.strip().rstrip("。") for x in s.rstrip("。").split("、")]
        items = [i for i in items if i]
        if len(items) < min_items:
            continue
        if max_item_len is not None and any(
                len(i) > max_item_len or "，" in i or "。" in i for i in items):
            continue
        return items
    return []


def load_materials(refs: Path) -> dict:
    lib = read_text(refs / "素材库.md").splitlines()
    chars = read_text(refs / "角色设计.md").splitlines()
    world = read_text(refs / "世界运转.md").splitlines()

    m: dict = {}
    m["dang_pool"] = [DANG_REAL, DANG_HALF, DANG_FULL]
    m["tone_axes"] = parse_axes(section(lib, "世界基调轴"))
    world_rule_sec = section(lib, "世界核心规则轴")
    m["world_rule_base"] = parse_axes(before_subsections(world_rule_sec))
    m["world_rule_supp"] = {
        SUPPLEMENT_TITLES[title]: parse_axes(body)
        for title, body in subsections(world_rule_sec)
        if title in SUPPLEMENT_TITLES
    }
    m["real_exclusions"] = parse_exclusions(section(lib, "现实档排除"))
    m["timescape"] = parse_axes(section(lib, "季节与时景轴"))
    m["scene_actions"] = parse_table(section(lib, "开场动作母型"))
    m["genres"] = {title: parse_axes(body) for title, body in subsections(section(lib, "大类细分轴"))}
    m["genre_dangs"] = {
        name: {value.strip() for value in values.split("、") if value.strip()}
        for name, values in parse_table(section(lib, "大类兼容档位"))
    }

    engine_sec = section(lib, "张力引擎")
    base, supplements = [], {}
    for title, body in subsections(engine_sec):
        if title in SUPPLEMENT_TITLES:
            grouped = {}
            for family, family_body in subsections(body, level=4):
                items = parse_numbered(family_body)
                if items:
                    grouped[re.sub(r"^\d+\.\s*", "", family)] = items
            if grouped:
                supplements[SUPPLEMENT_TITLES[title]] = grouped
            continue
        items = parse_numbered(body)
        if items:
            base.append((re.sub(r"^\d+\.\s*", "", title), items))
    m["engine_base"], m["engine_supp"] = base, supplements

    shell_sec = section(lib, "制度与场合壳")
    m["shell_base"] = parse_table(before_subsections(shell_sec))
    m["shell_supp"] = {SUPPLEMENT_TITLES[t]: parse_table(b)
                       for t, b in subsections(shell_sec) if t in SUPPLEMENT_TITLES}

    ident_sec = section(lib, "身份侧")
    m["identity_base"] = parse_table(before_subsections(ident_sec))
    m["identity_supp"] = {SUPPLEMENT_TITLES[t]: parse_table(b)
                          for t, b in subsections(ident_sec) if t in SUPPLEMENT_TITLES}

    situ_sec = section(lib, "处境侧")
    m["situation_base"] = parse_table(before_subsections(situ_sec))
    m["situation_supp"] = {SUPPLEMENT_TITLES[t]: parse_table(b)
                           for t, b in subsections(situ_sec) if t in SUPPLEMENT_TITLES}

    m["contrast"] = parse_dun_list(section(lib, "反差轴"), 8, max_item_len=14)
    m["relation_stages"] = parse_dun_list(section(lib, "关系阶段"), 8, max_item_len=14)

    m["flavors"] = [f for f in parse_dun_list(section(chars, "表层风味"), 5, max_item_len=8)
                    if f != "系统自拟"]
    m["appearance"] = parse_axes(section(chars, "外观与气质轴"))
    m["speech"] = parse_dun_list(section(chars, "口癖与语感"), 8, max_item_len=8)
    m["decision_axes"] = parse_axes(section(chars, "人物决策轴"))
    m["twists"] = {title: parse_dun_list(body, 3)
                   for title, body in subsections(section(world, "中期剧情转折"))}

    weights = {}
    for line in section(chars, "人物生成原则"):
        wm = re.match(r"^\s{2,}([a-z_]+):\s*(\d+)\s*$", line)
        if wm:
            weights[wm.group(1)] = int(wm.group(2))
    m["profile_weights"] = weights

    funcs: list[str] = []
    for line in section(chars, "配角"):
        fm = re.search(r"配角功能独立生成：(.+?)。", line)
        if fm:
            funcs = [x.strip() for part in fm.group(1).split("、") for x in part.split("或")]
            funcs = [f for f in funcs if f and f != "系统自拟"]
            break
    m["supporting_functions"] = funcs
    return m


# ---------------------------------------------------------------- rolling

class Roller:
    def __init__(self, materials: dict, rng: random.Random, allow_custom: bool = True):
        self.m = materials
        self.rng = rng
        self.allow_custom = allow_custom

    def pick(self, pool: list, custom: bool | None = None):
        """Uniform pick; with a virtual 系统自拟 tail row unless disabled."""
        if not pool:
            return CUSTOM
        use_custom = self.allow_custom if custom is None else (custom and self.allow_custom)
        n = len(pool)
        if use_custom and self.rng.randrange(n + 1) == n:
            return CUSTOM
        return pool[self.rng.randrange(n)]

    def pick_range(self, pool: list):
        return pool[self.rng.randrange(len(pool))]

    def allowed(self, dang: str, pool_name: str, value: str) -> bool:
        return dang != DANG_REAL or value not in self.m["real_exclusions"].get(pool_name, set())

    def tone_pool(self, dang: str, axis: str) -> list[str]:
        return [value for value in self.m["tone_axes"].get(axis, [])
                if self.allowed(dang, axis, value)]

    def world_rule_pool(self, dang: str, axis: str) -> list[str]:
        base = self.m["world_rule_base"].get(axis, [])
        extra = self.m["world_rule_supp"].get(dang, {}).get(axis, [])
        return base + extra

    def genre_axis_pool(self, dang: str, genre: str, axis: str) -> list[str]:
        pool_name = f"大类/{genre}/{axis}"
        return [value for value in self.m["genres"].get(genre, {}).get(axis, [])
                if self.allowed(dang, pool_name, value)]

    def engine_pool(self, dang: str) -> list[tuple[str, list[str]]]:
        supplements = self.m["engine_supp"].get(dang, {})
        pool = [(family, [item for item in items + supplements.get(family, [])
                          if self.allowed(dang, "张力引擎项", item)])
                for family, items in self.m["engine_base"]
                if self.allowed(dang, "张力引擎族", family)]
        return [(family, items) for family, items in pool if items]

    def roll_engine(self, dang: str, exclude: str | None = None):
        pool = self.engine_pool(dang)
        pool = [(f, items) for f, items in pool if f != exclude]
        fam = self.pick(pool)
        if fam == CUSTOM:
            return CUSTOM, CUSTOM
        family, items = fam
        item = self.pick(items)
        return family, item

    def shell_pool(self, dang: str) -> list[tuple[str, str]]:
        pool = [(name, examples) for name, examples in self.m["shell_base"]
                if self.allowed(dang, "制度与场合壳", name)]
        pool.extend(self.m["shell_supp"].get(dang, []))
        return pool

    def identity_pool(self, dang: str) -> list[tuple[str, str]]:
        pool = []
        sources = self.m["identity_base"] + self.m["identity_supp"].get(dang, [])
        for family, seeds in sources:
            if not self.allowed(dang, "身份族", family):
                continue
            allowed_seeds = [seed.strip() for seed in seeds.split("、")
                             if seed.strip() and self.allowed(dang, "身份种子", seed.strip())]
            if allowed_seeds:
                pool.append((family, "、".join(allowed_seeds)))
        return pool

    def situation_pool(self, dang: str) -> list[tuple[str, str]]:
        pool = [(name, hint) for name, hint in self.m["situation_base"]
                if self.allowed(dang, "处境类型", name)]
        pool.extend(self.m["situation_supp"].get(dang, []))
        return pool

    def roll_weighted(self) -> str:
        weights = self.m["profile_weights"]
        if not weights:
            return "ordinary_natural"
        total = sum(weights.values())
        r = self.rng.randrange(total)
        for key, w in weights.items():
            r -= w
            if r < 0:
                return key
        return next(iter(weights))

    def roll_appearance(self, count: int) -> str:
        axes = self.m["appearance"]
        if not axes or count <= 0:
            return "—"
        names = self.rng.sample(list(axes), min(count, len(axes)))
        return "、".join(f"{n}={self.pick(axes[n])}" for n in names)

    def roll_relation_stage(self, stages: list[str]) -> str:
        stage = self.pick(stages)
        if stage == "单向暗恋（方向另抽）":
            return f"单向暗恋（{self.pick_range(['玩家方', 'NPC方'])}）"
        return stage


def resolve_genre(genres: dict, wanted: str) -> str | None:
    for name in genres:
        if name == wanted or wanted in name:
            return name
    return None


def normalize_history_entry(entry) -> dict[str, str] | None:
    if (isinstance(entry, (list, tuple)) and len(entry) == 3
            and all(isinstance(value, str) and value for value in entry)):
        return {"engine": entry[0], "shell": entry[1], "identity": entry[2]}
    if isinstance(entry, dict):
        normalized = {
            key: value for key, value in entry.items()
            if key in HISTORY_DIMENSIONS and isinstance(value, str) and value
        }
        return normalized or None
    return None


def history_combo(record) -> tuple[str, str, str]:
    normalized = normalize_history_entry(record) or {}
    return (normalized.get("engine", ""), normalized.get("shell", ""),
            normalized.get("identity", ""))


def load_history(path: Path) -> list[dict[str, str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except OSError:
        return []

    history: list[dict[str, str]] = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        normalized = normalize_history_entry(entry)
        if normalized:
            history.append(normalized)
    return history[-HISTORY_LIMIT:]


def append_history(path: Path, record) -> None:
    history = load_history(path)
    normalized = normalize_history_entry(record)
    if not normalized:
        return
    history.append(normalized)
    kept = history[-HISTORY_LIMIT:]
    path.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in kept),
        encoding="utf-8",
    )


def history_value(value: str | None) -> str | None:
    if not value or value == "—" or CUSTOM in value:
        return None
    return value


def coverage_score(record: dict[str, str], history: list[dict[str, str]],
                   hard_combinations: set[tuple[str, str, str]] | None = None) -> int:
    """Lower is more varied; recent matches and repeated pairs cost more."""
    score = 0
    recent = history[-HISTORY_LIMIT:]
    for distance, old in enumerate(reversed(recent), start=1):
        recent_bonus = 1 if distance <= HISTORY_RECENT_LIMIT else 0
        for key in HISTORY_DIMENSIONS:
            current_value = history_value(record.get(key))
            if current_value and current_value == history_value(old.get(key)):
                score += 1 + recent_bonus
        for first, second in HISTORY_PAIRS:
            current_pair = (history_value(record.get(first)), history_value(record.get(second)))
            old_pair = (history_value(old.get(first)), history_value(old.get(second)))
            if all(current_pair) and current_pair == old_pair:
                score += 3 + 2 * recent_bonus

    hard = hard_combinations or set()
    if history_combo(record) in hard:
        score += 10_000
    return score


def roll_opening(materials: dict, rng: random.Random, locks: dict[str, str],
                 genre: str | None, allow_custom: bool,
                 mains: int = 1,
                 recent_combinations: set[tuple[str, str, str]] | None = None,
                 recent_history: list[dict[str, str]] | None = None,
                 ) -> tuple[list[str], dict[str, str]]:
    history = [entry for raw in (recent_history or [])
               if (entry := normalize_history_entry(raw))]
    hard = set(recent_combinations or ())
    hard.update(history_combo(entry) for entry in history[-HISTORY_RECENT_LIMIT:])
    hard.discard(("", "", ""))

    if not history and not hard:
        return roll_all(materials, rng, locks, genre, allow_custom,
                        mains=mains)

    best: tuple[list[str], dict[str, str]] | None = None
    best_score: int | None = None
    for _ in range(HISTORY_CANDIDATE_LIMIT):
        candidate = roll_all(materials, rng, locks, genre, allow_custom,
                             mains=mains)
        score = coverage_score(candidate[1], history, hard)
        if best_score is None or score < best_score:
            best, best_score = candidate, score
        if score == 0:
            break
    assert best is not None
    return best


def roll_twists(materials: dict, rng: random.Random) -> list[tuple[str, str]]:
    families = [(family, items) for family, items in materials["twists"].items() if items]
    if len(families) < 2:
        return []
    count = min(rng.randint(2, 3), len(families))
    return [(family, rng.choice(items)) for family, items in rng.sample(families, count)]


def roll_all(materials: dict, rng: random.Random, locks: dict[str, str],
             genre: str | None, allow_custom: bool,
             mains: int = 1) -> tuple[list[str], dict[str, str]]:
    r = Roller(materials, rng, allow_custom)
    out: list[str] = []
    resolved_genre = resolve_genre(materials["genres"], genre) if genre else None
    record: dict[str, str] = {key: CUSTOM for key in HISTORY_DIMENSIONS}
    record["genre"] = resolved_genre or genre or "—"

    def emit(key: str, value: str, locked: bool = False):
        out.append(f"{key}: {value}" + ("（预锁）" if locked else ""))

    # 1 世界观档 + 基调轴 + 开场时景（范围骰 + 表骰）
    if "dang" in locks:
        dang = locks["dang"]
        emit("世界观档", dang, locked=True)
    else:
        allowed_dangs = materials["genre_dangs"].get(resolved_genre, set(materials["dang_pool"]))
        dang_pool = [value for value in materials["dang_pool"] if value in allowed_dangs]
        dang = r.pick_range(dang_pool or materials["dang_pool"])
        emit("世界观档", dang)
    record["dang"] = dang

    out.append("世界基调:")
    for axis in TONE_AXES:
        lock_key = AXIS_LOCK_KEYS.get(axis)
        if lock_key and lock_key in locks:
            out.append(f"  {axis}: {locks[lock_key]}（预锁）")
        else:
            options = r.tone_pool(dang, axis)
            out.append(f"  {axis}: {r.pick(options)}")

    out.append("世界核心规则:")
    for axis in WORLD_RULE_AXES:
        lock_key = WORLD_RULE_LOCK_KEYS[axis]
        if lock_key in locks:
            value = locks[lock_key]
            out.append(f"  {axis}: {value}（预锁）")
        else:
            value = r.pick(r.world_rule_pool(dang, axis))
            out.append(f"  {axis}: {value}")
        if axis == "核心规则来源":
            record["world_rule"] = value

    if materials["timescape"]:
        out.append("开场时景:")
        for axis, options in materials["timescape"].items():
            out.append(f"  {axis}: {r.pick(options)}")

    # 大类细分轴
    if genre:
        if resolved_genre:
            out.append(f"大类细分（{resolved_genre}）:")
            for axis in materials["genres"][resolved_genre]:
                options = r.genre_axis_pool(dang, resolved_genre, axis)
                out.append(f"  {axis}: {r.pick(options)}")
        else:
            out.append(f"大类细分（{genre}）: 未收录该大类；按素材库「大类细分轴」比照自拟细分轴后逐轴抽取")

    # 2-4 引擎与咬合
    if "engine" in locks:
        main_family = locks["engine"]
        emit("主引擎", main_family, locked=True)
    else:
        main_family, main_item = r.roll_engine(dang)
        emit("主引擎", main_family if main_family == CUSTOM else f"{main_family} → {main_item}")
    record["engine"] = main_family
    mesh = locks.get("mesh") or r.pick_range(MESH_LABELS)
    emit("咬合", mesh, locked="mesh" in locks)
    if mesh == "双引擎":
        if "sub_engine" in locks:
            emit("副引擎", locks["sub_engine"], locked=True)
        else:
            sub_exclude = main_family if main_family != CUSTOM else None
            sub_family, sub_item = r.roll_engine(dang, exclude=sub_exclude)
            emit("副引擎", sub_family if sub_family == CUSTOM else f"{sub_family} → {sub_item}")
    else:
        emit("副引擎", "—（单引擎）")

    # 5 壳
    if "shell" in locks:
        emit("制度与场合壳", locks["shell"], locked=True)
        record["shell"] = locks["shell"].split("（", 1)[0].strip()
    else:
        shell = r.pick(r.shell_pool(dang))
        if shell == CUSTOM:
            emit("制度与场合壳", CUSTOM)
        else:
            name, examples = shell
            record["shell"] = name
            entry = ""
            if examples:
                entry = f"（建议入口：{r.pick_range([x.strip() for x in examples.split('、')])}）"
            emit("制度与场合壳", name + entry)

    if "action" in locks:
        emit("开场动作", locks["action"], locked=True)
        record["action"] = locks["action"].split("→", 1)[0].strip()
    else:
        action = r.pick(materials["scene_actions"])
        if action == CUSTOM:
            emit("开场动作", CUSTOM)
        else:
            family, seeds = action
            record["action"] = family
            seed_pick = r.pick_range([x.strip() for x in seeds.split("、")]) if seeds else ""
            emit("开场动作", f"{family} → {seed_pick}" if seed_pick else family)

    # 6-8 Tier/模式/权力（范围骰）
    emit("Tier", locks.get("tier") or str(r.pick_range([1, 2, 3])), locked="tier" in locks)
    emit("运行模式", locks.get("mode") or r.pick_range(MODE_LABELS), locked="mode" in locks)
    emit("权力结构", locks.get("power") or r.pick_range(POWER_LABELS), locked="power" in locks)

    # 9-10 主 NPC（可多名）与配角
    cast = int(locks["cast"]) if "cast" in locks else r.pick_range([1, 2, 3])

    def shuffled_iter(pool: list):
        items = list(pool)
        if allow_custom:
            items.append(CUSTOM)
        r.rng.shuffle(items)
        return iter(items)

    flavor_iter = shuffled_iter(materials["flavors"])
    speech_iter = shuffled_iter(materials["speech"])
    contrast_iter = shuffled_iter(materials["contrast"])
    decision_iters = {
        axis: shuffled_iter(materials["decision_axes"].get(axis, []))
        for axis in DECISION_AXES
    }
    decision_record_keys = {"核心价值": "value", "压力策略": "strategy", "关系姿态": "stance"}

    for n in range(1, max(1, mains) + 1):
        label = "主NPC" if n == 1 else f"主NPC{n}"
        use_locks = n == 1
        if use_locks and "identity" in locks:
            emit(f"{label}身份", locks["identity"], locked=True)
            record["identity"] = locks["identity"].split("→", 1)[0].strip()
        else:
            ident = r.pick(r.identity_pool(dang))
            if ident == CUSTOM:
                emit(f"{label}身份", CUSTOM)
            else:
                family, seeds = ident
                if use_locks:
                    record["identity"] = family
                seed_pick = r.pick_range([x.strip() for x in seeds.split("、")]) if seeds else ""
                emit(f"{label}身份", f"{family} → {seed_pick}" if seed_pick else family)
        if use_locks and "situation" in locks:
            emit(f"{label}处境", locks["situation"], locked=True)
            record["situation"] = locks["situation"].split("（", 1)[0].strip()
        else:
            situ = r.pick(r.situation_pool(dang))
            if situ == CUSTOM:
                emit(f"{label}处境", CUSTOM)
            else:
                stype, hint = situ
                if use_locks:
                    record["situation"] = stype
                emit(f"{label}处境", f"{stype}（{hint}）" if hint else stype)
        if use_locks and "relation_stage" in locks:
            relation_stage = locks["relation_stage"]
            emit(f"{label}关系阶段", relation_stage, locked=True)
        else:
            relation_stage = r.roll_relation_stage(materials["relation_stages"])
            emit(f"{label}关系阶段", relation_stage)
        if use_locks:
            record["relation"] = relation_stage
        for axis in DECISION_AXES:
            lock_key = DECISION_LOCK_KEYS[axis]
            if use_locks and lock_key in locks:
                decision_value = locks[lock_key]
                emit(f"{label}{axis}", decision_value, locked=True)
            else:
                decision_value = next(decision_iters[axis], CUSTOM)
                emit(f"{label}{axis}", decision_value)
            if use_locks:
                record[decision_record_keys[axis]] = decision_value
        if use_locks and "contrast" in locks:
            emit(f"{label}反差轴", locks["contrast"], locked=True)
        else:
            emit(f"{label}反差轴", next(contrast_iter, CUSTOM))
        emit(f"{label}表层风味", next(flavor_iter, CUSTOM))
        emit(f"{label}口癖", next(speech_iter, "—"))
        emit(f"{label}画像倾向", r.roll_weighted())
        emit(f"{label}外观", r.roll_appearance(2))
        emit(f"{label}初始关系建议", f"{r.rng.randint(-5, 5):+d}（9e 需写出原因，可小幅调整）")

    emit("配角数", str(cast), locked="cast" in locks)
    for i in range(1, cast + 1):
        func = r.pick(materials["supporting_functions"])
        out.append(f"配角{i}: 功能={func}, 表层风味={next(flavor_iter, '—')}, "
                   f"口癖={next(speech_iter, '—')}, 画像倾向={r.roll_weighted()}, "
                   f"核心价值={next(decision_iters['核心价值'], '—')}, "
                   f"压力策略={next(decision_iters['压力策略'], '—')}, "
                   f"外观={r.roll_appearance(1)}")

    for key, value in locks.items():
        if key == "extra":
            out.append(f"附加预锁: {value}")
    return out, record


# ---------------------------------------------------------------- cli

def parse_locks(pairs: list[str]) -> tuple[dict[str, str], str | None]:
    locks: dict[str, str] = {}
    genre = None
    extras = []
    for pair in pairs:
        if "=" not in pair:
            extras.append(pair)
            continue
        key, _, value = pair.partition("=")
        norm = LOCK_ALIASES.get(key.strip()) or LOCK_ALIASES.get(key.strip().lower())
        if norm == "genre":
            genre = value.strip()
        elif norm:
            locks[norm] = value.strip()
        else:
            extras.append(pair)
    if extras:
        locks["extra"] = "；".join(extras)
    return locks, genre


def validate_request(args: argparse.Namespace, locks: dict[str, str], materials: dict,
                     genre: str | None = None) -> list[str]:
    errors: list[str] = []
    finite_values = {
        "dang": set(materials["dang_pool"]),
        "tier": {"1", "2", "3"},
        "mode": MODE_LOCK_VALUES,
        "mesh": set(MESH_LABELS),
        "power": POWER_LOCK_VALUES,
    }
    labels = {"dang": "世界观档", "tier": "Tier", "mode": "运行模式",
              "mesh": "咬合", "power": "权力结构"}
    for key, allowed in finite_values.items():
        if key in locks and locks[key] not in allowed:
            errors.append(f"{labels[key]}={locks[key]!r} 不在允许范围内")

    if "cast" in locks:
        try:
            cast = int(locks["cast"])
        except ValueError:
            errors.append(f"配角数={locks['cast']!r} 必须是 1..3 的整数")
        else:
            if cast not in {1, 2, 3}:
                errors.append(f"配角数={locks['cast']!r} 必须是 1..3 的整数")

    if args.mains not in {1, 2, 3}:
        errors.append(f"--mains {args.mains} 必须是 1..3 的整数")
    if args.all_custom and args.no_custom:
        errors.append("--all-custom 与 --no-custom 不能同时使用")
    if locks.get("mesh") == "单引擎" and "sub_engine" in locks:
        errors.append("咬合=单引擎时不能预锁副引擎")
    if (locks.get("mesh") == "双引擎" and "engine" in locks and "sub_engine" in locks
            and locks["engine"] == locks["sub_engine"]):
        errors.append("双引擎的主引擎与副引擎不能相同")

    resolved_genre = resolve_genre(materials["genres"], genre) if genre else None
    allowed_dangs = materials["genre_dangs"].get(resolved_genre)
    if allowed_dangs and "dang" in locks and locks["dang"] not in allowed_dangs:
        errors.append(f"题材={resolved_genre!r} 不支持世界观档={locks['dang']!r}")

    if locks.get("dang") == DANG_REAL:
        checks = {
            "era": ("时代与技术", "时代与技术"),
            "region": ("地域气质", "地域气质"),
        }
        for key, (pool_name, label) in checks.items():
            if key not in locks:
                continue
            value = locks[key].split("→", 1)[0].strip()
            if value in materials["real_exclusions"].get(pool_name, set()):
                errors.append(f"现实档不能预锁{label}={locks[key]!r}")

    locked_dang = locks.get("dang")
    if locked_dang in materials["dang_pool"]:
        other_dangs = {DANG_HALF, DANG_FULL} - {locked_dang}
        forbidden_shells = {name for dang in other_dangs
                            for name, _examples in materials["shell_supp"].get(dang, [])}
        forbidden_situations = {name for dang in other_dangs
                                for name, _hint in materials["situation_supp"].get(dang, [])}
        forbidden_identity_parts = set()
        for dang in other_dangs:
            rows = materials["identity_supp"].get(dang, [])
            for family, seeds in rows:
                forbidden_identity_parts.add(family)
                forbidden_identity_parts.update(seed.strip() for seed in seeds.split("、"))
        forbidden_world_rules = {
            value for dang in other_dangs
            for values in materials["world_rule_supp"].get(dang, {}).values()
            for value in values
        }

        if "shell" in locks and locks["shell"].split("（", 1)[0].strip() in forbidden_shells:
            errors.append(f"{locked_dang}档不能预锁制度与场合壳={locks['shell']!r}")
        if ("situation" in locks
                and locks["situation"].split("（", 1)[0].strip() in forbidden_situations):
            errors.append(f"{locked_dang}档不能预锁主NPC处境={locks['situation']!r}")
        if "identity" in locks:
            parts = {part.strip() for part in locks["identity"].split("→")}
            if parts & forbidden_identity_parts:
                errors.append(f"{locked_dang}档不能预锁主NPC身份={locks['identity']!r}")
        for _axis, lock_key in WORLD_RULE_LOCK_KEYS.items():
            if lock_key in locks and locks[lock_key] in forbidden_world_rules:
                errors.append(f"{locked_dang}档不能预锁世界核心规则={locks[lock_key]!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Roll structural dice for a new opening.")
    parser.add_argument("--seed", type=int, default=None, help="可复现种子（对应玩家“种子 N”）")
    parser.add_argument("--genre", default=None, help="玩家限定的题材大类，如 末世、修真")
    parser.add_argument("--lock", action="append", default=[], metavar="字段=值",
                        help="预锁项，原样回显并跳过该骰；可重复")
    parser.add_argument("--no-custom", action="store_true", help="强制表内：去掉“系统自拟”末位")
    parser.add_argument("--all-custom", action="store_true",
                        help="表外全随机：核心规则、引擎、壳、动作、身份、处境和人物决策轴均自拟")
    parser.add_argument("--no-history", action="store_true", help="关闭开局历史的读取和写入")
    parser.add_argument("--mains", type=int, default=1, help="主 NPC 数量 1..3（后宫/群像局用；预锁只作用于第 1 名）")
    parser.add_argument("--twist", action="store_true", help="快进时掷 2-3 个中期剧情转折方向")
    parser.add_argument("--list-genres", action="store_true", help="列出已收录的大类细分轴")
    args = parser.parse_args(argv)

    refs = Path(__file__).resolve().parent.parent / "references"
    try:
        materials = load_materials(refs)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"素材解析失败：{exc}；请退回手工协议抽取（dice_source: protocol）。", file=sys.stderr)
        return 1

    if args.list_genres:
        print("已收录大类：" + "、".join(materials["genres"]))
        return 0

    locks, lock_genre = parse_locks(args.lock)
    genre = args.genre or lock_genre
    request_errors = validate_request(args, locks, materials, genre)
    if request_errors:
        for error in request_errors:
            print(f"参数错误：{error}", file=sys.stderr)
        return 2

    if args.all_custom:
        locks.update({key: CUSTOM for key in (
            "world_rule", "world_reach", "world_cost", "world_phase",
            "engine", "shell", "action", "identity", "situation",
            "core_value", "pressure_strategy", "relationship_stance",
        )})

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    seed_note = f"seed={args.seed}" if args.seed is not None else "seed=系统熵源"
    if args.twist:
        twists = roll_twists(materials, rng)
        if not twists:
            print("中期转折素材解析失败；请读取 references/世界运转.md 后手工抽取。", file=sys.stderr)
            return 1
        print(f"# 中期转折骰结果（{seed_note}；dice_source: script）")
        for index, (family, item) in enumerate(twists, start=1):
            print(f"转折方向{index}: {family} → {item}")
        print("# 仅用于 Tier2/Tier3 快进；按世界运转规则以事件队列、semantic_key 和既有引擎因果落账。")
        return 0

    mains = args.mains
    root = refs.parent
    history_path = root / ".opening_history"
    recent_history: list[dict[str, str]] = []
    if not args.no_history and args.seed is None:
        recent_history = load_history(history_path)

    lines, record = roll_opening(materials, rng, locks, genre, allow_custom=not args.no_custom,
                                 mains=mains,
                                 recent_history=recent_history)
    print(f"# 结构骰结果（{seed_note}；dice_source: script）")
    print("\n".join(lines))
    if not args.no_history:
        try:
            append_history(history_path, record)
        except OSError as exc:
            print(f"开局历史写入失败：{exc}", file=sys.stderr)
    print("# 使用规则：预锁项以玩家输入为准；某项与预锁或已生成内容明显不成立时，自拟同类替代或重跑一次脚本；")
    print("# 表格实时解析自 references/，行数变化自动生效；文本细节仍按各 references 文件规则生成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
