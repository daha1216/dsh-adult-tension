"""One narrative turn: validate and apply a commit on a working copy.

All-or-nothing: any invalid operation rejects the whole commit and the
caller's state is untouched (the working copy is discarded).

Order inside a commit:
  1. replaces_turn: restore the state before the replaced turn (same commit)
  2. the previous commit's requests (chapter summary, prologue)
  3. operations in order; advance_time settles in the fixed order of
     RUNTIME_PROTOCOL 6.1 (offscreen and propagation run as hooks); without
     one the clock moves the default 3 minutes after the operations
  4. required offscreen beats, action mode, intimacy and safety checks
  5. invariants, then bookkeeping: memory, chapter archive, prologue and the
     requests for the next commit
"""

from .. import schema as S
from ..errors import INVARIANT_VIOLATION, INVALID_INPUT, SAFETY_BLOCK, AppError, detail, top_code
from ..jsonio import copy
from . import clock as CL
from . import facts as FA
from . import invariants
from . import ops as OPS
from . import simulation
from . import state as SS
from . import structure as ST

F = S.Field
MAX_MEMORY_TURNS = 40  # backstop only: chapter summaries keep the list near 20
UNDO_KEEP = 30  # undo points kept per session (RUNTIME_PROTOCOL 8 wants a bound)
REWRITE_OPS = ("add_fact", "player_update", "advance_time", "npc_action", "npc_state", "enter_scene", "exit_scene", "offscreen_beat")


def commit_fields():
    return {
        "action_mode": F(S.Enum(*ST.ACTION_MODES), desc="result / attempt / rewrite（“其实……”）/ continue / wait"),
        "player_input": F(S.Str(0, 2000), desc="玩家这一句的原话（继续时可为空字符串）"),
        "player_authorized": F(S.Bool(), required=False, default=False, desc="玩家本人的话授权了玩家角色的移动、承诺、交易、同意、转折或设定修改时为 true"),
        "acts_on": F(S.Nullable(S.List(S.Id(), max_items=8, unique=True)), required=False, default=None, desc="玩家行动作用到的 NPC（身体、意志、财物）；attempt 不作用于任何 NPC 时写 []"),
        "operations": F(S.List(OPS.op_spec(), max_items=40), desc="操作列表（可以为空数组）"),
        "content_tags": F(S.List(S.Id(), max_items=12, unique=True), desc="本回合正文涉及的内容标签（可为空数组）；标签表见完整上下文的 tags"),
        "intimate_participants": F(S.List(S.Id(), max_items=6, unique=True), required=False, default=[], desc="content_tags 含 intimate 或 explicit 时必填：亲密参与者（含玩家）"),
        "summary": F(S.Str(1, 120), desc="本回合发生了什么，第三方视角，≤120 字"),
        "open_action": F(S.Str(1, 80), desc="回合停在哪里、谁在等谁，≤80 字"),
        "quotes": F(S.List(S.Str(1, 80), max_items=3), required=False, default=[], desc="≤3 条对后续有意义的原话，每条 ≤80 字"),
        "chapter_summary": F(S.Nullable(S.Str(1, 300)), required=False, default=None, desc="上下文 requests.chapter_summary 为 true 时必填：上一章（到上一回合为止）的摘要，≤300 字；没有要求时不写"),
        "prologue": F(S.Nullable(S.Str(1, 300)), required=False, default=None, desc="上下文 requests.prologue 为 true 时必填：把完整上下文 prologue_merge 里的旧前情与最早几章合并成一段前情，≤300 字；没有要求时不写"),
        "replaces_turn": F(S.Nullable(S.Int(1, 1000000)), required=False, default=None, desc="“刚才不算，改成……”：填当前最后一个回合的回合号，引擎在同一事务里撤销它再应用本次提交"),
    }


def _raise(errors, **extra):
    code = top_code(errors, INVARIANT_VIOLATION)
    message = errors[0]["reason"] if len(errors) == 1 else "提交有 %d 处问题，状态没有改变" % len(errors)
    raise AppError(code, message, errors, **extra)


