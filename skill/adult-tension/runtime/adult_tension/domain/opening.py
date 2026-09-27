"""Opening generation (RUNTIME_PROTOCOL.md section 4.4, CONTENT_BIBLE.md section 4).

An opening is a pure function of (world pack, seed, normalized conditions):
the same content version, RNG version, seed and conditions always give the
same opening. All combinations happen inside one world pack (D7).
"""

import math

from ..errors import NO_MATCH, SAFETY_BLOCK, AppError, detail
from . import clock as CL
from . import rng
from . import structure as ST
from .text import binding, render, render_name_pattern

LOCK_KEYS = ("world_id", "location_id", "combo_id", "activity_id", "pressure_id", "hook_id", "identity_id")
HOOK_WEIGHT = {"approach": 4.0, "observe": 1.0, "request": 1.0, "accident": 1.0}


def normalize_conditions(request):
    """The parts of a new-game request that determine the opening."""
    locks = {k: v for k, v in (request.get("locks") or {}).items() if v is not None}
    excludes = request.get("excludes") or {}
    player = {k: v for k, v in (request.get("player") or {}).items() if v not in (None, "", [])}
    return {
        "mode": request.get("mode") or "random",
        "locks": dict(sorted(locks.items())),
        "excludes": {
            "content_tags": sorted(set(excludes.get("content_tags") or [])),
            "world_ids": sorted(set(excludes.get("world_ids") or [])),
            "location_ids": sorted(set(excludes.get("location_ids") or [])),
        },
        "player": dict(sorted(player.items())),
        "npc_gender_preference": request.get("npc_gender_preference") or "any",
    }


def signature(plan):
    item = ("a:" + plan["activity_id"]) if plan.get("activity_id") else ("p:" + plan["pressure_id"])
    return "|".join((plan["world_id"], plan["location_id"], plan["combo_id"], item, plan["hook_id"]))


# ---------------------------------------------------------------------------
# Candidate filtering


def _excluded(tags, excluded):
    return bool(set(tags or ()) & excluded)


def _identity_candidates(pack, conditions):
    player = conditions["player"]
    locks = conditions["locks"]
    out = []
    for identity in sorted(pack["player_identities"], key=lambda i: i["id"]):
        if locks.get("identity_id") and identity["id"] != locks["identity_id"]:
            continue
        hint = player.get("identity_hint")
        if hint and hint not in identity["role"] and identity["role"] not in hint and hint != identity["id"]:
            continue
        gender = player.get("gender")
        if gender and identity["gender"] not in ("any", gender):
            continue
        out.append(identity)
    return out


def _custom_identity(conditions):
    player = conditions["player"]
    hint = player.get("identity_hint")
    if not hint:
        return None
    return {
        "id": "custom_identity",
        "role": hint[:20],
        "gender": "any",
        "title_patterns": [{"pattern": "{family}" + ("" if len(hint) > 6 else hint[:6]), "gender": "any"}],
        "age_range": [18, 80],
        "social_position": player.get("social_position", "equal"),
        "baseline": "",
        "resources": [],
        "reputation": "",
        "risks": [],
        "custom": True,
    }


def _identity_fits(identity, combo):
    if identity["social_position"] not in combo["player_positions"]:
        return False
    return not combo.get("identity_ids") or identity["id"] in combo["identity_ids"]


def _combo_gender_ok(pack, combo, preference):
    templates = {t["id"]: t for t in pack["character_templates"]}
    fixed = [templates[s]["gender"] for s in combo["slots"] if templates[s]["gender"] != "any"]
    n = len(combo["slots"])
    if preference == "female_only":
        return all(g == "female" for g in fixed)
    if preference == "male_only":
        return all(g == "male" for g in fixed)
    if preference in ("mostly_female", "mostly_male"):
        want = "female" if preference == "mostly_female" else "male"
        quota = max(1, math.ceil(0.6 * n))
        return n - sum(1 for g in fixed if g != want) >= quota
    return True


