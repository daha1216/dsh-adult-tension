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

import collections
import hashlib
import os
import re
import unicodedata
from datetime import datetime

from .. import paths
from .. import schema as S
from ..errors import (
    CONTENT_ERROR,
    IDEMPOTENCY_CONFLICT,
    INVALID_INPUT,
    INVARIANT_VIOLATION,
    NO_MATCH,
    NOT_FOUND,
    SAFETY_BLOCK,
    SLOT_CONFLICT,
    STALE_REVISION,
    STORAGE_BUSY,
    AppError,
    detail,
)
from ..jsonio import canonical, copy
from ..persistence import db, repo
from . import specs


class _LazyContext:
    def __init__(self):
        self._mod = None

    def __getattr__(self, attr):
        if self._mod is None:
            from ..projections import context as mod

            self._mod = mod
        return getattr(self._mod, attr)


CX = _LazyContext()

CREATE_SCOPE = "create"
RESERVED_SLOT_NAMES = paths.RESERVED_NAMES


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_request_id():
    return "r_" + os.urandom(6).hex()


def new_session_id(conn):
    while True:
        sid = "s_" + os.urandom(4).hex()
        if not repo.session_exists(conn, sid):
            return sid


FIRST_GAME_TIP = "第一次来？随时说“怎么玩”带你上手；想自己定故事，说“自定义世界”。"


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


def session_write(ctx, command, payload, handler, with_content=True):
    """Run a session-scoped write. handler(conn, session, now) -> response dict."""
    conn = ctx.db()
    digest = digest_of(command, payload)
    db.begin_write(conn)
    try:
        replay = _replay(conn, payload["session_id"], payload["request_id"], digest)
        if replay is not None:
            conn.execute("COMMIT")
            return replay
        session = repo.load_session(conn, payload["session_id"], with_content=with_content)
        if session["revision"] != payload["expected_revision"]:
            if not with_content:
                session = repo.load_session(conn, payload["session_id"], with_content=True)
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
    """--include-drafts, or the development switch (Context.drafts_switch)."""
    return bool(payload.get("include_drafts")) or ctx.drafts_switch()


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
    else:
        excluded_tags = set(conditions["excludes"]["content_tags"])
        mode = conditions["mode"]
        allowed = [
            w
            for w in allowed
            if not (excluded_tags & set(w.get("content_tags") or ()))
            and (mode == "random" or not w.get("modes") or mode in w["modes"])
        ]
    excluded = set(conditions["excludes"]["world_ids"])
    return sorted(w["id"] for w in allowed if w["id"] not in excluded)


def _plan_across(ctx, world_ids, seed, conditions, validate_chosen=True):
    from ..domain import opening, rng

    order = rng.shuffled(seed, "opening.world", list(world_ids))
    if len(order) == 1 and validate_chosen:
        pack = ctx.content().world(order[0])
        try:
            return pack, opening.plan(pack, seed, conditions)
        except AppError as err:
            if err.code != NO_MATCH:
                raise
            reasons = ["%s：%s" % (pack["title"], d["reason"]) for d in err.details]
            raise opening.no_match(reasons or ["没有可用的世界"], conditions["locks"].get("world_id"), conditions)
    want_mixed = conditions["npc_gender_preference"] == "mixed" and not conditions["locks"].get("combo_id")
    fallback = None
    reasons = []
    for world_id in order:
        raw = ctx.content().world_raw(world_id)
        try:
            planned = opening.plan(raw, seed, conditions)
        except AppError as err:
            if err.code != NO_MATCH:
                raise
            title = raw.get("title", world_id) if isinstance(raw, dict) else world_id
            reasons.extend("%s：%s" % (title, d["reason"]) for d in err.details)
            continue
        except Exception:
            ctx.content().world(world_id)
            raise
        if want_mixed and not opening.combo_can_mix(planned[1], pack=raw):
            if fallback is None:
                fallback = (world_id, raw, planned)
            continue
        pack = ctx.content().world(world_id) if validate_chosen else raw
        return pack, planned
    if fallback is not None:
        world_id, raw, planned = fallback
        pack = ctx.content().world(world_id) if validate_chosen else raw
        return pack, planned
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