# ---------------------------------------------------------------------------
# undo and rewrite


def restore(snapshot, current):
    """The state before a turn, keeping what an undo never takes back.

    Player settings made after that turn (boundaries, pause, preferences,
    voice settings from set-preferences), the session identity, the undo
    floor and the id counters (ids are never reused) come from `current`.
    """
    state = copy(snapshot)
    if "facts" not in snapshot:
        # Storage keeps facts outside the snapshot and has already reverted
        # the undone turn's fact changes (journal); keep its source.
        state["facts"] = current["facts"]
    state["session_id"] = current["session_id"]
    state["revision"] = current["revision"]
    state["undo_floor"] = current["undo_floor"]
    state["safety"] = copy(current["safety"])
    prefs = copy(current["preferences"])
    voice = dict(state["preferences"]["voice"])
    for npc, entry in current["preferences"]["voice"].items():
        if isinstance(entry, dict) and entry.get("via") == "meta" and entry.get("since_turn", 0) > snapshot["turn"]:
            voice[npc] = copy(entry)
    prefs["voice"] = voice
    state["preferences"] = prefs
    state["counters"]["next"] = copy(current["counters"]["next"])
    return state


def _undo_problem(current, turn, snapshot, path):
    if turn <= current["undo_floor"]:
        return detail(path, "第 %d 回合是本次读档或开局的那一回合，不能再往回退" % turn, "撤销最多退到本次读档或开局为止", INVARIANT_VIOLATION)
    if snapshot is None or snapshot["turn"] != turn - 1:
        return detail(path, "第 %d 回合的撤销点已经不在了" % turn, "只保留最近 %d 回合的撤销点" % UNDO_KEEP, INVARIANT_VIOLATION)
    return None


def undo(current, snapshot):
    """Undo the last turn. Returns (state, result); revision +1, turn -1."""
    turn = current["turn"]
    problem = _undo_problem(current, turn, snapshot, "$")
    if problem is not None:
        raise AppError(INVARIANT_VIOLATION, problem["reason"], [problem])
    state = restore(snapshot, current)
    state["revision"] = current["revision"] + 1
    return state, {"undone_turn": turn, "turn": state["turn"]}


def _replace_base(current, turn, snapshot):
    if turn != current["turn"]:
        _raise([detail("$.replaces_turn", "只能改写当前最后一个回合（第 %d 回合）" % current["turn"], "replaces_turn 填 %d" % current["turn"], INVARIANT_VIOLATION)])
    problem = _undo_problem(current, turn, snapshot, "$.replaces_turn")
    if problem is not None:
        _raise([problem])
    return restore(snapshot, current)


# ---------------------------------------------------------------------------
# checks


def _request_checks(ctx):
    commit = ctx.commit
    requests = ctx.state["requests"]
    if requests.get("chapter_summary"):
        if not commit["chapter_summary"]:
            ctx.error(
                "$.chapter_summary",
                "引擎要求本次提交附章节摘要",
                "把第 %d–%d 回合写成 ≤300 字的章节摘要，放进 chapter_summary" % (chapter_start(ctx.state), ctx.turn - 1),
            )
    elif commit["chapter_summary"]:
        ctx.error("$.chapter_summary", "引擎没有要求章节摘要", "去掉 chapter_summary；章节在每 20 回合或跨日后由引擎要求", INVALID_INPUT)
    if requests.get("prologue"):
        if not commit["prologue"]:
            ctx.error("$.prologue", "章节超过上限，引擎要求把最早几章合并成一段前情", "读完整上下文的 prologue_merge，合并成 ≤300 字放进 prologue")
    elif commit["prologue"]:
        ctx.error("$.prologue", "引擎没有要求前情", "去掉 prologue", INVALID_INPUT)


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
    if mode == "rewrite":
        if not commit["player_authorized"]:
            ctx.error("$.player_authorized", "“其实……”只能由玩家发起", "带 player_authorized: true")
        if npcs:
            ctx.error("$.acts_on", "“其实……”回合不作用于 NPC", "acts_on 留空；NPC 的反应用 npc_action、npc_state")
        retcons = [a for a in ctx.applied if a["op"] == "player_update" or (a["op"] == "add_fact" and a.get("origin") == "retcon")]
        if not retcons and not ctx.op_failed:
            ctx.error("$.operations", "“其实……”回合至少要有一条追溯事实（add_fact，origin: retcon）或 player_update")


