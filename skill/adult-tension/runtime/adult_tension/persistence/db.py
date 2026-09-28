"""SQLite storage: connection, schema migrations, backups.

One database file per data directory. All state lives here (D3). Migrations
are forward-only; before migrating an existing database it is copied to
backups/, and a failed migration restores that copy.
"""

import json
import os
import sqlite3
import time

from .. import DB_SCHEMA_VERSION, MIN_SQLITE
from ..errors import (
    MIGRATION_FAILED,
    RUNTIME_UNSUPPORTED,
    STORAGE_BUSY,
    UNSUPPORTED_VERSION,
    AppError,
    detail,
)

BUSY_TIMEOUT_MS = 2000


def sqlite_version_ok():
    return tuple(sqlite3.sqlite_version_info) >= MIN_SQLITE


def connect(path):
    if not sqlite_version_ok():
        raise AppError(
            RUNTIME_UNSUPPORTED,
            "SQLite 版本过低：需要 %s 或更高，当前 %s" % (".".join(map(str, MIN_SQLITE)), sqlite3.sqlite_version),
            [detail("$.sqlite", "SQLite %s" % sqlite3.sqlite_version, "换用自带较新 SQLite 的 Python 3.10+")],
        )
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000.0, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=%d" % BUSY_TIMEOUT_MS)
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def begin_write(conn):
    """Start a write transaction or report STORAGE_BUSY."""
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc) or "busy" in str(exc):
            raise AppError(
                STORAGE_BUSY,
                "数据库正被其他进程占用",
                [detail("$", str(exc), "稍后用同一个 request_id 重试")],
            )
        raise


def read_schema_version(conn):
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()
    if row is None:
        return 0
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Migrations. Each entry upgrades from version N-1 to N. Pre-release, version 1
# is the initial layout; every later change gets a new, tested migration.


def _exec_script(conn, script):
    # executescript() would COMMIT the surrounding transaction; run statements
    # one by one so that a migration stays atomic.
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)


