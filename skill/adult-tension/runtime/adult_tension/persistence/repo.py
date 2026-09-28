"""SQL for sessions, facts, turn log, undo points, idempotency, slots, history and archive.

Every function takes an open connection; transactions are owned by the
application's write path. Snapshots are compact JSON compressed with zlib.
States are upgraded to the current state schema when they are read.

A session is stored as a per-turn state blob *without* its facts, plus one
row per fact (domain/facts.py explains why). A loaded session's
state["facts"] is a FactSource that reads rows on demand. Each commit writes
only the facts it changed and journals their previous versions by turn, so
undo and rewrite can put them back. Slots and exports hold complete states.
"""

import json
import zlib

from ..domain import facts as FA
from ..domain.upgrade import upgrade
from ..errors import NOT_FOUND, AppError, detail

IDEMPOTENCY_KEEP = 1000
HISTORY_KEEP = 50


def pack(obj):
    return zlib.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 6)


def hot(state):
    """The per-turn blob: the state without its facts."""
    return {k: v for k, v in state.items() if k != "facts"}


# -- facts --------------------------------------------------------------------


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def fact_row(session_id, fact):
    knowers = "," + ",".join(fact["known_by"] + fact["believed_by"]) + ","
    spreading = 1 if fact.get("spreading") and fact["visibility"] != "inner" else 0
    return (
        session_id,
        FA.order(fact),
        fact["id"],
        fact["key"],
        fact["key"].split(".", 1)[0],
        1 if fact["truth"] else 0,
        fact["visibility"],
        fact["origin"],
        fact["turn"],
        spreading,
        knowers,
        fact["text"],
        _dump(fact),
    )


FACT_COLUMNS = "n, id, key, head, truth, visibility, origin, turn, spreading, knowers, text, data"
FACT_INSERT = "INSERT OR REPLACE INTO facts(session_id, %s) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)" % FACT_COLUMNS


def insert_facts(conn, session_id, facts):
    conn.executemany(FACT_INSERT, [fact_row(session_id, f) for f in facts])


def insert_slot_facts(conn, slot, facts):
    conn.executemany(
        "INSERT INTO slot_facts(slot, %s) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)" % FACT_COLUMNS,
        [fact_row(slot, f) for f in facts],
    )


class FactSource(FA.FactsAPI):
    """One session's facts, read from the facts table on demand."""

    def __init__(self, conn, session_id):
        self.conn = conn
        self.session_id = session_id
        self.cache = {}

    def _rows(self, where, args, tail=" ORDER BY n"):
        out = []
        sql = "SELECT id, data FROM facts WHERE session_id=?" + where + tail
        for fid, data in self.conn.execute(sql, (self.session_id,) + tuple(args)):
            fact = self.cache.get(fid)
            if fact is None:
                fact = self.cache[fid] = json.loads(data)
            out.append(fact)
        return out

    def get(self, fid, default=None):
        if fid in self.cache:
            return self.cache[fid]
        found = self._rows(" AND id=?", (fid,), "")
        return found[0] if found else default

    def all(self):
        return self._rows("", ())

    def by_key(self, key):
        return self._rows(" AND key=?", (key,))

    def known_to(self, cid):
        return self._rows(" AND instr(knowers, ?) > 0", ("," + cid + ",",))

    def spreading(self):
        return self._rows(" AND spreading=1", ())

    def player_ranked(self, player, present_ids, present_names, recent_turn, limit=None, exclude=()):
        # The same order as facts.rank_key, computed by SQLite so that only
        # the returned rows are decoded.
        mention, args = [], []
        if present_ids:
            mention.append("head IN (%s)" % ",".join("?" * len(present_ids)))
            args.extend(present_ids)
        for name in present_names:
            if name:
                mention.append("instr(text, ?) > 0")
                args.append(name)
        where = " AND instr(knowers, ?) > 0"
        where_args = ["," + player + ","]
        if exclude:
            where += " AND id NOT IN (%s)" % ",".join("?" * len(exclude))
            where_args.extend(exclude)
        tail = (
            " ORDER BY (CASE WHEN %s THEN 3 ELSE 0 END) + (CASE WHEN turn >= ? THEN 2 ELSE 0 END)"
            " - (CASE WHEN origin='setup' AND head='player' THEN 1 ELSE 0 END) DESC, turn DESC, n"
        ) % (" OR ".join(mention) or "0")
        tail_args = args + [recent_turn]
        if limit:
            tail += " LIMIT ?"
            tail_args.append(limit)
        return self._rows(where, where_args + tail_args, tail)


