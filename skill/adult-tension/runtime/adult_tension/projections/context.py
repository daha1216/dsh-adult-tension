"""Context projections for the model (DATA_CONTRACTS.md section 7).

Pure functions of (state, content, save info). Lists are bounded so the
brief context stays <= 6 KB and the full context <= 20 KB (UTF-8 JSON) no
matter how long the game runs; the trimming order is fixed here.
"""

import json

from ..domain import clock as CL
from ..domain import state as SS
from ..domain import structure as ST

BRIEF_LIMIT = 6 * 1024
FULL_LIMIT = 20 * 1024
LIMITS = {"due_soon": 10, "known_facts": 8, "recent": 3, "nearby": 5}


def size_of(obj):
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _clock(state, world):
    return {"day": state["clock"]["day"], "minute": state["clock"]["minute"], "label": CL.label(state["clock"], world.get("clock_style", "hm"))}


def _npc_brief(state, world, cid):
    char = state["characters"][cid]
    player = state["player_id"]
    to_player = SS.edge(state, cid, player) or {}
    entry = {
        "id": cid,
        "name": char["name"],
        "age": char["age"],
        "gender": char["gender"],
        "tier": char["tier"],
        "role": char["public_role"],
        "mood": char["status"]["mood"],
        "voice": _voice(state, cid),
        "can_act": SS.can_act(state, cid),
        "trust_to_player": to_player.get("trust", 0),
        "tension": to_player.get("tension", 0),
        "stage": SS.stage_label(world, to_player.get("stage", "stranger")),
    }
    if char["status"]["conditions"]:
        entry["conditions"] = [c["text"] for c in char["status"]["conditions"]]
    decision = char.get("decision")
    if decision:
        entry["goal"] = decision["current_goal"]
        entry["stance"] = decision["relationship_stance"]
    if char["tier"] == "background":
        entry["line"] = char.get("line")
    return entry


def _fact_score(state, fact, present_names, present_ids):
    score = 0
    head = fact["key"].split(".", 1)[0]
    if head in present_ids or any(name and name in fact["text"] for name in present_names):
        score += 3
    if fact["turn"] >= state["turn"] - 5:
        score += 2
    if fact["origin"] == "setup" and head == "player":
        score -= 1
    return score


def player_facts(state, limit=None):
    player = state["player_id"]
    present_ids = set(state["scene"]["present"]) - {player}
    present_names = [state["characters"][c]["name"] for c in present_ids]
    facts = [f for f in state["facts"].values() if player in f["known_by"] or player in f["believed_by"]]
    facts.sort(key=lambda f: (-_fact_score(state, f, present_names, present_ids), -f["turn"], f["id"]))
    out = []
    for fact in facts[:limit] if limit else facts:
        item = {"id": fact["id"], "text": fact["text"], "visibility": fact["visibility"]}
        if not fact["truth"]:
            item["believed_not_true"] = True
        out.append(item)
    return out


def _events(state, world, limit=None):
    pending = [e for e in state["events"].values() if e["state"] == "pending"]
    pending.sort(key=lambda e: (CL.to_abs(e["due"]), e["id"]))
    now = CL.to_abs(state["clock"])
    out = []
    for event in pending[:limit] if limit else pending:
        item = {
            "id": event["id"],
            "kind": event["kind"],
            "title": event["title"],
            "in_minutes": CL.to_abs(event["due"]) - now,
            "due_label": CL.label(event["due"], world.get("clock_style", "hm")),
        }
        if SS.player_involved(state, event):
            item["involves_player"] = True
        out.append(item)
    return out


def _leverage(state, only_present=False):
    present = set(state["scene"]["present"])
    out = []
    for lv in SS.active_leverage(state):
        if only_present and not ({lv["holder"], lv["subject"]} & present):
            continue
        out.append({"id": lv["id"], "holder": lv["holder"], "subject": lv["subject"], "basis_fact_id": lv["basis_fact_id"]})
    return out


def _voice(state, cid):
    value = state["preferences"]["voice"].get(cid)
    if isinstance(value, dict):
        return value.get("voice", "surface")
    return value or "surface"


def brief(state, content, save=None):
    world = content["world"]
    player = state["player_id"]
    pchar = state["characters"][player]
    scene = state["scene"]
    location = SS.location(world, scene["location_id"])
    present_npcs = [_npc_brief(state, world, cid) for cid in scene["present"] if cid != player]
    nearby = [
        {"id": cid, "name": char["name"], "role": char["public_role"]}
        for cid, char in sorted(state["characters"].items())
        if cid not in scene["present"] and char["status"]["location_id"] == scene["location_id"]
    ][: LIMITS["nearby"]]
    context = {
        "depth": "brief",
        "session_id": state["session_id"],
        "revision": state["revision"],
        "turn": state["turn"],
        "mode": state["mode"],
        "clock": _clock(state, world),
        "scene": {
            "id": scene["id"],
            "location_id": scene["location_id"],
            "location": location["name"] if location else scene["location_id"],
            "privacy": location["privacy"] if location else None,
            "present": list(scene["present"]),
        },
        "player": {
            "name": pchar["name"],
            "title": pchar["title"],
            "age": pchar["age"],
            "gender": pchar["gender"],
            "role": pchar["public_role"],
        },
        "present_npcs": present_npcs,
        "nearby": nearby,
        "due_soon": _events(state, world, LIMITS["due_soon"]),
        "known_facts": player_facts(state, LIMITS["known_facts"]),
        "recent": [t["summary"] for t in state["memory"]["turns"][-LIMITS["recent"] :]],
        "last_quotes": list(state["memory"]["last_quotes"]),
        "open_action": state["memory"]["open_action"],
        "scene_responses": [{"npc_id": r["npc_id"], "response": r["response"]} for r in scene["responses"][-3:]],
        "safety": {
            "paused": state["safety"]["paused"],
            "boundaries": [b["text"] for b in state["safety"]["boundaries"]],
            "leverage": _leverage(state, only_present=True),
        },
        "preferences": {
            "inner_view": state["preferences"]["inner_view"],
            "assistant": state["preferences"]["assistant"],
            "offscreen_simulation": state["preferences"]["offscreen_simulation"],
            "person": state["preferences"]["person"],
        },
        "save": save or {"current_slot": None, "turns_since_save": 0},
        "requests": dict(state["requests"]),
    }
    _fit(context, BRIEF_LIMIT, ("known_facts", "due_soon", "nearby", "scene_responses", "recent", "last_quotes"))
    return context


