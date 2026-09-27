"""`status` views: six plain lines, 状态+ sections, and the debug view.

Plain-language views never show field names or relationship numbers, and
状态+ lists only what the player character knows.
"""

from ..domain import clock as CL
from ..domain import state as SS
from ..domain import structure as ST
from . import context as CX

PREFERENCE_WORDS = {"inner_view": "内心可见", "assistant": "叙事助手", "offscreen_simulation": "离屏推演"}
# Foreshadows, rumors and chance rolls are the engine's business, not the player's to-do list.
PLAYER_VISIBLE_KINDS = ("promise", "deadline", "opportunity")


def _player_events(state):
    return sorted(
        (e for e in state["events"].values() if e["state"] == "pending" and e["kind"] in PLAYER_VISIBLE_KINDS and SS.player_involved(state, e)),
        key=lambda e: (CL.to_abs(e["due"]), e["id"]),
    )


def trust_words(value):
    if value <= -3:
        return "很不信任你"
    if value <= -1:
        return "对你有些提防"
    if value == 0:
        return "对你还在观望"
    if value <= 2:
        return "愿意信你几分"
    return "很信任你"


def tension_words(value):
    if value <= 0:
        return None
    if value <= 2:
        return "有点紧绷"
    if value <= 4:
        return "绷得很紧"
    return "一触即发"


def remaining(minutes):
    if minutes < 60:
        return "还有约 %d 分钟" % max(1, minutes)
    if minutes < ST.MINUTES_PER_DAY:
        return "还有约 %d 小时" % round(minutes / 60.0)
    return "还有约 %d 天" % round(minutes / float(ST.MINUTES_PER_DAY))


def _name(state, cid):
    return state["characters"][cid]["name"] if cid in state["characters"] else cid


def lines(state, content):
    world = content["world"]
    player = state["player_id"]
    scene = state["scene"]
    location = SS.location(world, scene["location_id"])
    loc_name = location["name"] if location else scene["location_id"]
    out = ["%s · %s" % (CL.label(state["clock"], world.get("clock_style", "hm")), loc_name)]
    present = [c for c in scene["present"] if c != player]
    people = []
    for cid in present:
        char = state["characters"][cid]
        bits = [char["public_role"]]
        if char["status"]["mood"]:
            bits.append(char["status"]["mood"])
        bits.extend(c["text"] for c in char["status"]["conditions"])
        people.append("%s（%s）" % (char["name"], "，".join(bits)))
    out.append("在场：%s" % ("、".join(people) if people else "只有你自己"))
    relations = []
    for cid in present:
        edge = SS.edge(state, cid, player)
        if edge is None:
            relations.append("%s和你还没有打过交道" % _name(state, cid))
            continue
        words = [trust_words(edge["trust"])]
        tension = tension_words(edge["tension"])
        if tension:
            words.append(tension)
        relations.append("%s%s（%s）" % (_name(state, cid), "，".join(words), SS.stage_label(world, edge["stage"])))
    out.append("关系：%s" % ("；".join(relations) if relations else "身边没有人"))
    now = CL.to_abs(state["clock"])
    todo = ["%s（%s）" % (e["title"], remaining(CL.to_abs(e["due"]) - now)) for e in _player_events(state)[:3]]
    for lv in SS.active_leverage(state):
        if lv["subject"] == player:
            todo.append("%s手里有你的把柄" % _name(state, lv["holder"]))
        elif lv["holder"] == player:
            todo.append("你握着%s的把柄" % _name(state, lv["subject"]))
    out.append("压力与待办：%s" % ("；".join(todo) if todo else "眼下没有压着的事"))
    boundaries = [b["text"] for b in state["safety"]["boundaries"]]
    pause = "已暂停（说“继续”恢复，或说“换个场景”）" if state["safety"]["paused"] else "未暂停"
    out.append("边界与暂停：%s；%s" % ("、".join(boundaries) if boundaries else "没有登记边界", pause))
    options = []
    if state["memory"]["open_action"]:
        options.append("眼下停在：%s" % state["memory"]["open_action"])
    if location:
        options.append("这里可以%s" % "、".join(location["affordances"][:3]))
        exits = [SS.location(world, e)["name"] for e in location["exits"] if SS.location(world, e)]
        if exits:
            options.append("也可以去%s" % "、".join(exits))
    out.append("现在可以做什么：%s" % "；".join(options))
    return out


def detail_sections(state, content):
    world = content["world"]
    player = state["player_id"]
    sections = []
    changes = []
    for key, edge in sorted(state["relationships"].items()):
        if edge["to"] != player or edge["from"] not in state["characters"]:
            continue
        reasons = [h["reason"] for h in edge["history"][-2:]]
        if reasons:
            changes.append("%s（%s）：%s" % (_name(state, edge["from"]), SS.stage_label(world, edge["stage"]), "；".join(reasons)))
    sections.append({"title": "关系变化的原因", "items": changes or ["还没有值得一提的变化"]})
    deadlines = []
    for event in _player_events(state):
        deadlines.append("%s：%s前" % (event["title"], CL.label(event["due"], world.get("clock_style", "hm"))))
    sections.append({"title": "承诺与期限", "items": deadlines or ["没有未了的约定或期限"]})
    secrets = [f["text"] for f in state["facts"].values() if f["visibility"] == "private" and (player in f["known_by"] or player in f["believed_by"])]
    sections.append({"title": "你知道的秘密", "items": secrets[-12:] or ["还没有"]})
    people = []
    for char in sorted(state["characters"].values(), key=lambda c: (c["id"] not in state["scene"]["present"], c["id"])):
        if char["id"] == player or char["tier"] == "background":
            continue
        if not SS.edge(state, player, char["id"]) and char["id"] not in state["scene"]["present"]:
            continue
        text = "%s，%d 岁，%s" % (char["name"], char["age"], char["public_role"])
        if char.get("appearance"):
            text += "。%s" % char["appearance"]
        people.append(text)
    sections.append({"title": "人物", "items": people or ["身边没有熟人"]})
    movers = [char["name"] for cid, char in sorted(state["characters"].items()) if cid in state["scene"]["present"] and cid != player and char["tier"] != "background" and SS.can_act(state, cid)]
    sections.append({"title": "谁可能主动出手", "items": movers or ["眼下没有人会主动出手"]})
    prefs = state["preferences"]
    sections.append(
        {
            "title": "设置",
            "items": ["%s：%s" % (label, "开" if prefs[key] else "关") for key, label in PREFERENCE_WORDS.items()]
            + ["人称：%s" % {"second": "第二人称", "first": "第一人称", "third": "第三人称"}[prefs["person"]]],
        }
    )
    return sections


def debug_view(state, content, save, recent):
    brief = CX.brief(state, content, save)
    full = CX.full(state, content, save)
    from ..domain import invariants

    return {
        "revision": state["revision"],
        "turn": state["turn"],
        "state": state,
        "recent_commits": recent,
        "context_bytes": {"brief": brief["size_bytes"], "full": full["size_bytes"]},
        "invariant_problems": invariants.check(state),
    }
