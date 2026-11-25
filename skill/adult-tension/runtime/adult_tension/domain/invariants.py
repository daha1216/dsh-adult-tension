"""Global invariants: the last net after every commit (ARCHITECTURE.md 4).

Operations validate themselves; this pass catches anything an operation
missed. Any violation rejects the whole commit.
"""

from ..errors import INVARIANT_VIOLATION, SAFETY_BLOCK, detail
from . import clock as CL
from . import facts as FA
from . import structure as ST


def check(state, before_clock=None, prefix="$.state"):
    problems = []

    def bad(path, reason, code=INVARIANT_VIOLATION):
        problems.append(detail(path, reason, "全局状态不变量校验未通过，请修正对应字段后重新提交", code))

    chars = state["characters"]
    player = state["player_id"]
    if player not in chars:
        bad("%s.characters" % prefix, "玩家角色缺失")
    for cid, char in chars.items():
        base = "%s.characters.%s" % (prefix, cid)
        age = char.get("age")
        if isinstance(age, bool) or not isinstance(age, int):
            bad(base + ".age", "角色 %s 缺少明确年龄" % cid)
        elif age < 18:
            bad(base + ".age", "角色 %s 年龄 %d 小于 18" % (cid, age), SAFETY_BLOCK)
        ctx_text = char.get("adult_context")
        if not isinstance(ctx_text, str) or not ctx_text.strip():
            bad(base + ".adult_context", "角色 %s 缺少成年身份说明" % cid)
        if char.get("tier") not in ST.TIERS:
            bad(base + ".tier", "角色层级非法")
    if before_clock is not None and CL.to_abs(state["clock"]) < CL.to_abs(before_clock):
        bad("%s.clock" % prefix, "时钟倒流")
    scene = state["scene"]
    if player not in scene["present"]:
        bad("%s.scene.present" % prefix, "玩家角色必须在当前场景")
    if len(set(scene["present"])) != len(scene["present"]):
        bad("%s.scene.present" % prefix, "在场名单有重复")
    for cid in scene["present"]:
        if cid not in chars:
            bad("%s.scene.present" % prefix, "在场的人不存在：%s" % cid)
    facts = state["facts"]
    # A commit checks the facts it created or changed; the rest were checked
    # when they were written and have not changed since.
    checked = facts.changed_facts() if isinstance(facts, FA.FactView) else FA.of(state).all()
    for fact in checked:
        fid = fact["id"]
        base = "%s.facts.%s" % (prefix, fid)
        for cid in fact["known_by"] + fact["believed_by"]:
            if cid not in chars:
                bad(base, "知情人不存在：%s" % cid)
        if fact["visibility"] == "inner":
            if len(fact["known_by"]) != 1 or fact["known_by"][0] == player or not fact["truth"] or fact["believed_by"] or fact.get("spreading"):
                bad(base, "内心事实只能属于本人、不能传播")
        if fact["truth"] and fact["believed_by"]:
            bad(base, "真事实不能有误信者")
        if not fact["truth"] and fact["visibility"] == "public":
            bad(base, "假事实不能设为 public")
        if set(fact["known_by"]) & set(fact["believed_by"]):
            bad(base, "同一角色不能同时在 known_by 与 believed_by 里")
    now = CL.to_abs(state["clock"])
    for eid, event in state["events"].items():
        base = "%s.events.%s" % (prefix, eid)
        if event["state"] not in ST.EVENT_STATES:
            bad(base, "事件状态非法")
        if event["state"] == "pending" and CL.to_abs(event["due"]) <= now:
            bad(base, "未结束事件的到期时间必须晚于现在")
        if event["state"] != "pending" and event["outcome"] is None:
            bad(base, "已结束事件缺少结果")
    for key, edge in state["relationships"].items():
        base = "%s.relationships.%s" % (prefix, key)
        if not ST.TRUST_RANGE[0] <= edge["trust"] <= ST.TRUST_RANGE[1]:
            bad(base, "信任超出范围")
        if not ST.TENSION_RANGE[0] <= edge["tension"] <= ST.TENSION_RANGE[1]:
            bad(base, "张力超出范围")
        if edge["stage"] not in ST.STAGES:
            bad(base, "阶段非法")
        if edge["from"] not in chars or edge["to"] not in chars:
            bad(base, "关系端点不存在")
    check_all_facts = not isinstance(facts, FA.FactView)
    for lid, lv in state["leverage"].items():
        if lv["holder"] not in chars or lv["subject"] not in chars:
            bad("%s.leverage.%s" % (prefix, lid), "把柄双方必须存在")
        if check_all_facts or lv["basis_fact_id"] in facts.changed or lv.get("created_turn", 0) > state["turn"]:
            if lv["basis_fact_id"] not in facts:
                bad("%s.leverage.%s" % (prefix, lid), "把柄依据的事实不存在")
    return problems
