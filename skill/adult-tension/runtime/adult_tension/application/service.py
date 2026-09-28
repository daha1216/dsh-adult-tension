"""The single write path (D4) and the game commands.

Every state change goes through session_write() or create_write():
  1. shape validation (unknown fields, duplicates, types, ranges)
  2. BEGIN IMMEDIATE (STORAGE_BUSY when the lock cannot be taken)
  3. idempotency lookup: same request_id + same input -> stored response
  4. revision check (session writes)
  5. domain on a working copy; any error -> rollback, nothing written
  6. write state, turn log and idempotency record in the same transaction
The response (including the next context) is built before COMMIT so that the
idempotency record stores exactly what the caller received.
"""

import hashlib
import os
import re
from datetime import datetime

from .. import schema as S
from ..errors import (
    CONTENT_ERROR,
    IDEMPOTENCY_CONFLICT,
    INVALID_INPUT,
    INVARIANT_VIOLATION,
    NOT_FOUND,
    SAFETY_BLOCK,
    SLOT_CONFLICT,
    STALE_REVISION,
    STORAGE_BUSY,
    AppError,
    detail,
)
from ..jsonio import canonical
from ..persistence import db, repo
from ..projections import context as CX
from . import specs

CREATE_SCOPE = "create"
RESERVED_SLOT_NAMES = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)}


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_request_id():
    return "r_" + os.urandom(6).hex()


def new_session_id(conn):
    while True:
        sid = "s_" + os.urandom(4).hex()
        if not repo.session_exists(conn, sid):
            return sid


def validate(spec, payload):
    normalized, errors = S.validate(spec, payload)
    if errors:
        raise AppError(INVALID_INPUT, "输入有 %d 处问题" % len(errors) if len(errors) > 1 else errors[0]["reason"], errors)
    return normalized


def digest_of(command, payload):
    return hashlib.sha256(canonical([command, payload]).encode("utf-8")).hexdigest()


def fault(name):
    return os.environ.get("ADULT_TENSION_FAULT") == name


def _replay(conn, scope, request_id, digest):
    cached = repo.idem_get(conn, scope, request_id)
    if cached is None:
        return None
    if cached["digest"] != digest:
        raise AppError(
            IDEMPOTENCY_CONFLICT,
            "request_id %s 已经用于另一个请求" % request_id,
            [detail("$.request_id", "同一个 request_id 带了不同的内容", "先 get-context 确认上一次是否已经生效，再决定是否用新的 request_id 补交；不能把同一回合写两次", IDEMPOTENCY_CONFLICT)],
        )
    response = cached["response"]
    response["replayed"] = True
    return response


def save_info(session):
    return {"current_slot": session["current_slot"], "turns_since_save": session["turns_since_save"]}


def session_write(ctx, command, payload, handler):
    """Run a session-scoped write. handler(conn, session, now) -> response dict."""
    conn = ctx.db()
    digest = digest_of(command, payload)
    db.begin_write(conn)
    try:
        replay = _replay(conn, payload["session_id"], payload["request_id"], digest)
        if replay is not None:
            conn.execute("COMMIT")
            return replay
        session = repo.load_session(conn, payload["session_id"])
        if session["revision"] != payload["expected_revision"]:
            raise AppError(
                STALE_REVISION,
                "局面已经变了：当前 revision 是 %d，不是 %d" % (session["revision"], payload["expected_revision"]),
                [detail("$.expected_revision", "revision 已过期", "基于附带的新上下文重新判断后再提交；不要只换 revision 重放旧操作", STALE_REVISION)],
                current_revision=session["revision"],
                context=CX.brief(session["state"], session["content"], save_info(session)),
            )
        now = now_iso()
        response = handler(conn, session, now)
        response.setdefault("next_request_id", new_request_id())
        response["replayed"] = False
        repo.idem_put(conn, payload["session_id"], payload["request_id"], digest, response, now)
        conn.execute("COMMIT")
        return response
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def create_write(ctx, command, payload, handler):
    """Run a write that creates a session. handler(conn, now) -> response dict."""
    conn = ctx.db()
    digest = digest_of(command, payload)
    db.begin_write(conn)
    try:
        replay = _replay(conn, CREATE_SCOPE, payload["request_id"], digest)
        if replay is not None:
            conn.execute("COMMIT")
            return replay
        now = now_iso()
        response = handler(conn, now)
        response.setdefault("next_request_id", new_request_id())
        response["replayed"] = False
        repo.idem_put(conn, CREATE_SCOPE, payload["request_id"], digest, response, now)
        conn.execute("COMMIT")
        return response
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# new-game


