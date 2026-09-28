"""Full validation of a complete session state (import, debug view).

Everything the runtime reads without a default must be present and of the
right type; unknown fields are refused; every reference must resolve; the
global invariants must hold. Returns every problem with its JSON path.
"""

from .. import STATE_SCHEMA_VERSION
from ..errors import INVALID_INPUT, detail
from . import clock as CL
from . import invariants
from . import structure as ST

# field -> type check; required keys first, optional keys second
INT, STR, BOOL, LIST, DICT = "int", "str", "bool", "list", "dict"
TYPES = {
    INT: lambda v: isinstance(v, int) and not isinstance(v, bool),
    STR: lambda v: isinstance(v, str),
    BOOL: lambda v: isinstance(v, bool),
    LIST: lambda v: isinstance(v, list),
    DICT: lambda v: isinstance(v, dict),
    "num": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "str?": lambda v: v is None or isinstance(v, str),
    "int?": lambda v: v is None or (isinstance(v, int) and not isinstance(v, bool)),
    "dict?": lambda v: v is None or isinstance(v, dict),
    "list?": lambda v: v is None or isinstance(v, list),
    "num?": lambda v: v is None or (isinstance(v, (int, float)) and not isinstance(v, bool)),
    "any": lambda v: True,
}
TYPE_NAMES = {INT: "整数", STR: "字符串", BOOL: "布尔", LIST: "数组", DICT: "对象", "num": "数字"}

TOP = (
    {
        "schema_version": INT, "session_id": "str?", "revision": INT, "turn": INT, "seed": INT, "rng_version": INT,
        "content_version": STR, "world_id": STR, "world_title": STR, "custom_world": BOOL, "mode": STR, "opening": DICT,
        "clock": DICT, "scene": DICT, "player_id": STR, "characters": DICT, "relationships": DICT, "facts": DICT,
        "events": DICT, "leverage": DICT, "pressure": "dict?", "preferences": DICT, "safety": DICT, "memory": DICT,
        "counters": DICT, "requests": DICT, "undo_floor": INT,
    },
    {},
)
CLOCK = ({"day": INT, "minute": INT}, {})
SCENE = ({"id": STR, "location_id": STR, "present": LIST, "since": DICT, "responses": LIST}, {})
RESPONSE = ({"turn": INT, "npc_id": STR, "response": STR, "note": STR}, {})
CHARACTER = (
    {"id": STR, "name": STR, "age": "any", "gender": STR, "tier": STR, "adult_context": "any", "public_role": STR, "status": DICT},
    {
        "family": "str?", "given": "str?", "call": "str?", "title": "str?", "appearance": "any", "background": "any",
        "baseline": "any", "decision": "dict?", "function": "any", "identity": "dict?", "identity_id": "str?",
        "intimacy": "dict?", "line": "any", "reputation": "any", "resources": "any", "risks": "any", "schedule": "list?",
        "situation": "dict?", "social_position": "any", "template_id": "str?", "voices": "dict?", "kin_of": "str?",
        "introduced_turn": "int?", "promoted_turn": "int?",
    },
)
STATUS = ({"location_id": "str?", "mood": "str?", "conditions": LIST}, {})
CONDITION = ({"kind": STR, "text": STR, "until": "dict?"}, {"since_turn": "int?"})
FACT = (
    {"id": STR, "key": STR, "text": STR, "truth": BOOL, "known_by": LIST, "believed_by": LIST, "visibility": STR, "origin": STR, "turn": INT, "spreading": BOOL, "coord": LIST},
    {"spread_hops": INT, "source_fact_id": "str?", "channel_id": "str?"},
)
EVENT = (
    {
        "id": STR, "kind": STR, "tier": STR, "title": STR, "text": "str?", "participants": LIST, "due": DICT, "probability": "num?",
        "dedupe_key": STR, "state": STR, "outcome": "str?", "created_turn": INT, "resolved_turn": "int?", "note": "str?", "coord": LIST,
    },
    {},
)
EDGE = ({"from": STR, "to": STR, "trust": INT, "tension": INT, "stage": STR, "history": LIST}, {})
HISTORY = ({"turn": INT, "change": STR, "reason": STR}, {"evidence": DICT})
LEVERAGE = (
    {"id": STR, "holder": STR, "subject": STR, "basis_fact_id": STR, "origin": STR, "state": STR, "created_turn": INT, "released_turn": "int?", "release_reason": "str?"},
    {},
)
PREFERENCES = (
    {"inner_view": BOOL, "assistant": BOOL, "offscreen_simulation": BOOL, "voice": DICT, "npc_gender_preference": STR, "person": STR, "pace": STR, "explicitness": STR},
    {},
)
VOICE = ({"voice": STR, "cause": STR, "since_turn": INT, "trigger": "str?"}, {"via": STR})
SAFETY = ({"paused": BOOL, "boundaries": LIST}, {})
BOUNDARY = ({"id": STR, "text": STR, "tags": LIST, "created_turn": INT}, {})
MEMORY = ({"turns": LIST, "chapters": LIST, "prologue": "str?", "open_action": "str?", "last_quotes": LIST}, {})
MEMORY_TURN = ({"turn": INT, "day": INT, "mode": STR, "summary": STR, "open_action": STR, "quotes": LIST}, {"offscreen": LIST})
CHAPTER = ({"index": INT, "from_turn": INT, "to_turn": INT, "day": INT, "summary": STR}, {})
COUNTERS = (
    {
        "next": DICT, "major_action_turn": DICT, "event_keys": DICT, "intimacy_evidence": DICT, "twists": DICT,
        "last_chapter_turn": INT, "chapter_count": INT, "chapter_requested_at": "int?", "offscreen_beat_turn": DICT,
    },
    {},
)
NEXT = ({"fact": INT, "event": INT, "leverage": INT, "scene": INT, "boundary": INT}, {})
TWISTS = ({"auto_offered": BOOL, "accepted_days": LIST, "accepted": LIST}, {})
REQUESTS = ({"chapter_summary": BOOL, "prologue": BOOL, "twist_offer": "list?", "offscreen_beat_candidates": LIST}, {})
ARCHIVE_KINDS = ("turn", "event", "chapter", "prologue")