def write_fact_changes(conn, session_id, turn, view):
    """Store a commit's new and changed facts; journal what they were."""
    changed = view.changed_facts()
    if not changed:
        return
    conn.executemany(FACT_INSERT, [fact_row(session_id, f) for f in changed])
    conn.executemany(
        "INSERT OR IGNORE INTO fact_journal(session_id, turn, id, before) VALUES(?,?,?,?)",
        [(session_id, turn, f["id"], None if view.before[f["id"]] is None else _dump(view.before[f["id"]])) for f in changed],
    )


def revert_turn_facts(conn, session_id, turn):
    """Put the facts back as they were before `turn` (undo, rewrite)."""
    rows = conn.execute("SELECT id, before FROM fact_journal WHERE session_id=? AND turn=?", (session_id, turn)).fetchall()
    for fid, before in rows:
        if before is None:
            conn.execute("DELETE FROM facts WHERE session_id=? AND id=?", (session_id, fid))
        else:
            conn.execute(FACT_INSERT, fact_row(session_id, json.loads(before)))
    conn.execute("DELETE FROM fact_journal WHERE session_id=? AND turn=?", (session_id, turn))


def count_facts(conn, session_id):
    return conn.execute("SELECT COUNT(*) FROM facts WHERE session_id=?", (session_id,)).fetchone()[0]


def unpack(blob):
    return json.loads(zlib.decompress(blob).decode("utf-8"))


# -- sessions -----------------------------------------------------------------

SESSION_COLUMNS = (
    "session_id",
    "revision",
    "turn",
    "world_id",
    "world_title",
    "mode",
    "origin",
    "current_slot",
    "slot_version",
    "turns_since_save",
    "created_at",
    "updated_at",
)


def load_session(conn, session_id, with_content=True):
    columns = ", ".join(SESSION_COLUMNS) + ", state" + (", content" if with_content else "")
    row = conn.execute("SELECT %s FROM sessions WHERE session_id=?" % columns, (session_id,)).fetchone()
    if row is None:
        raise AppError(
            NOT_FOUND,
            "会话不存在：%s" % session_id,
            [detail("$.session_id", "会话不存在：%s" % session_id, "用 list-sessions 列出实际存在的会话", NOT_FOUND)],
        )
    info = dict(zip(SESSION_COLUMNS, row[: len(SESSION_COLUMNS)]))
    info["state"] = upgrade(unpack(row[len(SESSION_COLUMNS)]))
    info["state"]["facts"] = FactSource(conn, session_id)
    if with_content:
        info["content"] = unpack(row[len(SESSION_COLUMNS) + 1])
    return info


def insert_session(conn, state, content, origin, now, current_slot=None, slot_version=None, with_facts=True):
    """A new session from a complete state (opening, import); a load copies
    the slot's fact rows itself (with_facts=False)."""
    if with_facts:
        insert_facts(conn, state["session_id"], FA.of(state).all())
    conn.execute(
        "INSERT INTO sessions(session_id, revision, turn, world_id, world_title, mode, origin, state, content, "
        "current_slot, slot_version, turns_since_save, created_at, updated_at, activity) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,(SELECT COALESCE(MAX(activity), 0) + 1 FROM sessions))",
        (
            state["session_id"],
            state["revision"],
            state["turn"],
            state["world_id"],
            state["world_title"],
            state["mode"],
            origin,
            pack(hot(state)),
            pack(content),
            current_slot,
            slot_version,
            0,
            now,
            now,
        ),
    )


def update_session(conn, state, now, turns_since_save=None):
    """Write the per-turn blob; fact rows are written by write_fact_changes()."""
    touch = "activity=(SELECT COALESCE(MAX(activity), 0) + 1 FROM sessions)"
    if turns_since_save is None:
        conn.execute(
            "UPDATE sessions SET revision=?, turn=?, state=?, updated_at=?, %s WHERE session_id=?" % touch,
            (state["revision"], state["turn"], pack(hot(state)), now, state["session_id"]),
        )
    else:
        conn.execute(
            "UPDATE sessions SET revision=?, turn=?, state=?, updated_at=?, turns_since_save=?, %s WHERE session_id=?" % touch,
            (state["revision"], state["turn"], pack(hot(state)), now, turns_since_save, state["session_id"]),
        )