def _content_snapshot(ctx, pack):
    return {"world": pack, "tags": ctx.content().tags()["tags"], "content_version": ctx.content().index()["content_version"]}


def include_drafts(ctx, payload):
    """--include-drafts, or the development switch ADULT_TENSION_INCLUDE_DRAFTS=1 set by a test harness."""
    return bool(payload.get("include_drafts")) or ctx.environ.get("ADULT_TENSION_INCLUDE_DRAFTS") == "1"


def _world_candidates(ctx, conditions, include_drafts):
    index = ctx.content().index()
    allowed = [w for w in index["worlds"] if include_drafts or w["status"] == "released"]
    locked = conditions["locks"].get("world_id")
    if locked:
        entry = next((w for w in index["worlds"] if w["id"] == locked), None)
        if entry is None:
            raise AppError(
                NOT_FOUND,
                "世界不存在：%s" % locked,
                [detail("$.locks.world_id", "世界不存在：%s" % locked, "用 list-worlds 查看可选世界", NOT_FOUND)],
            )
        if entry not in allowed:
            raise AppError(
                NOT_FOUND,
                "世界 %s 还没有发布" % locked,
                [detail("$.locks.world_id", "世界尚未发布（%s）" % entry["status"], "开发时可用 include_drafts", NOT_FOUND)],
            )
        allowed = [entry]
    excluded = set(conditions["excludes"]["world_ids"])
    return sorted(w["id"] for w in allowed if w["id"] not in excluded)


def _plan_across(ctx, world_ids, seed, conditions):
    from ..domain import opening, rng

    order = rng.shuffled(seed, "opening.world", list(world_ids))
    reasons = []
    for world_id in order:
        pack = ctx.content().world(world_id)
        try:
            return pack, opening.plan(pack, seed, conditions)
        except AppError as err:
            if err.code != "NO_MATCH":
                raise
            reasons.extend("%s：%s" % (pack["title"], d["reason"]) for d in err.details)
    raise opening.no_match(reasons or ["没有可用的世界"], conditions["locks"].get("world_id"), conditions)


MODE_ITEMS = (("daily", "daily_activities", "日常活动"), ("pressure", "pressures", "压力"))


def _custom_world(ctx, raw, conditions):
    """Validate a player-described world with the same validator (CONTENT_BIBLE 5).

    The lowered minimum "daily activities or pressures, >= 2 by mode" depends
    on the mode asked for, so it is checked here; a random mode settles on the
    one mode the world can open, if it can open only one.
    """
    from ..domain import structure as ST
    from ..domain import worldpack

    if not isinstance(raw, dict):
        raise AppError(CONTENT_ERROR, "自定义世界应为一个 JSON 对象", [detail("$.custom_world", "应为对象", "格式见 references/custom_world.md", CONTENT_ERROR)])
    tag_ids = [t["id"] for t in ctx.content().tags()["tags"]]
    pack, problems = worldpack.validate_world(raw, custom=True, tag_ids=tag_ids)
    problems = [dict(p, path="$.custom_world" + p["path"][1:] if p["path"].startswith("$") else p["path"]) for p in problems]
    if raw.get("extends") is not None:
        problems.append(detail("$.custom_world.extends", "自定义世界不能引用底包", "把需要的命名池、风俗直接写进这个世界", CONTENT_ERROR))
    if raw.get("id") in {w["id"] for w in ctx.content().index()["worlds"]}:
        problems.append(detail("$.custom_world.id", "与现有世界重名：%s" % raw["id"], "换一个 ID，例如加 custom_ 前缀", CONTENT_ERROR))
    need = ST.CUSTOM_MINIMUMS["mode_items"]
    counts = {mode: len(raw[key]) if isinstance(raw.get(key), list) else 0 for mode, key, _label in MODE_ITEMS}
    if conditions["mode"] == "random":
        openable = [mode for mode, _key, _label in MODE_ITEMS if counts[mode] >= need]
        if len(openable) == 1:
            conditions["mode"] = openable[0]
    else:
        for mode, key, label in MODE_ITEMS:
            if mode == conditions["mode"] and counts[mode] < need:
                problems.append(detail("$.custom_world.%s" % key, "要开%s模式，%s至少 %d 条，现有 %d 条" % ("日常" if mode == "daily" else "压力", label, need, counts[mode]), "补齐，或换一种模式开局", CONTENT_ERROR))
    if problems:
        raise AppError(
            CONTENT_ERROR,
            "自定义世界有 %d 处问题" % len(problems) if len(problems) > 1 else problems[0]["reason"],
            problems,
        )
    return pack