def plan_candidates(pack, mode, conditions):
    """All compatible (combo, item, location, hook) tuples, plus why none exist."""
    excluded = set(conditions["excludes"]["content_tags"])
    locks = conditions["locks"]
    preference = conditions["npc_gender_preference"]
    reasons = []
    if _excluded(pack["content_tags"], excluded):
        return [], ["世界 %s 带有被排除的标签：%s" % (pack["id"], "、".join(sorted(set(pack["content_tags"]) & excluded)))]
    excluded_locations = set(conditions["excludes"]["location_ids"])
    locations = [
        loc["id"]
        for loc in pack["locations"]
        if not _excluded(loc["tags"], excluded)
        and loc["id"] not in excluded_locations
        and (not locks.get("location_id") or loc["id"] == locks["location_id"])
    ]
    if not locations:
        reasons.append("没有满足条件的地点")
    identities = _identity_candidates(pack, conditions)
    custom_identity = None if identities else _custom_identity(conditions)
    if not identities and custom_identity is None:
        reasons.append("没有符合玩家设定（身份、性别、年龄）的玩家身份")
    combos = []
    for combo in sorted(pack["cast_combos"], key=lambda c: c["id"]):
        if locks.get("combo_id") and combo["id"] != locks["combo_id"]:
            continue
        if _excluded(combo["tags"], excluded):
            continue
        if not _combo_gender_ok(pack, combo, preference):
            continue
        if identities and not any(_identity_fits(i, combo) for i in identities):
            continue
        combos.append(combo)
    if not combos:
        reasons.append("没有满足锁定、排除、性别偏好与玩家身份的人物组合")
    if mode == "daily":
        items = [a for a in pack["daily_activities"] if not _excluded(a["tags"], excluded)]
        key = "activity_id"
    else:
        items = [p for p in pack["pressures"] if not _excluded(p["tags"], excluded)]
        key = "pressure_id"
    items = sorted(items, key=lambda i: i["id"])
    if locks.get("activity_id") and mode == "pressure":
        reasons.append("压力模式不能锁定日常活动")
        items = []
    if locks.get("pressure_id") and mode == "daily":
        reasons.append("日常模式不能锁定压力")
        items = []
    if locks.get(key):
        items = [i for i in items if i["id"] == locks[key]]
    if not items:
        reasons.append("没有满足条件的%s" % ("日常活动" if mode == "daily" else "压力"))
    hooks = sorted(pack["hooks"], key=lambda h: h["id"])
    if locks.get("hook_id"):
        hooks = [h for h in hooks if h["id"] == locks["hook_id"]]
        if not hooks:
            reasons.append("锁定的钩子不存在")
    tuples = []
    for combo in combos:
        slots = set(combo["slots"])
        combo_hooks = [h for h in hooks if h["slot"] in slots]
        for item in items:
            if mode == "pressure" and item["leverage"]:
                needed = {item["leverage"]["holder"], item["leverage"]["subject"]} - {"player"}
                if not needed <= slots:
                    continue
            item_hooks = [h for h in combo_hooks if not item["hook_ids"] or h["id"] in item["hook_ids"]]
            if not item_hooks:
                continue
            for location in item["location_ids"]:
                if location not in locations:
                    continue
                for hook in item_hooks:
                    if hook.get("location_ids") and location not in hook["location_ids"]:
                        continue
                    tuples.append((combo, item, location, hook))
    if not tuples and not reasons:
        reasons.append("锁定与排除条件组合起来没有可用的开局（人物组合、%s、地点与钩子互相配不上）" % ("活动" if mode == "daily" else "压力"))
    return tuples, reasons


def _choose(seed, tuples, mode):
    """Hierarchical choice: structure, combo, item, location, hook."""
    structures = sorted({t[0]["power_structure"] for t in tuples})
    structure = rng.pick(seed, "opening.structure", structures)
    tuples = [t for t in tuples if t[0]["power_structure"] == structure]
    combo_ids = sorted({t[0]["id"] for t in tuples})
    combo_id = rng.pick(seed, "opening.combo", combo_ids)
    tuples = [t for t in tuples if t[0]["id"] == combo_id]
    item_ids = sorted({t[1]["id"] for t in tuples})
    item_id = rng.pick(seed, "opening.item", item_ids)
    tuples = [t for t in tuples if t[1]["id"] == item_id]
    location_ids = sorted({t[2] for t in tuples})
    location_id = rng.pick(seed, "opening.location", location_ids)
    tuples = [t for t in tuples if t[2] == location_id]
    hooks = sorted({t[3]["id"]: t[3] for t in tuples}.values(), key=lambda h: h["id"])
    hook = rng.weighted(seed, "opening.hook", hooks, [HOOK_WEIGHT[h["kind"]] for h in hooks])
    return tuples[0][0], tuples[0][1], location_id, hook


