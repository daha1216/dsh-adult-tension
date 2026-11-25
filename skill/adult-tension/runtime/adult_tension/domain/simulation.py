"""Offscreen simulation, propagation and context requests (RUNTIME_PROTOCOL 6).

These are steps 4-6 of the settlement order, plugged into settlement.advance
as hooks. All randomness is derived from structured coordinates.
"""

from . import clock as CL
from . import facts as FA
from . import opening
from . import rng
from . import settlement
from . import state as SS
from . import structure as ST
from .text import binding, render

SPREAD_CHANCE = 0.5
MAX_SPREAD_HOPS = 3
MAX_REQUIRED_BEATS = 3
MAX_CANDIDATES = 3
CHAPTER_EVERY = 20
CHAPTER_CAP = 10
PROLOGUE_MERGE = 5
SCHEDULE_BLOCKING_CONDITIONS = frozenset(("away", "asleep", "unconscious"))


def frozen(state):
    return not state["preferences"]["offscreen_simulation"]


def hooks(turn):
    """Settlement steps 4-5 for a commit of the given turn."""
    return {
        "offscreen": lambda state, report: offscreen(state, report, turn),
        "propagation": lambda state, report: propagation(state, report, turn),
        "requests": lambda state, report: settlement_requests(state, report, turn),
    }


def _absent_majors(state):
    present = set(state["scene"]["present"])
    return sorted(
        cid
        for cid, char in state["characters"].items()
        if cid != state["player_id"] and char["tier"] == "major" and cid not in present
    )


def _priority(state, cid):
    pending = sum(1 for e in state["events"].values() if e["state"] == "pending" and cid in e["participants"])
    last_beat = state["counters"]["offscreen_beat_turn"].get(cid, 0)
    return (-min(pending, 1), last_beat, cid)


def beat_candidates(state, turn):
    if frozen(state):
        return []
    ready = [cid for cid in _absent_majors(state) if SS.can_act(state, cid, turn)]
    ready.sort(key=lambda cid: _priority(state, cid))
    return ready[:MAX_CANDIDATES]


def required_beats(state):
    if frozen(state):
        return []
    majors = _absent_majors(state)
    majors.sort(key=lambda cid: _priority(state, cid))
    return majors[:MAX_REQUIRED_BEATS]


def schedule_location(char, minute):
    for slot in char.get("schedule") or []:
        start, end = slot["from"], slot["to"]
        if start <= end and start <= minute <= end:
            return slot["location_id"]
        if start > end and (minute >= start or minute <= end):
            return slot["location_id"]
    return None


def offscreen(state, report, turn):
    """Step 4. Returns the offscreen part of the settlement report."""
    if frozen(state):
        return {"frozen": True, "tier": report["tier"], "moved": [], "required": [], "candidates": []}
    present = set(state["scene"]["present"])
    moved = []
    for cid in sorted(state["characters"]):
        char = state["characters"][cid]
        if cid == state["player_id"] or cid in present or char["tier"] == "background":
            continue
        if any(c["kind"] in SCHEDULE_BLOCKING_CONDITIONS for c in char["status"]["conditions"]):
            continue
        target = schedule_location(char, state["clock"]["minute"])
        if target and target != char["status"]["location_id"]:
            char["status"]["location_id"] = target
            moved.append({"character_id": cid, "location_id": target})
    tier = report["tier"]
    required = required_beats(state) if tier == "full" else []
    candidates = beat_candidates(state, turn) if tier in ("brief", "full") else []
    return {"frozen": False, "tier": tier, "moved": moved, "required": required, "candidates": candidates}


def _npc_knowers(state, fact):
    people = fact["known_by"] if fact["truth"] else fact["believed_by"]
    return [cid for cid in people if cid != state["player_id"]]


def _neighbors(state, cid):
    out = set()
    for edge in state["relationships"].values():
        if edge["from"] == cid:
            out.add(edge["to"])
        elif edge["to"] == cid:
            out.add(edge["from"])
    out.discard(state["player_id"])
    return sorted(out)


