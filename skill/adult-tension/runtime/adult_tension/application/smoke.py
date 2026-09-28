"""`smoke`: play a short game with the fake narrator in a temporary data dir.

Exercises the real write path end to end: new-game, commits, an idempotent
replay, a stale revision, a rejected commit, save, load, and more commits.
The user's data directory is never touched.
"""

import shutil
import tempfile
import time

from ..domain import invariants
from ..domain import state as SS
from ..errors import AppError
from ..persistence import repo
from . import service, specs
from .context import Context
from .fake_narrator import FakeNarrator


class _Counter:
    def __init__(self, tag):
        self.tag = tag
        self.value = 0

    def next(self, prefix):
        self.value += 1
        return "%s_%s_%04d" % (prefix, self.tag, self.value)


def _state(ctx, session_id):
    session = repo.load_session(ctx.db(), session_id)
    return session["state"], session["content"]


def play(ctx, seed, turns, mode="pressure"):
    """Play in `ctx` and return a report. Raises AssertionError on a broken invariant."""
    ids = _Counter("%s%d" % (mode, seed))
    narrator = FakeNarrator(seed)
    steps = []
    started = time.perf_counter()
    opened = service.new_game(ctx, {"request_id": ids.next("new"), "mode": mode, "seed": seed, "include_drafts": True})
    session_id = opened["session_id"]
    revision = opened["revision"]
    steps.append({"step": "new-game", "seed": opened["seed"], "signature": opened["opening"]["signature"]})
    replay_checked = stale_checked = reject_checked = False
    half = max(1, turns // 2)
    for index in range(turns):
        state, content = _state(ctx, session_id)
        commit = narrator.commit(state, content)
        request_id = ids.next("turn")
        payload = dict(commit, session_id=session_id, request_id=request_id, expected_revision=revision)
        result = service.commit_turn(ctx, payload)
        revision = result["revision"]
        steps.append({"step": "commit", "turn": result["turn"], "mode": commit["action_mode"], "applied": len(result["applied"])})
        if not replay_checked:
            again = service.commit_turn(ctx, payload)
            assert again["replayed"] is True and again["revision"] == revision, "replay changed state"
            replay_checked = True
            steps.append({"step": "replay", "replayed": True})
        if not stale_checked:
            try:
                service.commit_turn(ctx, dict(payload, request_id=ids.next("stale"), expected_revision=revision - 1))
                raise AssertionError("stale revision accepted")
            except AppError as err:
                assert err.code == "STALE_REVISION", err.code
            stale_checked = True
            steps.append({"step": "stale", "code": "STALE_REVISION"})
        if not reject_checked:
            state, content = _state(ctx, session_id)
            bad = narrator.invalid_commit(state, content, 0)
            try:
                service.commit_turn(ctx, dict(bad, session_id=session_id, request_id=ids.next("bad"), expected_revision=revision))
                raise AssertionError("invalid commit accepted")
            except AppError as err:
                after, _content = _state(ctx, session_id)
                assert SS.digest(after) == SS.digest(state), "rejected commit changed state"
                steps.append({"step": "reject", "code": err.code})
            reject_checked = True
        if index + 1 == half:
            saved = service.save_slot(ctx, {"session_id": session_id, "request_id": ids.next("save"), "expected_revision": revision, "name": "smoke-" + mode})
            steps.append({"step": "save", "receipt": saved["receipt"]})
            loaded = service.load_slot(ctx, {"request_id": ids.next("load"), "name": "smoke-" + mode})
            assert loaded["turn"] == saved["turn"], "load returned another turn"
            session_id = loaded["session_id"]
            revision = loaded["revision"]
            steps.append({"step": "load", "receipt": loaded["receipt"], "session_id": session_id})
    state, _content = _state(ctx, session_id)
    problems = invariants.check(state)
    assert not problems, problems
    return {
        "seed": opened["seed"],
        "mode": mode,
        "session_id": session_id,
        "turn": state["turn"],
        "revision": state["revision"],
        "clock": state["clock"],
        "steps": steps,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def run(ctx, payload):
    payload = service.validate(specs.SMOKE, payload)
    temp = tempfile.mkdtemp(prefix="at-smoke-")
    sub = Context(ctx.skill_root, temp, ctx.environ, {}, False)
    try:
        reports = [play(sub, payload["seed"], payload["turns"], mode) for mode in ("daily", "pressure")]
    except AssertionError as exc:
        raise AppError("INTERNAL_ERROR", "冒烟测试失败：%s" % exc, [])
    finally:
        sub.close()
        shutil.rmtree(temp, ignore_errors=True)
    return {"ok": True, "data_dir": "临时目录（已删除）", "runs": reports}