def seed_stream():
    while True:
        yield 1 + int.from_bytes(os.urandom(4), "big") % 999999


def new_game(ctx, payload):
    from ..domain import opening

    payload = validate(specs.NEW_GAME, payload)
    problems = []
    if payload["replay"] and payload["seed"] is None:
        problems.append(detail("$.seed", "“重开 N 号”必须给出种子编号", None, INVALID_INPUT))
    if payload["mode"] is None and not payload["replay"]:
        problems.append(detail("$.mode", "缺少模式", "先问玩家“1 日常 / 2 有压力”；玩家说“随便”才用 random", INVALID_INPUT))
    custom = None
    if payload["custom_world"] is not None:
        if payload["replay"]:
            problems.append(detail("$.replay", "自定义世界没有开局记录，不能“重开 N 号”", "带同一个 custom_world 与 seed 重新开局即可复现", INVALID_INPUT))
        if payload["locks"].get("world_id") or payload["excludes"].get("world_ids"):
            problems.append(detail("$.locks.world_id", "自定义世界不和现有世界一起锁定或排除", "去掉 world_id 的锁定与排除", INVALID_INPUT))
    if problems:
        raise AppError(INVALID_INPUT, problems[0]["reason"], problems)
    conditions = opening.normalize_conditions(payload)
    if payload["custom_world"] is not None:
        custom = _custom_world(ctx, payload["custom_world"], conditions)

    def handler(conn, now):
        seed = payload["seed"]
        restored = False
        if payload["replay"]:
            stored = repo.conditions_for_seed(conn, seed)
            if stored is not None:
                conditions.clear()
                conditions.update(stored)
                restored = True
            elif payload["mode"] is None:
                raise AppError(
                    NOT_FOUND,
                    "本机没有 %d 号开局的记录" % seed,
                    [detail("$.seed", "找不到这个种子的开局条件", "请玩家说明模式（日常/有压力），用同一种子与条件重开", NOT_FOUND)],
                )
        if custom is not None:
            # A custom world lives only in this game's snapshot: no history, no dedupe.
            if seed is None:
                seed = next(seed_stream())
            pack, planned = custom, opening.plan(custom, seed, conditions)
        else:
            worlds = _world_candidates(ctx, conditions, include_drafts(ctx, payload))
            if not worlds:
                raise opening.no_match(["排除之后没有可选的世界"], None, conditions)
            if seed is None:
                history = repo.opening_history(conn)
                seed, _result = opening.choose_seed(lambda s: _plan_across(ctx, worlds, s, conditions)[1][0], seed_stream(), history)
            pack, planned = _plan_across(ctx, worlds, seed, conditions)
        content = _content_snapshot(ctx, pack)
        state, opening_payload = opening.instantiate(pack, seed, conditions, planned, content["content_version"])
        state["session_id"] = new_session_id(conn)
        prefs = payload["preferences"]
        for key in ("inner_view", "assistant", "offscreen_simulation", "person"):
            if key in prefs:
                state["preferences"][key] = prefs[key]
        repo.insert_session(conn, state, content, "new_game", now)
        if not pack.get("custom"):
            repo.add_opening(conn, seed, planned[0], conditions, content["content_version"], now)
        repo.insert_turn_log(conn, state["session_id"], 1, 1, "opening", None, None, {"signature": planned[0]["signature"], "seed": seed}, None, None, now)
        return {
            "session_id": state["session_id"],
            "revision": state["revision"],
            "turn": state["turn"],
            "seed": seed,
            "conditions_restored": restored,
            "opening": opening_payload,
            "context": CX.full(state, content, {"current_slot": None, "turns_since_save": 0}),
        }

    return create_write(ctx, "new-game", payload, handler)


# ---------------------------------------------------------------------------
# get-context


def get_context(ctx, payload):
    from ..domain import settlement, simulation

    payload = validate(specs.GET_CONTEXT, payload)
    preview_time = payload["preview_time"]
    if preview_time is not None:
        given = [k for k in settlement.ADVANCE_KEYS if k in preview_time]
        if len(given) != 1:
            raise AppError(
                INVALID_INPUT,
                "preview_time 里 minutes、until、days 必须且只能给一个",
                [detail("$.preview_time", "minutes、until、days 必须且只能给一个", None, INVALID_INPUT)],
            )
    session = repo.load_session(ctx.db(), payload["session_id"])
    state, content = session["state"], session["content"]
    project = CX.full if payload["depth"] == "full" else CX.brief
    out = {
        "session_id": session["session_id"],
        "revision": session["revision"],
        "turn": session["turn"],
        "context": project(state, content, save_info(session)),
    }
    if preview_time is not None:
        out["preview"] = simulation.preview(state, content["world"], preview_time)
    if payload["want_twist"]:
        candidates, note = simulation.requested_twists(state, content["world"])
        out["twist_candidates"] = candidates
        if note:
            out["twist_note"] = note
    return out