def _migrate_to_1(conn):
    _exec_script(
        conn,
        """
        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            revision INTEGER NOT NULL,
            turn INTEGER NOT NULL,
            world_id TEXT NOT NULL,
            world_title TEXT NOT NULL,
            mode TEXT NOT NULL,
            origin TEXT NOT NULL,
            state BLOB NOT NULL,
            content BLOB NOT NULL,
            current_slot TEXT,
            slot_version INTEGER,
            turns_since_save INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE turn_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            revision INTEGER NOT NULL,
            kind TEXT NOT NULL,
            action_mode TEXT,
            player_input TEXT,
            payload TEXT NOT NULL,
            summary TEXT,
            open_action TEXT,
            undone INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX turn_log_session ON turn_log(session_id, id);
        CREATE TABLE undo_points (
            session_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            state BLOB NOT NULL,
            PRIMARY KEY (session_id, turn)
        );
        CREATE TABLE idempotency (
            scope TEXT NOT NULL,
            request_id TEXT NOT NULL,
            digest TEXT NOT NULL,
            response TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (scope, request_id)
        );
        CREATE TABLE archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            turn INTEGER,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX archive_session ON archive(session_id, id);
        CREATE TABLE slots (
            name TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            turn INTEGER NOT NULL,
            world_id TEXT NOT NULL,
            world_title TEXT NOT NULL,
            clock_label TEXT NOT NULL,
            open_action TEXT,
            version INTEGER NOT NULL,
            state BLOB NOT NULL,
            content BLOB NOT NULL,
            archive BLOB NOT NULL,
            saved_at TEXT NOT NULL
        );
        CREATE TABLE opening_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed INTEGER NOT NULL,
            signature TEXT NOT NULL,
            world_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            power_structure TEXT NOT NULL,
            identity_id TEXT NOT NULL,
            hook_kind TEXT NOT NULL,
            conditions TEXT NOT NULL,
            content_version TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def _migrate_to_2(conn):
    # v2:
    # - facts move out of the per-turn state blob into rows, so a commit's cost
    #   does not grow with the game (domain/facts.py); fact_journal keeps each
    #   turn's previous fact versions for undo and rewrite;
    # - remember the last failed commit per session (next context is full);
    # - index the turn log by turn (undo and rewrite look turns up) and the
    #   idempotency records by scope (trimming stays cheap at 1000 records).
    _exec_script(
        conn,
        """
        CREATE TABLE facts (
            session_id TEXT NOT NULL,
            n INTEGER NOT NULL,
            id TEXT NOT NULL,
            key TEXT NOT NULL,
            head TEXT NOT NULL,
            truth INTEGER NOT NULL,
            visibility TEXT NOT NULL,
            origin TEXT NOT NULL,
            turn INTEGER NOT NULL,
            spreading INTEGER NOT NULL,
            knowers TEXT NOT NULL,
            text TEXT NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (session_id, id)
        );
        CREATE INDEX facts_key ON facts(session_id, key);
        CREATE INDEX facts_spreading ON facts(session_id, spreading);
        CREATE TABLE fact_journal (
            session_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            id TEXT NOT NULL,
            before TEXT,
            PRIMARY KEY (session_id, turn, id)
        );
        CREATE TABLE commit_failures (
            session_id TEXT PRIMARY KEY,
            revision INTEGER NOT NULL,
            failed_at TEXT NOT NULL
        );
        CREATE INDEX turn_log_turn ON turn_log(session_id, turn);
        CREATE INDEX idempotency_scope ON idempotency(scope);
        """,
    )
    from . import repo
    from ..domain.upgrade import upgrade

    for session_id, blob in conn.execute("SELECT session_id, state FROM sessions").fetchall():
        state = upgrade(repo.unpack(blob))
        repo.insert_facts(conn, session_id, sorted(state.pop("facts").values(), key=lambda f: int(f["id"][1:])))
        conn.execute("UPDATE sessions SET state=? WHERE session_id=?", (repo.pack(state), session_id))
    # Schema 1 never wrote undo points; any there would predate the journal.
    conn.execute("DELETE FROM undo_points")


def _migrate_to_3(conn):
    # v3: a slot is kept like a session: its facts and archive are rows, so
    # saving and loading copy rows inside SQLite instead of decoding and
    # re-encoding everything (their cost no longer grows with the game).
    # Sessions get a write sequence for "most recently played" (timestamps
    # have one-second resolution).
    _exec_script(
        conn,
        """
        ALTER TABLE sessions ADD COLUMN activity INTEGER NOT NULL DEFAULT 0;
        CREATE INDEX sessions_activity ON sessions(activity);
        CREATE TABLE slot_facts (
            slot TEXT NOT NULL,
            n INTEGER NOT NULL,
            id TEXT NOT NULL,
            key TEXT NOT NULL,
            head TEXT NOT NULL,
            truth INTEGER NOT NULL,
            visibility TEXT NOT NULL,
            origin TEXT NOT NULL,
            turn INTEGER NOT NULL,
            spreading INTEGER NOT NULL,
            knowers TEXT NOT NULL,
            text TEXT NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (slot, id)
        );
        CREATE TABLE slot_archive (
            slot TEXT NOT NULL,
            seq INTEGER NOT NULL,
            kind TEXT NOT NULL,
            turn INTEGER,
            payload TEXT NOT NULL,
            PRIMARY KEY (slot, seq)
        );
        """,
    )
    from . import repo
    from ..domain.upgrade import upgrade

    for name, blob, archive in conn.execute("SELECT name, state, archive FROM slots").fetchall():
        state = upgrade(repo.unpack(blob))
        facts = state.pop("facts", None) or {}
        repo.insert_slot_facts(conn, name, sorted(facts.values(), key=lambda f: int(f["id"][1:])))
        for seq, item in enumerate(repo.unpack(archive)):
            conn.execute(
                "INSERT INTO slot_archive(slot, seq, kind, turn, payload) VALUES(?,?,?,?,?)",
                (name, seq, item["kind"], item["turn"], json.dumps(item["payload"], ensure_ascii=False, separators=(",", ":"))),
            )
        conn.execute("UPDATE slots SET state=?, archive=? WHERE name=?", (repo.pack(state), repo.pack([]), name))
    ordered = conn.execute("SELECT session_id FROM sessions ORDER BY updated_at, rowid").fetchall()
    for position, (session_id,) in enumerate(ordered, 1):
        conn.execute("UPDATE sessions SET activity=? WHERE session_id=?", (position, session_id))


MIGRATIONS = {1: _migrate_to_1, 2: _migrate_to_2, 3: _migrate_to_3}


def _now_stamp():
    return time.strftime("%Y%m%dT%H%M%S", time.localtime())


def backup(conn, backups_dir, label):
    """Copy the live database to backups/ using SQLite's online backup API."""
    os.makedirs(backups_dir, exist_ok=True)
    target = os.path.join(backups_dir, "adult_tension-%s-%s.db" % (label, _now_stamp()))
    suffix = 1
    base = target
    while os.path.exists(target):
        suffix += 1
        target = base[:-3] + "-%d.db" % suffix
    dest = sqlite3.connect(target)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return target


def restore(conn, backup_file):
    src = sqlite3.connect(backup_file)
    try:
        src.backup(conn)
    finally:
        src.close()


def _fault(name):
    return os.environ.get("ADULT_TENSION_FAULT") == name


def ensure_schema(conn, backups_dir):
    """Bring the database to DB_SCHEMA_VERSION. Returns a report dict."""
    current = read_schema_version(conn)
    report = {"from": current, "to": DB_SCHEMA_VERSION, "backup": None, "migrated": False}
    if current > DB_SCHEMA_VERSION:
        raise AppError(
            UNSUPPORTED_VERSION,
            "数据库来自更新版本的 Skill（schema %d，本版本支持 %d）" % (current, DB_SCHEMA_VERSION),
            [detail("$.db.schema_version", "schema %d > %d" % (current, DB_SCHEMA_VERSION), "升级 Skill 到更新的版本；数据库未被修改")],
            found=current,
            supported=DB_SCHEMA_VERSION,
        )
    if current == DB_SCHEMA_VERSION:
        return report
    backup_file = None
    if current == 0:
        conn.execute("PRAGMA journal_mode=WAL")
    if current > 0:
        backup_file = backup(conn, backups_dir, "schema%d" % current)
        report["backup"] = backup_file
    begin_write(conn)
    try:
        # Re-read inside the write lock: another process may have migrated.
        current = read_schema_version(conn)
        for target in range(current + 1, DB_SCHEMA_VERSION + 1):
            MIGRATIONS[target](conn)
            if _fault("migration_fail"):
                raise RuntimeError("injected migration failure")
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)", (str(target),))
        conn.execute("COMMIT")
    except AppError:
        conn.execute("ROLLBACK")
        raise
    except Exception as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        restored = False
        if backup_file is not None:
            restore(conn, backup_file)
            restored = True
        raise AppError(
            MIGRATION_FAILED,
            "数据库从 schema %d 迁移到 %d 失败，已恢复迁移前的状态" % (report["from"], DB_SCHEMA_VERSION),
            [detail("$.db", "%s: %s" % (type(exc).__name__, exc), "不会加载任何会话；换回可用版本的 Skill 或把错误报告给维护者")],
            backup=backup_file,
            restored=restored,
        )
    report["migrated"] = True
    return report