class _Checker:
    def __init__(self):
        self.problems = []

    def bad(self, path, reason, hint=None):
        self.problems.append(detail(path, reason, hint, INVALID_INPUT))

    def shape(self, value, spec, path):
        """Check one object against (required, optional); return it if usable."""
        if not isinstance(value, dict):
            self.bad(path, "应为对象")
            return None
        required, optional = spec
        ok = True
        for key, kind in required.items():
            if key not in value:
                self.bad("%s.%s" % (path, key), "缺少字段")
                ok = False
            elif not TYPES[kind](value[key]):
                self.bad("%s.%s" % (path, key), "类型不对，应为%s" % TYPE_NAMES.get(kind.rstrip("?"), kind))
                ok = False
        for key, kind in optional.items():
            if key in value and not TYPES[kind](value[key]):
                self.bad("%s.%s" % (path, key), "类型不对，应为%s" % TYPE_NAMES.get(kind.rstrip("?"), kind))
                ok = False
        for key in value:
            if key not in required and key not in optional:
                self.bad("%s.%s" % (path, key), "未知字段")
                ok = False
        return value if ok else None

    def each(self, items, spec, path):
        out = []
        for index, item in enumerate(items):
            checked = self.shape(item, spec, "%s[%d]" % (path, index))
            if checked is not None:
                out.append(checked)
        return out

    def ids(self, values, known, path, what="角色"):
        if not isinstance(values, list):
            self.bad(path, "应为数组")
            return
        for index, cid in enumerate(values):
            if cid not in known:
                self.bad("%s[%d]" % (path, index), "%s不存在：%s" % (what, cid))

    def clock(self, value, path):
        clock = self.shape(value, CLOCK, path)
        if clock is not None and not (clock["day"] >= 1 and 0 <= clock["minute"] < ST.MINUTES_PER_DAY):
            self.bad(path, "时钟越界")


