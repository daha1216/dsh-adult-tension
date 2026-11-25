"""Forward upgrades of a stored session state (STATE_SCHEMA_VERSION).

A state written by an older Skill is upgraded in memory when it is read; the
next write stores the new shape. Each step fills what the older version did
not record, derived from what it did record, so an upgraded game plays on
exactly like a new one. Pure: storage is not touched here.
"""

from .. import STATE_SCHEMA_VERSION
from ..errors import INVALID_INPUT, UNSUPPORTED_VERSION, AppError, detail


def _number(item_id):
    if not isinstance(item_id, str):
        return 0
    digits = "".join(ch for ch in item_id if ch.isdigit())
    return int(digits) if digits else 0


def _to_2(state):
    # Stable random coordinates [turn, creation index] for facts and events.
    for kind, turn_key in (("facts", "turn"), ("events", "created_turn")):
        bucket = state.get(kind)
        if not isinstance(bucket, dict):
            continue  # a stored per-turn blob keeps facts as rows
        seen = {}
        items = [x for x in bucket.values() if isinstance(x, dict)]
        for item in sorted(items, key=lambda x: _number(x.get("id"))):
            if "coord" not in item:
                turn = item.get(turn_key)
                if type(turn) is not int:
                    continue
                seen[turn] = seen.get(turn, 0) + 1
                item["coord"] = [turn, seen[turn]]
    # Dedupe keys already used, including the "#n" repeats.
    keys = {}
    events = state.get("events")
    if isinstance(events, dict):
        for event in events.values():
            if not isinstance(event, dict) or not isinstance(event.get("dedupe_key"), str):
                continue
            base, _sep, suffix = event["dedupe_key"].partition("#")
            used = int(suffix) if suffix.isdigit() else 1
            keys[base] = max(keys.get(base, 0), used)
    counters = state.get("counters")
    if isinstance(counters, dict):
        counters.setdefault("event_keys", keys)
        memory = state.get("memory")
        chapters = memory.get("chapters") if isinstance(memory, dict) else None
        if isinstance(chapters, list):
            counters.setdefault("chapter_count", len(chapters))
    requests = state.get("requests")
    if isinstance(requests, dict):
        requests.setdefault("prologue", False)


UPGRADES = {2: _to_2}


def upgrade(state):
    if not isinstance(state, dict):
        raise AppError(
            INVALID_INPUT,
            "局面状态格式非法",
            [detail("$.state", "局面状态应为对象", None, INVALID_INPUT)],
        )
    version = state.get("schema_version", 1)
    if type(version) is not int or version < 1:
        raise AppError(
            INVALID_INPUT,
            "局面状态版本号非法：%r" % (version,),
            [detail("$.state.schema_version", "状态版本号必须为 ≥ 1 的整数", None, INVALID_INPUT)],
        )
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
