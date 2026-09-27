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

GET_CONTEXT = _obj(
    {
        "session_id": F(SESSION_ID),
        "depth": F(S.Enum("brief", "full"), required=False, default="brief"),
    },
    "get-context",
)

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
