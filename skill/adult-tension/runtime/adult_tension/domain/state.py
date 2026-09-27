"""Read helpers over the session state dict. No mutation except id allocation."""

from . import clock as CL
from . import structure as ST


def next_id(state, kind, prefix):
    counters = state["counters"]["next"]
    value = counters[kind]
    counters[kind] = value + 1
    return "%s%d" % (prefix, value)


def character(state, cid):
    return state["characters"].get(cid)


def is_npc(state, cid):
    return cid in state["characters"] and cid != state["player_id"]


def present(state):
    return state["scene"]["present"]


def is_present(state, cid):
    return cid in state["scene"]["present"]


def edge_key(a, b):
    return "%s>%s" % (a, b)


def edge(state, a, b):
    return state["relationships"].get(edge_key(a, b))


def has_edge_either(state, a, b):
    return edge_key(a, b) in state["relationships"] or edge_key(b, a) in state["relationships"]


def info_set(state, cid):
    """Fact ids the character knows or (mis)believes."""
    return {
        fid
        for fid, fact in state["facts"].items()
        if cid in fact["known_by"] or cid in fact["believed_by"]
    }


def knows(state, cid, fid):
    fact = state["facts"].get(fid)
    return fact is not None and (cid in fact["known_by"] or cid in fact["believed_by"])


def true_fact_by_key(state, key):
    for fact in state["facts"].values():
        if fact["key"] == key and fact["truth"]:
            return fact
    return None


def stage_index(stage):
    return ST.STAGES.index(stage)


def stage_label(world, stage):
    labels = world.get("stage_labels") or {}
    return labels.get(stage) or ST.STAGE_LABELS[stage]


def clock_label(state, world):
    return CL.label(state["clock"], world.get("clock_style", "hm"))


def location(world, lid):
    for loc in world["locations"]:
        if loc["id"] == lid:
            return loc
    return None


def can_act(state, cid, turn=None):
    """Whether a significant autonomous action is off cooldown for the next turn."""
    turn = state["turn"] + 1 if turn is None else turn
    last = state["counters"]["major_action_turn"].get(cid)
    return last is None or turn - last >= ST.COOLDOWN_TURNS


def player_involved(state, event):
    return state["player_id"] in event["participants"]


def active_leverage(state):
    return [lv for lv in state["leverage"].values() if lv["state"] == "active"]
