"""Operations on people, knowledge and leverage (registered into ops.SPECS).

Knowledge only travels along relationship edges or distorted channels;
inner facts never travel. Voice switches are expression, never escalation.
Tendency cards evolve item by item with evidence from distinct turns.
"""

from .. import schema as S
from ..errors import INVARIANT_VIOLATION, NOT_FOUND, SAFETY_BLOCK, detail
from . import cards as C
from . import facts as FA
from . import state as SS
from . import structure as ST
from .ops import FACT_KEY, _basis, _flush, _need_character, register

F = S.Field
EVIDENCE_NEEDED = 2
BOUNDARY_RELAX_NEEDED = 3
MAX_CARD_OPS_PER_NPC = 2


def _present_or_beat(ctx, cid, path, errs, what):
    if ctx.in_beat is None and not SS.is_present(ctx.state, cid):
        errs.append(detail(path, "%s 不在场，不能在这一幕里%s" % (ctx.name(cid), what), "当面的事要在场；不在场的人在离屏推演里处理", INVARIANT_VIOLATION))


def _card_budget(ctx, npc, path, errs):
    used = ctx.card_ops.get(npc, 0) + 1
    ctx.card_ops[npc] = used
    if used > MAX_CARD_OPS_PER_NPC:
        errs.append(detail(path, "一次提交里 %s 的身份/倾向卡最多改 %d 项" % (ctx.name(npc), MAX_CARD_OPS_PER_NPC), "卡片只能逐项演化，不能一次重写", INVARIANT_VIOLATION))


# ---------------------------------------------------------------------------
# knowledge


@register(
    "reveal_fact",
    {
        "fact_id": F(S.Id()),
        "from": F(S.Id()),
        "to": F(S.List(S.Id(), 1, 12, unique=True)),
        "spread": F(S.Bool(), required=False, default=False),
    },
    "把一条事实从知情人告诉别人。只能沿已有的关系边进行，当面告知时双方都要在场；内心事实永远不能传播。告诉某人真相时，若他正误信同键的假事实，引擎记录他的信息集变化",
)
def op_reveal_fact(ctx, op, path):
    errs = []
    state = ctx.state
    fact = state["facts"].get(op["fact_id"])
    source = op["from"]
    if fact is None:
        errs.append(detail(path + ".fact_id", "事实不存在：%s" % op["fact_id"], None, NOT_FOUND))
    elif fact["visibility"] == "inner":
        errs.append(detail(path + ".fact_id", "内心事实永远不能被传播", "内心只属于本人；需要让别人知道，要本人在正文里说出来并记一条新事实", INVARIANT_VIOLATION))
    if _need_character(ctx, source, path + ".from", errs) and fact is not None:
        if not SS.knows(state, source, fact["id"]):
            errs.append(detail(path + ".from", "%s 并不知道这件事，没法告诉别人" % ctx.name(source), None, INVARIANT_VIOLATION))
        _present_or_beat(ctx, source, path + ".from", errs, "当面告知")
    for index, target in enumerate(op["to"]):
        tpath = "%s.to[%d]" % (path, index)
        if not _need_character(ctx, target, tpath, errs) or fact is None:
            continue
        if target == source:
            errs.append(detail(tpath, "不能告诉自己", None, INVARIANT_VIOLATION))
            continue
        if target in fact["known_by"] or (not fact["truth"] and target in fact["believed_by"]):
            errs.append(detail(tpath, "%s 已经知道这件事" % ctx.name(target), None, INVARIANT_VIOLATION))
        if not SS.has_edge_either(state, source, target):
            errs.append(detail(tpath, "%s 与 %s 之间没有关系边，消息传不过去" % (ctx.name(source), ctx.name(target)), "先让两人有实际接触；远处的人只能通过走样渠道听到传闻（spread_rumor）", INVARIANT_VIOLATION))
        _present_or_beat(ctx, target, tpath, errs, "听到这件事")
    if not _flush(ctx, errs):
        return
    corrected = []
    fact = FA.edit(state, fact["id"])
    for target in op["to"]:
        if fact["truth"]:
            fact["known_by"].append(target)
            for other in FA.of(state).by_key(fact["key"]):
                if not other["truth"] and target in other["believed_by"]:
                    other = FA.edit(state, other["id"])
                    other["believed_by"].remove(target)
                    if target not in other["known_by"]:
                        other["known_by"].append(target)
                    corrected.append({"character_id": target, "false_fact_id": other["id"]})
        else:
            fact["believed_by"].append(target)
    if op["spread"]:
        fact["spreading"] = True
    ctx.observable = True
    for cid in (source,) + tuple(op["to"]):
        if cid != state["player_id"]:
            ctx.actors.add(cid)
    ctx.applied.append({"op": "reveal_fact", "fact_id": fact["id"], "from": source, "to": list(op["to"]), "corrected": corrected})


