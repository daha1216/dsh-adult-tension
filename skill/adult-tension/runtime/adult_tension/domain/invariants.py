"""Global invariants: the last net after every commit (ARCHITECTURE.md 4).

Operations validate themselves; this pass catches anything an operation
missed. Any violation rejects the whole commit.
"""

from ..errors import INVARIANT_VIOLATION, SAFETY_BLOCK, detail
from . import clock as CL
from . import structure as ST


def check(state, before_clock=None):
    problems = []

    def bad(path, reason, code=INVARIANT_VIOLATION):
        problems.append(detail(path, reason, "这是引擎的最后一道检查；请修正提交", code))

    chars = state["characters"]
    player = state["player_id"]
    if player not in chars:
        bad("$.state.characters", "玩家角色缺失")
    for cid, char in chars.items():
        base = "$.state.characters.%s" % cid
        age = char.get("age")
        if not isinstance(age, int):
            bad(base + ".age", "角色 %s 缺少明确年龄" % cid)
        elif age < 18:
            bad(base + ".age", "角色 %s 年龄 %d 小于 18" % (cid, age), SAFETY_BLOCK)
        if not char.get("adult_context"):
            bad(base + ".adult_context", "角色 %s 缺少成年身份说明" % cid)
        if char.get("tier") not in ST.TIERS:
            bad(base + ".tier", "角色层级非法")
    if before_clock is not None and CL.to_abs(state["clock"]) < CL.to_abs(before_clock):
        bad("$.state.clock", "时钟倒流")
    scene = state["scene"]
    if player not in scene["present"]:
        bad("$.state.scene.present", "玩家角色必须在当前场景")
    if len(set(scene["present"])) != len(scene["present"]):
        bad("$.state.scene.present", "在场名单有重复")
    for cid in scene["present"]:
        if cid not in chars:
            bad("$.state.scene.present", "在场的人不存在：%s" % cid)
    for fid, fact in state["facts"].items():
        base = "$.state.facts.%s" % fid
        for cid in fact["known_by"] + fact["believed_by"]:
            if cid not in chars:
                bad(base, "知情人不存在：%s" % cid)
        if fact["visibility"] == "inner":
            if len(fact["known_by"]) != 1 or fact["believed_by"] or fact.get("spreading"):
                bad(base, "内心事实只能属于本人、不能传播")
        if fact["truth"] and fact["believed_by"]:
            bad(base, "真事实不能有误信者")
    now = CL.to_abs(state["clock"])
    for eid, event in state["events"].items():
        base = "$.state.events.%s" % eid
        if event["state"] not in ST.EVENT_STATES:
            bad(base, "事件状态非法")
        if event["state"] == "pending" and CL.to_abs(event["due"]) <= now:
            bad(base, "未结束事件的到期时间必须晚于现在")
        if event["state"] != "pending" and event["outcome"] is None:
            bad(base, "已结束事件缺少结果")
    for key, edge in state["relationships"].items():
        base = "$.state.relationships.%s" % key
        if not ST.TRUST_RANGE[0] <= edge["trust"] <= ST.TRUST_RANGE[1]:
            bad(base, "信任超出范围")
        if not ST.TENSION_RANGE[0] <= edge["tension"] <= ST.TENSION_RANGE[1]:
            bad(base, "张力超出范围")
        if edge["stage"] not in ST.STAGES:
            bad(base, "阶段非法")
        if edge["from"] not in chars or edge["to"] not in chars:
            bad(base, "关系端点不存在")
    for lid, lv in state["leverage"].items():
        if lv["holder"] not in chars or lv["subject"] not in chars:
            bad("$.state.leverage.%s" % lid, "把柄双方必须存在")
        if lv["basis_fact_id"] not in state["facts"]:
            bad("$.state.leverage.%s" % lid, "把柄依据的事实不存在")
    return problems