def resolve_mode(seed, mode):
    if mode in ("daily", "pressure"):
        return mode
    return rng.pick(seed, "opening.mode", ["daily", "pressure"])


def plan(pack, seed, conditions):
    """Choose the opening skeleton; raise NO_MATCH when constraints cannot be met."""
    mode = resolve_mode(seed, conditions["mode"])
    tuples, reasons = plan_candidates(pack, mode, conditions)
    if not tuples:
        raise no_match(reasons, pack["id"], conditions)
    combo, item, location_id, hook = _choose(seed, tuples, mode)
    identities = [i for i in _identity_candidates(pack, conditions) if _identity_fits(i, combo)]
    if identities:
        identity = rng.pick(seed, "opening.identity", identities)
    else:
        identity = dict(_custom_identity(conditions))
        identity["social_position"] = combo["player_positions"][0]
    result = {
        "world_id": pack["id"],
        "mode": mode,
        "combo_id": combo["id"],
        "power_structure": combo["power_structure"],
        "location_id": location_id,
        "hook_id": hook["id"],
        "hook_kind": hook["kind"],
        "identity_id": identity["id"],
        "activity_id": item["id"] if mode == "daily" else None,
        "pressure_id": item["id"] if mode == "pressure" else None,
    }
    result["signature"] = signature(result)
    return result, combo, item, hook, identity


def no_match(reasons, world_id, conditions):
    relax = []
    if conditions["locks"]:
        relax.append("放宽锁定：%s" % "、".join(sorted(conditions["locks"])))
    if conditions["excludes"]["content_tags"] or conditions["excludes"]["world_ids"] or conditions["excludes"]["location_ids"]:
        relax.append("减少排除条件")
    if conditions["npc_gender_preference"] not in ("any", "mixed"):
        relax.append("把 NPC 性别偏好改成“不限”")
    if conditions["player"]:
        relax.append("放宽玩家设定（身份、年龄、性别）")
    return AppError(
        NO_MATCH,
        "开局条件在%s中无法同时满足" % (("世界 " + world_id) if world_id else "现有世界"),
        [detail("$.conditions", reason, None, NO_MATCH) for reason in reasons] or [detail("$.conditions", "没有可用的开局", None, NO_MATCH)],
        relax=relax,
        world_id=world_id,
    )


# ---------------------------------------------------------------------------
# Instantiation


class _Names:
    def __init__(self, pack, seed):
        pools = pack["name_pools"]
        self.pools = pools
        self.seed = seed
        self.families = rng.shuffled(seed, "names.family", sorted(pools["family"]))
        self.used_given = set()
        self.index = 0

    def reserve_family(self, family):
        if family in self.families:
            self.families.remove(family)

    def next_family(self, allow_reuse=False):
        if self.families:
            return self.families.pop(0)
        if not allow_reuse:
            return None
        self.index += 1
        return rng.pick(self.seed, "names.family.reuse", sorted(self.pools["family"]), self.index)

    def given(self, gender, key):
        pool_key = {"female": "given_female", "male": "given_male"}.get(gender, "given_neutral")
        pool = sorted(self.pools[pool_key])
        if gender in ("female", "male") and self.pools["given_neutral"] and rng.unit(self.seed, "names.neutral", key) < 0.15:
            pool = sorted(self.pools["given_neutral"])
        if not pool:
            pool = sorted(self.pools["given_neutral"] or self.pools["given_female"] + self.pools["given_male"])
        fresh = [g for g in pool if g not in self.used_given] or pool
        given = rng.pick(self.seed, "names.given", fresh, key)
        self.used_given.add(given)
        return given

    def call(self, family, given, gender, key):
        patterns = [p["pattern"] for p in self.pools["nickname_patterns"] if p["gender"] in ("any", gender)]
        if not patterns:
            return family + given
        return render_name_pattern(rng.pick(self.seed, "names.call", patterns, key), family, given)