QUERY_NOISE = re.compile(r"[\s，。、·:：;；!！?？\"'“”‘’()（）《》【】\[\]<>—\-_/|｜]+")
QUERY_CANDIDATES = 5
LIST_QUERY_LIMIT = 20
FIRST_SENTENCE = re.compile(r"[^。！？!?]*[。！？!?]+[”’」』）)]*")


def one_line(summary):
    """A world's one-line introduction: the first sentence of its summary
    (a summary runs to several sentences; whole ones for every world would
    not fit a reply)."""
    match = FIRST_SENTENCE.match(summary)
    return match.group(0) if match else summary


def _norm_query(text):
    return QUERY_NOISE.sub("", text or "").lower()


def world_query_matches(entries, query):
    """(score, entry) for the worlds a player's name or keyword points at,
    best first. 1000: the title or ID itself; 500+: the title contains the
    query or the query the title; below: shared two-character pieces, title
    weighted over place and era over the one-line summary, kept only when at
    least half of the query's pieces are found."""
    raw = query.strip().lower()
    q = _norm_query(query)
    if q.endswith("世界") and len(q) > 2:
        q = q[:-2]
    if not q:
        return []
    grams = {q[i : i + 2] for i in range(len(q) - 1)} or {q}
    scored = []
    for entry in entries:
        title = _norm_query(entry["title"])
        if q == title or raw == entry["id"]:
            score = 1000
        elif q in title or (len(title) >= 2 and title in q) or (raw.isascii() and raw in entry["id"]):
            score = 500 + len(q)
        else:
            fields = ((title, 3), (_norm_query(entry["region"]) + _norm_query(entry["era"]), 2), (_norm_query(entry["summary"]), 1))
            found = [g for g in grams if any(g in text for text, _w in fields)]
            if len(found) * 2 < len(grams):
                continue
            score = sum(weight for g in grams for text, weight in fields if g in text)
        scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return scored


def _match_world_query(ctx, query, drafts):
    """One world: open it. Several: NO_MATCH with candidates for the player
    to choose from. None: NOT_FOUND."""
    entries = [w for w in ctx.content().index()["worlds"] if drafts or w["status"] == "released"]
    scored = world_query_matches(entries, query)
    if not scored:
        raise AppError(
            NOT_FOUND,
            "没有匹配“%s”的世界" % query,
            [detail("$.world_query", "没有匹配“%s”的世界" % query, "换个关键词，或用 list-worlds 查看全部；都没有就提议最接近的世界或自定义世界，由玩家选", NOT_FOUND)],
        )
    exact = [item for item in scored if item[0] == 1000]
    if len(exact) == 1:
        return exact[0][1]["id"]
    strong = [item for item in scored if item[0] >= 500]
    if strong:
        scored = strong
    best = scored[0]
    if len(scored) == 1 or (not strong and best[0] >= 2 * scored[1][0]):
        return best[1]["id"]
    shown = scored[:QUERY_CANDIDATES]
    candidates = [{"world_id": e["id"], "title": e["title"], "summary": one_line(e["summary"])} for _s, e in shown]
    raise AppError(
        NO_MATCH,
        "“%s”匹配到 %d 个世界" % (query, len(scored)),
        [detail("$.world_query", "匹配到的世界：%s" % "、".join(c["title"] for c in candidates), "把候选列给玩家选，选定后用 locks.world_id 开局；不替玩家选", NO_MATCH)],
        candidates=candidates,
    )


def _unknown_excluded_tags(ctx, tags, path="$.excludes.content_tags"):
    """An unknown tag would exclude nothing, so the player's "不要 X" would silently fail."""
    labels = {t["id"]: t["label"] for t in ctx.content().tags()["tags"] if t["id"] != "custom"}
    hint = "可用：" + "、".join("%s（%s）" % (tid, label) for tid, label in labels.items())
    return [
        detail("%s[%d]" % (path, i), "未知内容标签：%s" % tag, hint, INVALID_INPUT)
        for i, tag in enumerate(tags)
        if tag not in labels
    ]