def _card(state, world, char):
    cid = char["id"]
    player = state["player_id"]
    card = {
        "id": cid,
        "name": char["name"],
        "call": char.get("call"),
        "age": char["age"],
        "gender": char["gender"],
        "tier": char["tier"],
        "role": char["public_role"],
        "adult_context": char["adult_context"],
        "location_id": char["status"]["location_id"],
        "present": cid in state["scene"]["present"],
        "can_act": SS.can_act(state, cid),
        "voice": _voice(state, cid),
    }
    for key in ("appearance", "voices"):
        if char.get(key):
            card[key] = char[key]
    if char.get("identity"):
        card["identity"] = char["identity"]
    if char.get("situation"):
        card["situation"] = char["situation"]
    if char.get("decision"):
        d = char["decision"]
        card["decision"] = {
            k: d[k]
            for k in ("core_value", "current_goal", "pressure_responses", "withdrawal", "relationship_stance", "contrast", "prefers", "avoids", "never")
            if k in d
        }
    if char.get("intimacy"):
        card["intimacy"] = char["intimacy"]
    edge = SS.edge(state, cid, player)
    if edge:
        card["to_player"] = {"trust": edge["trust"], "tension": edge["tension"], "stage": SS.stage_label(world, edge["stage"])}
    return card


def full(state, content, save=None):
    world = content["world"]
    context = brief(state, content, save)
    context["depth"] = "full"
    player = state["player_id"]
    pchar = state["characters"][player]
    context["player"].update(
        {
            "social_position": pchar.get("social_position"),
            "baseline": pchar.get("baseline"),
            "resources": pchar.get("resources"),
            "reputation": pchar.get("reputation"),
            "risks": pchar.get("risks"),
            "background": pchar.get("background"),
        }
    )
    context["world"] = {
        "title": world["title"],
        "era": world["era"],
        "region": world["region"],
        "premise": world["premise"],
        "tone": world["tone"],
        "style_hint": world["style_hint"],
        "rules": [r["text"] for r in world["rules"]],
        "customs": list(world["customs"]),
    }
    if world.get("stage_labels"):
        context["world"]["stage_labels"] = world["stage_labels"]
    context["locations"] = [
        {"id": loc["id"], "name": loc["name"], "privacy": loc["privacy"], "detail": loc["detail"], "affordances": loc["affordances"], "exits": loc["exits"]}
        for loc in world["locations"]
    ]
    majors = [c for c in state["characters"].values() if c["id"] != player and c["tier"] in ("major", "supporting")]
    majors.sort(key=lambda c: (c["id"] not in state["scene"]["present"], c["id"]))
    context["characters"] = [_card(state, world, c) for c in majors]
    context["background"] = [
        {"id": c["id"], "name": c["name"], "role": c["public_role"], "line": c.get("line"), "location_id": c["status"]["location_id"]}
        for c in sorted(state["characters"].values(), key=lambda c: c["id"])
        if c["tier"] == "background"
    ]
    relevant = {player} | {c["id"] for c in majors}
    context["relationships"] = [
        {
            "from": e["from"],
            "to": e["to"],
            "trust": e["trust"],
            "tension": e["tension"],
            "stage": SS.stage_label(world, e["stage"]),
            "recent": [h["reason"] for h in e["history"][-2:]],
        }
        for key, e in sorted(state["relationships"].items())
        if e["from"] in relevant and e["to"] in relevant
    ]
    context["player_facts"] = player_facts(state, 30)
    context["events"] = _events(state, world)
    context["leverage_all"] = _leverage(state)
    if state.get("pressure"):
        context["pressure"] = state["pressure"]
    context["chapters"] = [c["summary"] for c in state["memory"]["chapters"][-3:]]
    if state["memory"].get("prologue"):
        context["prologue"] = state["memory"]["prologue"]
    context["tags"] = [t["id"] for t in content["tags"]]
    pools = world["name_pools"]
    used = {c.get("family") for c in state["characters"].values()}
    context["name_pool"] = {
        "family_unused": [f for f in pools["family"] if f not in used][:12],
        "given_female": pools["given_female"][:12],
        "given_male": pools["given_male"][:12],
        "given_neutral": pools["given_neutral"][:8],
    }
    _fit(
        context,
        FULL_LIMIT,
        ("name_pool", "background", "player_facts", "relationships", "events", "customs", "chapters", "known_facts", "due_soon"),
    )
    return context


def _fit(context, limit, order):
    """Trim lists in the given order until the context fits."""
    if size_of(context) <= limit:
        context["size_bytes"] = size_of(context)
        return
    for key in order:
        holder = context
        if key == "customs":
            holder = context.get("world", {})
        value = holder.get(key)
        if isinstance(value, dict):
            holder[key] = {}
        while isinstance(holder.get(key), list) and holder[key] and size_of(context) > limit:
            holder[key].pop()
        if size_of(context) <= limit:
            break
    context["size_bytes"] = size_of(context)