def propagation(state, report, turn):
    """Step 5: spreading facts travel exactly along relationship edges."""
    if frozen(state):
        return {"frozen": True, "spread": []}
    minutes = report["minutes"]
    if minutes >= ST.MINUTES_PER_DAY:
        hops = 3
    elif minutes >= ST.SCENE_BREAK_MINUTES:
        hops = 2
    elif minutes >= 16:
        hops = 1
    else:
        hops = 0
    spread = []
    for hop in range(hops):
        for fact in FA.of(state).spreading():
            fact = FA.edit(state, fact["id"])
            knowers = _npc_knowers(state, fact)
            candidates = sorted(
                {
                    neighbor
                    for knower in knowers
                    for neighbor in _neighbors(state, knower)
                    if neighbor not in fact["known_by"] and neighbor not in fact["believed_by"]
                }
            )
            coord = fact.get("coord") or [fact["turn"], fact["id"]]
            reached = [
                neighbor
                for neighbor in candidates
                if rng.unit(state["seed"], "spread", coord[0], coord[1], neighbor, turn, hop) < SPREAD_CHANCE
            ]
            target = fact["known_by"] if fact["truth"] else fact["believed_by"]
            target.extend(reached)
            if reached:
                if fact["truth"]:
                    for other in FA.of(state).by_key(fact["key"]):
                        if not other["truth"]:
                            misbelievers = [cid for cid in reached if cid in other["believed_by"]]
                            if misbelievers:
                                other = FA.edit(state, other["id"])
                                for cid in misbelievers:
                                    other["believed_by"].remove(cid)
                                    if cid not in other["known_by"]:
                                        other["known_by"].append(cid)
                spread.append({"fact_id": fact["id"], "to": reached, "hop": hop + 1})
            fact["spread_hops"] = fact.get("spread_hops", 0) + 1
            if fact["spread_hops"] >= MAX_SPREAD_HOPS:
                fact["spreading"] = False
    return {"frozen": False, "hops": hops, "spread": spread}


# ---------------------------------------------------------------------------
# twists


def _eligible(state, twist, world=None):
    accepted = {t.get("twist_id") for t in state["counters"]["twists"]["accepted"]}
    if twist["id"] in accepted:
        return False
    standby = {t["id"] for t in (world or {}).get("character_templates", [])}
    for token in twist["requires"]:
        if token in ("pressure", "daily"):
            if state["mode"] != token:
                return False
        elif token in state["characters"] or token in standby:
            continue
        elif state.get("pressure") and state["pressure"]["id"] == token:
            continue
        else:
            return False
    return True


def render_twist(state, twist, world=None):
    scopes = {cid: binding(char) for cid, char in state["characters"].items()}
    if world:
        for sid, preview in opening.standby_previews(state, world).items():
            scopes.setdefault(sid, binding(preview))
    scopes["player"] = binding(state["characters"][state["player_id"]])
    return {"id": twist["id"], "category": twist["category"], "text": render(twist["text"], scopes)}


def twist_candidates(state, world, purpose, *coords):
    """2-3 eligible twists from different categories, chosen deterministically."""
    pool = [t for t in sorted(world.get("twists", []), key=lambda t: t["id"]) if _eligible(state, t, world)]
    shuffled = rng.shuffled(state["seed"], purpose, pool, *coords)
    chosen = []
    categories = set()
    for twist in shuffled:
        if twist["category"] in categories:
            continue
        chosen.append(twist)
        categories.add(twist["category"])
        if len(chosen) == 3:
            break
    return [render_twist(state, t, world) for t in chosen]


def eligible_twist(state, world, twist_id):
    for twist in world.get("twists", []):
        if twist["id"] == twist_id:
            return twist if _eligible(state, twist, world) else None
    return None


# ---------------------------------------------------------------------------
# requests


def settlement_requests(state, report, turn):
    """Step 6: what this time skip asks of the next record. The record's end
    (finalize_requests) sets the actual requests, after every operation."""
    return {
        "chapter_summary": report["crossed_day"] or (turn - state["counters"]["last_chapter_turn"] >= CHAPTER_EVERY),
        "twist_offer": bool(report["crossed_day"] and state["mode"] == "pressure" and not state["counters"]["twists"]["auto_offered"]),
        "offscreen_beat_candidates": list((report.get("offscreen") or {}).get("candidates", [])),
    }