def _npc_genders(pack, combo, seed, preference):
    templates = {t["id"]: t for t in pack["character_templates"]}
    slots = list(combo["slots"])
    genders = {s: templates[s]["gender"] for s in slots if templates[s]["gender"] != "any"}
    free = [s for s in rng.shuffled(seed, "opening.gender.order", sorted(s for s in slots if s not in genders))]
    mix = pack["default_npc_gender_mix"]

    def by_mix(slot):
        items = ["female", "male", "nonbinary"]
        weights = [mix["female"], mix["male"], mix["nonbinary"]]
        return rng.weighted(seed, "opening.gender", items, weights, slot)

    if preference in ("female_only", "male_only"):
        want = "female" if preference == "female_only" else "male"
        for slot in free:
            genders[slot] = want
    elif preference in ("mostly_female", "mostly_male"):
        want = "female" if preference == "mostly_female" else "male"
        quota = max(1, math.ceil(0.6 * len(slots)))
        have = sum(1 for g in genders.values() if g == want)
        for slot in free:
            if have < quota:
                genders[slot] = want
                have += 1
            else:
                genders[slot] = by_mix(slot)
    elif preference == "mixed" and len(slots) >= 2:
        for slot in free:
            genders[slot] = by_mix(slot)
        present = set(genders.values())
        for want in ("female", "male"):
            if want not in present and free:
                genders[free[0 if want == "female" else -1]] = want
                present = set(genders.values())
    else:
        for slot in free:
            genders[slot] = by_mix(slot)
    return genders


def background_gender(pack, bg, seed, preference):
    if bg["gender"] != "any":
        return bg["gender"]
    if preference == "female_only":
        return "female"
    if preference == "male_only":
        return "male"
    mix = dict(pack["default_npc_gender_mix"])
    if preference == "mostly_female":
        mix = {"female": 0.8, "male": 0.2, "nonbinary": 0.0}
    elif preference == "mostly_male":
        mix = {"female": 0.2, "male": 0.8, "nonbinary": 0.0}
    items = ["female", "male", "nonbinary"]
    return rng.weighted(seed, "opening.bg_gender", items, [mix["female"], mix["male"], mix.get("nonbinary", 0.0)], bg["id"])


def _render_tree(node, scopes):
    if isinstance(node, str):
        return render(node, scopes)
    if isinstance(node, list):
        return [_render_tree(v, scopes) for v in node]
    if isinstance(node, dict):
        return {k: _render_tree(v, scopes) for k, v in node.items()}
    return node


