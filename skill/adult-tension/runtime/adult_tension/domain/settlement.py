"""Time advance and settlement, in the fixed order of RUNTIME_PROTOCOL.md 6.1:

1. clock forward (new scene when the jump is >= 60 minutes)
2. due events, by (due, id): expire, roll chance events, surface foreshadows
3. timed character conditions expire
4. offscreen simulation (by span tier)
5. propagation of spreading facts
6. context requests for the next commit
"""

from . import clock as CL
from . import rng
from . import structure as ST


ADVANCE_KEYS = ("minutes", "until", "days")


def minutes_for(clock, spec):
    """Minutes for an advance spec with exactly one of minutes / until / days."""
    if "minutes" in spec:
        return spec["minutes"]
    if "days" in spec:
        return spec["days"] * ST.MINUTES_PER_DAY
    return CL.until_target(clock, spec["until"])


def tier_for(minutes, crossed_day=False):
    if minutes >= 60 or crossed_day:
        return "full"
    if minutes >= 16:
        return "brief"
    return "routine"


def new_scene(state, reason):
    counters = state["counters"]["next"]
    scene_id = "sc%d" % counters["scene"]
    counters["scene"] += 1
    state["scene"]["id"] = scene_id
    state["scene"]["since"] = dict(state["clock"])
    # Interaction judgments never outlive their scene (NARRATIVE_RULES.md 7.1).
    state["scene"]["responses"] = []
    return {"scene_id": scene_id, "reason": reason}


def settle_events(state, until_clock, turn):
    due = [
        e
        for e in state["events"].values()
        if e["state"] == "pending" and CL.to_abs(e["due"]) <= CL.to_abs(until_clock)
    ]
    due.sort(key=lambda e: (CL.to_abs(e["due"]), e["id"]))
    resolved = []
    for event in due:
        if event["kind"] == "chance":
            # Stable coordinates (creating turn, creation index), never the id:
            # an undone and redone turn gets the same roll.
            coord = event.get("coord") or [event["created_turn"], event["id"]]
            roll = rng.unit(state["seed"], "event", coord[0], coord[1])
            outcome = "hit" if roll < event["probability"] else "miss"
        else:
            outcome = ST.DUE_OUTCOME[event["kind"]]
        event["state"] = "resolved"
        event["outcome"] = outcome
        event["resolved_turn"] = turn
        resolved.append(
            {
                "event_id": event["id"],
                "kind": event["kind"],
                "title": event["title"],
                "outcome": outcome,
                "due": dict(event["due"]),
            }
        )
    return resolved


def expire_conditions(state, until_clock):
    now = CL.to_abs(until_clock)
    expired = []
    for cid in sorted(state["characters"]):
        char = state["characters"][cid]
        conditions = char["status"]["conditions"]
        keep = []
        for cond in conditions:
            if cond.get("until") is not None and CL.to_abs(cond["until"]) <= now:
                expired.append({"character_id": cid, "kind": cond["kind"], "text": cond["text"]})
            else:
                keep.append(cond)
        char["status"]["conditions"] = keep
    return expired


def advance(state, minutes, turn, hooks=None):
    """Advance the clock and settle. Returns the settlement report.

    `hooks` lets later stages plug offscreen simulation, propagation and
    request computation into steps 4-6 without changing the order.
    """
    hooks = hooks or {}
    before = dict(state["clock"])
    state["clock"] = CL.add_minutes(before, minutes)
    crossed_day = state["clock"]["day"] > before["day"]
    report = {
        "from": before,
        "to": dict(state["clock"]),
        "minutes": minutes,
        "tier": tier_for(minutes, crossed_day),
        "crossed_day": crossed_day,
        "steps": ["clock"],
        "scene": None,
        "resolved_events": [],
        "expired_conditions": [],
        "offscreen": None,
        "propagation": None,
        "requests": None,
    }
    if minutes >= ST.SCENE_BREAK_MINUTES:
        report["scene"] = new_scene(state, "time_skip")
    report["resolved_events"] = settle_events(state, state["clock"], turn)
    report["steps"].append("events")
    report["expired_conditions"] = expire_conditions(state, state["clock"])
    report["steps"].append("status")
    if "offscreen" in hooks:
        report["offscreen"] = hooks["offscreen"](state, report)
    report["steps"].append("offscreen")
    if "propagation" in hooks:
        report["propagation"] = hooks["propagation"](state, report)
    report["steps"].append("propagation")
    if "requests" in hooks:
        report["requests"] = hooks["requests"](state, report)
    report["steps"].append("requests")
    return report