def finalize_requests(state, world, crossed_day, accepted_twist):
    """Step 6, run once at the end of every record (turn.close_record); the
    offscreen candidates are set after every turn."""
    requests = state["requests"]
    counters = state["counters"]
    memory = state["memory"]
    requests["chapter_summary"] = crossed_day or (state["turn"] - counters["last_chapter_turn"] >= CHAPTER_EVERY)
    requests["prologue"] = len(memory["chapters"]) > CHAPTER_CAP
    # An offer is shown once: in the context the day-crossing record returns.
    # The next record takes it or lets it go; a candidate's id can still be
    # accepted after that (twist_accept checks the world, not the offer).
    requests["twist_offer"] = None
    if crossed_day and not accepted_twist and state["mode"] == "pressure" and not counters["twists"]["auto_offered"]:
        offer = twist_candidates(state, world, "twist.auto", state["clock"]["day"])
        if offer:
            requests["twist_offer"] = offer
            counters["twists"]["auto_offered"] = True


def prologue_source(state):
    """What the model merges into the prologue when requests.prologue is set."""
    chapters = state["memory"]["chapters"][:PROLOGUE_MERGE]
    return {
        "previous": state["memory"]["prologue"],
        "chapters": [{"index": c["index"], "from_turn": c["from_turn"], "to_turn": c["to_turn"], "summary": c["summary"]} for c in chapters],
    }


def preview_npc(state, cid):
    char = state["characters"][cid]
    known = FA.of(state).known_to(cid)
    known.sort(key=lambda f: (f["turn"], FA.order(f)))
    return {
        "npc_id": cid,
        "name": char["name"],
        "goal": (char.get("decision") or {}).get("current_goal"),
        "location_id": char["status"]["location_id"],
        "mood": char["status"]["mood"],
        "knows": [{"id": f["id"], "text": f["text"]} for f in known[-5:]],
    }


def preview_payload(state, world, report):
    """What a time skip settles, right after steps 1-5 (RUNTIME_PROTOCOL 6.4).

    Built at the same point for get-context's preview and for the commit, so
    the two agree whenever advance_time is the commit's first operation. The
    requests the skip raises are left out: they bind the commit after this
    one, and shown here they read as this commit's.
    """
    style = world.get("clock_style", "hm")
    off = report.get("offscreen") or {}
    spread = (report.get("propagation") or {}).get("spread") or []
    return {
        "from": dict(report["from"], label=CL.label(report["from"], style)),
        "to": dict(report["to"], label=CL.label(report["to"], style)),
        "minutes": report["minutes"],
        "tier": report["tier"],
        "crossed_day": report["crossed_day"],
        "new_scene": bool(report["scene"]),
        "resolved_events": [dict(e) for e in report["resolved_events"]],
        "expired_conditions": [dict(c) for c in report["expired_conditions"]],
        "frozen": bool(off.get("frozen")),
        "moved": [dict(m) for m in off.get("moved", [])],
        "spread": [dict(s) for s in spread],
        "required_beats": [preview_npc(state, cid) for cid in off.get("required", [])],
        "beat_candidates": list(off.get("candidates", [])),
    }


def preview(state, world, spec):
    """Settle a time skip on a copy and describe it; the state is untouched."""
    work = FA.working_copy(state)
    minutes = settlement.minutes_for(work["clock"], spec)
    report = settlement.advance(work, minutes, work["turn"] + 1, hooks(work["turn"] + 1))
    return preview_payload(work, world, report)


def requested_twists(state, world):
    """Candidates for “来点转折” (get-context want_twist). Returns (candidates, note)."""
    day = state["clock"]["day"]
    if day in state["counters"]["twists"]["accepted_days"]:
        return [], "今天已经接受过一个转折；同一游戏日最多一次"
    offer = twist_candidates(state, world, "twist.want", state["turn"], day)
    if not offer:
        return [], "世界包里没有此刻可用的转折；可以请玩家口述一个（要有类别）"
    return offer, None


def label(state, world):
    return CL.label(state["clock"], world.get("clock_style", "hm"))