def instantiate(pack, seed, conditions, planned, content_version, tag_ids=None):
    """Build the initial session state (without session_id) and the opening payload."""
    result, combo, item, hook, identity = planned
    mode = result["mode"]
    player_req = conditions["player"]
    names = _Names(pack, seed)
    preference = conditions["npc_gender_preference"]
    start_minute = item.get("start_minute")
    if start_minute is None:
        start_minute = pack["clock_start"]["minute"]
    now = {"day": 1, "minute": start_minute}

    # -- player ---------------------------------------------------------------
    gender = player_req.get("gender")
    if not gender:
        gender = identity["gender"] if identity["gender"] != "any" else rng.pick(seed, "player.gender", ["female", "male"])
    age = player_req.get("age")
    if age is None:
        lo, hi = identity["age_range"]
        if player_req.get("age_band"):
            lo, hi = max(lo, player_req["age_band"][0]), min(hi, player_req["age_band"][1])
            if lo > hi:
                lo, hi = player_req["age_band"]
        age = rng.randint(seed, "player.age", lo, hi)
    if age < 18:
        raise AppError(SAFETY_BLOCK, "玩家角色必须是成年人", [detail("$.player.age", "年龄 %d 小于 18" % age, "所有角色都必须年满 18 岁", SAFETY_BLOCK)])
    if player_req.get("name"):
        full = player_req["name"]
        family = full[0] if full[0] in pack["name_pools"]["family"] else ""
        if len(full) >= 3 and full[:2] in pack["name_pools"]["family"]:
            family = full[:2]
        given = full[len(family) :] if family else full
        names.reserve_family(family)
    else:
        family = names.next_family(allow_reuse=True)
        given = names.given(gender, "player")
        full = family + given
    title = player_req.get("title")
    if not title:
        patterns = [p["pattern"] for p in identity["title_patterns"] if p["gender"] in ("any", gender)] or [identity["title_patterns"][0]["pattern"]]
        title = render_name_pattern(rng.pick(seed, "player.title", patterns), family, given or full)
    player = {
        "id": "player",
        "name": full,
        "family": family,
        "given": given,
        "title": title,
        "call": title,
        "tier": "major",
        "age": age,
        "gender": gender,
        "adult_context": "成年玩家角色（%d 岁），%s" % (age, identity["role"]),
        "public_role": identity["role"],
        "identity_id": identity["id"],
        "social_position": identity["social_position"],
        "baseline": identity["baseline"],
        "resources": list(identity["resources"]),
        "reputation": identity["reputation"],
        "risks": list(identity["risks"]),
        "background": [],
        "status": {"location_id": result["location_id"], "mood": None, "conditions": []},
    }
    player_scope = binding(player)
    player_scope["title"] = title

    # -- NPCs -----------------------------------------------------------------
    templates = {t["id"]: t for t in pack["character_templates"]}
    genders = _npc_genders(pack, combo, seed, preference)
    characters = {"player": player}
    scopes = {"player": player_scope}
    for slot in combo["slots"]:
        tpl = templates[slot]
        g = genders[slot]
        fam = names.next_family(allow_reuse=True)
        giv = names.given(g, slot)
        npc = {
            "id": slot,
            "template_id": slot,
            "name": fam + giv,
            "family": fam,
            "given": giv,
            "call": names.call(fam, giv, g, slot),
            "tier": "major",
            "age": rng.randint(seed, "npc.age", tpl["age_range"][0], tpl["age_range"][1], slot),
            "gender": g,
            "adult_context": tpl["adult_context"],
            "public_role": tpl["public_role"],
        }
        characters[slot] = npc
        scopes[slot] = binding(npc)
    for slot in combo["slots"]:
        tpl = templates[slot]
        npc = characters[slot]
        own = dict(scopes, npc=scopes[slot])
        tendency = tpl["intimacy_tendency"]
        npc.update(
            {
                "appearance": render(rng.pick(seed, "npc.appearance", tpl["appearance_options"], slot), own),
                "identity": _render_tree(
                    {
                        "authority": tpl["identity"]["authority"],
                        "resources": tpl["identity"]["resources"],
                        "limits": tpl["identity"]["limits"],
                        "obligations": tpl["identity"]["obligations"],
                        "exposure_risk": tpl["identity"]["exposure"],
                        "hidden_mismatch": tpl["identity"]["hidden"],
                    },
                    own,
                ),
                "situation": _render_tree(
                    {"trigger": tpl["situation"]["trigger"], "pressure": tpl["situation"]["pressure"], "deadline": None, "exits": tpl["situation"]["exits"]},
                    own,
                ),
                "decision": _render_tree(
                    {
                        "core_value": tpl["decision"]["core_value"],
                        "current_goal": rng.pick(seed, "npc.goal", tpl["decision"]["goal_options"], slot),
                        "goal_options": tpl["decision"]["goal_options"],
                        "pressure_responses": tpl["decision"]["pressure_responses"],
                        "withdrawal": tpl["decision"]["withdrawal"],
                        "relationship_stance": tpl["decision"]["relationship_stance"],
                        "contrast": tpl["decision"]["contrast"],
                        "prefers": tpl["decision"]["prefers"],
                        "avoids": tpl["decision"]["avoids"],
                        "never": tpl["decision"]["never"],
                    },
                    own,
                ),
                "intimacy": _render_tree(
                    {
                        "desire_level": rng.randint(seed, "npc.desire", tendency["desire_range"][0], tendency["desire_range"][1], slot),
                        "attraction_sources": tendency["attraction_sources"],
                        "likes": tendency["likes"],
                        "dislikes": tendency["dislikes"],
                        "preconditions": tendency["preconditions"],
                        "boundaries": tendency["boundaries"],
                        "expression": tendency["expression"],
                        "self_control": rng.randint(seed, "npc.control", tendency["self_control_range"][0], tendency["self_control_range"][1], slot),
                        "desired_position": tendency["desired_position"],
                    },
                    own,
                ),
                "voices": _render_tree(tpl["voices"], own),
                "schedule": [dict(s) for s in tpl["schedule"]],
                "status": {"location_id": result["location_id"], "mood": None, "conditions": []},
            }
        )

    # -- background cast ------------------------------------------------------
    for bg in sorted(pack["background_cast"], key=lambda b: b["id"]):
        g = background_gender(pack, bg, seed, preference)
        if bg["name"]:
            name, fam, giv = bg["name"], "", bg["name"]
        else:
            fam = names.next_family(allow_reuse=True)
            giv = names.given(g, bg["id"])
            name = fam + giv
        npc = {
            "id": bg["id"],
            "name": name,
            "family": fam,
            "given": giv,
            "call": names.call(fam, giv, g, bg["id"]) if fam else name,
            "tier": "background",
            "age": rng.randint(seed, "bg.age", bg["age_range"][0], bg["age_range"][1], bg["id"]),
            "gender": g,
            "adult_context": bg["adult_context"],
            "public_role": bg["role"],
            "function": bg["function"],
            "status": {"location_id": bg["location_ids"][0], "mood": None, "conditions": []},
        }
        characters[bg["id"]] = npc
        scopes[bg["id"]] = binding(npc)
        npc["line"] = render(bg["line"], dict(scopes, npc=scopes[bg["id"]]))

    # -- relationships ------------------------------------------------------------
    relationships = {}
    for rel in combo["relations"]:
        reason = render(rel["reason"], scopes)
        for src, dst, values in ((rel["a"], rel["b"], rel["a_to_b"]), (rel["b"], rel["a"], rel["b_to_a"])):
            relationships["%s>%s" % (src, dst)] = {
                "from": src,
                "to": dst,
                "trust": values["trust"],
                "tension": values["tension"],
                "stage": rel["stage"],
                "history": [{"turn": 1, "change": "init", "reason": reason}],
            }

    # -- facts ------------------------------------------------------------------
    facts = {}
    present = ["player"] + list(combo["slots"])

    def add_fact(key, text, known_by, visibility="private"):
        fid = "f%d" % (len(facts) + 1)
        facts[fid] = {
            "id": fid,
            "key": key,
            "text": text,
            "truth": True,
            "known_by": list(known_by),
            "believed_by": [],
            "visibility": visibility,
            "origin": "setup",
            "turn": 1,
            "spreading": False,
        }
        return fid

    for slot in combo["slots"]:
        npc = characters[slot]
        add_fact("%s.exposure" % slot, "%s：%s" % (npc["name"], npc["identity"]["exposure_risk"]), [slot])
        add_fact("%s.hidden" % slot, "%s：%s" % (npc["name"], npc["identity"]["hidden_mismatch"]), [slot])
    add_fact("player.baseline", "%s：%s" % (player["name"], identity["baseline"]) if identity["baseline"] else "%s是%s" % (player["name"], identity["role"]), ["player"])
    for index, risk in enumerate(identity["risks"]):
        add_fact("player.risk.%d" % (index + 1), "%s：%s" % (player["name"], risk), ["player"])
    stakes = _render_tree(combo["stakes"], scopes)
    add_fact("combo.meeting", stakes["meeting_reason"], present, "public")
    engines = {e["id"]: e for e in pack["tension_engines"]}
    engine_texts = []
    for engine_id in combo["tension_engine_ids"]:
        text = render(engines[engine_id]["text"], scopes)
        engine_texts.append(text)
        add_fact("tension.%s" % engine_id, text, present, "public")

    # -- pressure: events and leverage ------------------------------------------
    events = {}
    leverage = {}
    pressure_block = None
    if mode == "pressure":
        pr = _render_tree(item, scopes)
        pressure_block = {
            "id": pr["id"],
            "title": pr["title"],
            "source": pr["source"],
            "trigger": pr["trigger"],
            "objective": pr["objective"],
            "choice": pr["choice"],
            "exits": pr["exits"],
            "location_modifier": next((loc["pressure_modifiers"].get(pr["id"]) for loc in pack["locations"] if loc["id"] == result["location_id"]), None),
        }
        add_fact("pressure.%s.trigger" % pr["id"], pr["trigger"], present, "public")
        tiers = (
            ("immediate", "deadline", pr["immediate"]["minutes"], pr["immediate"]["text"]),
            ("near", "deadline", pr["near"]["deadline_minutes"], pr["near"]["text"]),
            ("far", "foreshadow", pr["far"]["due_days"] * ST.MINUTES_PER_DAY, "%s（%s）" % (pr["far"]["trigger"], pr["far"]["consequence"])),
        )
        for tier, kind, minutes, text in tiers:
            eid = "e%d" % (len(events) + 1)
            events[eid] = {
                "id": eid,
                "kind": kind,
                "tier": tier,
                "title": "%s·%s" % (pr["title"], {"immediate": "眼前", "near": "近期", "far": "伏笔"}[tier]),
                "text": text,
                "participants": list(present),
                "due": CL.add_minutes(now, minutes),
                "probability": None,
                "dedupe_key": "pressure.%s.%s" % (pr["id"], tier),
                "state": "pending",
                "outcome": None,
                "created_turn": 1,
                "resolved_turn": None,
                "note": None,
            }
        if pr["leverage"]:
            lv = pr["leverage"]
            basis = add_fact("leverage.%s" % pr["id"], render(lv["basis"], scopes), [lv["holder"], lv["subject"]])
            leverage["lv1"] = {
                "id": "lv1",
                "holder": lv["holder"],
                "subject": lv["subject"],
                "basis_fact_id": basis,
                "origin": "pressure:%s" % pr["id"],
                "state": "active",
                "created_turn": 1,
                "released_turn": None,
                "release_reason": None,
            }

    location = next(loc for loc in pack["locations"] if loc["id"] == result["location_id"])
    person = pack["default_person"]
    preferences = {
        "inner_view": False,
        "assistant": False,
        "offscreen_simulation": True,
        "voice": {},
        "npc_gender_preference": preference,
        "person": person,
        "pace": "standard",
        "explicitness": "standard",
    }
    state = {
        "schema_version": 1,
        "session_id": None,
        "revision": 1,
        "turn": 1,
        "seed": seed,
        "rng_version": rng.RNG_VERSION,
        "content_version": content_version,
        "world_id": pack["id"],
        "world_title": pack["title"],
        "custom_world": bool(pack.get("custom")),
        "mode": mode,
        "opening": dict(result, conditions=conditions),
        "clock": now,
        "scene": {"id": "sc1", "location_id": result["location_id"], "present": list(present), "since": dict(now), "responses": []},
        "player_id": "player",
        "characters": characters,
        "relationships": relationships,
        "facts": facts,
        "events": events,
        "leverage": leverage,
        "pressure": pressure_block,
        "preferences": preferences,
        "safety": {"paused": False, "boundaries": []},
        "memory": {"turns": [], "chapters": [], "prologue": None, "open_action": None, "last_quotes": []},
        "counters": {
            "next": {"fact": len(facts) + 1, "event": len(events) + 1, "leverage": len(leverage) + 1, "scene": 2, "boundary": 1},
            "major_action_turn": {},
            "intimacy_evidence": {},
            "twists": {"auto_offered": False, "accepted_days": [], "accepted": []},
            "last_chapter_turn": 1,
            "chapter_requested_at": None,
            "offscreen_beat_turn": {},
        },
        "requests": {"chapter_summary": False, "twist_offer": None, "offscreen_beat_candidates": []},
        "undo_floor": 1,
    }

    rule = rng.pick(seed, "opening.rule", sorted(pack["rules"], key=lambda r: r["id"]))
    customs = rng.shuffled(seed, "opening.customs", list(pack["customs"]))[:2]
    hook_text = render(hook["text"], dict(scopes, npc=scopes[hook["slot"]]))
    opening = {
        "seed": seed,
        "mode": mode,
        "signature": result["signature"],
        "world": {
            "title": pack["title"],
            "era": pack["era"],
            "region": pack["region"],
            "premise": pack["premise"],
            "tone": pack["tone"],
            "style_hint": pack["style_hint"],
            "date_label": pack["clock_start"]["label"],
            "rule_in_play": rule["text"],
            "customs": customs,
        },
        "player": {
            "name": player["name"],
            "title": title,
            "age": age,
            "gender": gender,
            "role": identity["role"],
            "social_position": identity["social_position"],
            "baseline": identity["baseline"],
            "resources": identity["resources"],
            "reputation": identity["reputation"],
        },
        "npcs": [
            {
                "id": slot,
                "name": characters[slot]["name"],
                "call": characters[slot]["call"],
                "age": characters[slot]["age"],
                "gender": characters[slot]["gender"],
                "role": characters[slot]["public_role"],
                "adult_context": characters[slot]["adult_context"],
                "appearance": characters[slot]["appearance"],
                "surface_voice": characters[slot]["voices"]["surface"],
            }
            for slot in combo["slots"]
        ],
        "scene": {
            "location_id": location["id"],
            "location": location["name"],
            "detail": location["detail"],
            "privacy": location["privacy"],
            "visibility": location["visibility"],
            "affordances": location["affordances"],
            "time_label": CL.label(now, pack.get("clock_style", "hm")),
        },
        "tension": {"engines": engine_texts, "chemistry": render(combo["chemistry"], scopes), "meeting_reason": stakes["meeting_reason"]},
        "hook": {"kind": hook["kind"], "text": hook_text},
        "person": person,
    }
    if mode == "daily":
        opening["activity"] = {"title": item["title"], "beats": [render(b, scopes) for b in item["beats"]], "duration_minutes": item["duration_minutes"]}
    else:
        opening["pressure"] = {
            "title": pressure_block["title"],
            "trigger": pressure_block["trigger"],
            "objective": pressure_block["objective"],
            "choice": pressure_block["choice"],
            "immediate": events["e1"]["text"],
            "near": {"text": events["e2"]["text"], "due_label": CL.label(events["e2"]["due"], pack.get("clock_style", "hm"))},
            "foreshadow": render(item["far"]["trigger"], scopes),
            "location_modifier": pressure_block["location_modifier"],
        }
    opening["footer"] = "【时间】%s｜【地点】%s｜回合：1｜种子：%d" % (CL.label(now, pack.get("clock_style", "hm")), location["name"], seed)
    return state, opening


