"""Operations the model submits (DATA_CONTRACTS.md section 6.1).

Each operation has a shape spec (used for validation and for the generated
references/operations.md) and a handler. A handler first collects every
problem for its operation; only when there are none does it change the
working copy. Operations apply in order; later ones see earlier effects.
"""

from .. import schema as S
from ..errors import INVARIANT_VIOLATION, NOT_FOUND, SAFETY_BLOCK, detail
from . import clock as CL
from . import rng
from . import settlement
from . import state as SS
from . import structure as ST

F = S.Field
FACT_KEY = S.Str(1, 80, r"[a-z0-9_]+(\.[a-z0-9_#]+){0,5}", "点分的 ASCII 小写键，例如 lin_wan.secret.press")
CLOCK = S.Obj({"day": F(S.Int(1, 100000)), "minute": F(S.Int(0, 1439))}, name="游戏时钟")
CONDITION = S.Obj(
    {
        "kind": F(S.Enum(*ST.CONDITION_KINDS)),
        "text": F(S.Str(1, 40)),
        "minutes": F(S.Nullable(S.Int(1, ST.MAX_ADVANCE_MINUTES)), required=False, default=None),
    },
    name="状况",
)


def _op(name, fields, desc):
    spec = {"op": F(S.Enum(name))}
    spec.update(fields)
    return S.Obj(spec, desc=desc, name=name)


SPECS = {}
DESCRIPTIONS = {}
HANDLERS = {}


def register(name, fields, desc, branch=True):
    def wrap(func):
        SPECS[name] = _op(name, fields, desc)
        DESCRIPTIONS[name] = desc
        HANDLERS[name] = (func, branch)
        return func

    return wrap


class TurnContext:
    """Mutable bookkeeping for one commit, over a working copy of the state."""

    def __init__(self, state, world, commit, hooks=None):
        self.state = state
        self.world = world
        self.commit = commit
        self.mode = commit["action_mode"]
        self.authorized = commit["player_authorized"]
        self.turn = state["turn"] + 1
        self.errors = []
        self.applied = []
        self.resolved_events = []
        self.settlements = []
        self.roll_index = 0
        self.responses = {}
        self.actors = set()
        self.observable = False
        self.time_ops = 0
        self.trust_start = {}
        self.stage_pairs = set()
        self.player_moved = False
        self.new_characters = []
        self.hooks = hooks or {}
        self.in_beat = None
        self.moved = {}
        self.relationship_reasons = []
        self.voice_reasons = []
        self.card_ops = {}
        # Ids reserved by the world pack: never reused for new characters.
        self.world_ids = {t["id"] for t in world.get("character_templates", [])} | {b["id"] for b in world.get("background_cast", [])}

    def error(self, path, reason, hint=None, code=INVARIANT_VIOLATION):
        self.errors.append(detail(path, reason, hint, code))

    def name(self, cid):
        char = self.state["characters"].get(cid)
        return char["name"] if char else cid

    def frozen(self):
        return not self.state["preferences"]["offscreen_simulation"]


def _need_character(ctx, cid, path, errs, npc=False):
    if cid not in ctx.state["characters"]:
        errs.append(detail(path, "角色不存在：%s" % cid, "用上下文里列出的角色 ID；新角色先 introduce_character", NOT_FOUND))
        return False
    if npc and cid == ctx.state["player_id"]:
        errs.append(detail(path, "这里需要 NPC，不能是玩家角色", None, INVARIANT_VIOLATION))
        return False
    return True


def _basis(ctx, npc_id, fact_ids, path, errs):
    for index, fid in enumerate(fact_ids):
        if fid not in ctx.state["facts"]:
            errs.append(detail("%s[%d]" % (path, index), "事实不存在：%s" % fid, None, NOT_FOUND))
        elif not SS.knows(ctx.state, npc_id, fid):
            errs.append(
                detail(
                    "%s[%d]" % (path, index),
                    "%s 不知道事实 %s，不能以它为依据" % (ctx.name(npc_id), fid),
                    "NPC 只能依据自己知道或误信的事实行动；先让信息以合理途径传到对方",
                    INVARIANT_VIOLATION,
                )
            )


def _absent_actor_ok(ctx, npc_id, path, errs):
    if not SS.is_present(ctx.state, npc_id) and ctx.frozen() and ctx.in_beat is None:
        errs.append(detail(path, "离屏推演已冻结，不在场的 %s 不能行动" % ctx.name(npc_id), "等玩家打开离屏推演，或让对方先登场", INVARIANT_VIOLATION))
        return False
    return True


def _flush(ctx, errs):
    if errs:
        ctx.errors.extend(errs)
        return False
    return True


# ---------------------------------------------------------------------------
# time


