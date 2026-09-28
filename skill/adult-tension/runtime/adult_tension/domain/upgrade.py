"""Forward upgrades of a stored session state (STATE_SCHEMA_VERSION).

A state written by an older Skill is upgraded in memory when it is read; the
next write stores the new shape. Each step fills what the older version did
not record, derived from what it did record, so an upgraded game plays on
exactly like a new one. Pure: storage is not touched here.
"""

from .. import STATE_SCHEMA_VERSION
from ..errors import UNSUPPORTED_VERSION, AppError, detail


def _number(item_id):
    digits = "".join(ch for ch in item_id if ch.isdigit())
    return int(digits) if digits else 0


def _to_2(state):
    # Stable random coordinates [turn, creation index] for facts and events.
    for kind, turn_key in (("facts", "turn"), ("events", "created_turn")):
        if not isinstance(state.get(kind), dict):
            continue  # a stored per-turn blob keeps facts as rows
        seen = {}
        for item in sorted(state[kind].values(), key=lambda x: _number(x["id"])):
            if "coord" not in item:
                seen[item[turn_key]] = seen.get(item[turn_key], 0) + 1
                item["coord"] = [item[turn_key], seen[item[turn_key]]]
    # Dedupe keys already used, including the "#n" repeats.
    keys = {}
    for event in state["events"].values():
        base, _sep, suffix = event["dedupe_key"].partition("#")
        used = int(suffix) if suffix.isdigit() else 1
        keys[base] = max(keys.get(base, 0), used)
    counters = state["counters"]
    counters.setdefault("event_keys", keys)
    counters.setdefault("chapter_count", len(state["memory"]["chapters"]))
    state["requests"].setdefault("prologue", False)


UPGRADES = {2: _to_2}


def upgrade(state):
    version = state.get("schema_version", 1)
    if version > STATE_SCHEMA_VERSION:
        raise AppError(
            UNSUPPORTED_VERSION,
            "这个局面来自更新版本的 Skill（状态格式 %d > %d）" % (version, STATE_SCHEMA_VERSION),
            [detail("$.state.schema_version", "状态格式 %d 比当前支持的 %d 新" % (version, STATE_SCHEMA_VERSION), "升级 Skill 后再读取；数据没有被修改", UNSUPPORTED_VERSION)],
        )
    while version < STATE_SCHEMA_VERSION:
        version += 1
        UPGRADES[version](state)
        state["schema_version"] = version
    return state