def set_save_info(conn, session_id, slot, version, now):
    conn.execute(
        "UPDATE sessions SET current_slot=?, slot_version=?, turns_since_save=0, updated_at=? WHERE session_id=?",
        (slot, version, now, session_id),
    )


def session_exists(conn, session_id):
    return conn.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone() is not None


def list_sessions(conn, limit=10):
    """Most recently played first, with each one's per-turn state."""
    rows = conn.execute(
        "SELECT session_id, world_title, mode, turn, revision, current_slot, turns_since_save, origin, updated_at, state, content "
        "FROM sessions ORDER BY activity DESC LIMIT ?",
        (limit,),
    ).fetchall()
    keys = ("session_id", "world_title", "mode", "turn", "revision", "current_slot", "turns_since_save", "origin", "updated_at")
    out = []
    for row in rows:
        item = dict(zip(keys, row[: len(keys)]))
        item["state"] = upgrade(unpack(row[len(keys)]))
        item["clock_style"] = unpack(row[len(keys) + 1])["world"].get("clock_style", "hm")
        out.append(item)
    return out


# -- turn log -------------------------------------------------------------------


def insert_turn_log(conn, session_id, turn, revision, kind, action_mode, player_input, payload, summary, open_action, now):
    conn.execute(
        "INSERT INTO turn_log(session_id, turn, revision, kind, action_mode, player_input, payload, summary, open_action, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (session_id, turn, revision, kind, action_mode, player_input, json.dumps(payload, ensure_ascii=False, separators=(",", ":")), summary, open_action, now),
    )


