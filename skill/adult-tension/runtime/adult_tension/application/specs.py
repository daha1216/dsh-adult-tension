"""Input specs for every command (the generated references read these)."""

from .. import schema as S
from ..domain import structure as ST
from ..domain.turn import commit_fields

F = S.Field
SESSION_ID = S.Str(3, 40, r"s_[a-z0-9]{2,38}", "会话 ID，形如 s_1a2b3c4d")


def session_write_fields():
    return {
        "session_id": F(SESSION_ID),
        "request_id": F(S.RequestId()),
        "expected_revision": F(S.Int(1, 10**9), desc="上一次返回的 revision"),
    }


def _obj(fields, name):
    return S.Obj(fields, name=name)


COMMIT_TURN = _obj(dict(session_write_fields(), **commit_fields()), "commit-turn")

LOCKS = S.Obj(
    {key: F(S.Nullable(S.Id()), required=False, default=None) for key in ("world_id", "location_id", "combo_id", "activity_id", "pressure_id", "hook_id", "identity_id")},
    name="锁定",
)
EXCLUDES = S.Obj(
    {
        "content_tags": F(S.List(S.Id(), max_items=20, unique=True), required=False, default=[]),
        "world_ids": F(S.List(S.Id(), max_items=20, unique=True), required=False, default=[]),
        "location_ids": F(S.List(S.Id(), max_items=20, unique=True), required=False, default=[]),
    },
    name="排除",
)
PLAYER = S.Obj(
    {
        "gender": F(S.Nullable(S.Enum(*ST.GENDERS)), required=False, default=None),
        "age": F(S.Nullable(S.Int(0, 120)), required=False, default=None),
        "age_band": F(S.Nullable(S.List(S.Int(0, 120), 2, 2)), required=False, default=None),
        "identity_hint": F(S.Nullable(S.Str(1, 20)), required=False, default=None),
        "social_position": F(S.Nullable(S.Enum(*ST.SOCIAL_POSITIONS)), required=False, default=None),
        "name": F(S.Nullable(S.Str(1, 12)), required=False, default=None),
        "title": F(S.Nullable(S.Str(1, 12)), required=False, default=None),
    },
    name="玩家设定",
)
PREFERENCES = S.Obj(
    {
        "inner_view": F(S.Bool(), required=False),
        "assistant": F(S.Bool(), required=False),
        "offscreen_simulation": F(S.Bool(), required=False),
        "person": F(S.Enum(*ST.PERSONS), required=False),
    },
    name="偏好",
)

NEW_GAME = _obj(
    {
        "request_id": F(S.RequestId()),
        "mode": F(S.Nullable(S.Enum("daily", "pressure", "random")), required=False, default=None, desc="daily 日常 / pressure 有压力 / random 玩家明确说“随便”时；replay 时可省略"),
        "seed": F(S.Nullable(S.Int(1, 999999)), required=False, default=None),
        "replay": F(S.Bool(), required=False, default=False, desc="“重开 N 号”：按本机记录的该种子开局条件复现"),
        "locks": F(LOCKS, required=False, default={}),
        "excludes": F(EXCLUDES, required=False, default={}),
        "player": F(PLAYER, required=False, default={}),
        "npc_gender_preference": F(S.Enum(*ST.NPC_GENDER_PREFERENCES), required=False, default="any"),
        "custom_world": F(S.Nullable(S.Any("自定义世界包")), required=False, default=None),
        "preferences": F(PREFERENCES, required=False, default={}),
        "include_drafts": F(S.Bool(), required=False, default=False),
    },
    "new-game",
)

PREVIEW_TIME = S.Obj(
    {
        "minutes": F(S.Int(1, ST.MAX_ADVANCE_MINUTES), required=False),
        "until": F(S.Enum("morning", "noon", "evening", "night", "next_morning"), required=False),
        "days": F(S.Int(1, 30), required=False),
    },
    name="预览推进",
    desc="与 advance_time 相同：minutes / until / days 三选一",
)

GET_CONTEXT = _obj(
    {
        "session_id": F(SESSION_ID),
        "depth": F(S.Enum("brief", "full"), required=False, default="brief"),
        "preview_time": F(
            S.Nullable(PREVIEW_TIME),
            required=False,
            default=None,
            desc="快进预览：返回目标时钟、将到期的事件与确定性结果、必须写离屏片段的 NPC（附目标与信息集）、将到期的状态；不改变状态",
        ),
        "want_twist": F(S.Bool(), required=False, default=False, desc="玩家说“来点转折”时为 true：返回 2–3 个类别不同的转折候选"),
    },
    "get-context",
)

