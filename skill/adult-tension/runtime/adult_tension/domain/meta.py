"""Meta commands: boundaries, pause, preferences. They change state (revision)
but never advance the turn, and they write no narrative.
"""

from ..errors import INVALID_INPUT, INVARIANT_VIOLATION, NOT_FOUND, AppError, detail
from . import facts as FA
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
PACE_LABELS = {"slow": "慢热", "standard": "标准", "direct": "直接"}
EXPLICITNESS_LABELS = {"subtle": "含蓄", "standard": "标准", "explicit": "直白"}
SHOWN_PREFERENCES = ("inner_view", "assistant", "offscreen_simulation", "person", "npc_gender_preference", "pace", "explicitness")
BOUNDARY_LEADINS = ("麻烦", "请", "希望你", "希望", "我个人", "我")
BOUNDARY_PREFIXES = (
    "不想看到",
    "不想看",
    "不想要",
    "不喜欢",
    "不接受",
    "不能接受",
    "不能看到",
    "不能看",
    "不能有",
    "不能",
    "不要再",
    "不要让",
    "不要写到",
    "不要写",
    "不要出现",
    "不要涉及",
    "不要有",
    "不要",
    "不看",
    "拒绝",
    "别让",
    "别再",
    "别写到",
    "别写",
    "别有",
    "别",
    "不许",
    "禁止",
)
BOUNDARY_VERBS = ("写到", "写", "出现", "涉及", "看到", "看")
BARE_BOUNDARY_MODALS = ("不要", "不能", "别", "不许", "禁止", "拒绝", "不想", "不接受", "不能接受", "不要再", "别再")


def _bump(state):
    state["revision"] += 1
    state["facts"] = state["facts"].settle()  # meta commands never change facts
    return state


def _boundary_subject(text):
    raw = text.strip()
    cand = raw
    # Strip chained polite/first-person lead-ins only when followed by a negation prefix.
    while True:
        matched_lead = False
        for lead in BOUNDARY_LEADINS:
            if cand.startswith(lead):
                after = cand[len(lead) :].strip()
                if after:
                    cand = after
                    matched_lead = True
                    break
        if not matched_lead:
            break
    body = cand if any(cand.startswith(p) for p in BOUNDARY_PREFIXES) else raw
    stripped = False
    matched_prefix = None
    for prefix in BOUNDARY_PREFIXES:
        if body.startswith(prefix):
            rest = body[len(prefix) :].strip()
            if prefix.endswith("有") and rest.startswith("人"):
                continue
            if rest:
                body = rest
                stripped = True
                matched_prefix = prefix
                break
    if stripped and matched_prefix in BARE_BOUNDARY_MODALS:
        for verb in BOUNDARY_VERBS:
            if body.startswith(verb):
                rest = body[len(verb) :].strip()
                if rest:
                    body = rest
                break
    return (body if stripped else raw) or raw


def set_boundary(state, content, action, text=None, tags=None, boundary_id=None):
    work = FA.working_copy(state)
    boundaries = work["safety"]["boundaries"]
    if text is not None:
        text = text.strip()
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
    if not boundary_id and not text:
        raise AppError(INVALID_INPUT, "撤销边界要给 boundary_id 或原话", [detail("$.text", "缺少要撤销的边界", None, INVALID_INPUT)])
    by_id = next((b for b in boundaries if b["id"] == boundary_id), None) if boundary_id else None
    by_text = next((b for b in boundaries if b["text"] == text), None) if text else None
    if boundary_id and text and by_id is not None and by_text is not None and by_id["id"] != by_text["id"]:
        raise AppError(
            INVALID_INPUT,
            "boundary_id 与 text 指向了不同的边界",
            [detail("$.boundary_id", "boundary_id（%s）与 text（%s）指向了不同边界" % (by_id["id"], by_text["id"]), "只传 boundary_id，或确保两者对应同一条边界", INVALID_INPUT)],
        )
    target = by_id if boundary_id else by_text
    if target is None:
        raise AppError(
            NOT_FOUND,
            "没有找到这条边界",
            [detail("$.boundary_id" if boundary_id else "$.text", "边界不存在", "现有边界：%s" % ("、".join("%s（%s）" % (b["text"], b["id"]) for b in boundaries) or "（无）"), NOT_FOUND)],
        )
    work["safety"]["boundaries"] = [b for b in boundaries if b["id"] != target["id"]]
    return _bump(work), {"boundary": target, "receipt": "已撤销边界：%s" % target["text"], "changed": True}


