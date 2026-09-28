"""Offscreen beats and twists (registered into ops.SPECS).

An offscreen beat records what an absent NPC did while the player was not
there: only that NPC's own actions, relations between NPCs, facts and
events. It never changes the player character, never gives an NPC knowledge
outside its information set, and never settles events involving the player.
"""

from .. import schema as S
from ..errors import INVARIANT_VIOLATION, NOT_FOUND, detail
from . import simulation
from . import state as SS
from . import structure as ST
from .ops import SPECS, _flush, apply_op, register

F = S.Field
BEAT_OPS = (
    "npc_state",
    "npc_action",
    "move",
    "add_fact",
    "relationship",
    "reveal_fact",
    "spread_rumor",
    "event_create",
    "event_resolve",
    "event_cancel",
    "leverage_set",
    "leverage_release",
)
ID_FIELDS = ("npc_id", "character_id", "from", "to", "known_by", "believed_by", "participants", "holder", "subject", "target_id")


def beat_spec():
    return S.List(S.Tagged("op", {name: SPECS[name] for name in BEAT_OPS}, "离屏操作"), max_items=6)


def _mentions(op, cid):
    for field in ID_FIELDS:
        value = op.get(field)
        if value == cid or (isinstance(value, list) and cid in value):
            return True
    return False


def _actor_ok(ctx, npc, op):
    kind = op["op"]
    state = ctx.state
    if kind in ("npc_state", "npc_action"):
        return op["npc_id"] == npc
    if kind == "move":
        return op["character_id"] == npc
    if kind == "add_fact":
        return npc in op["known_by"] or npc in op["believed_by"]
    if kind == "relationship":
        return npc in (op["from"], op["to"])
    if kind in ("reveal_fact", "spread_rumor"):
        return op["from"] == npc
    if kind == "event_create":
        return npc in op["participants"]
    if kind in ("event_resolve", "event_cancel"):
        event = state["events"].get(op["event_id"])
        return event is None or npc in event["participants"]
    if kind == "leverage_set":
        return npc in (op["holder"], op["subject"])
    if kind == "leverage_release":
        lv = state["leverage"].get(op["leverage_id"])
        return lv is None or npc in (lv["holder"], lv["subject"])
    return False