@register(
    "spread_rumor",
    {
        "from": F(S.Id()),
        "source_fact_id": F(S.Nullable(S.Id()), required=False, default=None),
        "key": F(FACT_KEY),
        "text": F(S.Str(1, 120)),
        "believed_by": F(S.List(S.Id(), 1, 20, unique=True)),
        "channel_id": F(S.Nullable(S.Id()), required=False, default=None),
    },
    "传出一条走样的传闻：生成新的假事实（来源为传闻），原事实不变。不经渠道时沿关系边、双方在场；经世界里的走样渠道时可以传到没有关系边的人",
)
def op_spread_rumor(ctx, op, path):
    errs = []
    state = ctx.state
    source = op["from"]
    channel = None
    if op["channel_id"] is not None:
        channel = next((c for c in ctx.world.get("channels", []) if c["id"] == op["channel_id"]), None)
        if channel is None:
            errs.append(detail(path + ".channel_id", "渠道不存在：%s" % op["channel_id"], "用世界里的关系渠道 ID", NOT_FOUND))
        elif channel["fidelity"] != "distorted":
            errs.append(detail(path + ".channel_id", "精确渠道不会让消息走样", "走样的传闻要走 distorted 渠道；精确转告用 reveal_fact", INVARIANT_VIOLATION))
    if _need_character(ctx, source, path + ".from", errs):
        if channel is None:
            _present_or_beat(ctx, source, path + ".from", errs, "传话")
        if op["source_fact_id"] is not None:
            fact = state["facts"].get(op["source_fact_id"])
            if fact is None:
                errs.append(detail(path + ".source_fact_id", "事实不存在：%s" % op["source_fact_id"], None, NOT_FOUND))
            elif fact["visibility"] == "inner":
                errs.append(detail(path + ".source_fact_id", "内心事实永远不能被传播，也不能变成传闻", None, INVARIANT_VIOLATION))
            elif not SS.knows(state, source, fact["id"]):
                errs.append(detail(path + ".source_fact_id", "%s 不知道这件事，传不出走样的版本" % ctx.name(source), None, INVARIANT_VIOLATION))
    for index, target in enumerate(op["believed_by"]):
        tpath = "%s.believed_by[%d]" % (path, index)
        if not _need_character(ctx, target, tpath, errs):
            continue
        if target == source:
            errs.append(detail(tpath, "传话的人不必再相信自己的传闻", None, INVARIANT_VIOLATION))
        elif channel is None:
            if not SS.has_edge_either(state, source, target):
                errs.append(detail(tpath, "%s 与 %s 之间没有关系边" % (ctx.name(source), ctx.name(target)), "经走样渠道传播时带 channel_id", INVARIANT_VIOLATION))
            _present_or_beat(ctx, target, tpath, errs, "听到传闻")
    if not _flush(ctx, errs):
        return
    fid = SS.next_id(state, "fact", "f")
    state["facts"][fid] = {
        "id": fid,
        "key": op["key"],
        "text": op["text"],
        "truth": False,
        "known_by": [source],
        "believed_by": list(op["believed_by"]),
        "visibility": "private",
        "origin": "rumor",
        "turn": ctx.turn,
        "spreading": False,
        "source_fact_id": op["source_fact_id"],
        "channel_id": op["channel_id"],
        "coord": ctx.fact_coord(),
    }
    ctx.observable = True
    if source != state["player_id"]:
        ctx.actors.add(source)
    ctx.applied.append({"op": "spread_rumor", "fact_id": fid, "from": source, "believed_by": list(op["believed_by"]), "channel_id": op["channel_id"]})