def recent_turn_log(conn, session_id, limit=5):
    rows = conn.execute(
        "SELECT turn, revision, kind, action_mode, payload, summary, undone, created_at FROM turn_log "
        "WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    keys = ("turn", "revision", "kind", "action_mode", "payload", "summary", "undone", "created_at")
    out = []
    for row in rows:
        item = dict(zip(keys, row))
        item["payload"] = json.loads(item["payload"])
        out.append(item)
    return out


def mark_turn_undone(conn, session_id, turn):
    conn.execute("UPDATE turn_log SET undone=1 WHERE session_id=? AND turn=? AND kind='commit' AND undone=0", (session_id, turn))


def count_rows(conn, table, session_id):
    return conn.execute("SELECT COUNT(*) FROM %s WHERE session_id=?" % table, (session_id,)).fetchone()[0]


# -- undo points ------------------------------------------------------------------
# The state before turn N is stored under (session, N). Undo and rewrite read
# it; a load starts a new session, so its undo history starts empty.


def save_undo_point_from_session(conn, session_id, turn):
    """Store the session's current (pre-commit) state blob as the point for `turn`."""
    conn.execute(
        "INSERT OR REPLACE INTO undo_points(session_id, turn, state) SELECT session_id, ?, state FROM sessions WHERE session_id=?",
        (turn, session_id),
    )


def put_undo_point(conn, session_id, turn, state):
    conn.execute("INSERT OR REPLACE INTO undo_points(session_id, turn, state) VALUES(?,?,?)", (session_id, turn, pack(hot(state))))


def undo_point(conn, session_id, turn):
    row = conn.execute("SELECT state FROM undo_points WHERE session_id=? AND turn=?", (session_id, turn)).fetchone()
    return upgrade(unpack(row[0])) if row else None


def delete_undo_point(conn, session_id, turn):
    conn.execute("DELETE FROM undo_points WHERE session_id=? AND turn=?", (session_id, turn))


def trim_undo_points(conn, session_id, keep):
    conn.execute(
        "DELETE FROM undo_points WHERE session_id=? AND turn NOT IN "
        "(SELECT turn FROM undo_points WHERE session_id=? ORDER BY turn DESC LIMIT ?)",
        (session_id, session_id, keep),
    )
    # The fact journal of a turn is only needed while its undo point exists.
    conn.execute(
        "DELETE FROM fact_journal WHERE session_id=? AND turn < "
        "(SELECT COALESCE(MIN(turn), 1000000000) FROM undo_points WHERE session_id=?)",
        (session_id, session_id),
    )


# -- commit failures ----------------------------------------------------------------
# A failed commit leaves a marker; the next successful commit returns the full
# context (DESIGN_DECISIONS defaults: "上一次提交出错").


def mark_commit_failure(conn, session_id, now):
    row = conn.execute("SELECT revision FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if row is not None:
        conn.execute("INSERT OR REPLACE INTO commit_failures(session_id, revision, failed_at) VALUES(?,?,?)", (session_id, row[0], now))


def commit_failure(conn, session_id):
    row = conn.execute("SELECT revision FROM commit_failures WHERE session_id=?", (session_id,)).fetchone()
    return row[0] if row else None


def take_commit_failure(conn, session_id):
    row = conn.execute("SELECT revision FROM commit_failures WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM commit_failures WHERE session_id=?", (session_id,))
    return row[0]


# -- idempotency ----------------------------------------------------------------


def idem_get(conn, scope, request_id):
    row = conn.execute("SELECT digest, response FROM idempotency WHERE scope=? AND request_id=?", (scope, request_id)).fetchone()
    if row is None:
        return None
    return {"digest": row[0], "response": unpack(row[1])}


def idem_put(conn, scope, request_id, digest, response, now):
    conn.execute(
        "INSERT INTO idempotency(scope, request_id, digest, response, created_at) VALUES(?,?,?,?,?)",
        (scope, request_id, digest, pack(response), now),
    )
    # Keep the newest IDEMPOTENCY_KEEP rows of the scope. The index on scope
    # (rowids in order) finds the cut-off without reading the whole scope.
    conn.execute(
        "DELETE FROM idempotency WHERE scope=? AND rowid < "
        "(SELECT rowid FROM idempotency WHERE scope=? ORDER BY rowid DESC LIMIT 1 OFFSET ?)",
        (scope, scope, IDEMPOTENCY_KEEP - 1),
    )


def idem_count(conn, scope):
    return conn.execute("SELECT COUNT(*) FROM idempotency WHERE scope=?", (scope,)).fetchone()[0]


# -- slots ------------------------------------------------------------------------

SLOT_COLUMNS = ("name", "session_id", "revision", "turn", "world_id", "world_title", "clock_label", "open_action", "version", "saved_at")


# A slot is a complete copy of a session at one revision, kept like a session:
# the per-turn blob and content in `slots`, facts in `slot_facts`, archive in
# `slot_archive`. Saving and loading copy rows inside SQLite.


def get_slot(conn, name, with_blobs=False):
    columns = ", ".join(SLOT_COLUMNS) + (", state, content" if with_blobs else "")
    row = conn.execute("SELECT %s FROM slots WHERE name=?" % columns, (name,)).fetchone()
    if row is None:
        return None
    info = dict(zip(SLOT_COLUMNS, row[: len(SLOT_COLUMNS)]))
    if with_blobs:
        info["state"] = upgrade(unpack(row[len(SLOT_COLUMNS)]))
        info["content"] = unpack(row[len(SLOT_COLUMNS) + 1])
    return info


def put_slot(conn, name, session_id, clock_label, open_action, version, now):
    """Copy the session as it is stored now into the slot `name`."""
    _drop_slot_rows(conn, name)
    conn.execute(
        "INSERT INTO slots(name, session_id, revision, turn, world_id, world_title, clock_label, open_action, version, state, content, archive, saved_at) "
        "SELECT ?, session_id, revision, turn, world_id, world_title, ?, ?, ?, state, content, ?, ? FROM sessions WHERE session_id=?",
        (name, clock_label, open_action, version, pack([]), now, session_id),
    )
    conn.execute(
        "INSERT INTO slot_facts(slot, {0}) SELECT ?, {0} FROM facts WHERE session_id=?".format(FACT_COLUMNS),
        (name, session_id),
    )
    conn.execute(
        "INSERT INTO slot_archive(slot, seq, kind, turn, payload) SELECT ?, id, kind, turn, payload FROM archive WHERE session_id=?",
        (name, session_id),
    )


def copy_slot_rows(conn, name, session_id, now):
    """A load: the slot's facts and archive become the new session's."""
    conn.execute(
        "INSERT INTO facts(session_id, {0}) SELECT ?, {0} FROM slot_facts WHERE slot=?".format(FACT_COLUMNS),
        (session_id, name),
    )
    conn.execute(
        "INSERT INTO archive(session_id, kind, turn, payload, created_at) SELECT ?, kind, turn, payload, ? FROM slot_archive WHERE slot=? ORDER BY seq",
        (session_id, now, name),
    )


def slot_facts(conn, name):
    return {fid: json.loads(data) for fid, data in conn.execute("SELECT id, data FROM slot_facts WHERE slot=? ORDER BY n", (name,))}


def slot_archive(conn, name):
    rows = conn.execute("SELECT kind, turn, payload FROM slot_archive WHERE slot=? ORDER BY seq", (name,)).fetchall()
    return [{"kind": r[0], "turn": r[1], "payload": json.loads(r[2])} for r in rows]


def list_slots(conn):
    rows = conn.execute("SELECT %s FROM slots ORDER BY saved_at DESC, name" % ", ".join(SLOT_COLUMNS)).fetchall()
    return [dict(zip(SLOT_COLUMNS, row)) for row in rows]


def _drop_slot_rows(conn, name):
    conn.execute("DELETE FROM slots WHERE name=?", (name,))
    conn.execute("DELETE FROM slot_facts WHERE slot=?", (name,))
    conn.execute("DELETE FROM slot_archive WHERE slot=?", (name,))


def delete_slot(conn, name):
    """An explicit deletion: sessions whose current slot it was no longer have one."""
    _drop_slot_rows(conn, name)
    conn.execute("UPDATE sessions SET current_slot=NULL, slot_version=NULL WHERE current_slot=?", (name,))


# -- archive -----------------------------------------------------------------------


def archive_items(conn, session_id):
    rows = conn.execute("SELECT kind, turn, payload FROM archive WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    return [{"kind": r[0], "turn": r[1], "payload": json.loads(r[2])} for r in rows]


def add_archive(conn, session_id, kind, turn, payload, now):
    conn.execute(
        "INSERT INTO archive(session_id, kind, turn, payload, created_at) VALUES(?,?,?,?,?)",
        (session_id, kind, turn, json.dumps(payload, ensure_ascii=False, separators=(",", ":")), now),
    )


def delete_archive_turn(conn, session_id, turn):
    conn.execute("DELETE FROM archive WHERE session_id=? AND turn=?", (session_id, turn))


def restore_archive(conn, session_id, items, now):
    for item in items:
        add_archive(conn, session_id, item["kind"], item["turn"], item["payload"], now)


def count_archive(conn, session_id):
    return conn.execute("SELECT COUNT(*) FROM archive WHERE session_id=?", (session_id,)).fetchone()[0]


# -- opening history -----------------------------------------------------------------


def add_opening(conn, seed, result, conditions, content_version, now):
    conn.execute(
        "INSERT INTO opening_history(seed, signature, world_id, mode, power_structure, identity_id, hook_kind, conditions, content_version, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            seed,
            result["signature"],
            result["world_id"],
            result["mode"],
            result["power_structure"],
            result["identity_id"],
            result["hook_kind"],
            json.dumps(conditions, ensure_ascii=False, sort_keys=True),
            content_version,
            now,
        ),
    )
    conn.execute(
        "DELETE FROM opening_history WHERE id NOT IN (SELECT id FROM opening_history ORDER BY id DESC LIMIT ?)",
        (HISTORY_KEEP,),
    )


def opening_history(conn, limit=HISTORY_KEEP):
    rows = conn.execute(
        "SELECT seed, signature, world_id, mode, power_structure, identity_id, hook_kind, conditions, content_version "
        "FROM opening_history ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    keys = ("seed", "signature", "world_id", "mode", "power_structure", "identity_id", "hook_kind", "conditions", "content_version")
    out = []
    for row in rows:
        item = dict(zip(keys, row))
        item["conditions"] = json.loads(item["conditions"])
        item["combo_id"] = item["signature"].split("|")[2] if item["signature"].count("|") >= 4 else None
        out.append(item)
    return out


def conditions_for_seed(conn, seed):
    row = conn.execute("SELECT conditions FROM opening_history WHERE seed=? ORDER BY id DESC LIMIT 1", (seed,)).fetchone()
    return json.loads(row[0]) if row else None