@register(
    "advance_time",
    {
        "minutes": F(S.Int(1, ST.MAX_ADVANCE_MINUTES), required=False),
        "until": F(S.Enum("morning", "noon", "evening", "night", "next_morning"), required=False),
        "days": F(S.Int(1, 30), required=False),
    },
    "推进游戏时钟：minutes / until / days 三选一；触发到期事件与状态到期结算。没有此操作时时钟默认推进 3 分钟",
    branch=False,
)
def op_advance_time(ctx, op, path):
    errs = []
    given = [k for k in ("minutes", "until", "days") if k in op]
    if len(given) != 1:
        errs.append(detail(path, "minutes、until、days 必须且只能给一个", None, INVARIANT_VIOLATION))
    ctx.time_ops += 1
    if ctx.time_ops > 1:
        errs.append(detail(path, "一次提交最多一个 advance_time", "把两段时间合并成一次推进", INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    if "minutes" in op:
        minutes = op["minutes"]
    elif "days" in op:
        minutes = op["days"] * ST.MINUTES_PER_DAY
    else:
        minutes = CL.until_target(ctx.state["clock"], op["until"])
    advance(ctx, minutes, path)


def advance(ctx, minutes, path, default=False):
    report = settlement.advance(ctx.state, minutes, ctx.turn, ctx.hooks)
    report["default"] = default
    ctx.settlements.append(report)
    ctx.resolved_events.extend(report["resolved_events"])
    ctx.applied.append(
        {
            "op": "advance_time",
            "minutes": minutes,
            "default": default,
            "clock": dict(ctx.state["clock"]),
            "label": SS.clock_label(ctx.state, ctx.world),
            "new_scene": bool(report["scene"]),
        }
    )
    return report


# ---------------------------------------------------------------------------
# scene


@register(
    "move",
    {"character_id": F(S.Id()), "location_id": F(S.Id())},
    "角色移动到地点。玩家移动需要 result/attempt 模式并带 player_authorized；玩家换地点即换场景",
)
def op_move(ctx, op, path):
    errs = []
    cid, lid = op["character_id"], op["location_id"]
    if not _need_character(ctx, cid, path + ".character_id", errs):
        return _flush(ctx, errs)
    if SS.location(ctx.world, lid) is None:
        errs.append(detail(path + ".location_id", "地点不在本局快照中：%s" % lid, "用上下文地点列表里的 ID", NOT_FOUND))
    is_player = cid == ctx.state["player_id"]
    if is_player:
        if ctx.mode not in ("result", "attempt") or not ctx.authorized:
            errs.append(detail(path, "玩家角色的移动只能出现在 result/attempt 模式并带 player_authorized: true", "继续/等待回合里玩家角色不移动", INVARIANT_VIOLATION))
        if lid == ctx.state["scene"]["location_id"]:
            errs.append(detail(path + ".location_id", "玩家已经在这里", None, INVARIANT_VIOLATION))
    else:
        _absent_actor_ok(ctx, cid, path, errs)
    if not _flush(ctx, errs):
        return
    char = ctx.state["characters"][cid]
    char["status"]["location_id"] = lid
    scene = ctx.state["scene"]
    if is_player:
        scene["location_id"] = lid
        # NPCs who went ahead to the same place earlier in this commit are there.
        scene["present"] = [ctx.state["player_id"]] + [n for n, where in ctx.moved.items() if where == lid]
        settlement.new_scene(ctx.state, "location")
        ctx.player_moved = True
    else:
        ctx.moved[cid] = lid
        ctx.actors.add(cid)
        ctx.observable = True
        if lid == scene["location_id"]:
            if cid not in scene["present"]:
                scene["present"].append(cid)
        elif cid in scene["present"]:
            scene["present"].remove(cid)
    ctx.applied.append({"op": "move", "character_id": cid, "location_id": lid})


@register("enter_scene", {"character_id": F(S.Id())}, "角色登场，加入当前场景")
def op_enter_scene(ctx, op, path):
    errs = []
    cid = op["character_id"]
    if _need_character(ctx, cid, path + ".character_id", errs, npc=True) and SS.is_present(ctx.state, cid):
        errs.append(detail(path + ".character_id", "%s 已经在场" % ctx.name(cid), None, INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    ctx.state["scene"]["present"].append(cid)
    ctx.state["characters"][cid]["status"]["location_id"] = ctx.state["scene"]["location_id"]
    ctx.observable = True
    ctx.applied.append({"op": "enter_scene", "character_id": cid})


@register(
    "exit_scene",
    {"character_id": F(S.Id()), "to_location_id": F(S.Nullable(S.Id()), required=False, default=None)},
    "角色离场；可写去向地点。玩家角色用 move",
)
def op_exit_scene(ctx, op, path):
    errs = []
    cid = op["character_id"]
    if _need_character(ctx, cid, path + ".character_id", errs, npc=True) and not SS.is_present(ctx.state, cid):
        errs.append(detail(path + ".character_id", "%s 不在场" % ctx.name(cid), None, INVARIANT_VIOLATION))
    target = op["to_location_id"]
    if target is not None and SS.location(ctx.world, target) is None:
        errs.append(detail(path + ".to_location_id", "地点不在本局快照中：%s" % target, None, NOT_FOUND))
    if not _flush(ctx, errs):
        return
    ctx.state["scene"]["present"].remove(cid)
    if target is not None:
        ctx.state["characters"][cid]["status"]["location_id"] = target
    ctx.observable = True
    ctx.applied.append({"op": "exit_scene", "character_id": cid, "to_location_id": target})


# ---------------------------------------------------------------------------
# NPC


@register(
    "npc_response",
    {
        "npc_id": F(S.Id()),
        "response": F(S.Enum(*ST.RESPONSES)),
        "note": F(S.Str(1, 80)),
        "basis_fact_ids": F(S.List(S.Id(), max_items=8, unique=True), required=False, default=[]),
        "true_intent": F(S.Nullable(S.Str(1, 120)), required=False, default=None),
    },
    "NPC 对玩家尝试的回应：refuse 拒绝 / negotiate 协商 / partial 有限配合 / surface 表面配合 / genuine 真诚配合。surface 必须写 true_intent（记为只有本人知道的事实）",
)
def op_npc_response(ctx, op, path):
    errs = []
    npc = op["npc_id"]
    if _need_character(ctx, npc, path + ".npc_id", errs, npc=True):
        if not SS.is_present(ctx.state, npc):
            errs.append(detail(path + ".npc_id", "%s 不在场，不能当面回应" % ctx.name(npc), "先 enter_scene", INVARIANT_VIOLATION))
        _basis(ctx, npc, op["basis_fact_ids"], path + ".basis_fact_ids", errs)
    if op["response"] == "surface" and not op["true_intent"]:
        errs.append(detail(path + ".true_intent", "表面配合必须写明真实意图", "true_intent 会记为只有本人知道的事实", INVARIANT_VIOLATION))
    if op["response"] != "surface" and op["true_intent"]:
        errs.append(detail(path + ".true_intent", "只有 surface 回应需要 true_intent", None, INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    entry = {"op": "npc_response", "npc_id": npc, "response": op["response"]}
    if op["response"] == "surface":
        fid = SS.next_id(ctx.state, "fact", "f")
        ctx.state["facts"][fid] = {
            "id": fid,
            "key": "%s.intent.t%d" % (npc, ctx.turn),
            "text": "%s的真实打算：%s" % (ctx.name(npc), op["true_intent"]),
            "truth": True,
            "known_by": [npc],
            "believed_by": [],
            "visibility": "private",
            "origin": "observed",
            "turn": ctx.turn,
            "spreading": False,
        }
        entry["intent_fact_id"] = fid
    ctx.responses.setdefault(npc, []).append(op["response"])
    ctx.actors.add(npc)
    ctx.observable = True
    responses = ctx.state["scene"]["responses"]
    responses.append({"turn": ctx.turn, "npc_id": npc, "response": op["response"], "note": op["note"]})
    del responses[:-6]
    ctx.applied.append(entry)


@register(
    "npc_action",
    {
        "npc_id": F(S.Id()),
        "action": F(S.Str(1, 120)),
        "significant": F(S.Bool(), required=False, default=False),
        "kind": F(S.Nullable(S.Enum("approach", "reveal", "trade", "leave", "confess", "provoke", "other")), required=False, default=None),
        "target_id": F(S.Nullable(S.Id()), required=False, default=None),
        "basis_fact_ids": F(S.List(S.Id(), max_items=8, unique=True), required=False, default=[]),
    },
    "NPC 自主行动。significant: true 的重大行动（主动接近、揭发、交易、离开、表白、挑衅等）受冷却限制；依据事实必须在其信息集中",
)
def op_npc_action(ctx, op, path):
    errs = []
    npc = op["npc_id"]
    if _need_character(ctx, npc, path + ".npc_id", errs, npc=True):
        _absent_actor_ok(ctx, npc, path, errs)
        _basis(ctx, npc, op["basis_fact_ids"], path + ".basis_fact_ids", errs)
        if op["significant"] and not SS.can_act(ctx.state, npc, ctx.turn):
            last = ctx.state["counters"]["major_action_turn"][npc]
            errs.append(
                detail(
                    path + ".significant",
                    "%s 在冷却中：第 %d 回合刚有过重大行动" % (ctx.name(npc), last),
                    "第 %d 回合起才能再有重大行动；这回合写成非重大行动，或让能行动的人出手" % (last + ST.COOLDOWN_TURNS),
                    INVARIANT_VIOLATION,
                )
            )
    if op["target_id"] is not None:
        _need_character(ctx, op["target_id"], path + ".target_id", errs)
    if not _flush(ctx, errs):
        return
    if op["significant"]:
        ctx.state["counters"]["major_action_turn"][npc] = ctx.turn
    ctx.actors.add(npc)
    ctx.observable = True
    ctx.applied.append({"op": "npc_action", "npc_id": npc, "significant": op["significant"], "kind": op["kind"]})


@register(
    "npc_state",
    {
        "npc_id": F(S.Id()),
        "mood": F(S.Nullable(S.Str(1, 20)), required=False, default=None),
        "add_conditions": F(S.List(CONDITION, max_items=4), required=False, default=[]),
        "remove_conditions": F(S.List(S.Enum(*ST.CONDITION_KINDS), max_items=7, unique=True), required=False, default=[]),
    },
    "更新 NPC 的情绪与状况（醉意、睡眠、受伤、外出等）；minutes 表示多久后自动消退",
)
def op_npc_state(ctx, op, path):
    errs = []
    npc = op["npc_id"]
    if _need_character(ctx, npc, path + ".npc_id", errs, npc=True):
        _absent_actor_ok(ctx, npc, path, errs)
    if op["mood"] is None and not op["add_conditions"] and not op["remove_conditions"]:
        errs.append(detail(path, "没有任何变化", "至少给 mood、add_conditions、remove_conditions 之一", INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    status = ctx.state["characters"][npc]["status"]
    if op["mood"] is not None:
        status["mood"] = op["mood"]
    removed = set(op["remove_conditions"])
    status["conditions"] = [c for c in status["conditions"] if c["kind"] not in removed]
    for cond in op["add_conditions"]:
        until = CL.add_minutes(ctx.state["clock"], cond["minutes"]) if cond["minutes"] else None
        status["conditions"] = [c for c in status["conditions"] if c["kind"] != cond["kind"]]
        status["conditions"].append({"kind": cond["kind"], "text": cond["text"], "until": until, "since_turn": ctx.turn})
    ctx.observable = True
    ctx.applied.append({"op": "npc_state", "npc_id": npc, "mood": status["mood"], "conditions": [c["kind"] for c in status["conditions"]]})


# ---------------------------------------------------------------------------
# knowledge


@register(
    "add_fact",
    {
        "key": F(FACT_KEY),
        "text": F(S.Str(1, 120)),
        "truth": F(S.Bool(), required=False, default=True),
        "known_by": F(S.List(S.Id(), max_items=20, unique=True), required=False, default=[]),
        "believed_by": F(S.List(S.Id(), max_items=20, unique=True), required=False, default=[]),
        "visibility": F(S.Enum(*ST.FACT_VISIBILITY)),
        "origin": F(S.Enum(*ST.MODEL_FACT_ORIGINS)),
        "spread": F(S.Bool(), required=False, default=False),
    },
    "记录一条事实。public 在场者自动知道；private 只有 known_by；inner 是内心，只属于一个 NPC 且永不传播。误信用 truth: false + believed_by。正文里新写出、之后要继承的细节都要用它记下",
)
def op_add_fact(ctx, op, path):
    errs = []
    state = ctx.state
    for field in ("known_by", "believed_by"):
        for index, cid in enumerate(op[field]):
            if _need_character(ctx, cid, "%s.%s[%d]" % (path, field, index), errs):
                if not SS.is_present(state, cid) and ctx.in_beat is None:
                    errs.append(
                        detail(
                            "%s.%s[%d]" % (path, field, index),
                            "%s 不在场，不能在这一幕里得知这件事" % ctx.name(cid),
                            "消息要传到不在场的人，等离屏推演或以后当面告知",
                            INVARIANT_VIOLATION,
                        )
                    )
    if op["truth"] and op["believed_by"]:
        errs.append(detail(path + ".believed_by", "真事实用 known_by；believed_by 只用于 truth: false 的误信", None, INVARIANT_VIOLATION))
    if not op["truth"] and not op["believed_by"]:
        errs.append(detail(path + ".believed_by", "假事实（误信）必须写明谁相信它", None, INVARIANT_VIOLATION))
    if op["visibility"] == "inner":
        knowers = op["known_by"]
        if len(knowers) != 1 or knowers[0] == state["player_id"] or not op["truth"] or op["believed_by"] or op["spread"]:
            errs.append(detail(path, "内心事实只能属于一个 NPC 本人，必须为真，且永不传播", None, INVARIANT_VIOLATION))
    elif op["visibility"] == "private" and not op["known_by"] and not op["believed_by"]:
        errs.append(detail(path + ".known_by", "私密事实至少要有一个知情人", None, INVARIANT_VIOLATION))
    if op["origin"] == "retcon":
        errs.append(detail(path + ".origin", "追溯事实只能通过“其实……”的改写回合登记", "action_mode 用 rewrite（改写与追溯在后续版本开放）", INVARIANT_VIOLATION))
    if op["truth"]:
        existing = SS.true_fact_by_key(state, op["key"])
        if existing is not None:
            errs.append(
                detail(
                    path + ".key",
                    "同键的真事实已存在（%s：%s）" % (existing["id"], existing["text"][:30]),
                    "有人新得知这件事用 reveal_fact；情况有变化就换一个新键",
                    INVARIANT_VIOLATION,
                )
            )
    if not _flush(ctx, errs):
        return
    known = list(op["known_by"])
    if op["visibility"] == "public":
        for cid in state["scene"]["present"]:
            if cid not in known:
                known.append(cid)
    fid = SS.next_id(state, "fact", "f")
    state["facts"][fid] = {
        "id": fid,
        "key": op["key"],
        "text": op["text"],
        "truth": op["truth"],
        "known_by": known,
        "believed_by": list(op["believed_by"]),
        "visibility": op["visibility"],
        "origin": "offscreen" if ctx.in_beat else op["origin"],
        "turn": ctx.turn,
        "spreading": bool(op["spread"]),
    }
    ctx.observable = True
    ctx.applied.append({"op": "add_fact", "fact_id": fid, "key": op["key"], "known_by": known})


# ---------------------------------------------------------------------------
# relationships


@register(
    "relationship",
    {
        "from": F(S.Id()),
        "to": F(S.Id()),
        "trust_delta": F(S.Int(-ST.MAX_TRUST_DELTA, ST.MAX_TRUST_DELTA), required=False, default=0),
        "tension_delta": F(S.Int(-5, 5), required=False, default=0),
        "stage_advance": F(S.Bool(), required=False, default=False),
        "stage_retreat_to": F(S.Nullable(S.Enum(*ST.STAGES)), required=False, default=None),
        "reason": F(S.Str(1, 80)),
    },
    "有向关系变化（from 对 to）：信任 -5..5（单次提交净变化 ≤2）、张力 0..5、亲近进程前进一个阶段（需要同一提交里玩家的行动 + 对方的 partial/genuine 回应）或后退。原因必填",
)
def op_relationship(ctx, op, path):
    errs = []
    state = ctx.state
    a, b = op["from"], op["to"]
    ok_a = _need_character(ctx, a, path + ".from", errs)
    ok_b = _need_character(ctx, b, path + ".to", errs)
    if ok_a and ok_b and a == b:
        errs.append(detail(path, "关系的两端不能是同一个人", None, INVARIANT_VIOLATION))
    if not (ok_a and ok_b) or a == b:
        return _flush(ctx, errs)
    key = SS.edge_key(a, b)
    current = state["relationships"].get(key)
    if current is None and not (SS.is_present(state, a) and SS.is_present(state, b)) and ctx.in_beat is None:
        errs.append(detail(path, "%s 与 %s 还没有实际接触过，关系要在两人同场时建立" % (ctx.name(a), ctx.name(b)), None, INVARIANT_VIOLATION))
    if op["trust_delta"] == 0 and op["tension_delta"] == 0 and not op["stage_advance"] and op["stage_retreat_to"] is None:
        errs.append(detail(path, "关系没有任何变化", None, INVARIANT_VIOLATION))
    if op["stage_advance"] and op["stage_retreat_to"] is not None:
        errs.append(detail(path, "不能同时前进与后退", None, INVARIANT_VIOLATION))
    player = state["player_id"]
    if a == player and (op["trust_delta"] or op["tension_delta"]) and ctx.mode not in ("result", "attempt"):
        errs.append(detail(path, "玩家角色对别人的态度只随玩家自己的行动变化", "不替玩家下情绪结论", INVARIANT_VIOLATION))
    trust = current["trust"] if current else 0
    tension = current["tension"] if current else 0
    stage = current["stage"] if current else "stranger"
    start = ctx.trust_start.setdefault(key, trust)
    new_trust = trust + op["trust_delta"]
    new_tension = tension + op["tension_delta"]
    if not ST.TRUST_RANGE[0] <= new_trust <= ST.TRUST_RANGE[1]:
        errs.append(detail(path + ".trust_delta", "信任将变成 %d，超出 -5..5" % new_trust, "不会自动截断，换一个幅度", INVARIANT_VIOLATION))
    elif abs(new_trust - start) > ST.MAX_TRUST_DELTA:
        errs.append(detail(path + ".trust_delta", "单次提交中信任净变化不能超过 %d" % ST.MAX_TRUST_DELTA, None, INVARIANT_VIOLATION))
    if not ST.TENSION_RANGE[0] <= new_tension <= ST.TENSION_RANGE[1]:
        errs.append(detail(path + ".tension_delta", "张力将变成 %d，超出 0..5" % new_tension, "不会自动截断，换一个幅度", INVARIANT_VIOLATION))
    pair = frozenset((a, b))
    new_stage = stage
    evidence = None
    if op["stage_advance"]:
        index = SS.stage_index(stage)
        if index + 1 >= len(ST.STAGES):
            errs.append(detail(path + ".stage_advance", "已经是最后一个阶段", None, INVARIANT_VIOLATION))
        elif pair in ctx.stage_pairs:
            errs.append(detail(path + ".stage_advance", "同一提交中这对关系只能前进一个阶段", None, INVARIANT_VIOLATION))
        else:
            new_stage = ST.STAGES[index + 1]
            evidence = _stage_evidence(ctx, a, b, path, errs)
    if op["stage_retreat_to"] is not None:
        if SS.stage_index(op["stage_retreat_to"]) >= SS.stage_index(stage):
            errs.append(detail(path + ".stage_retreat_to", "后退的目标必须低于当前阶段（%s）" % stage, None, INVARIANT_VIOLATION))
        else:
            new_stage = op["stage_retreat_to"]
    if not _flush(ctx, errs):
        return
    if current is None:
        current = {"from": a, "to": b, "trust": 0, "tension": 0, "stage": stage, "history": []}
        state["relationships"][key] = current
    changes = []
    if op["trust_delta"]:
        current["trust"] = new_trust
        changes.append("trust%+d" % op["trust_delta"])
    if op["tension_delta"]:
        current["tension"] = new_tension
        changes.append("tension%+d" % op["tension_delta"])
    if new_stage != stage:
        changes.append("stage:%s" % new_stage)
        ctx.stage_pairs.add(pair)
        # The stage is the pair's shared history: keep both directions in step.
        current["stage"] = new_stage
        other = state["relationships"].get(SS.edge_key(b, a))
        if other is None:
            other = {"from": b, "to": a, "trust": 0, "tension": 0, "stage": new_stage, "history": []}
            state["relationships"][SS.edge_key(b, a)] = other
        other["stage"] = new_stage
        other["history"].append({"turn": ctx.turn, "change": "stage:%s" % new_stage, "reason": op["reason"]})
        del other["history"][:-12]
    record = {"turn": ctx.turn, "change": ",".join(changes), "reason": op["reason"]}
    if evidence:
        record["evidence"] = evidence
    current["history"].append(record)
    del current["history"][:-12]
    ctx.observable = True
    ctx.relationship_reasons.append(op["reason"])
    ctx.applied.append({"op": "relationship", "from": a, "to": b, "trust": current["trust"], "tension": current["tension"], "stage": current["stage"]})


def _stage_evidence(ctx, a, b, path, errs):
    player = ctx.state["player_id"]
    if player in (a, b):
        npc = b if a == player else a
        if ctx.mode not in ("result", "attempt"):
            errs.append(detail(path + ".stage_advance", "亲近进程前进需要玩家本回合的行动（result/attempt）", None, INVARIANT_VIOLATION))
            return None
        cooperative = [r for r in ctx.responses.get(npc, []) if r in ST.COOPERATIVE_RESPONSES]
        if not cooperative:
            errs.append(
                detail(
                    path + ".stage_advance",
                    "亲近进程前进需要同一提交里 %s 的 partial 或 genuine 回应" % ctx.name(npc),
                    "先写 npc_response；阶段是双方共同经历的历史，不是一方说了算",
                    INVARIANT_VIOLATION,
                )
            )
            return None
        return {"player_action_turn": ctx.turn, "npc_response": cooperative[-1]}
    if a not in ctx.actors or b not in ctx.actors:
        errs.append(detail(path + ".stage_advance", "两名 NPC 之间的阶段前进需要双方本提交都有行动或回应", None, INVARIANT_VIOLATION))
        return None
    return {"npc_actions_turn": ctx.turn}


# ---------------------------------------------------------------------------
# events


@register(
    "event_create",
    {
        "kind": F(S.Enum(*ST.EVENT_KINDS)),
        "title": F(S.Str(1, 40)),
        "text": F(S.Nullable(S.Str(1, 120)), required=False, default=None),
        "tier": F(S.Nullable(S.Enum(*ST.EVENT_TIERS)), required=False, default=None),
        "participants": F(S.List(S.Id(), 1, 12, unique=True)),
        "due": F(CLOCK, required=False),
        "in_minutes": F(S.Int(1, 400 * ST.MINUTES_PER_DAY), required=False),
        "probability": F(S.Nullable(S.Num(0, 1, lo_open=True, hi_open=True)), required=False, default=None),
        "dedupe_key": F(FACT_KEY),
        "repeat": F(S.Bool(), required=False, default=False),
    },
    "创建事件（约定、截止、风声、机会、伏笔、概率事件）。due 与 in_minutes 二选一且必须晚于现在；chance 必须带 probability，到期由引擎掷骰；涉及玩家的承诺需要 player_authorized；dedupe_key 与未结束事件不能重复",
)
def op_event_create(ctx, op, path):
    errs = []
    state = ctx.state
    for index, cid in enumerate(op["participants"]):
        _need_character(ctx, cid, "%s.participants[%d]" % (path, index), errs)
    given = [k for k in ("due", "in_minutes") if k in op]
    due = None
    if len(given) != 1:
        errs.append(detail(path, "due 与 in_minutes 必须且只能给一个", None, INVARIANT_VIOLATION))
    else:
        due = op["due"] if "due" in op else CL.add_minutes(state["clock"], op["in_minutes"])
        if CL.to_abs(due) <= CL.to_abs(state["clock"]):
            errs.append(detail(path + ".due", "到期时间必须晚于现在（%s）" % SS.clock_label(state, ctx.world), None, INVARIANT_VIOLATION))
    if op["kind"] == "chance" and op["probability"] is None:
        errs.append(detail(path + ".probability", "概率事件必须带 probability", "结果由引擎在到期时掷骰", INVARIANT_VIOLATION))
    if op["kind"] != "chance" and op["probability"] is not None:
        errs.append(detail(path + ".probability", "只有 chance 事件带 probability", None, INVARIANT_VIOLATION))
    if state["mode"] == "daily" and op["kind"] in ("deadline", "chance"):
        errs.append(detail(path + ".kind", "日常模式没有倒计时与概率事件", "用 promise、opportunity、rumor 或 foreshadow", INVARIANT_VIOLATION))
    player = state["player_id"]
    if op["kind"] == "promise" and player in op["participants"] and ctx.in_beat is None:
        if ctx.mode not in ("result", "attempt") or not ctx.authorized:
            errs.append(detail(path, "涉及玩家角色的承诺只能在玩家本人答应时成立（result/attempt + player_authorized）", None, INVARIANT_VIOLATION))
    if ctx.in_beat is not None and player in op["participants"]:
        errs.append(detail(path + ".participants", "离屏片段不能创建涉及玩家角色的事件", None, INVARIANT_VIOLATION))
    key = op["dedupe_key"]
    same = [e for e in state["events"].values() if e["dedupe_key"].split("#")[0] == key]
    if any(e["state"] == "pending" for e in same):
        errs.append(detail(path + ".dedupe_key", "已有同一去重键的未结束事件：%s" % key, "推进或结束那个事件，而不是再建一个", INVARIANT_VIOLATION))
    elif same and not op["repeat"]:
        errs.append(detail(path + ".dedupe_key", "去重键 %s 已被结束的事件用过" % key, "确实是重复发生时带 repeat: true", INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    if same:
        key = "%s#%d" % (key, len(same) + 1)
    tier = op["tier"]
    if tier is None:
        minutes = CL.minutes_between(state["clock"], due)
        tier = "immediate" if minutes <= 60 else ("near" if minutes <= 2 * ST.MINUTES_PER_DAY else "far")
    eid = SS.next_id(state, "event", "e")
    state["events"][eid] = {
        "id": eid,
        "kind": op["kind"],
        "tier": tier,
        "title": op["title"],
        "text": op["text"],
        "participants": list(op["participants"]),
        "due": due,
        "probability": op["probability"],
        "dedupe_key": key,
        "state": "pending",
        "outcome": None,
        "created_turn": ctx.turn,
        "resolved_turn": None,
        "note": None,
    }
    ctx.observable = True
    ctx.applied.append({"op": "event_create", "event_id": eid, "kind": op["kind"], "due": due})


def _pending_event(ctx, eid, path, errs):
    event = ctx.state["events"].get(eid)
    if event is None:
        errs.append(detail(path, "事件不存在：%s" % eid, None, NOT_FOUND))
        return None
    if event["state"] != "pending":
        errs.append(detail(path, "事件 %s 已经结束（%s），终态不可修改" % (eid, event["outcome"]), None, INVARIANT_VIOLATION))
        return None
    return event


def _player_deal_guard(ctx, event, path, errs):
    player = ctx.state["player_id"]
    if event["kind"] == "promise" and player in event["participants"]:
        if ctx.in_beat is not None:
            errs.append(detail(path, "离屏片段不能兑现或取消涉及玩家角色的事件", None, INVARIANT_VIOLATION))
        elif ctx.mode not in ("result", "attempt") or not ctx.authorized:
            errs.append(detail(path, "涉及玩家角色的承诺，其兑现与取消要由玩家本人决定（result/attempt + player_authorized）", None, INVARIANT_VIOLATION))


@register(
    "event_resolve",
    {"event_id": F(S.Id()), "outcome": F(S.Enum("fulfilled", "surfaced")), "note": F(S.Str(1, 80))},
    "在到期前结束事件：约定、截止、机会用 fulfilled（兑现）；伏笔、风声用 surfaced（提前浮出）。概率事件只能由引擎到期掷骰",
)
def op_event_resolve(ctx, op, path):
    errs = []
    event = _pending_event(ctx, op["event_id"], path + ".event_id", errs)
    if event is not None:
        allowed = ST.MANUAL_OUTCOMES[event["kind"]]
        if op["outcome"] not in allowed:
            if not allowed:
                errs.append(detail(path + ".outcome", "概率事件的结果只能由引擎在到期时掷骰", None, INVARIANT_VIOLATION))
            else:
                errs.append(detail(path + ".outcome", "%s 事件只能以 %s 结束" % (event["kind"], "/".join(allowed)), None, INVARIANT_VIOLATION))
        _player_deal_guard(ctx, event, path, errs)
    if not _flush(ctx, errs):
        return
    event["state"] = "resolved"
    event["outcome"] = op["outcome"]
    event["resolved_turn"] = ctx.turn
    event["note"] = op["note"]
    ctx.observable = True
    ctx.applied.append({"op": "event_resolve", "event_id": event["id"], "outcome": op["outcome"]})


@register("event_cancel", {"event_id": F(S.Id()), "reason": F(S.Str(1, 80))}, "因剧情取消未结束的事件（outcome: cancelled_by_story）")
def op_event_cancel(ctx, op, path):
    errs = []
    event = _pending_event(ctx, op["event_id"], path + ".event_id", errs)
    if event is not None:
        _player_deal_guard(ctx, event, path, errs)
    if not _flush(ctx, errs):
        return
    event["state"] = "cancelled"
    event["outcome"] = "cancelled_by_story"
    event["resolved_turn"] = ctx.turn
    event["note"] = op["reason"]
    ctx.observable = True
    ctx.applied.append({"op": "event_cancel", "event_id": event["id"]})


# ---------------------------------------------------------------------------
# roll


def branch_spec():
    variants = {name: SPECS[name] for name, (_f, allowed) in HANDLERS.items() if allowed}
    return S.List(S.Tagged("op", variants, "分支操作"), max_items=8)


@register(
    "roll",
    {
        "purpose": F(S.Str(1, 60)),
        "probability": F(S.Num(0, 1, lo_open=True, hi_open=True)),
        "on_success": F(S.List(S.Any("分支操作"), max_items=8), required=False, default=[]),
        "on_failure": F(S.List(S.Any("分支操作"), max_items=8), required=False, default=[]),
    },
    "即时概率：引擎确定性掷骰后执行 on_success 或 on_failure（分支内不能再嵌套 roll，也不能推进时间）。结果以返回的 applied 为准",
    branch=False,
)
def op_roll(ctx, op, path):
    errs = []
    branches = {}
    spec = branch_spec()
    for key in ("on_success", "on_failure"):
        normalized, problems = S.validate(spec, op[key], "%s.%s" % (path, key))
        errs.extend(problems)
        branches[key] = normalized
    if not _flush(ctx, errs):
        return
    value = rng.unit(ctx.state["seed"], "roll", ctx.turn, ctx.roll_index)
    ctx.roll_index += 1
    success = value < op["probability"]
    ctx.observable = True
    ctx.applied.append({"op": "roll", "purpose": op["purpose"], "probability": op["probability"], "result": "success" if success else "failure"})
    key = "on_success" if success else "on_failure"
    for index, sub in enumerate(branches[key]):
        apply_op(ctx, sub, "%s.%s[%d]" % (path, key, index))


# ---------------------------------------------------------------------------
# player


@register(
    "player_update",
    {
        "name": F(S.Nullable(S.Str(1, 12)), required=False, default=None),
        "title": F(S.Nullable(S.Str(1, 12)), required=False, default=None),
        "add_background": F(S.Nullable(S.Str(1, 120)), required=False, default=None),
        "add_resources": F(S.List(S.Str(1, 60), max_items=4), required=False, default=[]),
        "add_risks": F(S.List(S.Str(1, 60), max_items=4), required=False, default=[]),
    },
    "玩家角色的姓名、称谓、背景、资源与风险。只能在 result 或 rewrite 模式、并带 player_authorized",
)
def op_player_update(ctx, op, path):
    errs = []
    if ctx.mode not in ("result", "rewrite") or not ctx.authorized:
        errs.append(detail(path, "玩家角色设定只能按玩家本人的话修改（result/rewrite + player_authorized）", None, INVARIANT_VIOLATION))
    if not any([op["name"], op["title"], op["add_background"], op["add_resources"], op["add_risks"]]):
        errs.append(detail(path, "没有任何变化", None, INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    player = ctx.state["characters"][ctx.state["player_id"]]
    if op["name"]:
        player["name"] = op["name"]
        player["family"] = ""
        player["given"] = op["name"]
    if op["title"]:
        player["title"] = op["title"]
        player["call"] = op["title"]
    if op["add_background"]:
        player["background"].append(op["add_background"])
    player["resources"].extend(op["add_resources"])
    player["risks"].extend(op["add_risks"])
    ctx.observable = True
    ctx.applied.append({"op": "player_update", "name": player["name"], "title": player["title"]})


# ---------------------------------------------------------------------------


def op_spec():
    return S.Tagged("op", dict(SPECS), "操作")


def apply_op(ctx, op, path):
    handler, _branch = HANDLERS[op["op"]]
    handler(ctx, op, path)


def check_safety_tags(state, tags):
    """Hard boundaries and pause, for a set of content tags. Returns details."""
    problems = []
    for boundary in state["safety"]["boundaries"]:
        clash = sorted(set(boundary["tags"]) & set(tags) - {"custom"})
        if clash:
            problems.append(
                detail(
                    "$.content_tags",
                    "与玩家登记的边界冲突：%s" % boundary["text"],
                    "换一个不涉及 %s 的写法；硬边界不能被折算成剧情代价" % "、".join(clash),
                    SAFETY_BLOCK,
                )
            )
    if state["safety"]["paused"]:
        blocked = sorted(set(tags) & (set(ST.INTIMACY_TAGS) | set(ST.CONFLICT_TAGS)))
        if blocked:
            problems.append(
                detail(
                    "$.content_tags",
                    "玩家已暂停，亲密与冲突内容都不能继续：%s" % "、".join(blocked),
                    "回到中性叙述；等玩家明确恢复",
                    SAFETY_BLOCK,
                )
            )
    return problems


# People, knowledge and leverage operations register themselves on import.
from . import ops_people  # noqa: E402,F401