# ---------------------------------------------------------------------------
# voice


@register(
    "set_voice",
    {
        "npc_id": F(S.Id()),
        "voice": F(S.Enum("surface", "inner")),
        "cause": F(S.Enum("player_request", "npc_self", "revert")),
        "trigger": F(S.Nullable(S.Enum("alone", "drunk", "breakdown", "exposed")), required=False, default=None),
        "note": F(S.Str(1, 80)),
    },
    "切换 NPC 的表层/里层语态。玩家要求（player_request）优先；NPC 自主切入里层（npc_self）要写触发因素：alone 独处 / drunk 醉意 / breakdown 情绪崩溃 / exposed 被戳穿；revert 切回表层。语态只改变说话方式，不是关系升级，note 不能与同一提交里的关系变化共用原因",
)
def op_set_voice(ctx, op, path):
    errs = []
    state = ctx.state
    npc = op["npc_id"]
    current = state["preferences"]["voice"].get(npc)
    if _need_character(ctx, npc, path + ".npc_id", errs, npc=True):
        char = state["characters"][npc]
        if not char.get("voices"):
            errs.append(detail(path + ".npc_id", "%s 没有语态设定（只有重要角色有表里两层）" % char["name"], "先升格为 major", INVARIANT_VIOLATION))
        if op["cause"] == "npc_self":
            if op["voice"] != "inner":
                errs.append(detail(path + ".voice", "NPC 自主切换只能切入里层；切回表层用 revert", None, INVARIANT_VIOLATION))
            if op["trigger"] is None:
                errs.append(detail(path + ".trigger", "NPC 自主切入里层必须有触发因素", "alone / drunk / breakdown / exposed", INVARIANT_VIOLATION))
            elif op["trigger"] == "alone" and sorted(state["scene"]["present"]) != sorted([state["player_id"], npc]):
                errs.append(detail(path + ".trigger", "场上不只你们两个人，谈不上独处", None, INVARIANT_VIOLATION))
            elif op["trigger"] == "drunk" and not any(c["kind"] == "drunk" for c in char["status"]["conditions"]):
                errs.append(detail(path + ".trigger", "%s 没有醉意" % char["name"], "先用 npc_state 记下醉意", INVARIANT_VIOLATION))
            if current and current.get("cause") == "player_request":
                errs.append(detail(path + ".cause", "玩家要求的语态优先，NPC 不能自己改掉", None, INVARIANT_VIOLATION))
        if op["cause"] == "revert":
            if op["voice"] != "surface":
                errs.append(detail(path + ".voice", "revert 只用于切回表层", None, INVARIANT_VIOLATION))
            if current and current.get("cause") == "player_request":
                errs.append(detail(path + ".cause", "玩家要求的语态只能由玩家改", None, INVARIANT_VIOLATION))
        if op["cause"] == "player_request" and ctx.mode in ("continue", "wait"):
            errs.append(detail(path + ".cause", "继续/等待回合里玩家没有提出要求", None, INVARIANT_VIOLATION))
        if ctx.in_beat is None and not SS.is_present(state, npc):
            errs.append(detail(path + ".npc_id", "%s 不在场" % char["name"], None, INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    state["preferences"]["voice"][npc] = {"voice": op["voice"], "cause": op["cause"], "since_turn": ctx.turn, "trigger": op["trigger"]}
    ctx.voice_reasons.append(op["note"])
    ctx.observable = True
    ctx.applied.append({"op": "set_voice", "npc_id": npc, "voice": op["voice"], "cause": op["cause"]})


# ---------------------------------------------------------------------------
# cards


@register(
    "intimacy_evidence",
    {
        "npc_id": F(S.Id()),
        "item": F(S.Enum(*(C.INTIMACY_NUMERIC + C.INTIMACY_LISTS + C.INTIMACY_TEXT))),
        "direction": F(S.Enum("increase", "decrease", "add", "remove", "set")),
        "value": F(S.Nullable(S.Str(1, 80)), required=False, default=None),
        "evidence": F(S.Str(1, 80)),
    },
    "为私密倾向卡的某一项记一条证据。同一项同一方向需要至少 2 条来自不同回合的证据才会改动（界线项的放宽 remove 需要 3 条）；数值项用 increase/decrease，列表项用 add/remove，文字项用 set",
)
def op_intimacy_evidence(ctx, op, path):
    errs = []
    state = ctx.state
    npc = op["npc_id"]
    item, direction, value = op["item"], op["direction"], op["value"]
    card = None
    if _need_character(ctx, npc, path + ".npc_id", errs, npc=True):
        card = state["characters"][npc].get("intimacy")
        if not card:
            errs.append(detail(path + ".npc_id", "%s 还没有倾向卡（只有重要角色有）" % ctx.name(npc), "先升格为 major", INVARIANT_VIOLATION))
        _card_budget(ctx, npc, path, errs)
    allowed = {"increase", "decrease"} if item in C.INTIMACY_NUMERIC else ({"add", "remove"} if item in C.INTIMACY_LISTS else {"set"})
    if direction not in allowed:
        errs.append(detail(path + ".direction", "%s 只能用 %s" % (item, "/".join(sorted(allowed))), None, INVARIANT_VIOLATION))
    if direction in ("add", "remove", "set") and not value:
        errs.append(detail(path + ".value", "这个方向需要写明具体内容", None, INVARIANT_VIOLATION))
    if card and direction in allowed:
        if item in C.INTIMACY_NUMERIC:
            target = card[item] + (1 if direction == "increase" else -1)
            if not 0 <= target <= 5:
                errs.append(detail(path + ".direction", "%s 已经到头了" % item, "不会自动截断", INVARIANT_VIOLATION))
        elif direction == "add" and value in card[item]:
            errs.append(detail(path + ".value", "这一项里已经有“%s”" % value, None, INVARIANT_VIOLATION))
        elif direction == "remove" and value not in card[item]:
            errs.append(detail(path + ".value", "这一项里没有“%s”" % value, "只能去掉卡片上已有的内容", INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    bucket = state["counters"]["intimacy_evidence"].setdefault(npc, {})
    key = "%s|%s|%s" % (item, direction, value or "")
    turns = bucket.setdefault(key, [])
    if ctx.turn not in turns:
        turns.append(ctx.turn)
    needed = BOUNDARY_RELAX_NEEDED if (item == "boundaries" and direction == "remove") else EVIDENCE_NEEDED
    changed = len(turns) >= needed
    if changed:
        if item in C.INTIMACY_NUMERIC:
            card[item] += 1 if direction == "increase" else -1
        elif direction == "add":
            card[item].append(value)
        elif direction == "remove":
            card[item].remove(value)
        else:
            card[item] = value
        del bucket[key]
    ctx.observable = True
    ctx.applied.append({"op": "intimacy_evidence", "npc_id": npc, "item": item, "direction": direction, "evidence_count": len(turns), "needed": needed, "changed": changed})


@register(
    "identity_update",
    {
        "npc_id": F(S.Id()),
        "item": F(S.Enum(*C.IDENTITY_ITEMS)),
        "action": F(S.Enum("add", "remove", "set")),
        "value": F(S.Str(1, 120)),
        "reason": F(S.Str(1, 80)),
    },
    "逐项修改身份卡（资源、限制、义务用 add/remove；权限、暴露风险、隐藏落差用 set）。身份卡不能整体替换",
)
def op_identity_update(ctx, op, path):
    errs = []
    npc = op["npc_id"]
    identity = None
    if _need_character(ctx, npc, path + ".npc_id", errs, npc=True):
        identity = ctx.state["characters"][npc].get("identity")
        if not identity:
            errs.append(detail(path + ".npc_id", "%s 还没有身份卡" % ctx.name(npc), "先升格为 supporting 或 major", INVARIANT_VIOLATION))
        _card_budget(ctx, npc, path, errs)
    is_list = op["item"] in C.IDENTITY_LISTS
    if is_list and op["action"] == "set":
        errs.append(detail(path + ".action", "列表项用 add/remove", None, INVARIANT_VIOLATION))
    if not is_list and op["action"] != "set":
        errs.append(detail(path + ".action", "文字项用 set", None, INVARIANT_VIOLATION))
    if identity and is_list:
        if op["action"] == "add" and op["value"] in identity.get(op["item"], []):
            errs.append(detail(path + ".value", "已经有这一条", None, INVARIANT_VIOLATION))
        if op["action"] == "remove" and op["value"] not in identity.get(op["item"], []):
            errs.append(detail(path + ".value", "没有这一条", None, INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    if is_list:
        values = identity.setdefault(op["item"], [])
        if op["action"] == "add":
            values.append(op["value"])
        else:
            values.remove(op["value"])
    else:
        identity[op["item"]] = op["value"]
    ctx.observable = True
    ctx.applied.append({"op": "identity_update", "npc_id": npc, "item": op["item"], "action": op["action"]})


NPC_FIELDS = ("public_role", "appearance", "current_goal", "relationship_stance", "situation_trigger", "situation_pressure")


@register(
    "npc_update",
    {"npc_id": F(S.Id()), "field": F(S.Enum(*NPC_FIELDS)), "value": F(S.Str(1, 120)), "reason": F(S.Str(1, 80))},
    "修改 NPC 的公开身份、外貌、当前目标、对关系的态度或处境（不含身份卡与倾向卡）",
)
def op_npc_update(ctx, op, path):
    errs = []
    npc = op["npc_id"]
    if _need_character(ctx, npc, path + ".npc_id", errs, npc=True):
        char = ctx.state["characters"][npc]
        if op["field"] in ("current_goal", "relationship_stance") and not char.get("decision"):
            errs.append(detail(path + ".field", "%s 没有决策卡" % char["name"], "先升格", INVARIANT_VIOLATION))
        if op["field"].startswith("situation_") and not char.get("situation"):
            errs.append(detail(path + ".field", "%s 没有处境设定" % char["name"], "先升格为 major", INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    char = ctx.state["characters"][npc]
    field = op["field"]
    if field in ("public_role", "appearance"):
        char[field] = op["value"]
    elif field in ("current_goal", "relationship_stance"):
        char["decision"][field] = op["value"]
    else:
        char["situation"][field.split("_", 1)[1]] = op["value"]
    ctx.observable = True
    ctx.applied.append({"op": "npc_update", "npc_id": npc, "field": field})


# ---------------------------------------------------------------------------
# new characters and promotion


def _gender_preference_ok(ctx, gender, reason, path, errs):
    preference = ctx.state["preferences"]["npc_gender_preference"]
    others = [c["gender"] for c in ctx.state["characters"].values() if c["id"] != ctx.state["player_id"] and c["tier"] != "background"]
    if preference in ("female_only", "male_only"):
        want = "female" if preference == "female_only" else "male"
        if gender != want and not reason:
            errs.append(detail(path + ".gender", "玩家的配对偏好是只要%s NPC" % ("女性" if want == "female" else "男性"), "换成符合偏好的性别，或在 gender_reason 里写明叙事理由", INVARIANT_VIOLATION))
    elif preference in ("mostly_female", "mostly_male"):
        want = "female" if preference == "mostly_female" else "male"
        after = others + [gender]
        if gender != want and after.count(want) * 2 <= len(after) and not reason:
            errs.append(detail(path + ".gender", "加上这个角色后，%s NPC 不再占多数" % ("女性" if want == "female" else "男性"), "换成符合偏好的性别，或在 gender_reason 里写明叙事理由", INVARIANT_VIOLATION))


def _name_ok(ctx, name, tier, kin_of, path, errs):
    state = ctx.state
    if any(c["name"] == name for c in state["characters"].values()):
        errs.append(detail(path + ".name", "本局已经有人叫“%s”" % name, "换一个名字", INVARIANT_VIOLATION))
    if tier == "background":
        return None
    families = sorted(ctx.world["name_pools"]["family"], key=len, reverse=True)
    family = next((f for f in families if name.startswith(f)), None)
    if family is None:
        errs.append(detail(path + ".name", "名字“%s”的姓不在本世界的名字池里" % name, "从完整上下文 name_pool 里取姓，不自造出戏的名字", INVARIANT_VIOLATION))
        return None
    taken = {c.get("family") for c in state["characters"].values() if c["tier"] in ("major", "supporting") and c.get("family")}
    if family in taken and not kin_of:
        errs.append(detail(path + ".name", "本局的重要人物里已经有人姓%s" % family, "换一个姓；确实是亲属时写 kin_of", INVARIANT_VIOLATION))
    return family


def _card_errors(tier, card, path, errs, allowed_missing=()):
    for missing in C.missing_for_tier(tier, card):
        if missing in allowed_missing:
            continue
        errs.append(detail("%s.%s" % (path, missing), "%s 层级的角色必须有 %s" % (tier, missing), "补齐对应层级的必填字段", INVARIANT_VIOLATION))


@register(
    "introduce_character",
    dict(
        {
            "id": F(S.Id()),
            "name": F(S.Str(1, 12)),
            "tier": F(S.Enum(*ST.TIERS)),
            "age": F(S.Int(0, 120)),
            "gender": F(S.Enum(*ST.GENDERS)),
            "gender_reason": F(S.Nullable(S.Str(1, 80)), required=False, default=None),
            "adult_context": F(S.Str(1, 80)),
            "public_role": F(S.Str(1, 30)),
            "kin_of": F(S.Nullable(S.Id()), required=False, default=None),
            "present": F(S.Bool(), required=False, default=True),
            "location_id": F(S.Nullable(S.Id()), required=False, default=None),
        },
        **C.card_fields()
    ),
    "新角色登场：正文里第一次点名的人都要登场，只被提起、不在场的也算（present 写 false，location_id 写他所在的地点）；必须明确成年（age ≥ 18，adult_context 一句话说明成年身份），名字取自世界名字池且重要人物不同姓；按层级补齐字段（background：line；supporting：appearance、identity、decision 的 core_value 与 current_goal；major：再加完整 decision、intimacy、voices、situation）；性别要符合配对偏好，否则写 gender_reason",
    branch=False,
)
def op_introduce_character(ctx, op, path):
    errs = []
    state = ctx.state
    cid = op["id"]
    if cid in state["characters"] or cid == "player" or cid in ctx.world_ids:
        errs.append(detail(path + ".id", "ID 已被使用：%s" % cid, "ID 一经分配永不复用；换一个新的 ASCII 小写 ID", INVARIANT_VIOLATION))
    if op["age"] < 18:
        errs.append(detail(path + ".age", "年龄 %d 小于 18，不能登场" % op["age"], "所有角色都必须是明确的成年人", SAFETY_BLOCK))
    _name_ok(ctx, op["name"], op["tier"], op["kin_of"], path, errs)
    if op["kin_of"] is not None:
        _need_character(ctx, op["kin_of"], path + ".kin_of", errs)
    _gender_preference_ok(ctx, op["gender"], op["gender_reason"], path, errs)
    card = {k: op[k] for k in ("appearance", "line", "identity", "decision", "intimacy", "voices", "situation")}
    _card_errors(op["tier"], card, path, errs)
    if op["tier"] == "background" and any(op[k] for k in ("identity", "intimacy", "voices", "situation")):
        errs.append(detail(path + ".tier", "背景人物只有名字和一句话", "要带身份或倾向卡就用 supporting 或 major", INVARIANT_VIOLATION))
    if op["tier"] == "supporting" and (op["intimacy"] or op["voices"]):
        errs.append(detail(path + ".tier", "只有重要角色（major）有倾向卡和表里语态", None, INVARIANT_VIOLATION))
    location = state["scene"]["location_id"] if op["present"] else op["location_id"]
    if not op["present"] and location is None:
        errs.append(detail(path + ".location_id", "不在场的新角色要写所在地点", None, INVARIANT_VIOLATION))
    elif location is not None and SS.location(ctx.world, location) is None:
        errs.append(detail(path + ".location_id", "地点不在本局快照中：%s" % location, None, NOT_FOUND))
    if not _flush(ctx, errs):
        return
    families = sorted(ctx.world["name_pools"]["family"], key=len, reverse=True)
    family = next((f for f in families if op["name"].startswith(f)), "")
    char = {
        "id": cid,
        "name": op["name"],
        "family": family,
        "given": op["name"][len(family) :],
        "call": op["name"],
        "tier": op["tier"],
        "age": op["age"],
        "gender": op["gender"],
        "adult_context": op["adult_context"],
        "public_role": op["public_role"],
        "introduced_turn": ctx.turn,
        "status": {"location_id": location, "mood": None, "conditions": []},
    }
    for key in ("appearance", "line", "identity", "voices", "situation", "schedule"):
        if op[key] is not None:
            char[key] = op[key]
    if op["decision"] is not None:
        char["decision"] = dict(op["decision"])
    if op["intimacy"] is not None:
        char["intimacy"] = dict(op["intimacy"])
    if op["situation"] is not None:
        char["situation"] = dict(op["situation"], deadline=None)
    if op["kin_of"]:
        char["kin_of"] = op["kin_of"]
    state["characters"][cid] = char
    if op["present"]:
        state["scene"]["present"].append(cid)
    ctx.new_characters.append(cid)
    ctx.observable = True
    ctx.applied.append({"op": "introduce_character", "character_id": cid, "tier": op["tier"], "present": op["present"]})


@register(
    "promote_character",
    dict({"character_id": F(S.Id()), "to_tier": F(S.Enum("supporting", "major"))}, **C.card_fields()),
    "把背景或配角升格（只升不降，保留 ID），并补齐新层级缺少的字段。身份卡与倾向卡只能在升格时创建一次，已有的不能再给",
    branch=False,
)
def op_promote_character(ctx, op, path):
    errs = []
    cid = op["character_id"]
    char = None
    if _need_character(ctx, cid, path + ".character_id", errs, npc=True):
        char = ctx.state["characters"][cid]
        if C.TIER_ORDER[op["to_tier"]] <= C.TIER_ORDER[char["tier"]]:
            errs.append(detail(path + ".to_tier", "层级只升不降：%s 已经是 %s" % (char["name"], char["tier"]), None, INVARIANT_VIOLATION))
        for part in ("identity", "intimacy"):
            if op[part] is not None and char.get(part):
                errs.append(detail("%s.%s" % (path, part), "%s 已经有%s，只能逐项演化" % (char["name"], "身份卡" if part == "identity" else "倾向卡"), None, INVARIANT_VIOLATION))
        if op["to_tier"] == "supporting" and (op["intimacy"] or op["voices"]):
            errs.append(detail(path + ".to_tier", "只有重要角色（major）有倾向卡和表里语态", None, INVARIANT_VIOLATION))
    if char is not None:
        merged = dict(char)
        for key in ("appearance", "line", "identity", "intimacy", "voices", "situation"):
            if op[key] is not None:
                merged[key] = op[key]
        if op["decision"] is not None:
            merged["decision"] = dict(char.get("decision") or {}, **op["decision"])
        _card_errors(op["to_tier"], merged, path, errs)
    if not _flush(ctx, errs):
        return
    for key in ("appearance", "line", "identity", "voices", "schedule"):
        if op[key] is not None:
            char[key] = op[key]
    if op["intimacy"] is not None:
        char["intimacy"] = dict(op["intimacy"])
    if op["situation"] is not None:
        char["situation"] = dict(op["situation"], deadline=None)
    if op["decision"] is not None:
        char["decision"] = dict(char.get("decision") or {}, **op["decision"])
    before = char["tier"]
    char["tier"] = op["to_tier"]
    char["promoted_turn"] = ctx.turn
    ctx.new_characters.append(cid)
    ctx.observable = True
    ctx.applied.append({"op": "promote_character", "character_id": cid, "from": before, "to": op["to_tier"]})


# ---------------------------------------------------------------------------
# leverage


@register(
    "leverage_set",
    {
        "holder": F(S.Id()),
        "subject": F(S.Id()),
        "basis_fact_id": F(S.Nullable(S.Id()), required=False, default=None),
        "basis_text": F(S.Nullable(S.Str(1, 120)), required=False, default=None),
        "origin": F(S.Str(1, 60)),
    },
    "登记把柄：一方开始拿捏另一方（把柄、债务、生计）时，必须在同一提交里登记。依据二选一：已有事实（持有方要知道它）或一句新事实。生效期间，双方之间的亲密提交被拒",
)
def op_leverage_set(ctx, op, path):
    errs = []
    state = ctx.state
    holder, subject = op["holder"], op["subject"]
    ok = _need_character(ctx, holder, path + ".holder", errs) & _need_character(ctx, subject, path + ".subject", errs)
    if ok and holder == subject:
        errs.append(detail(path, "持有方与对象不能是同一个人", None, INVARIANT_VIOLATION))
    if (op["basis_fact_id"] is None) == (op["basis_text"] is None):
        errs.append(detail(path, "basis_fact_id 与 basis_text 必须且只能给一个", None, INVARIANT_VIOLATION))
    elif op["basis_fact_id"] is not None and ok:
        fact = state["facts"].get(op["basis_fact_id"])
        if fact is None:
            errs.append(detail(path + ".basis_fact_id", "事实不存在：%s" % op["basis_fact_id"], None, NOT_FOUND))
        elif not SS.knows(state, holder, fact["id"]):
            errs.append(detail(path + ".basis_fact_id", "%s 不知道这件事，拿不住对方" % ctx.name(holder), None, INVARIANT_VIOLATION))
    if ok and holder == state["player_id"] and ctx.in_beat is None and (ctx.mode not in ("result", "attempt") or not ctx.authorized):
        errs.append(detail(path + ".holder", "玩家角色拿捏别人要出自玩家本人的指令（result/attempt + player_authorized）", None, INVARIANT_VIOLATION))
    if ok and any(lv["holder"] == holder and lv["subject"] == subject and lv["state"] == "active" and lv["basis_fact_id"] == op["basis_fact_id"] for lv in state["leverage"].values() if op["basis_fact_id"]):
        errs.append(detail(path, "同一把柄已经登记过", None, INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    basis = op["basis_fact_id"]
    if basis is None:
        basis = SS.next_id(state, "fact", "f")
        state["facts"][basis] = {
            "id": basis,
            "key": "leverage.%s.%s.t%d" % (holder, subject, ctx.turn),
            "text": op["basis_text"],
            "truth": True,
            "known_by": [holder],
            "believed_by": [],
            "visibility": "private",
            "origin": "offscreen" if ctx.in_beat else "observed",
            "turn": ctx.turn,
            "spreading": False,
            "coord": ctx.fact_coord(),
        }
    lid = SS.next_id(state, "leverage", "lv")
    state["leverage"][lid] = {
        "id": lid,
        "holder": holder,
        "subject": subject,
        "basis_fact_id": basis,
        "origin": op["origin"],
        "state": "active",
        "created_turn": ctx.turn,
        "released_turn": None,
        "release_reason": None,
    }
    ctx.observable = True
    ctx.applied.append({"op": "leverage_set", "leverage_id": lid, "holder": holder, "subject": subject, "basis_fact_id": basis})


@register(
    "leverage_release",
    {"leverage_id": F(S.Id()), "reason": F(S.Str(1, 80))},
    "解除把柄（把柄被销毁、债务结清、秘密已经公开等），原因必填。同一提交里先解除再亲密不算解除",
)
def op_leverage_release(ctx, op, path):
    errs = []
    lv = ctx.state["leverage"].get(op["leverage_id"])
    if lv is None:
        errs.append(detail(path + ".leverage_id", "把柄不存在：%s" % op["leverage_id"], None, NOT_FOUND))
    elif lv["state"] != "active":
        errs.append(detail(path + ".leverage_id", "把柄已经解除", None, INVARIANT_VIOLATION))
    elif lv["holder"] == ctx.state["player_id"] and (ctx.mode not in ("result", "attempt") or not ctx.authorized):
        errs.append(detail(path, "放掉玩家手里的把柄要由玩家决定（result/attempt + player_authorized）", None, INVARIANT_VIOLATION))
    if not _flush(ctx, errs):
        return
    lv["state"] = "released"
    lv["released_turn"] = ctx.turn
    lv["release_reason"] = op["reason"]
    ctx.observable = True
    ctx.applied.append({"op": "leverage_release", "leverage_id": lv["id"]})