@register(
    "offscreen_beat",
    {
        "npc_id": F(S.Id()),
        "summary": F(S.Str(1, 120)),
        "operations": F(S.List(S.Any("离屏操作"), max_items=6), required=False, default=[]),
    },
    "离屏片段：不在场的重要 NPC 在这段时间里做了什么。只能写上下文 `offscreen_beat_candidates` 或时间推进要求的 NPC；子操作只能是这个 NPC 自己的行动、状态、移动，NPC 之间的关系与消息，以及不涉及玩家的事件与把柄",
    branch=False,
)
def op_offscreen_beat(ctx, op, path):
    errs = []
    state = ctx.state
    npc = op["npc_id"]
    if simulation.frozen(state):
        errs.append(detail(path, "离屏推演已冻结，不产生离屏片段", "玩家打开离屏推演后再写", INVARIANT_VIOLATION))
    elif npc not in state["characters"]:
        errs.append(detail(path + ".npc_id", "角色不存在：%s" % npc, None, NOT_FOUND))
    else:
        if npc in ctx.beat_npcs:
            errs.append(detail(path + ".npc_id", "同一提交里 %s 只能有一段离屏片段" % ctx.name(npc), None, INVARIANT_VIOLATION))
        if npc not in ctx.beat_candidates and npc not in ctx.required_beats:
            hint = "只能写上下文 requests.offscreen_beat_candidates 或推进时间后要求的 NPC"
            if ctx.time_ops == 0:
                hint += "；推进时间带来的离屏片段写在 advance_time 之后"
            errs.append(detail(path + ".npc_id", "%s 不在离屏片段的候选里" % ctx.name(npc), hint, INVARIANT_VIOLATION))
        if SS.is_present(state, npc):
            errs.append(detail(path + ".npc_id", "%s 在场，不是离屏" % ctx.name(npc), None, INVARIANT_VIOLATION))
    subs, problems = S.validate(beat_spec(), op["operations"], path + ".operations")
    errs.extend(problems)
    if subs is not None:
        player = state["player_id"]
        for index, sub in enumerate(subs):
            sub_path = "%s.operations[%d]" % (path, index)
            if _mentions(sub, player):
                errs.append(detail(sub_path, "离屏片段不能改变或牵涉玩家角色", "玩家角色只在台前行动", INVARIANT_VIOLATION))
            elif not _actor_ok(ctx, npc, sub):
                errs.append(detail(sub_path, "离屏片段里的操作必须是 %s 自己做的、自己知道的或与自己有关的" % ctx.name(npc), None, INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    outer = ctx.applied
    ctx.applied = []
    ctx.in_beat = npc
    try:
        for index, sub in enumerate(subs):
            apply_op(ctx, sub, "%s.operations[%d]" % (path, index))
    finally:
        sub_applied = ctx.applied
        ctx.applied = outer
        ctx.in_beat = None
    ctx.beat_npcs.add(npc)
    if ctx.settlements:
        ctx.beats_after_time.add(npc)
    ctx.beats.append({"npc_id": npc, "summary": op["summary"]})
    state["counters"]["offscreen_beat_turn"][npc] = ctx.turn
    ctx.observable = True
    ctx.applied.append({"op": "offscreen_beat", "npc_id": npc, "summary": op["summary"], "applied": sub_applied})


@register(
    "twist_accept",
    {
        "twist_id": F(S.Nullable(S.Id()), required=False, default=None),
        "category": F(S.Nullable(S.Enum(*ST.TWIST_CATEGORIES)), required=False, default=None),
        "text": F(S.Nullable(S.Str(1, 160)), required=False, default=None),
    },
    "接受一个转折：引用上下文 requests.twist_offer 或 get-context want_twist 给出的候选 id（写进 twist_id），或给出玩家口述的转折（category 与 text 必填）。玩家选定时用 result 模式并带 player_authorized；同一游戏日最多接受一次",
    branch=False,
)
def op_twist_accept(ctx, op, path):
    errs = []
    state = ctx.state
    twists = state["counters"]["twists"]
    day = state["clock"]["day"]
    if day in twists["accepted_days"]:
        errs.append(detail(path, "今天已经接受过一个转折了", "同一游戏日最多一次；等到下一天", INVARIANT_VIOLATION))
    if not ctx.authorized or ctx.mode not in ("result", "attempt"):
        errs.append(detail(path, "转折要由玩家选定：result 模式并带 player_authorized", None, INVARIANT_VIOLATION))
    entry = None
    if op["twist_id"] is not None:
        if op["category"] or op["text"]:
            errs.append(detail(path, "引用候选时不要再写 category 与 text", None, INVARIANT_VIOLATION))
        twist = simulation.eligible_twist(state, ctx.world, op["twist_id"])
        if twist is None:
            errs.append(detail(path + ".twist_id", "这个转折不可用：%s" % op["twist_id"], "用上下文给出的候选，或让玩家口述一个", NOT_FOUND))
        else:
            entry = dict(simulation.render_twist(state, twist), twist_id=twist["id"])
    elif not (op["category"] and op["text"]):
        errs.append(detail(path, "玩家口述的转折要写 category 与 text", "category 取七类之一：%s" % "、".join(ST.TWIST_CATEGORIES), INVARIANT_VIOLATION))
    else:
        entry = {"twist_id": None, "id": None, "category": op["category"], "text": op["text"]}
    if not _flush(ctx, errs):
        return
    entry.update(day=day, turn=ctx.turn)
    twists["accepted"].append(entry)
    twists["accepted_days"].append(day)
    ctx.accepted_twist = entry
    ctx.observable = True
    ctx.applied.append({"op": "twist_accept", "twist_id": entry["twist_id"], "category": entry["category"], "text": entry["text"]})

