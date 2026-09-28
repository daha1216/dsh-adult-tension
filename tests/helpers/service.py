"""In-process access to the application layer with a temporary data dir."""

import contextlib
import shutil
import tempfile

from adult_tension.application import service
from adult_tension.application.context import Context
from adult_tension.domain import facts as FA
from adult_tension.persistence import repo

from .cli import SKILL_ROOT, clean_env


@contextlib.contextmanager
def app(env=None):
    temp = tempfile.mkdtemp(prefix="at-app-")
    ctx = Context(SKILL_ROOT, temp, env or clean_env(), {}, False)
    try:
        yield ctx
    finally:
        ctx.close()
        shutil.rmtree(temp, ignore_errors=True)


class Ids:
    def __init__(self, prefix="req"):
        self.prefix = prefix
        self.n = 0

    def __call__(self):
        self.n += 1
        return "%s_%06d" % (self.prefix, self.n)


def open_game(ctx, ids, mode="pressure", seed=7, **extra):
    payload = dict({"request_id": ids(), "mode": mode, "seed": seed, "include_drafts": True}, **extra)
    return service.new_game(ctx, payload)


def session(ctx, session_id):
    """A stored session with its complete state (facts read into a dict)."""
    info = repo.load_session(ctx.db(), session_id)
    info["state"] = FA.full_state(info["state"])
    return info


def table_counts(ctx, session_id):
    conn = ctx.db()
    return {
        "turn_log": repo.count_rows(conn, "turn_log", session_id),
        "idempotency": repo.idem_count(conn, session_id),
    }
