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
    IDEMPOTENCY_CONFLICT,
    INVALID_INPUT,
    NOT_FOUND,
    SLOT_CONFLICT,
    STALE_REVISION,
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
    if payload["custom_world"] is not None:
        problems.append(detail("$.custom_world", "自定义世界在当前版本还没有开放", "先用现有世界开局", INVALID_INPUT))
    if problems:
        raise AppError(INVALID_INPUT, problems[0]["reason"], problems)
    conditions = opening.normalize_conditions(payload)

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
    payload = validate(specs.GET_CONTEXT, payload)
    session = repo.load_session(ctx.db(), payload["session_id"])
    project = CX.full if payload["depth"] == "full" else CX.brief
    return {
        "session_id": session["session_id"],
        "revision": session["revision"],
        "turn": session["turn"],
        "context": project(session["state"], session["content"], save_info(session)),
    }


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
    "replaces_turn",
)


def choose_depth(state, result):
    if result["location_changed"] or result["new_characters"] or result["crossed_day"]:
        return "full"
    if state["turn"] % 5 == 0:
        return "full"
    return "brief"


def commit_turn(ctx, payload):
    from ..domain import turn

    payload = validate(specs.COMMIT_TURN, payload)
    commit = {key: payload[key] for key in DOMAIN_KEYS}

    def handler(conn, session, now):
        new_state, result = turn.commit_turn(session["state"], session["content"], commit)
        unsaved = session["turns_since_save"] + 1
        repo.update_session(conn, new_state, now, turns_since_save=unsaved)
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
        depth = choose_depth(new_state, result)
        project = CX.full if depth == "full" else CX.brief
        return {
            "revision": new_state["revision"],
            "turn": new_state["turn"],
            "applied": result["applied"],
            "resolved_events": result["resolved_events"],
            "simulation": result["simulation"],
            "clock": result["clock"],
            "default_time_advance": result["default_time_advance"],
            "context": project(new_state, session["content"], {"current_slot": session["current_slot"], "turns_since_save": unsaved}),
        }

    return session_write(ctx, "commit-turn", payload, handler)


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
        repo.put_slot(conn, name, state, content, repo.archive_items(conn, state["session_id"]), label, state["memory"]["open_action"], version, now)
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
        repo.insert_session(conn, state, slot["content"], "load_slot", now, current_slot=name, slot_version=slot["version"])
        repo.restore_archive(conn, state["session_id"], slot["archive"], now)
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