def build(pack, seed, conditions, content_version):
    return instantiate(pack, seed, conditions, plan(pack, seed, conditions), content_version)


# ---------------------------------------------------------------------------
# Random openings with recent-history dedupe


def penalty(result, history):
    """Lower is better. history: newest first, dicts with signature etc."""
    score = 0
    recent = history[:10]
    if any(h["signature"] == result["signature"] for h in recent):
        score += 1000
    if history:
        last = history[0]
        if last["power_structure"] == result["power_structure"]:
            score += 3
        if last["identity_id"] == result["identity_id"]:
            score += 2
        if last.get("combo_id") == result["combo_id"]:
            score += 2
    if len(history) > 1 and history[1]["power_structure"] == result["power_structure"]:
        score += 1
    if result["hook_kind"] != "approach" and any(h["hook_kind"] != "approach" for h in history[:2]):
        score += 2
    return score


def choose_seed(evaluate, seed_stream, history, max_candidates=24):
    """Pick a seed from the stream, avoiding recent signatures and repetition.

    evaluate(seed) -> plan result dict (raises AppError NO_MATCH if impossible).
    Returns (seed, result). Deterministic for a given stream and history.
    """
    best = None
    for index, seed in enumerate(seed_stream):
        if index >= max_candidates:
            break
        result = evaluate(seed)
        score = penalty(result, history)
        if best is None or score < best[0]:
            best = (score, seed, result)
        if score == 0:
            break
    return best[1], best[2]
