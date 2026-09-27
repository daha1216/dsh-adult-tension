"""One narrative turn: validate and apply a commit on a working copy.

All-or-nothing: any invalid operation rejects the whole commit and the
caller's state is untouched (the working copy is discarded).
"""

from .. import schema as S
from ..errors import INVARIANT_VIOLATION, INVALID_INPUT, SAFETY_BLOCK, AppError, detail, top_code
from ..jsonio import copy
from . import clock as CL
from . import invariants
from . import ops as OPS
from . import state as SS
from . import structure as ST

F = S.Field
MAX_MEMORY_TURNS = 20


def commit_fields():
    return {
        "action_mode": F(S.Enum(*ST.ACTION_MODES), desc="result / attempt / rewrite / continue / wait"),
        "player_input": F(S.Str(0, 2000), desc="玩家这一句的原话（继续时可为空字符串）"),
        "player_authorized": F(S.Bool(), required=False, default=False, desc="玩家本人的话授权了玩家角色的移动、承诺、交易、同意或设定修改时为 true"),
        "acts_on": F(S.Nullable(S.List(S.Id(), max_items=8, unique=True)), required=False, default=None, desc="玩家行动作用到的 NPC（身体、意志、财物）；attempt 不作用于任何 NPC 时写 []"),
        "operations": F(S.List(OPS.op_spec(), max_items=40), desc="操作列表（可以为空数组）"),
        "content_tags": F(S.List(S.Id(), max_items=12, unique=True), desc="本回合正文涉及的内容标签（可为空数组）；标签表见完整上下文的 tags"),
        "intimate_participants": F(S.List(S.Id(), max_items=6, unique=True), required=False, default=[], desc="content_tags 含 intimate 或 explicit 时必填：亲密参与者（含玩家）"),
        "summary": F(S.Str(1, 120), desc="本回合发生了什么，第三方视角，≤120 字"),
        "open_action": F(S.Str(1, 80), desc="回合停在哪里、谁在等谁，≤80 字"),
        "quotes": F(S.List(S.Str(1, 80), max_items=3), required=False, default=[], desc="≤3 条对后续有意义的原话，每条 ≤80 字"),
        "chapter_summary": F(S.Nullable(S.Str(1, 300)), required=False, default=None, desc="上下文 requests.chapter_summary 为 true 时必填，≤300 字"),
        "replaces_turn": F(S.Nullable(S.Int(1, 1000000)), required=False, default=None, desc="“刚才不算，改成……”时填上一回合的回合号"),
    }


def _raise(errors):
    code = top_code(errors, INVARIANT_VIOLATION)
    message = errors[0]["reason"] if len(errors) == 1 else "提交有 %d 处问题，状态没有改变" % len(errors)
    raise AppError(code, message, errors)


def _mode_checks(ctx):
    commit = ctx.commit
    mode = commit["action_mode"]
    player = ctx.state["player_id"]
    acts_on = commit["acts_on"]
    if acts_on:
        for index, cid in enumerate(acts_on):
            if cid not in ctx.state["characters"]:
                ctx.error("$.acts_on[%d]" % index, "角色不存在：%s" % cid, None, "NOT_FOUND")
            elif cid == player:
                ctx.error("$.acts_on[%d]" % index, "acts_on 只写玩家行动作用到的 NPC", None, INVALID_INPUT)
    npcs = [c for c in (acts_on or []) if c != player and c in ctx.state["characters"]]
    if mode == "result" and npcs:
        ctx.error(
            "$.action_mode",
            "作用于 NPC 身体、意志、财物的行动是尝试档，不是结果档",
            "改为 attempt，并附这些 NPC 的回应：%s" % "、".join(ctx.name(c) for c in npcs),
        )
    if mode == "attempt":
        if acts_on is None and not ctx.responses:
            ctx.error(
                "$.acts_on",
                "尝试档要么附 NPC 回应，要么用 acts_on: [] 声明这次尝试不作用于任何 NPC",
                "尝试作用于 NPC 时，结果由 NPC 与处境决定：加一条 npc_response",
            )
        for cid in npcs:
            if cid not in ctx.responses:
                ctx.error("$.operations", "尝试作用于 %s，却没有 %s 的回应" % (ctx.name(cid), ctx.name(cid)), "加一条 npc_response（拒绝/协商/有限配合/表面配合/真诚配合）")
    if mode in ("continue", "wait"):
        if commit["player_authorized"]:
            ctx.error("$.player_authorized", "继续/等待回合里玩家没有做决定，不能带 player_authorized", "去掉它")
        if not ctx.observable and not ctx.op_failed:
            ctx.error("$.operations", "继续/等待回合至少要有一个可观察的变化", "让 NPC 行动、状态变化、新事实或有人来去（npc_action、npc_state、add_fact、enter_scene 等）")