# ---------------------------------------------------------------------------
# commit-turn

DOMAIN_KEYS = (
    "action_mode",
    "player_input",
    "player_authorized",
    "acts_on",
    "operations",
    "content_tags",
    "intimate_participants",
    "summary",
    "open_action",
    "quotes",
    "chapter_summary",
    "prologue",
    "replaces_turn",
)
# A failed commit with one of these codes makes the next context full.
FAILURE_CODES = (INVALID_INPUT, INVARIANT_VIOLATION, NOT_FOUND, SAFETY_BLOCK)
SESSION_ID_RE = re.compile(r"s_[a-z0-9]{2,38}")


def choose_depth(state, result, failed_before=False):
    """DESIGN_DECISIONS defaults: full after a failed commit, on a new place,
    a new character or a new day, every 5 turns, and when a prologue is due."""
    if failed_before or result["location_changed"] or result["new_characters"] or result["crossed_day"]:
        return "full"
    if state["requests"].get("prologue") or state["turn"] % 5 == 0:
        return "full"
    return "brief"


def _mark_failure(ctx, session_id):
    """Best effort: a busy database skips the marker, never the caller's error."""
    conn = ctx.db()
    try:
        db.begin_write(conn)
    except AppError as err:
        if err.code == STORAGE_BUSY:
            return
        raise
    try:
        repo.mark_commit_failure(conn, session_id, now_iso())
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def commit_turn(ctx, payload):
    try:
        return _commit_turn(ctx, payload)
    except AppError as err:
        sid = payload.get("session_id") if isinstance(payload, dict) else None
        if err.code in FAILURE_CODES and isinstance(sid, str) and SESSION_ID_RE.fullmatch(sid):
            _mark_failure(ctx, sid)
        raise


def _commit_turn(ctx, payload):
    from ..domain import turn

    payload = validate(specs.COMMIT_TURN, payload)
    commit = {key: payload[key] for key in DOMAIN_KEYS}

    def handler(conn, session, now):
        sid = session["session_id"]
        state = session["state"]
        snapshot = None
        replacing = commit["replaces_turn"]
        if replacing is not None:
            snapshot = repo.undo_point(conn, sid, replacing)
            if replacing == state["turn"] and snapshot is not None:
                # Undo the replaced turn in this same transaction (RUNTIME_PROTOCOL 8):
                # its facts first, so the domain sees the facts from before it.
                repo.revert_turn_facts(conn, sid, replacing)
                state["facts"] = repo.FactSource(conn, sid)
        new_state, result = turn.commit_turn(state, session["content"], commit, snapshot)
        failed_before = repo.take_commit_failure(conn, sid) is not None
        replaced = result["replaced_turn"]
        if replaced is not None:
            repo.mark_turn_undone(conn, sid, replaced)
            repo.delete_archive_turn(conn, sid, replaced)
            repo.put_undo_point(conn, sid, new_state["turn"], result["undo_base"])
        else:
            repo.save_undo_point_from_session(conn, sid, new_state["turn"])
        repo.write_fact_changes(conn, sid, new_state["turn"], new_state["facts"])
        repo.trim_undo_points(conn, sid, turn.UNDO_KEEP)
        unsaved = session["turns_since_save"] + 1
        repo.update_session(conn, new_state, now, turns_since_save=unsaved)
        for item in result["archive"]:
            repo.add_archive(conn, sid, item["kind"], new_state["turn"], item["payload"], now)
        repo.insert_turn_log(
            conn,
            new_state["session_id"],
            new_state["turn"],
            new_state["revision"],
            "commit",
            commit["action_mode"],
            commit["player_input"],
            {"operations": commit["operations"], "applied": result["applied"], "resolved_events": result["resolved_events"], "content_tags": commit["content_tags"]},
            commit["summary"],
            commit["open_action"],
            now,
        )
        if fault("kill_in_commit"):
            os._exit(137)  # test hook: the process dies inside the write transaction
        depth = choose_depth(new_state, result, failed_before)
        project = CX.full if depth == "full" else CX.brief
        response = {
            "revision": new_state["revision"],
            "turn": new_state["turn"],
            "applied": result["applied"],
            "resolved_events": result["resolved_events"],
            "simulation": result["simulation"],
            "clock": result["clock"],
            "default_time_advance": result["default_time_advance"],
            "context": project(new_state, session["content"], {"current_slot": session["current_slot"], "turns_since_save": unsaved}),
        }
        for key in ("chapter", "twist", "replaced_turn"):
            if result[key] is not None:
                response[key] = result[key]
        return response

    return session_write(ctx, "commit-turn", payload, handler)


