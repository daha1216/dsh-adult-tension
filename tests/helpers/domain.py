"""In-process helpers over the pure domain (real content, no mocks)."""

import hashlib
import json
import os

from adult_tension import schema as S
from adult_tension.content.store import ContentStore
from adult_tension.domain import opening, turn
from adult_tension.errors import AppError

from .cli import SKILL_ROOT

STORE = ContentStore(os.path.join(SKILL_ROOT, "content"))
WORLD = "harbor_night_shift"
COMMIT = S.Obj(turn.commit_fields())


def content(world_id=WORLD):
    return {"world": STORE.world(world_id), "tags": STORE.tags()["tags"], "content_version": STORE.index()["content_version"]}


def new_state(mode="pressure", seed=7, world_id=WORLD, **request):
    request = dict(request, mode=mode)
    request.setdefault("locks", {})
    request["locks"] = dict(request["locks"], world_id=world_id)
    conditions = opening.normalize_conditions(request)
    state, payload = opening.build(STORE.world(world_id), seed, conditions, "test")
    state["session_id"] = "s_test"
    return state, payload


def commit(mode="continue", ops=(), **extra):
    raw = {
        "action_mode": mode,
        "player_input": extra.pop("player_input", "……"),
        "operations": list(ops),
        "content_tags": extra.pop("tags", []),
        "summary": extra.pop("summary", "测试回合"),
        "open_action": extra.pop("open_action", "场面停住"),
    }
    raw.update(extra)
    normalized, errors = S.validate(COMMIT, raw)
    if errors:
        raise AssertionError("test commit does not match the schema: %s" % errors)
    return normalized


def apply(state, c, world_id=WORLD):
    return turn.commit_turn(state, content(world_id), c)


def rejected(state, c, world_id=WORLD):
    """Return the AppError of a commit that must be rejected; assert state untouched."""
    before = json.dumps(state, sort_keys=True, ensure_ascii=False)
    try:
        turn.commit_turn(state, content(world_id), c)
    except AppError as err:
        assert json.dumps(state, sort_keys=True, ensure_ascii=False) == before, "input state mutated"
        return err
    raise AssertionError("commit was accepted but should be rejected")


def npcs(state):
    return [c for c in state["scene"]["present"] if c != state["player_id"]]


def state_digest(state):
    """Digest of the game state without per-session identity fields."""
    clean = {k: v for k, v in state.items() if k not in ("session_id", "undo_floor")}
    return hashlib.sha256(json.dumps(clean, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
