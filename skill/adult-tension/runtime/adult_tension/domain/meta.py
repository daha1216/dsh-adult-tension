"""Meta commands: boundaries, pause, preferences. They change state (revision)
but never advance the turn, and they write no narrative.
"""

from ..errors import INVALID_INPUT, INVARIANT_VIOLATION, NOT_FOUND, AppError, detail
from ..jsonio import copy
from . import settlement
from . import state as SS

PERSON_LABELS = {"second": "第二人称（你）", "first": "第一人称（我）", "third": "第三人称"}
PREFERENCE_LABELS = {
    "any": "不限",
    "mostly_female": "女性为主",
    "mostly_male": "男性为主",
    "female_only": "只要女性",
    "male_only": "只要男性",
    "mixed": "男女都有",
}
BOUNDARY_PREFIXES = ("不想看到", "不想要", "不要", "别写", "别", "不许")


def _bump(state):
    state["revision"] += 1
    return state


def _boundary_subject(text):
    for prefix in BOUNDARY_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix) :].strip() or text
    return text


def set_boundary(state, content, action, text=None, tags=None, boundary_id=None):
    work = copy(state)
    boundaries = work["safety"]["boundaries"]
    if action == "add":
        valid = {t["id"] for t in content["tags"]}
        problems = [
            detail("$.tags[%d]" % i, "未知内容标签：%s" % tag, "可用：%s；映射不上就用 custom" % "、".join(sorted(valid)), INVALID_INPUT)
            for i, tag in enumerate(tags or [])
            if tag not in valid
        ]
        if not text:
            problems.append(detail("$.text", "边界要保留玩家的原话", None, INVALID_INPUT))
        if problems:
            raise AppError(INVALID_INPUT, problems[0]["reason"], problems)
        if any(b["text"] == text for b in boundaries):
            existing = next(b for b in boundaries if b["text"] == text)
            return None, {"boundary": existing, "receipt": "已记下：不会出现%s" % _boundary_subject(text), "changed": False}
        bid = SS.next_id(work, "boundary", "b")
        boundary = {"id": bid, "text": text, "tags": list(tags) if tags else ["custom"], "created_turn": work["turn"]}
        boundaries.append(boundary)
        return _bump(work), {"boundary": boundary, "receipt": "已记下：不会出现%s" % _boundary_subject(text), "changed": True}
    target = None
    for boundary in boundaries:
        if (boundary_id and boundary["id"] == boundary_id) or (text and boundary["text"] == text):
            target = boundary
    if target is None:
        raise AppError(
            NOT_FOUND,
            "没有找到这条边界",
            [detail("$.boundary_id" if boundary_id else "$.text", "边界不存在", "现有边界：%s" % ("、".join("%s（%s）" % (b["text"], b["id"]) for b in boundaries) or "（无）"), NOT_FOUND)],
        )
    work["safety"]["boundaries"] = [b for b in boundaries if b["id"] != target["id"]]
    return _bump(work), {"boundary": target, "receipt": "已撤销边界：%s" % target["text"], "changed": True}


def set_safety(state, paused, change_scene=False):
    work = copy(state)
    safety = work["safety"]
    if change_scene and not paused:
        raise AppError(INVARIANT_VIOLATION, "“换个场景”会保持暂停", [detail("$.change_scene", "换场景时 paused 必须为 true", "恢复用 paused: false", INVARIANT_VIOLATION)])
    if paused:
        was = safety["paused"]
        safety["paused"] = True
        if change_scene:
            scene = settlement.new_scene(work, "change_scene")
            return _bump(work), {"paused": True, "scene": scene, "receipt": "仍在暂停中，换到一个新的非亲密场景。", "changed": True}
        if was:
            return None, {"paused": True, "receipt": "已暂停。说“继续”恢复，或说“换个场景”", "changed": False}
        return _bump(work), {"paused": True, "receipt": "已暂停。说“继续”恢复，或说“换个场景”", "changed": True}
    if not safety["paused"]:
        return None, {"paused": False, "receipt": "当前没有暂停", "changed": False}
    safety["paused"] = False
    # Resuming never continues an escalation: judgments are made again.
    work["scene"]["responses"] = []
    return _bump(work), {"paused": False, "receipt": "已恢复。从停下的地方重新开始，对方的反应重新判断。", "changed": True}


def set_preferences(state, content, changes):
    work = copy(state)
    prefs = work["preferences"]
    receipts = []
    problems = []
    for key in ("inner_view", "assistant", "offscreen_simulation"):
        if key in changes:
            prefs[key] = changes[key]
            label = {"inner_view": "内心可见", "assistant": "叙事助手", "offscreen_simulation": "离屏推演"}[key]
            suffix = "（世界冻结）" if key == "offscreen_simulation" and not changes[key] else ""
            receipts.append("%s：%s%s" % (label, "开" if changes[key] else "关", suffix))
    if "person" in changes:
        prefs["person"] = changes["person"]
        receipts.append("人称：%s" % PERSON_LABELS[changes["person"]])
    if "npc_gender_preference" in changes:
        prefs["npc_gender_preference"] = changes["npc_gender_preference"]
        receipts.append("配对偏好：%s" % PREFERENCE_LABELS[changes["npc_gender_preference"]])
    voice = changes.get("voice")
    if voice:
        npc = voice["npc_id"]
        char = work["characters"].get(npc)
        if char is None or npc == work["player_id"]:
            problems.append(detail("$.voice.npc_id", "角色不存在：%s" % npc, None, NOT_FOUND))
        elif not char.get("voices"):
            problems.append(detail("$.voice.npc_id", "%s 没有表里两层语态" % char["name"], "只有重要角色有", INVARIANT_VIOLATION))
        else:
            prefs["voice"][npc] = {"voice": voice["voice"], "cause": "player_request", "since_turn": work["turn"], "trigger": None}
            receipts.append("%s：%s" % (char["name"], "里层语态" if voice["voice"] == "inner" else "表层语态"))
    if problems:
        raise AppError(problems[0]["code"], problems[0]["reason"], problems)
    if not receipts:
        raise AppError(INVALID_INPUT, "没有要改的设置", [detail("$", "至少给一个设置", None, INVALID_INPUT)])
    return _bump(work), {"receipt": "；".join(receipts), "preferences": {k: prefs[k] for k in ("inner_view", "assistant", "offscreen_simulation", "person", "npc_gender_preference")}, "changed": True}