# ---------------------------------------------------------------------------
# undo-turn


def undo_turn(ctx, payload):
    from ..domain import turn

    payload = validate(specs.UNDO_TURN, payload)

    def handler(conn, session, now):
        sid = session["session_id"]
        undone = session["state"]["turn"]
        snapshot = repo.undo_point(conn, sid, undone)
        new_state, result = turn.undo(session["state"], snapshot)
        repo.revert_turn_facts(conn, sid, undone)
        new_state["facts"] = repo.FactSource(conn, sid)
        repo.delete_undo_point(conn, sid, undone)
        repo.mark_turn_undone(conn, sid, undone)
        repo.delete_archive_turn(conn, sid, undone)
        unsaved = session["turns_since_save"] + 1
        repo.update_session(conn, new_state, now, turns_since_save=unsaved)
        repo.insert_turn_log(conn, sid, new_state["turn"], new_state["revision"], "undo", None, None, {"undone_turn": undone}, None, None, now)
        return {
            "revision": new_state["revision"],
            "turn": new_state["turn"],
            "undone_turn": result["undone_turn"],
            "receipt": "已撤销第 %d 回合" % result["undone_turn"],
            "context": CX.brief(new_state, session["content"], {"current_slot": session["current_slot"], "turns_since_save": unsaved}),
        }

    return session_write(ctx, "undo-turn", payload, handler)


# ---------------------------------------------------------------------------
# save / load / list


def normalize_slot_name(raw, path="$.name"):
    name = re.sub(r"\s+", "-", raw.strip())
    problems = []
    if not name:
        problems.append("存档名不能为空")
    if len(name) > 40:
        problems.append("存档名最长 40 个字符")
    if re.search(r"[\\/:*?\"<>|]", name):
        problems.append("存档名不能含路径分隔符或 \\ / : * ? \" < > |")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        problems.append("存档名不能含控制字符")
    if name.strip(".") == "" or name.endswith("."):
        problems.append("存档名不能只由点组成或以点结尾")
    if name.split(".")[0].lower() in RESERVED_SLOT_NAMES:
        problems.append("存档名是系统保留名：%s" % name)
    if problems:
        raise AppError(INVALID_INPUT, problems[0], [detail(path, p, "换一个名字（可以用中文）", INVALID_INPUT) for p in problems])
    return name


def save_slot(ctx, payload):
    payload = validate(specs.SAVE_SLOT, payload)

    def handler(conn, session, now):
        state, content = session["state"], session["content"]
        auto = False
        if payload["name"]:
            name = normalize_slot_name(payload["name"])
        elif session["current_slot"]:
            name = session["current_slot"]
        else:
            name = normalize_slot_name("%s-第%d回合" % (state["world_title"], state["turn"]))
            auto = True
        existing = repo.get_slot(conn, name)
        if existing is not None and not payload["overwrite"]:
            if name != session["current_slot"]:
                raise AppError(
                    SLOT_CONFLICT,
                    "「%s」已存在" % name,
                    [detail("$.name", "存档名已被占用", "问玩家是否覆盖；确认后带 overwrite: true 重交", SLOT_CONFLICT)],
                    reason="exists",
                    slot={k: existing[k] for k in ("name", "world_title", "turn", "clock_label", "saved_at")},
                )
            if existing["version"] != session["slot_version"]:
                raise AppError(
                    SLOT_CONFLICT,
                    "「%s」已在别的对话里被改动过" % name,
                    [detail("$.name", "本局的当前槽已被别处更新", "给玩家三个选项：A 读取最新 / B 另存为新名 / C 取消", SLOT_CONFLICT)],
                    reason="changed_elsewhere",
                    options=["A 读取最新", "B 另存为新名", "C 取消"],
                    slot={k: existing[k] for k in ("name", "world_title", "turn", "clock_label", "saved_at")},
                )
        version = (existing["version"] + 1) if existing else 1
        from ..domain import state as SS

        label = SS.clock_label(state, content["world"])
        repo.put_slot(conn, name, state["session_id"], label, state["memory"]["open_action"], version, now)
        repo.set_save_info(conn, state["session_id"], name, version, now)
        verb = "已另存为" if payload["save_as"] else "已保存到"
        return {
            "revision": state["revision"],
            "turn": state["turn"],
            "slot": {"name": name, "version": version, "turn": state["turn"], "world_title": state["world_title"], "clock_label": label, "saved_at": now},
            "auto_named": auto,
            "receipt": "%s「%s」·第 %d 回合" % (verb, name, state["turn"]),
        }

    return session_write(ctx, "save-slot", payload, handler)