def new_game(ctx, payload):
    from ..domain import opening

    payload = validate(specs.NEW_GAME, payload)
    paths.prune_inputs(ctx.data_dir)
    problems = []
    if payload["replay"] and payload["seed"] is None:
        problems.append(detail("$.seed", "“重开 N 号”必须给出种子编号", None, INVALID_INPUT))
    if payload["mode"] is None and not payload["replay"]:
        problems.append(detail("$.mode", "缺少模式", "先询问玩家选“1 日常 / 2 压力”；仅当玩家明确说“随便”时才传 random", INVALID_INPUT))
    custom = None
    has_my_world = payload["my_world"] is not None
    has_custom_world = payload["custom_world"] is not None
    if has_my_world and has_custom_world:
        problems.append(detail("$.my_world", "my_world 不和 custom_world 同用", "开保存过的世界只给 my_world", INVALID_INPUT))
    if has_my_world or has_custom_world:
        if payload["replay"]:
            if has_my_world and not has_custom_world:
                problems.append(detail("$.replay", "保存的自定义世界没有开局记录，不能“重开 N 号”", "带同一个 my_world 与 seed 重新开局即可复现", INVALID_INPUT))
            else:
                problems.append(detail("$.replay", "自定义世界没有开局记录，不能“重开 N 号”", "带同一个 custom_world 与 seed 重新开局即可复现", INVALID_INPUT))
        if payload["locks"].get("world_id") or payload["excludes"].get("world_ids"):
            path = "$.locks.world_id" if payload["locks"].get("world_id") else "$.excludes.world_ids"
            label = "保存的自定义世界" if (has_my_world and not has_custom_world) else "自定义世界"
            problems.append(detail(path, "%s不和现有世界一起锁定或排除" % label, "去掉 world_id 的锁定与排除", INVALID_INPUT))
    problems.extend(_unknown_excluded_tags(ctx, payload["excludes"].get("content_tags") or []))
    if payload["world_query"] is not None:
        clash = [
            name
            for name, given in (
                ("locks.world_id", payload["locks"].get("world_id")),
                ("custom_world", has_custom_world),
                ("my_world", has_my_world),
                ("replay", payload["replay"]),
            )
            if given
        ]
        if clash:
            problems.append(detail("$.world_query", "world_query 不和 %s 同用" % "、".join(clash), "已知世界 ID 时只用 locks.world_id", INVALID_INPUT))
    if problems:
        raise AppError(INVALID_INPUT, problems[0]["reason"], problems)
    if payload["world_query"] is not None:
        # Resolved before the conditions are recorded, so "重开 N 号" replays the world itself.
        world_id = _match_world_query(ctx, payload["world_query"], include_drafts(ctx, payload))
        payload["locks"] = dict(payload["locks"], world_id=world_id)
    conditions = opening.normalize_conditions(payload)
    custom_raw = _my_world_pack(ctx, payload["my_world"]) if has_my_world else payload["custom_world"]
    if custom_raw is not None:
        custom = _custom_world(ctx, custom_raw, conditions)

    def handler(conn, now):
        seed = payload["seed"]
        restored = None
        if payload["replay"]:
            restored = repo.opening_for_seed(conn, seed)
            if restored is not None:
                conditions.clear()
                conditions.update(restored["conditions"])
            elif payload["mode"] is None:
                raise AppError(
                    NOT_FOUND,
                    "本机没有 %d 号开局的记录" % seed,
                    [detail("$.seed", "找不到这个种子的开局条件", "请玩家说明模式（日常 / 压力），再用同一种子与条件重开", NOT_FOUND)],
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
                disaster = {w["id"] for w in ctx.content().index()["worlds"] if opening.DISASTER in w["content_tags"]}
                for item in history:
                    item["disaster"] = item["world_id"] in disaster
                chosen_plan = {}

                def evaluate(candidate):
                    raw_pack, planned_cand = _plan_across(ctx, worlds, candidate, conditions, validate_chosen=False)
                    chosen_plan[candidate] = (raw_pack["id"], planned_cand)
                    return dict(planned_cand[0], disaster=opening.DISASTER in raw_pack["content_tags"])

                seed, _result = opening.choose_seed(evaluate, seed_stream(), history)
                chosen_wid, planned = chosen_plan[seed]
                pack = ctx.content().world(chosen_wid)
            else:
                pack, planned = _plan_across(ctx, worlds, seed, conditions, validate_chosen=True)
        content = _content_snapshot(ctx, pack)
        state, opening_payload = opening.instantiate(pack, seed, conditions, planned, content["content_version"])
        # Updated content can open the same seed differently; the footer, which
        # the model copies as it is, tells the player (DESIGN_DECISIONS D10).
        changed = restored is not None and restored["signature"] != planned[0]["signature"]
        if changed:
            opening_payload["footer"] += "（内容已更新，和之前的 %d 号开局不同）" % seed
        if not repo.has_sessions(conn):
            # the first game on this machine: one line pointing at the play guide
            opening_payload["tip"] = FIRST_GAME_TIP
        state["session_id"] = new_session_id(conn)
        prefs = payload["preferences"]
        for key in ("inner_view", "assistant", "offscreen_simulation", "person", "pace", "explicitness"):
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
            "conditions_restored": restored is not None,
            "replay_changed": changed,
            "opening": opening_payload,
            "context": CX.full(state, content, {"current_slot": None, "turns_since_save": 0}),
            "commit_template": CX.commit_template(state),
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
    if payload["depth"] == "full":
        # "继续上次" starts a conversation with a full context: it gets the template too.
        out["commit_template"] = CX.commit_template(state)
    if preview_time is not None:
        out["preview"] = simulation.preview(state, content["world"], preview_time)
        # its own key: the next ordinary turn still fills the commit_template
        out["skip_template"] = CX.skip_template(state, preview_time, out["preview"])
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


def choose_depth(state, results, failed_before=False):
    """DESIGN_DECISIONS defaults: full after a failed commit, after a record of
    several turns (the model wrote them from memory), on a new place, a new
    character or a new day, every 5 turns, and when a prologue is due."""
    if failed_before or len(results) > 1:
        return "full"
    result = results[0]
    if result["location_changed"] or result["new_characters"] or result["crossed_day"]:
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
    commits = [{key: item[key] for key in DOMAIN_KEYS} for item in payload["turns"]]
    late = ["$.turns[%d].replaces_turn" % i for i, c in enumerate(commits) if i and c["replaces_turn"] is not None]
    if late:
        problems = [detail(path, "只有第一项可以改写上一回合", "去掉它；还没记录的回合直接改写正文", INVALID_INPUT) for path in late]
        raise AppError(INVALID_INPUT, problems[0]["reason"], problems)

    def handler(conn, session, now):
        sid = session["session_id"]
        state = session["state"]
        failed_before = repo.take_commit_failure(conn, sid) is not None
        unsaved = session["turns_since_save"]
        results = []
        for index, commit in enumerate(commits):
            unsaved += 1
            # Undoing a later turn of a record goes back to where a record of
            # the turns before it would have left the game, requests included.
            undo_base = _record_end(state, session["content"]["world"], results) if results else None
            try:
                state, result = _apply_turn(conn, session, state, commit, unsaved, now, undo_base)
            except AppError as err:
                _at_turn(err, index)
                raise
            results.append(result)
        _engine_outcomes_last(results)
        turn.close_record(state, session["content"]["world"], results)
        repo.update_session(conn, state, now, turns_since_save=unsaved)
        if fault("kill_in_commit"):
            os._exit(137)  # test hook: the process dies inside the write transaction
        depth = choose_depth(state, results, failed_before)
        project = CX.full if depth == "full" else CX.brief
        return {
            "revision": state["revision"],
            "turn": state["turn"],
            "turns": [_turn_result(result) for result in results],
            "clock": results[-1]["clock"],
            "context": project(state, session["content"], {"current_slot": session["current_slot"], "turns_since_save": unsaved}),
        }

    return session_write(ctx, "commit-turn", payload, handler)


def _record_end(state, world, results):
    from ..domain import turn

    base = dict(state, requests=copy(state["requests"]), counters=copy(state["counters"]))
    turn.close_record(base, world, results)
    return base


def _apply_turn(conn, session, state, commit, unsaved, now, undo_base=None):
    """One turn of a record inside the commit transaction: domain commit, undo
    point, facts, session row, archive and turn log."""
    from ..domain import turn

    sid = session["session_id"]
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
    replaced = result["replaced_turn"]
    if replaced is not None:
        repo.mark_turn_undone(conn, sid, replaced)
        repo.delete_archive_turn(conn, sid, replaced)
        repo.put_undo_point(conn, sid, new_state["turn"], result["undo_base"])
    elif undo_base is not None:
        repo.put_undo_point(conn, sid, new_state["turn"], undo_base)
    else:
        repo.save_undo_point_from_session(conn, sid, new_state["turn"])
    repo.write_fact_changes(conn, sid, new_state["turn"], new_state["facts"])
    repo.trim_undo_points(conn, sid, turn.UNDO_KEEP)
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
    # The next turn of the record reads the facts as just written.
    new_state["facts"] = repo.FactSource(conn, sid)
    return new_state, result


def _turn_result(result):
    out = {
        "turn": result["turn"],
        "applied": result["applied"],
        "resolved_events": result["resolved_events"],
        "simulation": result["simulation"],
        "default_time_advance": result["default_time_advance"],
    }
    for key in ("chapter", "twist", "replaced_turn"):
        if result[key] is not None:
            out[key] = result[key]
    return out


def _engine_outcomes_last(results):
    """A turn whose outcome the engine decides (a roll, an accepted twist, an
    event coming due) is recorded before its prose is written, so it can only
    be the last turn of a record: a turn before it had its prose written
    without the outcome (DATA_CONTRACTS 6.3)."""
    problems = []
    last = len(results) - 1
    for index, result in enumerate(results[:last]):
        decided = sorted({a["op"] for a in result["applied"] if a["op"] in ("roll", "twist_accept")})
        if result["resolved_events"]:
            decided.append("到期事件")
        if decided:
            problems.append(detail(
                "$.turns[%d]" % index,
                "第 %d 项含需由引擎裁定结果的操作（%s），只能作为单次提交的最后一项" % (index + 1, "、".join(decided)),
                "请先提交至第 %d 项，根据引擎返回的结果续写正文；后续回合留到下一次提交" % (index + 1),
                INVALID_INPUT,
            ))
    if problems:
        raise AppError(INVALID_INPUT, problems[0]["reason"] if len(problems) == 1 else "记录有 %d 处问题" % len(problems), problems)


def _at_turn(err, index):
    """Point a rejected record's problems at the turn that caused them."""
    for item in err.details:
        if isinstance(item, dict) and str(item.get("path", "")).startswith("$"):
            item["path"] = "$.turns[%d]%s" % (index, item["path"][1:])
    err.message = "第 %d 项：%s" % (index + 1, err.message)


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


_BIDI_OVERRIDES = frozenset("\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


def normalize_slot_name(raw, path="$.name", label="存档名"):
    name = re.sub(r"\s+", "-", raw.strip(" \t\r\n\u200b\u2060\ufeff"))
    problems = []
    if not name or not any(unicodedata.category(ch)[0] not in ("C", "Z") for ch in name):
        problems.append(label + "不能为空")
    if len(name) > 40:
        problems.append(label + "最长 40 个字符")
    if re.search(r"[\\/:*?\"<>|]", name):
        problems.append(label + "不能含路径分隔符或 \\ / : * ? \" < > |")
    if any(ord(ch) < 32 or 127 <= ord(ch) <= 159 or ch in _BIDI_OVERRIDES for ch in name):
        problems.append(label + "不能含控制字符")
    if name and (name.strip(".") == "" or name.endswith(".")):
        problems.append(label + "不能只由点组成或以点结尾")
    stem_head = "".join(ch for ch in name.split(".")[0] if unicodedata.category(ch)[0] != "C").lower()
    if stem_head in RESERVED_SLOT_NAMES:
        problems.append(label + "是系统保留名：%s" % name)
    if problems:
        raise AppError(INVALID_INPUT, problems[0], [detail(path, p, "换一个名字（可以用中文）", INVALID_INPUT) for p in problems])
    return name


def _auto_slot_name(world_title, turn):
    suffix = "-第%d回合" % turn
    cleaned = "".join("-" if ord(ch) < 32 or ord(ch) == 127 else ch for ch in (world_title or ""))
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', "-", cleaned).strip("-.")
    if cleaned.split(".")[0].lower() in RESERVED_SLOT_NAMES:
        cleaned = cleaned.replace(".", "-")
    max_prefix = 40 - len(suffix)
    if max_prefix >= 1:
        prefix = cleaned[:max_prefix].rstrip("-.") or "存档"[:max_prefix]
        raw = prefix + suffix
    else:
        raw = ("第%d回合" % turn)[:40]
    return normalize_slot_name(raw)


def save_slot(ctx, payload):
    payload = validate(specs.SAVE_SLOT, payload)

    def handler(conn, session, now):
        state = session["state"]
        auto = False
        if payload["name"]:
            name = normalize_slot_name(payload["name"])
        elif session["current_slot"]:
            name = session["current_slot"]
        else:
            name = _auto_slot_name(state["world_title"], state["turn"])
            auto = True
        existing = repo.get_slot(conn, name)
        if existing is not None and not payload["overwrite"]:
            if name != session["current_slot"]:
                raise AppError(
                    SLOT_CONFLICT,
                    "「%s」已存在" % name,
                    [detail("$.name", "存档名已被占用", "问玩家是否覆盖；确认后带 overwrite: true 重新提交", SLOT_CONFLICT)],
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
        from ..domain import clock as CL

        label = CL.label(state["clock"], repo.session_clock_style(conn, state["session_id"]))
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

    return session_write(ctx, "save-slot", payload, handler, with_content=False)


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
    paths.prune_inputs(ctx.data_dir)
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
        repo.insert_session(
            conn,
            state,
            slot["content"],
            "load_slot",
            now,
            current_slot=name,
            slot_version=slot["version"],
            with_facts=False,
            raw_content=slot.get("raw_content"),
        )
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
            "commit_template": CX.commit_template(state),
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
            [detail("$.confirm", "玩家还没有确认", "先问“确定删除「%s」吗？”，确认后带 confirm: true 重新提交" % name, INVALID_INPUT)],
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

    return session_write(ctx, "delete-slot", payload, handler, with_content=False)


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
    paths.prune_inputs(ctx.data_dir)
    if (payload["path"] is None) == (payload["data"] is None):
        raise AppError(INVALID_INPUT, "path 与 data 必须且只能给一个", [detail("$", "给出导出文件的路径，或粘贴的导出内容", None, INVALID_INPUT)])
    slot_name = normalize_slot_name(payload["slot"], "$.slot") if payload["slot"] is not None else None
    doc, raw = transfer.read_source(payload)
    state, content, archive, upgraded = transfer.check(doc)

    def handler(conn, now):
        from ..domain import state as SS

        existing = None
        if slot_name is not None:
            existing = repo.get_slot(conn, slot_name)
            if existing is not None and not payload["overwrite"]:
                raise AppError(
                    SLOT_CONFLICT,
                    "「%s」已存在" % slot_name,
                    [detail("$.slot", "存档名已被占用", "问玩家是否覆盖；确认后带 overwrite: true 重新提交", SLOT_CONFLICT)],
                    reason="exists",
                    slot={k: existing[k] for k in ("name", "world_title", "turn", "clock_label", "saved_at")},
                )
        backup = transfer.backup_import(ctx, doc, raw) if upgraded else None
        state["session_id"] = new_session_id(conn)
        state["undo_floor"] = state["turn"]
        repo.insert_session(conn, state, content, "import", now)
        repo.restore_archive(conn, state["session_id"], archive, now)
        repo.insert_turn_log(conn, state["session_id"], state["turn"], state["revision"], "import", None, None, {"source": doc["source"], "exported_at": doc["exported_at"], "upgraded": upgraded}, None, None, now)
        slot = None
        save = {"current_slot": None, "turns_since_save": 0}
        if slot_name is not None:
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
            "commit_template": CX.commit_template(state),
        }

    return create_write(ctx, "import-save", payload, handler)


def list_worlds(ctx, payload):
    payload = validate(specs.LIST_WORLDS, payload)
    index = ctx.content().index()
    drafts = include_drafts(ctx, payload)
    problems = _unknown_excluded_tags(ctx, payload["tags"], "$.tags") + _unknown_excluded_tags(ctx, payload["exclude_tags"], "$.exclude_tags")
    if problems:
        raise AppError(INVALID_INPUT, problems[0]["reason"], problems)
    worlds = [w for w in index["worlds"] if drafts or w["status"] == "released"]
    out = {"content_version": index["content_version"], "total": len(worlds)}
    wanted, unwanted = set(payload["tags"]), set(payload["exclude_tags"])
    if wanted or unwanted:
        worlds = [w for w in worlds if wanted <= set(w["content_tags"]) and not unwanted & set(w["content_tags"])]
    # what the listed worlds carry, for browsing by tag (before the query cut)
    counts = collections.Counter(tag for w in worlds for tag in w["content_tags"])
    labels = {t["id"]: t["label"] for t in ctx.content().tags()["tags"]}
    out["tag_counts"] = [{"id": tag, "label": labels[tag], "count": n} for tag, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    if payload["query"] is not None:
        # matched against the whole entry (title, era, place, full summary)
        scored = world_query_matches(worlds, payload["query"])
        worlds = [entry for _score, entry in scored[:LIST_QUERY_LIMIT]]
        out["matched"] = len(scored)
    elif wanted or unwanted:
        out["matched"] = len(worlds)
    if "matched" in out and not out["matched"]:
        out["hint"] = "没有匹配的世界：换个关键词或标签，或不带条件列出全部；都没有就提议最接近的世界或自定义世界，由玩家选"
    keys = ("id", "title", "modes", "status") if drafts else ("id", "title", "modes")
    out["worlds"] = [dict({k: w[k] for k in keys}, summary=one_line(w["summary"])) for w in worlds]
    return out


# ---------------------------------------------------------------------------
# my worlds: custom worlds the player keeps ("保存世界", "我的世界")


def _my_world_names(conn):
    return [w["name"] for w in repo.list_my_worlds(conn)]


def _no_my_world(conn, name, path="$.name"):
    names = _my_world_names(conn)
    return AppError(
        NOT_FOUND,
        "没有名为「%s」的世界" % name,
        [detail(path, "保存的世界里没有这个名字", "我的世界：%s" % ("、".join(names[:20]) or "（无）"), NOT_FOUND)],
        available=names[:20],
    )


def _my_world_pack(ctx, raw_name):
    name = normalize_slot_name(raw_name, "$.my_world", "世界名")
    found = repo.get_my_world(ctx.db(), name, with_world=True)
    if found is None:
        raise _no_my_world(ctx.db(), name, "$.my_world")
    return found["world"]


def save_world(ctx, payload):
    """Keep the custom world of a game under a name, to open it again later."""
    payload = validate(specs.SAVE_WORLD, payload)
    name = normalize_slot_name(payload["name"], label="世界名")

    def handler(conn, now):
        session = repo.load_session(conn, payload["session_id"])
        world = session["content"]["world"]
        if not world.get("custom"):
            raise AppError(
                INVALID_INPUT,
                "只有自定义世界能保存",
                [detail("$.session_id", "这一局用的是现成的世界《%s》" % world["title"], "现成的世界随时能开：开局时说出它的名字", INVALID_INPUT)],
            )
        existing = repo.get_my_world(conn, name)
        if existing is not None and not payload["overwrite"]:
            raise AppError(
                SLOT_CONFLICT,
                "「%s」已存在" % name,
                [detail("$.name", "世界名已被占用（《%s》）" % existing["title"], "问玩家是否覆盖；确认后带 overwrite: true 重新提交，或换个名字", SLOT_CONFLICT)],
                reason="exists",
                world={k: existing[k] for k in ("name", "title", "saved_at")},
            )
        repo.put_my_world(conn, name, world, now)
        return {
            "world": {"name": name, "title": world["title"], "saved_at": now},
            "receipt": "已保存世界「%s」（《%s》）。以后说“我的世界”查看，说“开局 我的世界 %s”再玩。" % (name, world["title"], name),
        }

    return create_write(ctx, "save-world", payload, handler)


def my_worlds(ctx, payload):
    worlds = repo.list_my_worlds(ctx.db())
    out = {"worlds": [dict(w, summary=one_line(w["summary"])) for w in worlds]}
    if not worlds:
        out["hint"] = "还没有保存的世界：用自定义世界开一局，再说“保存世界 名字”"
    return out


def delete_world(ctx, payload):
    payload = validate(specs.DELETE_WORLD, payload)
    name = normalize_slot_name(payload["name"], label="世界名")
    if not payload["confirm"]:
        raise AppError(
            INVALID_INPUT,
            "删除世界需要玩家确认",
            [detail("$.confirm", "玩家还没有确认", "先问“确定删除世界「%s」吗？”，确认后带 confirm: true 重新提交" % name, INVALID_INPUT)],
        )

    def handler(conn, now):
        if repo.get_my_world(conn, name) is None:
            raise _no_my_world(conn, name)
        repo.delete_my_world(conn, name)
        return {"deleted": name, "receipt": "已删除世界「%s」（用它玩过的存档不受影响）" % name}

    return create_write(ctx, "delete-world", payload, handler)


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