def check_state(state, world=None):
    """Every problem of a complete state (facts as a dict). `world` is the
    content snapshot's world pack, for location references."""
    c = _Checker()
    if c.shape(state, TOP, "$") is None:
        if not isinstance(state, dict) or any(key not in state for key in TOP[0]):
            return c.problems
    if not TYPES[INT](state.get("schema_version")) or state["schema_version"] != STATE_SCHEMA_VERSION:
        c.bad("$.schema_version", "状态格式应为 %d" % STATE_SCHEMA_VERSION)
    for key in ("revision", "turn", "undo_floor"):
        if TYPES[INT](state.get(key)) and state[key] < 1:
            c.bad("$." + key, "必须 ≥ 1")
    if TYPES[INT](state.get("undo_floor")) and TYPES[INT](state.get("turn")) and state["undo_floor"] > state["turn"]:
        c.bad("$.undo_floor", "不能晚于当前回合")
    if state.get("mode") not in ("daily", "pressure"):
        c.bad("$.mode", "模式只能是 daily 或 pressure")
    c.clock(state.get("clock"), "$.clock")
    locations = {loc["id"] for loc in (world or {}).get("locations", [])} if world else None

    characters = state.get("characters") if isinstance(state.get("characters"), dict) else {}
    known = set(characters)
    for cid, char in characters.items():
        path = "$.characters.%s" % cid
        char = c.shape(char, CHARACTER, path)
        if char is None:
            continue
        if char["id"] != cid:
            c.bad(path + ".id", "ID 与键不一致")
        if char["tier"] not in ST.TIERS:
            c.bad(path + ".tier", "层级非法")
        if char["gender"] not in ST.GENDERS:
            c.bad(path + ".gender", "性别非法")
        status = c.shape(char["status"], STATUS, path + ".status")
        if status is not None:
            if locations is not None and status["location_id"] is not None and status["location_id"] not in locations:
                c.bad(path + ".status.location_id", "地点不在内容快照中：%s" % status["location_id"])
            for index, cond in enumerate(c.each(status["conditions"], CONDITION, path + ".status.conditions")):
                if cond["kind"] not in ST.CONDITION_KINDS:
                    c.bad("%s.status.conditions[%d].kind" % (path, index), "状况类型非法")
                if cond["until"] is not None:
                    c.clock(cond["until"], "%s.status.conditions[%d].until" % (path, index))
        if "kin_of" in char and char["kin_of"] is not None and char["kin_of"] not in known:
            c.bad(path + ".kin_of", "角色不存在：%s" % char["kin_of"])
    if state.get("player_id") not in known:
        c.bad("$.player_id", "玩家角色不存在")

    scene = c.shape(state.get("scene"), SCENE, "$.scene")
    if scene is not None:
        c.ids(scene["present"], known, "$.scene.present")
        c.clock(scene["since"], "$.scene.since")
        if locations is not None and scene["location_id"] not in locations:
            c.bad("$.scene.location_id", "地点不在内容快照中：%s" % scene["location_id"])
        for index, response in enumerate(c.each(scene["responses"], RESPONSE, "$.scene.responses")):
            if response["response"] not in ST.RESPONSES:
                c.bad("$.scene.responses[%d].response" % index, "回应类型非法")

    facts = state.get("facts") if isinstance(state.get("facts"), dict) else {}
    for fid, fact in facts.items():
        path = "$.facts.%s" % fid
        fact = c.shape(fact, FACT, path)
        if fact is None:
            continue
        if fact["id"] != fid:
            c.bad(path + ".id", "ID 与键不一致")
        if fact["visibility"] not in ST.FACT_VISIBILITY:
            c.bad(path + ".visibility", "可见度非法")
        if fact["origin"] not in ST.FACT_ORIGINS:
            c.bad(path + ".origin", "来源非法")
        c.ids(fact["known_by"], known, path + ".known_by")
        c.ids(fact["believed_by"], known, path + ".believed_by")
        if fact.get("source_fact_id") is not None and fact["source_fact_id"] not in facts:
            c.bad(path + ".source_fact_id", "事实不存在：%s" % fact["source_fact_id"])

    events = state.get("events") if isinstance(state.get("events"), dict) else {}
    for eid, event in events.items():
        path = "$.events.%s" % eid
        event = c.shape(event, EVENT, path)
        if event is None:
            continue
        if event["id"] != eid:
            c.bad(path + ".id", "ID 与键不一致")
        if event["kind"] not in ST.EVENT_KINDS:
            c.bad(path + ".kind", "事件类型非法")
        if event["state"] not in ST.EVENT_STATES:
            c.bad(path + ".state", "事件状态非法")
        c.ids(event["participants"], known, path + ".participants")
        c.clock(event["due"], path + ".due")

    relationships = state.get("relationships") if isinstance(state.get("relationships"), dict) else {}
    for key, edge in relationships.items():
        path = "$.relationships.%s" % key
        edge = c.shape(edge, EDGE, path)
        if edge is None:
            continue
        if key != "%s>%s" % (edge["from"], edge["to"]):
            c.bad(path, "关系键与端点不一致")
        c.ids([edge["from"], edge["to"]], known, path + ".ends")
        if edge["stage"] not in ST.STAGES:
            c.bad(path + ".stage", "阶段非法")
        c.each(edge["history"], HISTORY, path + ".history")

    leverage = state.get("leverage") if isinstance(state.get("leverage"), dict) else {}
    for lid, lv in leverage.items():
        path = "$.leverage.%s" % lid
        lv = c.shape(lv, LEVERAGE, path)
        if lv is None:
            continue
        c.ids([lv["holder"], lv["subject"]], known, path + ".parties")
        if lv["basis_fact_id"] not in facts:
            c.bad(path + ".basis_fact_id", "事实不存在：%s" % lv["basis_fact_id"])

    prefs = c.shape(state.get("preferences"), PREFERENCES, "$.preferences")
    if prefs is not None:
        for npc, entry in prefs["voice"].items():
            if npc not in known:
                c.bad("$.preferences.voice.%s" % npc, "角色不存在：%s" % npc)
            c.shape(entry, VOICE, "$.preferences.voice.%s" % npc)
    safety = c.shape(state.get("safety"), SAFETY, "$.safety")
    if safety is not None:
        c.each(safety["boundaries"], BOUNDARY, "$.safety.boundaries")
    memory = c.shape(state.get("memory"), MEMORY, "$.memory")
    if memory is not None:
        c.each(memory["turns"], MEMORY_TURN, "$.memory.turns")
        c.each(memory["chapters"], CHAPTER, "$.memory.chapters")
    counters = c.shape(state.get("counters"), COUNTERS, "$.counters")
    if counters is not None:
        nxt = c.shape(counters["next"], NEXT, "$.counters.next")
        c.shape(counters["twists"], TWISTS, "$.counters.twists")
        if nxt is not None:
            for kind, prefix, table in (("fact", "f", facts), ("event", "e", events), ("leverage", "lv", leverage)):
                used = [int(i[len(prefix):]) for i in table if i[len(prefix):].isdigit()]
                if used and max(used) >= nxt[kind]:
                    c.bad("$.counters.next.%s" % kind, "ID 计数小于已用的 ID")
    requests = c.shape(state.get("requests"), REQUESTS, "$.requests")
    if requests is not None:
        c.ids(requests["offscreen_beat_candidates"], known, "$.requests.offscreen_beat_candidates")
    if not c.problems:
        # the global invariants read everything above; only run them on a sound shape
        for problem in invariants.check(state):
            c.problems.append(problem)
        now = CL.to_abs(state["clock"])
        if CL.to_abs(state["scene"]["since"]) > now:
            c.bad("$.scene.since", "场景开始时间晚于现在")
    return c.problems


def check_archive(items):
    c = _Checker()
    if not isinstance(items, list):
        c.bad("$.archive", "应为数组")
        return c.problems
    for index, item in enumerate(items):
        item = c.shape(item, ({"kind": STR, "turn": "int?", "payload": DICT}, {}), "$.archive[%d]" % index)
        if item is not None and item["kind"] not in ARCHIVE_KINDS:
            c.bad("$.archive[%d].kind" % index, "归档类型非法")
    return c.problems