def _resume(state):
    turns = state["memory"]["turns"]
    chapters = state["memory"]["chapters"]
    return {
        "chapter_summary": chapters[-1]["summary"] if chapters else None,
        "prologue": state["memory"].get("prologue"),
        "recent": [t["summary"] for t in turns[-3:]],
        "last_quotes": list(state["memory"]["last_quotes"]),
        "open_action": state["memory"]["open_action"],
    }


def load_slot(ctx, payload):
    payload = validate(specs.LOAD_SLOT, payload)
    name = normalize_slot_name(payload["name"])

    def handler(conn, now):
        slot = repo.get_slot(conn, name, with_blobs=True)
        if slot is None:
            names = [s["name"] for s in repo.list_slots(conn)]
            raise AppError(
                NOT_FOUND,
                "没有名为「%s」的存档" % name,
                [detail("$.name", "存档不存在", "现有存档：%s" % ("、".join(names[:20]) or "（无）"), NOT_FOUND)],
                available=names[:20],
            )
        state = slot["state"]
        state["session_id"] = new_session_id(conn)
        state["undo_floor"] = state["turn"]
        repo.insert_session(conn, state, slot["content"], "load_slot", now, current_slot=name, slot_version=slot["version"], with_facts=False)
        repo.copy_slot_rows(conn, name, state["session_id"], now)
        state["facts"] = repo.FactSource(conn, state["session_id"])
        repo.insert_turn_log(conn, state["session_id"], state["turn"], state["revision"], "load", None, None, {"slot": name, "version": slot["version"]}, None, None, now)
        return {
            "session_id": state["session_id"],
            "revision": state["revision"],
            "turn": state["turn"],
            "slot": {"name": name, "version": slot["version"], "saved_at": slot["saved_at"]},
            "receipt": "已读取「%s」·第 %d 回合" % (name, state["turn"]),
            "resume": _resume(state),
            "context": CX.full(state, slot["content"], {"current_slot": name, "turns_since_save": 0}),
        }

    return create_write(ctx, "load-slot", payload, handler)


def list_slots(ctx, payload):
    slots = repo.list_slots(ctx.db())
    return {
        "slots": [
            {
                "name": s["name"],
                "world_title": s["world_title"],
                "turn": s["turn"],
                "clock_label": s["clock_label"],
                "saved_at": s["saved_at"],
                "open_action": s["open_action"],
            }
            for s in slots
        ]
    }


def delete_slot(ctx, payload):
    payload = validate(specs.DELETE_SLOT, payload)
    name = normalize_slot_name(payload["name"])
    if not payload["confirm"]:
        raise AppError(
            INVALID_INPUT,
            "删除存档需要玩家确认",
            [detail("$.confirm", "玩家还没有确认", "先问“确定删除「%s」吗？”，确认后带 confirm: true 重交" % name, INVALID_INPUT)],
        )

    def handler(conn, session, now):
        if repo.get_slot(conn, name) is None:
            names = [s["name"] for s in repo.list_slots(conn)]
            raise AppError(
                NOT_FOUND,
                "没有名为「%s」的存档" % name,
                [detail("$.name", "存档不存在", "现有存档：%s" % ("、".join(names[:20]) or "（无）"), NOT_FOUND)],
                available=names[:20],
            )
        repo.delete_slot(conn, name)
        return {"revision": session["revision"], "turn": session["turn"], "deleted": name, "receipt": "已删除「%s」" % name}

    return session_write(ctx, "delete-slot", payload, handler)


# ---------------------------------------------------------------------------
# sessions, export, import


def list_sessions(ctx, payload):
    from ..domain import clock as CL

    payload = validate(specs.LIST_SESSIONS, payload)
    out = []
    for row in repo.list_sessions(ctx.db(), payload["limit"]):
        state = row["state"]
        memory = state["memory"]
        last = memory["turns"][-1]["summary"] if memory["turns"] else (memory["chapters"][-1]["summary"] if memory["chapters"] else None)
        out.append(
            {
                "session_id": row["session_id"],
                "world_title": row["world_title"],
                "mode": row["mode"],
                "turn": row["turn"],
                "clock_label": CL.label(state["clock"], row["clock_style"]),
                "last_summary": last,
                "open_action": memory["open_action"],
                "paused": state["safety"]["paused"],
                "current_slot": row["current_slot"],
                "turns_since_save": row["turns_since_save"],
                "origin": row["origin"],
                "updated_at": row["updated_at"],
            }
        )
    return {"sessions": out}