def _beat_checks(ctx):
    """Every NPC a large time skip named must get an offscreen beat, written
    after the skip: the beat is what they did in the skipped time (6.2)."""
    missing = [npc for npc in ctx.required_beats if npc not in ctx.beats_after_time]
    if not missing:
        return None
    report = ctx.settlements[0]
    names = "、".join(ctx.name(npc) for npc in missing)
    if report["default"]:
        hint = "默认的 3 分钟推进跨过了午夜：在操作列表开头加 advance_time（例如 minutes: 3），再在其后为 %s 各加一条 offscreen_beat" % names
    else:
        hint = "在 advance_time 之后为 %s 各加一条 offscreen_beat；错误附带的 preview 给出他们的目标与信息集" % names
    for npc in missing:
        if npc in ctx.beat_npcs:
            ctx.error("$.operations", "%s 的离屏片段写在了时间推进之前" % ctx.name(npc), hint)
        else:
            ctx.error("$.operations", "时间跨度大，%s 必须有一段离屏片段" % ctx.name(npc), hint)
    return report["preview"]


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


# ---------------------------------------------------------------------------
# long-term memory (RUNTIME_PROTOCOL 7)


def chapter_start(state):
    counters = state["counters"]
    return 1 if counters["chapter_count"] == 0 else counters["last_chapter_turn"] + 1


def _close_chapter(state, turn, summary):
    """Archive the turns before `turn` and the ended events; add the chapter."""
    memory = state["memory"]
    counters = state["counters"]
    archive = []
    kept = []
    for entry in memory["turns"]:
        if entry["turn"] < turn:
            archive.append(("turn", entry))
        else:
            kept.append(entry)
    memory["turns"] = kept
    for eid in sorted(state["events"], key=lambda e: int(e[1:])):
        event = state["events"][eid]
        if event["state"] != "pending" and event["resolved_turn"] is not None and event["resolved_turn"] < turn:
            archive.append(("event", event))
            del state["events"][eid]
    days = [payload["day"] for kind, payload in archive if kind == "turn"]
    chapter = {
        "index": counters["chapter_count"] + 1,
        "from_turn": chapter_start(state),
        "to_turn": turn - 1,
        "day": days[-1] if days else state["clock"]["day"],
        "summary": summary,
    }
    counters["chapter_count"] += 1
    counters["last_chapter_turn"] = turn - 1
    memory["chapters"].append(chapter)
    return chapter, archive


def _merge_prologue(state, text):
    memory = state["memory"]
    merged = memory["chapters"][: simulation.PROLOGUE_MERGE]
    memory["chapters"] = memory["chapters"][simulation.PROLOGUE_MERGE :]
    archive = [("chapter", chapter) for chapter in merged]
    if memory["prologue"]:
        archive.insert(0, ("prologue", {"text": memory["prologue"]}))
    memory["prologue"] = text
    return archive


def _simulation_result(ctx):
    report = ctx.settlements[0]
    preview = report["preview"]
    sim = {key: preview[key] for key in ("tier", "minutes", "crossed_day") if key in preview}
    for key in ("moved", "spread", "expired_conditions"):
        if preview[key]:
            sim[key] = preview[key]
    if preview["frozen"] and report["tier"] != "routine":
        sim["frozen"] = True
    if ctx.beats:
        sim["offscreen_beats"] = list(ctx.beats)
    if report["tier"] == "routine" and len(sim) == 3:
        return None
    return sim


# ---------------------------------------------------------------------------


