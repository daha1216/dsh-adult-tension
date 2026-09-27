"""SQL for sessions, turn log, idempotency, slots, history and archive.

Every function takes an open connection; transactions are owned by the
application's write path. Snapshots are compact JSON compressed with zlib.
"""

import json
import zlib

from ..errors import NOT_FOUND, AppError, detail

IDEMPOTENCY_KEEP = 1000
HISTORY_KEEP = 50


def pack(obj):
    return zlib.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 6)


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
    info["state"] = unpack(row[len(SESSION_COLUMNS)])
    if with_content:
        info["content"] = unpack(row[len(SESSION_COLUMNS) + 1])
    return info


def insert_session(conn, state, content, origin, now, current_slot=None, slot_version=None):
    conn.execute(
        "INSERT INTO sessions(session_id, revision, turn, world_id, world_title, mode, origin, state, content, "
        "current_slot, slot_version, turns_since_save, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            state["session_id"],
            state["revision"],
            state["turn"],
            state["world_id"],
            state["world_title"],
            state["mode"],
            origin,
            pack(state),
            pack(content),
            current_slot,
            slot_version,
            0,
            now,
            now,
        ),
    )


def update_session(conn, state, now, turns_since_save=None):
    if turns_since_save is None:
        conn.execute(
            "UPDATE sessions SET revision=?, turn=?, state=?, updated_at=? WHERE session_id=?",
            (state["revision"], state["turn"], pack(state), now, state["session_id"]),
        )
    else:
        conn.execute(
            "UPDATE sessions SET revision=?, turn=?, state=?, updated_at=?, turns_since_save=? WHERE session_id=?",
            (state["revision"], state["turn"], pack(state), now, turns_since_save, state["session_id"]),
        )


def set_save_info(conn, session_id, slot, version, now):
    conn.execute(
        "UPDATE sessions SET current_slot=?, slot_version=?, turns_since_save=0, updated_at=? WHERE session_id=?",
        (slot, version, now, session_id),
    )


def session_exists(conn, session_id):
    return conn.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone() is not None


def list_sessions(conn, limit=10):
    rows = conn.execute(
        "SELECT session_id, world_title, mode, turn, revision, current_slot, turns_since_save, origin, updated_at "
        "FROM sessions ORDER BY updated_at DESC, rowid DESC LIMIT ?",
        (limit,),
    ).fetchall()
    keys = ("session_id", "world_title", "mode", "turn", "revision", "current_slot", "turns_since_save", "origin", "updated_at")
    return [dict(zip(keys, row)) for row in rows]


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


def count_rows(conn, table, session_id):
    return conn.execute("SELECT COUNT(*) FROM %s WHERE session_id=?" % table, (session_id,)).fetchone()[0]


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
    conn.execute(
        "DELETE FROM idempotency WHERE scope=? AND rowid NOT IN "
        "(SELECT rowid FROM idempotency WHERE scope=? ORDER BY rowid DESC LIMIT ?)",
        (scope, scope, IDEMPOTENCY_KEEP),
    )


def idem_count(conn, scope):
    return conn.execute("SELECT COUNT(*) FROM idempotency WHERE scope=?", (scope,)).fetchone()[0]


# -- slots ------------------------------------------------------------------------

SLOT_COLUMNS = ("name", "session_id", "revision", "turn", "world_id", "world_title", "clock_label", "open_action", "version", "saved_at")


def get_slot(conn, name, with_blobs=False):
    columns = ", ".join(SLOT_COLUMNS) + (", state, content, archive" if with_blobs else "")
    row = conn.execute("SELECT %s FROM slots WHERE name=?" % columns, (name,)).fetchone()
    if row is None:
        return None
    info = dict(zip(SLOT_COLUMNS, row[: len(SLOT_COLUMNS)]))
    if with_blobs:
        info["state"] = unpack(row[len(SLOT_COLUMNS)])
        info["content"] = unpack(row[len(SLOT_COLUMNS) + 1])
        info["archive"] = unpack(row[len(SLOT_COLUMNS) + 2])
    return info


def put_slot(conn, name, state, content, archive, clock_label, open_action, version, now):
    conn.execute("DELETE FROM slots WHERE name=?", (name,))
    conn.execute(
        "INSERT INTO slots(name, session_id, revision, turn, world_id, world_title, clock_label, open_action, version, state, content, archive, saved_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            name,
            state["session_id"],
            state["revision"],
            state["turn"],
            state["world_id"],
            state["world_title"],
            clock_label,
            open_action,
            version,
            pack(state),
            pack(content),
            pack(archive),
            now,
        ),
    )


def list_slots(conn):
    rows = conn.execute("SELECT %s FROM slots ORDER BY saved_at DESC, name" % ", ".join(SLOT_COLUMNS)).fetchall()
    return [dict(zip(SLOT_COLUMNS, row)) for row in rows]


def delete_slot(conn, name):
    conn.execute("DELETE FROM slots WHERE name=?", (name,))


# -- archive -----------------------------------------------------------------------


def archive_items(conn, session_id):
    rows = conn.execute("SELECT kind, turn, payload FROM archive WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    return [{"kind": r[0], "turn": r[1], "payload": json.loads(r[2])} for r in rows]


def add_archive(conn, session_id, kind, turn, payload, now):
    conn.execute(
        "INSERT INTO archive(session_id, kind, turn, payload, created_at) VALUES(?,?,?,?,?)",
        (session_id, kind, turn, json.dumps(payload, ensure_ascii=False, separators=(",", ":")), now),
    )


def restore_archive(conn, session_id, items, now):
    for item in items:
        add_archive(conn, session_id, item["kind"], item["turn"], item["payload"], now)


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