def export_save(ctx, payload):
    from ..domain import facts as FA
    from . import transfer

    payload = validate(specs.EXPORT_SAVE, payload)
    if (payload["session_id"] is None) == (payload["slot"] is None):
        raise AppError(INVALID_INPUT, "session_id 与 slot 必须且只能给一个", [detail("$", "说明要导出哪个会话或哪个存档", None, INVALID_INPUT)])
    conn = ctx.db()
    if payload["session_id"] is not None:
        session = repo.load_session(conn, payload["session_id"])
        state = FA.full_state(session["state"])
        content = session["content"]
        archive = repo.archive_items(conn, session["session_id"])
        source = {"kind": "session", "session_id": session["session_id"], "current_slot": session["current_slot"]}
    else:
        name = normalize_slot_name(payload["slot"], "$.slot")
        slot = repo.get_slot(conn, name, with_blobs=True)
        if slot is None:
            names = [s["name"] for s in repo.list_slots(conn)]
            raise AppError(NOT_FOUND, "没有名为「%s」的存档" % name, [detail("$.slot", "存档不存在", "现有存档：%s" % ("、".join(names[:20]) or "（无）"), NOT_FOUND)], available=names[:20])
        state = slot["state"]
        state["facts"] = repo.slot_facts(conn, name)
        content = slot["content"]
        archive = repo.slot_archive(conn, name)
        source = {"kind": "slot", "name": name, "version": slot["version"]}
    doc = transfer.build(state, content, archive, source, now_iso())
    target = transfer.export_target(ctx, payload["path"], "%s-第%d回合" % (state["world_title"], state["turn"]), payload["overwrite"])
    size = transfer.write_file(target, doc)
    return {
        "path": target,
        "bytes": size,
        "checksum": doc["checksum"],
        "format": doc["format"],
        "schema_version": doc["schema_version"],
        "turn": state["turn"],
        "receipt": "已导出到 %s" % target,
    }


def import_save(ctx, payload):
    from . import transfer

    payload = validate(specs.IMPORT_SAVE, payload)
    if (payload["path"] is None) == (payload["data"] is None):
        raise AppError(INVALID_INPUT, "path 与 data 必须且只能给一个", [detail("$", "给出导出文件的路径，或粘贴的导出内容", None, INVALID_INPUT)])
    slot_name = normalize_slot_name(payload["slot"], "$.slot") if payload["slot"] is not None else None
    doc, raw = transfer.read_source(payload)
    state, content, archive, upgraded = transfer.check(doc)

    def handler(conn, now):
        from ..domain import state as SS

        backup = transfer.backup_import(ctx, doc, raw) if upgraded else None
        state["session_id"] = new_session_id(conn)
        state["undo_floor"] = state["turn"]
        repo.insert_session(conn, state, content, "import", now)
        repo.restore_archive(conn, state["session_id"], archive, now)
        repo.insert_turn_log(conn, state["session_id"], state["turn"], state["revision"], "import", None, None, {"source": doc["source"], "exported_at": doc["exported_at"], "upgraded": upgraded}, None, None, now)
        slot = None
        save = {"current_slot": None, "turns_since_save": 0}
        if slot_name is not None:
            existing = repo.get_slot(conn, slot_name)
            if existing is not None and not payload["overwrite"]:
                raise AppError(
                    SLOT_CONFLICT,
                    "「%s」已存在" % slot_name,
                    [detail("$.slot", "存档名已被占用", "问玩家是否覆盖；确认后带 overwrite: true 重交", SLOT_CONFLICT)],
                    reason="exists",
                )
            version = (existing["version"] + 1) if existing else 1
            label = SS.clock_label(state, content["world"])
            repo.put_slot(conn, slot_name, state["session_id"], label, state["memory"]["open_action"], version, now)
            repo.set_save_info(conn, state["session_id"], slot_name, version, now)
            slot = {"name": slot_name, "version": version}
            save = {"current_slot": slot_name, "turns_since_save": 0}
        return {
            "session_id": state["session_id"],
            "revision": state["revision"],
            "turn": state["turn"],
            "upgraded_from": doc["schema_version"] if upgraded else None,
            "backup": backup,
            "slot": slot,
            "receipt": "已导入「%s」·第 %d 回合" % (state["world_title"], state["turn"]),
            "resume": _resume(state),
            "context": CX.full(state, content, save),
        }

    return create_write(ctx, "import-save", payload, handler)