def commit_turn(state, content, commit, undo_snapshot=None):
    """Return (new_state, result) or raise AppError with every problem found.

    `undo_snapshot` is the stored state from before turn `replaces_turn`
    (loaded by the application); that turn is undone in this same commit.
    """
    world = content["world"]
    replaced = commit["replaces_turn"]
    base = _replace_base(state, replaced, undo_snapshot) if replaced is not None else state
    work = FA.working_copy(base)
    ctx = OPS.TurnContext(work, world, commit, simulation.hooks(work["turn"] + 1))
    ctx.significant_actors = lambda: {a["npc_id"] for a in ctx.applied if a["op"] == "npc_action"}
    before_clock = dict(work["clock"])
    leverage_at_start = [lv for lv in SS.active_leverage(work)]
    tag_ids = {tag["id"] for tag in content["tags"]}
    for index, tag in enumerate(commit["content_tags"]):
        if tag not in tag_ids:
            ctx.error("$.content_tags[%d]" % index, "未知内容标签：%s" % tag, "可用：%s" % "、".join(sorted(tag_ids)), INVALID_INPUT)
    _request_checks(ctx)
    for index, op in enumerate(commit["operations"]):
        path = "$.operations[%d]" % index
        if ctx.mode == "rewrite" and op["op"] not in REWRITE_OPS:
            ctx.error(
                path + ".op",
                "“其实……”回合不能用 %s" % op["op"],
                "只允许追溯事实（add_fact，origin: retcon）、player_update，以及 NPC 的反应（npc_action、npc_state、enter_scene、exit_scene）与时间推进",
            )
            continue
        OPS.apply_op(ctx, op, path)
    ctx.op_failed = bool(ctx.errors)
    if ctx.time_ops == 0:
        OPS.advance(ctx, ST.DEFAULT_ADVANCE_MINUTES, "$", default=True)
    preview = _beat_checks(ctx)
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
        if preview is not None:
            _raise(ctx.errors, preview=preview)
        _raise(ctx.errors)

    # -- bookkeeping ------------------------------------------------------------
    work["turn"] = ctx.turn
    work["revision"] = state["revision"] + 1
    memory = work["memory"]
    entry = {
        "turn": ctx.turn,
        "day": work["clock"]["day"],
        "mode": commit["action_mode"],
        "summary": commit["summary"],
        "open_action": commit["open_action"],
        "quotes": list(commit["quotes"]),
    }
    if ctx.beats:
        entry["offscreen"] = [{"npc_id": b["npc_id"], "summary": b["summary"]} for b in ctx.beats]
    archive = []
    chapter = None
    if commit["chapter_summary"]:
        chapter, archive = _close_chapter(work, ctx.turn, commit["chapter_summary"])
    if commit["prologue"]:
        archive.extend(_merge_prologue(work, commit["prologue"]))
    memory["turns"].append(entry)
    overflow = memory["turns"][:-MAX_MEMORY_TURNS]
    if overflow:
        archive.extend(("turn", old) for old in overflow)
        del memory["turns"][:-MAX_MEMORY_TURNS]
    memory["open_action"] = commit["open_action"]
    memory["last_quotes"] = list(commit["quotes"])
    crossed_day = work["clock"]["day"] > before_clock["day"]
    simulation.finalize_requests(work, world, ctx.turn, crossed_day, ctx.accepted_twist)
    work["facts"] = work["facts"].settle()
    scene_changed = ctx.player_moved or any(s["scene"] for s in ctx.settlements)
    result = {
        "turn": ctx.turn,
        "applied": ctx.applied,
        "resolved_events": ctx.resolved_events,
        "simulation": _simulation_result(ctx),
        "clock": dict(work["clock"], label=CL.label(work["clock"], world.get("clock_style", "hm"))),
        "default_time_advance": any(s.get("default") for s in ctx.settlements),
        "scene_changed": scene_changed,
        "location_changed": ctx.player_moved,
        "crossed_day": crossed_day,
        "new_characters": list(ctx.new_characters),
        "chapter": chapter,
        "twist": ctx.accepted_twist,
        "replaced_turn": replaced,
        # internal, for the application: archive rows and the replaced turn's undo base
        "archive": [{"kind": kind, "payload": payload} for kind, payload in archive],
        "undo_base": base if replaced is not None else None,
    }
    return work, result