UNDO_TURN = _obj(session_write_fields(), "undo-turn")

SAVE_SLOT = _obj(
    dict(
        session_write_fields(),
        name=F(S.Nullable(S.Str(1, 60)), required=False, default=None),
        overwrite=F(S.Bool(), required=False, default=False),
        save_as=F(S.Bool(), required=False, default=False),
    ),
    "save-slot",
)

LOAD_SLOT = _obj({"request_id": F(S.RequestId()), "name": F(S.Str(1, 60))}, "load-slot")
DELETE_SLOT = _obj(
    dict(
        session_write_fields(),
        name=F(S.Str(1, 60)),
        confirm=F(S.Bool(), required=False, default=False, desc="玩家确认删除后才为 true"),
    ),
    "delete-slot",
)
LIST_SESSIONS = _obj({"limit": F(S.Int(1, 20), required=False, default=10)}, "list-sessions")
EXPORT_SAVE = _obj(
    {
        "session_id": F(S.Nullable(SESSION_ID), required=False, default=None, desc="导出这个会话的当前状态"),
        "slot": F(S.Nullable(S.Str(1, 60)), required=False, default=None, desc="或导出这个存档"),
        "path": F(S.Nullable(S.Str(1, 400)), required=False, default=None, desc="玩家明确给出的绝对路径（.json）；不给时写到数据目录的 exports/"),
        "overwrite": F(S.Bool(), required=False, default=False),
    },
    "export-save",
)
IMPORT_SAVE = _obj(
    {
        "request_id": F(S.RequestId()),
        "path": F(S.Nullable(S.Str(1, 400)), required=False, default=None, desc="导出文件的路径"),
        "data": F(S.Nullable(S.Any("导出的 JSON 对象")), required=False, default=None, desc="或玩家粘贴的导出内容（整个 JSON 对象）"),
        "slot": F(S.Nullable(S.Str(1, 60)), required=False, default=None, desc="同时写入这个存档槽（可省略）"),
        "overwrite": F(S.Bool(), required=False, default=False, desc="存档名已被占用时，玩家确认覆盖"),
    },
    "import-save",
)
LIST_WORLDS = _obj({"include_drafts": F(S.Bool(), required=False, default=False)}, "list-worlds")
SMOKE = _obj({"seed": F(S.Int(1, 999999), required=False, default=42), "turns": F(S.Int(2, 60), required=False, default=8)}, "smoke")
VERIFY_CONTENT = _obj(
    {
        "world": F(S.Nullable(S.Id()), required=False, default=None),
        "stats": F(S.Bool(), required=False, default=False),
        "skip_diversity": F(S.Bool(), required=False, default=False),
    },
    "verify-content",
)

SET_BOUNDARY = _obj(
    dict(
        session_write_fields(),
        action=F(S.Enum("add", "remove"), desc="add 登记 / remove 撤销"),
        text=F(S.Nullable(S.Str(1, 80)), required=False, default=None, desc="玩家的原话，例如“不要涉及怀孕”"),
        tags=F(S.List(S.Id(), max_items=6, unique=True), required=False, default=[], desc="映射到的内容标签；映射不上就留空（记为 custom，由你自己遵守）"),
        boundary_id=F(S.Nullable(S.Id()), required=False, default=None, desc="撤销时可用边界 ID"),
    ),
    "set-boundary",
)

SET_SAFETY = _obj(
    dict(
        session_write_fields(),
        paused=F(S.Bool(), desc="true 暂停 / false 恢复"),
        change_scene=F(S.Bool(), required=False, default=False, desc="“换个场景”：保持暂停，换到新的非亲密场景"),
    ),
    "set-safety",
)

VOICE_CHANGE = S.Obj({"npc_id": F(S.Id()), "voice": F(S.Enum("surface", "inner"))}, name="语态")
SET_PREFERENCES = _obj(
    dict(
        session_write_fields(),
        inner_view=F(S.Bool(), required=False),
        assistant=F(S.Bool(), required=False),
        offscreen_simulation=F(S.Bool(), required=False),
        person=F(S.Enum(*ST.PERSONS), required=False),
        npc_gender_preference=F(S.Enum(*ST.NPC_GENDER_PREFERENCES), required=False),
        voice=F(VOICE_CHANGE, required=False),
    ),
    "set-preferences",
)

STATUS = _obj(
    {
        "session_id": F(SESSION_ID),
        "level": F(S.Enum("brief", "detail", "debug"), required=False, default="brief", desc="brief 六行 / detail 状态+ / debug 调试"),
    },
    "status",
)