def list_worlds(ctx, payload):
    payload = validate(specs.LIST_WORLDS, payload)
    index = ctx.content().index()
    worlds = [w for w in index["worlds"] if include_drafts(ctx, payload) or w["status"] == "released"]
    return {
        "content_version": index["content_version"],
        "worlds": [
            {k: w[k] for k in ("id", "title", "era", "region", "summary", "modes", "status")}
            for w in worlds
        ],
    }


# ---------------------------------------------------------------------------
# meta commands: boundaries, pause, preferences (revision changes, turn does not)


def _meta_write(ctx, command, payload, apply):
    def handler(conn, session, now):
        new_state, result = apply(session["state"], session["content"])
        state = session["state"]
        if new_state is not None:
            repo.update_session(conn, new_state, now)
            repo.insert_turn_log(
                conn, new_state["session_id"], new_state["turn"], new_state["revision"], "meta", None, None,
                {"command": command, "input": {k: v for k, v in payload.items() if k not in ("session_id", "request_id", "expected_revision")}},
                None, None, now,
            )
            state = new_state
        response = {"revision": state["revision"], "turn": state["turn"], "changed": new_state is not None}
        response.update({k: v for k, v in result.items() if k != "changed"})
        response["context"] = CX.brief(state, session["content"], save_info(session))
        return response

    return session_write(ctx, command, payload, handler)


def set_boundary(ctx, payload):
    from ..domain import meta

    payload = validate(specs.SET_BOUNDARY, payload)
    if payload["action"] == "remove" and not (payload["boundary_id"] or payload["text"]):
        raise AppError(INVALID_INPUT, "撤销边界要给 boundary_id 或原话", [detail("$.boundary_id", "缺少要撤销的边界", None, INVALID_INPUT)])
    return _meta_write(
        ctx,
        "set-boundary",
        payload,
        lambda state, content: meta.set_boundary(state, content, payload["action"], payload["text"], payload["tags"], payload["boundary_id"]),
    )


def set_safety(ctx, payload):
    from ..domain import meta

    payload = validate(specs.SET_SAFETY, payload)
    return _meta_write(ctx, "set-safety", payload, lambda state, content: meta.set_safety(state, payload["paused"], payload["change_scene"]))


def set_preferences(ctx, payload):
    from ..domain import meta

    payload = validate(specs.SET_PREFERENCES, payload)
    changes = {k: v for k, v in payload.items() if k not in ("session_id", "request_id", "expected_revision")}
    return _meta_write(ctx, "set-preferences", payload, lambda state, content: meta.set_preferences(state, content, changes))


def status(ctx, payload):
    from ..projections import status as ST

    payload = validate(specs.STATUS, payload)
    session = repo.load_session(ctx.db(), payload["session_id"])
    state, content = session["state"], session["content"]
    out = {"session_id": session["session_id"], "revision": session["revision"], "turn": session["turn"], "level": payload["level"]}
    if payload["level"] == "brief":
        out["lines"] = ST.lines(state, content)
        out["text"] = "\n".join("%s %s" % ("①②③④⑤⑥"[i], line) for i, line in enumerate(out["lines"]))
    elif payload["level"] == "detail":
        out["lines"] = ST.lines(state, content)
        out["sections"] = ST.detail_sections(state, content)
    else:
        from .. import DB_SCHEMA_VERSION, SKILL_VERSION, STATE_SCHEMA_VERSION
        from ..domain import rng

        conn = ctx.db()
        sid = session["session_id"]
        storage = {
            "skill_version": SKILL_VERSION,
            "db_schema_version": DB_SCHEMA_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "rng_version": rng.RNG_VERSION,
            "content_version": content["content_version"],
            "origin": session["origin"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "save": save_info(session),
            "undo": {"floor": state["undo_floor"], "points": repo.count_rows(conn, "undo_points", sid)},
            "archive_rows": repo.count_archive(conn, sid),
            "turn_log_rows": repo.count_rows(conn, "turn_log", sid),
            "last_failed_commit_revision": repo.commit_failure(conn, sid),
            "data_dir": ctx.data_dir,
        }
        out["debug"] = ST.debug_view(state, content, save_info(session), repo.recent_turn_log(conn, sid, 5), storage)
    return out