def _intimacy_checks(ctx, leverage_at_start):
    commit = ctx.commit
    tags = set(commit["content_tags"])
    participants = commit["intimate_participants"]
    structural = tags & set(ST.STRUCTURAL_INTIMACY_TAGS)
    if not structural:
        if participants:
            ctx.error("$.intimate_participants", "只有带 intimate 或 explicit 标签的提交才写亲密参与者", None, INVALID_INPUT)
        return
    if len(participants) < 2:
        ctx.error("$.intimate_participants", "亲密场景的提交必须写明参与者（角色 ID 数组，含玩家）", None, INVALID_INPUT)
        return
    state = ctx.state
    player = state["player_id"]
    for index, cid in enumerate(participants):
        path = "$.intimate_participants[%d]" % index
        char = state["characters"].get(cid)
        if char is None:
            ctx.error(path, "角色不存在：%s" % cid, None, "NOT_FOUND")
            continue
        if not isinstance(char.get("age"), int):
            ctx.error(path, "%s 的年龄不明确，亲密升级被阻断" % char["name"], "先补齐明确的成年年龄", SAFETY_BLOCK)
        elif char["age"] < 18:
            ctx.error(path, "%s 未成年" % char["name"], None, SAFETY_BLOCK)
        if char["tier"] != "major":
            ctx.error(path, "%s 不是重要角色，不能参与亲密场景" % char["name"], "先 promote_character 升格为 major")
        if not SS.is_present(state, cid):
            ctx.error(path, "%s 不在场" % char["name"])
        bad = [c for c in char["status"]["conditions"] if c["kind"] in ST.INCAPACITATING]
        if bad:
            ctx.error(path, "%s 处于%s状态，不能参与亲密场景" % (char["name"], bad[0]["text"]), "醉酒、睡着、失去意识的人不参与亲密场景")
        if cid == player:
            if commit["action_mode"] not in ("result", "attempt") or not commit["player_authorized"]:
                ctx.error(path, "玩家角色的同意只能来自玩家本人的指令（result/attempt + player_authorized）")
        else:
            cooperative = [r for r in ctx.responses.get(cid, []) if r in ST.COOPERATIVE_RESPONSES]
            if not cooperative and cid not in ctx.significant_actors():
                ctx.error(
                    path,
                    "%s 在本次提交里没有 partial/genuine 回应或主动行动" % char["name"],
                    "每一步都要有对方可见的回应；没有回应就不能继续",
                )
    for a_index, a in enumerate(participants):
        for b in participants[a_index + 1 :]:
            for lv in leverage_at_start + [l for l in state["leverage"].values() if l["created_turn"] == ctx.turn]:
                if {lv["holder"], lv["subject"]} == {a, b}:
                    ctx.error(
                        "$.intimate_participants",
                        "%s 与 %s 之间有生效中的把柄（%s），处境不是同意" % (ctx.name(a), ctx.name(b), lv["id"]),
                        "把柄必须在之前的回合解除；同一提交里先解除再亲密不算",
                    )


def commit_turn(state, content, commit, hooks=None):
    """Return (new_state, result) or raise AppError with every problem found."""
    world = content["world"]
    work = copy(state)
    ctx = OPS.TurnContext(work, world, commit, hooks)
    ctx.significant_actors = lambda: {a["npc_id"] for a in ctx.applied if a["op"] == "npc_action"}
    before_clock = dict(work["clock"])
    leverage_at_start = [lv for lv in SS.active_leverage(work)]
    tag_ids = {tag["id"] for tag in content["tags"]}
    for index, tag in enumerate(commit["content_tags"]):
        if tag not in tag_ids:
            ctx.error("$.content_tags[%d]" % index, "未知内容标签：%s" % tag, "可用：%s" % "、".join(sorted(tag_ids)), INVALID_INPUT)
    if commit["replaces_turn"] is not None:
        ctx.error("$.replaces_turn", "改写上一回合在当前版本还没有开放", "去掉 replaces_turn", INVALID_INPUT)
    requests = work["requests"]
    if requests.get("chapter_summary") and not commit["chapter_summary"]:
        ctx.error("$.chapter_summary", "引擎要求本次提交附章节摘要", "写 ≤300 字的章节摘要放进 chapter_summary")
    for index, op in enumerate(commit["operations"]):
        OPS.apply_op(ctx, op, "$.operations[%d]" % index)
    ctx.op_failed = bool(ctx.errors)
    if ctx.time_ops == 0:
        OPS.advance(ctx, ST.DEFAULT_ADVANCE_MINUTES, "$", default=True)
    _mode_checks(ctx)
    _intimacy_checks(ctx, leverage_at_start)
    shared = set(ctx.voice_reasons) & set(ctx.relationship_reasons)
    if shared:
        ctx.error("$.operations", "语态切换与关系变化用了同一条原因：%s" % "、".join(sorted(shared)), "语态只是说话方式，不是关系升级；两者分别写原因")
    for problem in OPS.check_safety_tags(work, commit["content_tags"]):
        ctx.errors.append(problem)
    if not ctx.errors:
        ctx.errors.extend(invariants.check(work, before_clock))
    if ctx.errors:
        _raise(ctx.errors)

    # -- bookkeeping ------------------------------------------------------------
    work["turn"] = ctx.turn
    work["revision"] = state["revision"] + 1
    memory = work["memory"]
    memory["turns"].append(
        {
            "turn": ctx.turn,
            "day": work["clock"]["day"],
            "mode": commit["action_mode"],
            "summary": commit["summary"],
            "open_action": commit["open_action"],
            "quotes": list(commit["quotes"]),
        }
    )
    del memory["turns"][:-MAX_MEMORY_TURNS]
    memory["open_action"] = commit["open_action"]
    memory["last_quotes"] = list(commit["quotes"])
    crossed_day = work["clock"]["day"] > before_clock["day"]
    scene_changed = ctx.player_moved or any(s["scene"] for s in ctx.settlements)
    result = {
        "turn": ctx.turn,
        "applied": ctx.applied,
        "resolved_events": ctx.resolved_events,
        "simulation": None,
        "clock": dict(work["clock"], label=CL.label(work["clock"], world.get("clock_style", "hm"))),
        "default_time_advance": any(s.get("default") for s in ctx.settlements),
        "scene_changed": scene_changed,
        "location_changed": ctx.player_moved,
        "crossed_day": crossed_day,
        "new_characters": list(ctx.new_characters),
    }
    return work, result
