"""Structural checks on generated openings and the anti-collapse gate.

check_opening() is the structural validation run on fixed seeds
(ACCEPTANCE.md section 3). diversity() simulates consecutive random
openings exactly the way new-game picks them (history-aware), and measures
the CONTENT_BIBLE.md section 4 metrics.
"""

from collections import Counter

from ..errors import AppError
from . import invariants
from . import opening
from . import rng
from . import structure as ST


def check_opening(state, pack):
    """Problems (strings) with one generated opening."""
    problems = []
    world_ids = {"player"}
    world_ids |= {t["id"] for t in pack["character_templates"]}
    world_ids |= {b["id"] for b in pack["background_cast"]}
    for cid, char in state["characters"].items():
        if cid not in world_ids:
            problems.append("角色 %s 不来自本世界包" % cid)
        if not isinstance(char.get("age"), int) or char["age"] < 18:
            problems.append("角色 %s 年龄不合规" % cid)
        if not char.get("adult_context"):
            problems.append("角色 %s 缺少成年身份" % cid)
    location_ids = {loc["id"] for loc in pack["locations"]}
    if state["scene"]["location_id"] not in location_ids:
        problems.append("开局地点不在本世界包")
    present = state["scene"]["present"]
    for i, a in enumerate(present):
        for b in present[i + 1 :]:
            if "%s>%s" % (a, b) not in state["relationships"] or "%s>%s" % (b, a) not in state["relationships"]:
                problems.append("在场的 %s 与 %s 之间没有关系边" % (a, b))
    for key, edge in state["relationships"].items():
        if not edge["history"] or not edge["history"][0]["reason"]:
            problems.append("关系 %s 缺少原因" % key)
    families = [c["family"] for c in state["characters"].values() if c["tier"] == "major" and c["family"]]
    if len(families) != len(set(families)):
        problems.append("同一局的重要人物重名同姓")
    events = list(state["events"].values())
    if state["mode"] == "pressure":
        tiers = {e["tier"] for e in events}
        if tiers != {"immediate", "near", "far"}:
            problems.append("压力模式开局缺少三层事件：%s" % sorted(tiers))
        if not any(e["tier"] == "far" and e["kind"] == "foreshadow" for e in events):
            problems.append("远期层必须是伏笔")
    else:
        if any(e["kind"] in ("deadline", "chance") for e in events):
            problems.append("日常模式开局出现了倒计时或概率事件")
        if events:
            problems.append("日常模式开局不应有到期事件")
    for text in _strings(state):
        if "{" in text and "}" in text:
            problems.append("未渲染的占位：%s" % text[:40])
            break
    problems.extend(p["reason"] for p in invariants.check(state))
    return problems


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)


def seed_stream(base):
    """A deterministic stand-in for the random seed source."""
    index = 0
    while True:
        yield 1 + int(rng.unit(base, "gate.stream", index) * 999999)
        index += 1


def diversity(pack, mode, base=1, count=20):
    """Simulate `count` consecutive random openings for one world and mode."""
    conditions = opening.normalize_conditions({"mode": mode, "locks": {"world_id": pack["id"]}})
    history = []
    stream = seed_stream(base * 1000 + (1 if mode == "daily" else 2))
    results = []
    for _ in range(count):

        def evaluate(seed):
            return opening.plan(pack, seed, conditions)[0]

        _seed, result = opening.choose_seed(evaluate, stream, history)
        history.insert(0, dict(result))
        results.append(result)
    signatures = {r["signature"] for r in results}
    structures = Counter(r["power_structure"] for r in results)
    identities = Counter(r["identity_id"] for r in results)
    hooks = Counter(r["hook_kind"] for r in results)
    approach_share = hooks.get("approach", 0) / float(count)
    min_structure = min(structures.get(s, 0) for s in ST.POWER_STRUCTURES) / float(count)
    checks = {
        "signatures": {"value": len(signatures), "need": ">= 12", "pass": len(signatures) >= 12},
        "min_power_structure_share": {"value": round(min_structure, 3), "need": ">= 0.15", "pass": min_structure >= 0.15},
        "identities": {"value": len(identities), "need": ">= 3", "pass": len(identities) >= 3},
        "approach_hook_share": {"value": round(approach_share, 3), "need": ">= 0.60", "pass": approach_share >= 0.60},
    }
    return {
        "world_id": pack["id"],
        "mode": mode,
        "base": base,
        "count": count,
        "pass": all(c["pass"] for c in checks.values()),
        "checks": checks,
        "power_structures": dict(structures),
        "identities": dict(identities),
        "hook_kinds": dict(hooks),
    }


def fixed_seed_openings(pack, seeds=range(1, 11)):
    """Structural check of openings for fixed seeds in both modes."""
    failures = []
    count = 0
    for mode in ("daily", "pressure"):
        if mode == "daily" and not pack["daily_activities"]:
            continue
        if mode == "pressure" and not pack["pressures"]:
            continue
        for seed in seeds:
            conditions = opening.normalize_conditions({"mode": mode, "locks": {"world_id": pack["id"]}})
            try:
                state, _opening = opening.build(pack, seed, conditions, "check")
            except AppError as err:
                failures.append({"mode": mode, "seed": seed, "problems": [err.message]})
                continue
            count += 1
            problems = check_opening(state, pack)
            if problems:
                failures.append({"mode": mode, "seed": seed, "problems": problems})
    return count, failures