def set_safety(state, paused, change_scene=False):
    work = FA.working_copy(state)
    safety = work["safety"]
    if change_scene and not paused:
        raise AppError(INVARIANT_VIOLATION, "“换个场景”会保持暂停", [detail("$.change_scene", "换场景时 paused 必须为 true", "恢复用 paused: false", INVARIANT_VIOLATION)])
    if paused:
        was = safety["paused"]
        safety["paused"] = True
        if change_scene:
            scene = settlement.new_scene(work, "change_scene")
            work["memory"]["open_action"] = None
            work["memory"]["last_quotes"] = []
            return _bump(work), {"paused": True, "scene": scene, "receipt": "仍在暂停中，换到一个新的非亲密场景", "changed": True}
        if was:
            return None, {"paused": True, "receipt": "已暂停。说“继续”恢复，或说“换个场景”", "changed": False}
        return _bump(work), {"paused": True, "receipt": "已暂停。说“继续”恢复，或说“换个场景”", "changed": True}
    if not safety["paused"]:
        return None, {"paused": False, "receipt": "当前没有暂停", "changed": False}
    safety["paused"] = False
    # Resuming never continues an escalation: judgments are made again.
    work["scene"]["responses"] = []
    return _bump(work), {"paused": False, "receipt": "已恢复。从停下的地方重新开始，对方的反应重新判断", "changed": True}


def set_preferences(state, content=None, changes=None):
    if changes is None and isinstance(content, dict) and "world" not in content:
        changes = content
    changes = changes or {}
    work = FA.working_copy(state)
    prefs = work["preferences"]
    receipts = []
    problems = []
    changed = False
    for key in ("inner_view", "assistant", "offscreen_simulation"):
        if key in changes:
            if prefs[key] != changes[key]:
                changed = True
            prefs[key] = changes[key]
            label = {"inner_view": "内心可见", "assistant": "叙事助手", "offscreen_simulation": "离屏推演"}[key]
            suffix = "（世界冻结）" if key == "offscreen_simulation" and not changes[key] else ""
            receipts.append("%s：%s%s" % (label, "开" if changes[key] else "关", suffix))
    if "person" in changes:
        if prefs["person"] != changes["person"]:
            changed = True
        prefs["person"] = changes["person"]
        receipts.append("人称：%s" % PERSON_LABELS[changes["person"]])
    if "npc_gender_preference" in changes:
        if prefs["npc_gender_preference"] != changes["npc_gender_preference"]:
            changed = True
        prefs["npc_gender_preference"] = changes["npc_gender_preference"]
        receipts.append("配对偏好：%s" % PREFERENCE_LABELS[changes["npc_gender_preference"]])
    # Style preferences change how the story is written, never the rules (PRODUCT_SPEC 4.4).
    if "pace" in changes:
        if prefs["pace"] != changes["pace"]:
            changed = True
        prefs["pace"] = changes["pace"]
        receipts.append("节奏：%s" % PACE_LABELS[changes["pace"]])
    if "explicitness" in changes:
        if prefs["explicitness"] != changes["explicitness"]:
            changed = True
        prefs["explicitness"] = changes["explicitness"]
        receipts.append("尺度：%s" % EXPLICITNESS_LABELS[changes["explicitness"]])
    voice = changes.get("voice")
    if voice:
        npc = voice["npc_id"]
        char = work["characters"].get(npc)
        if char is None or npc == work["player_id"]:
            problems.append(detail("$.voice.npc_id", "角色不存在：%s" % npc, None, NOT_FOUND))
        elif not char.get("voices"):
            problems.append(detail("$.voice.npc_id", "%s 没有表里语态" % char["name"], "只有重要角色有", INVARIANT_VIOLATION))
        else:
            cur = prefs["voice"].get(npc)
            same = (
                isinstance(cur, dict)
                and cur.get("voice") == voice["voice"]
                and cur.get("cause") == "player_request"
                and cur.get("via") == "meta"
                and cur.get("trigger") is None
            )
            if not same:
                # via: meta marks a player setting, which an undo of the story keeps.
                prefs["voice"][npc] = {"voice": voice["voice"], "cause": "player_request", "since_turn": work["turn"], "trigger": None, "via": "meta"}
                changed = True
            receipts.append("%s：%s" % (char["name"], "里层语态" if voice["voice"] == "inner" else "表层语态"))
    if problems:
        raise AppError(problems[0]["code"], problems[0]["reason"], problems)
    if not receipts:
        raise AppError(INVALID_INPUT, "没有要改的设置", [detail("$", "至少给一个设置", None, INVALID_INPUT)])
    payload = {"receipt": "；".join(receipts), "preferences": {k: prefs[k] for k in SHOWN_PREFERENCES}, "changed": changed}
    if not changed:
        return None, payload
    return _bump(work), payload
