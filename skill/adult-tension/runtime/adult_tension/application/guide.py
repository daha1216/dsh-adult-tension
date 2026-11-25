"""`guide`: the play guide for a new player ("怎么玩"), fixed text the model
relays as it is. Plain words only: no NPC, turn, command or field names."""

from .. import schema as S
from ..errors import INVALID_INPUT, AppError
from ..persistence import repo
from . import specs

TITLE = "怎么玩"
EXAMPLE = "· 直接打字，写你的动作与台词。例如：我反手带上门，替她拢好滑落的披肩：“外头人多，先进来避避。”"

WHAT = [
    "【这是什么】",
    "一个由你当主角的互动故事。你打字说你做什么、说什么，AI 接着把故事写下去。",
    "故事里的其他人有自己的脾气和想法，会答应你，也会拒绝你。",
]
CUSTOM = "· 创造专属世界：说“自定义世界”，会给你一份灵感清单；保存过的世界说“我的世界”就能查看。"
START = [
    "【第一步：开一局】",
    "· 直接开局：说“开局”，然后选氛围：",
    "  日常：私密日常里的暧昧试探与暗流拉扯。",
    "  压力：开局即身处把柄、时限或困局，在紧绷博弈中贴近。",
    "  拿不定主意就直接说“随便”。",
    "· 自选世界：说“世界列表”浏览预设世界；也可直接指定题材，如“开局 民国”“开局 豪门”。",
    "· 偏好柔和氛围：说“开局 轻松点”，避开高压危机题材。",
    CUSTOM,
]
AGAIN = "· 继续进度：说“继续上次”，接着玩上一局未完的故事。"
FIRST_STEPS = [
    "【第二步：开始玩】",
    EXAMPLE,
    "· 只写你自己的事，别人怎么反应交给故事。",
    "· 想不出来就说“继续”，故事会自己往下走一点。",
]
HOW = [
    "【怎么玩】",
    EXAMPLE,
    "· 写得越具体，故事越照你的意思走。",
    "· 你只决定自己的言行。故事里的人各有欲望、软肋与算计，会迎合试探，也会抗拒或反将一军。",
    "· 想不出来就说“继续”，故事会自己往下走一点。",
]
ANYTIME = [
    "【随时能说】",
    "· 存档 / 读档：保存进度，或回到存过的进度",
    "· 撤销：刚才那步不算，重来",
]
COMMON = [
    "【常用的话】",
    "· 状态：看看现在几点、在哪、和谁关系怎么样",
    "· 存档 / 读档：保存进度，或回到存过的进度",
    "· 撤销：刚才那步不算，重来",
    "· 快进到明早：跳过一段时间",
    "· 来点转折：让故事出点意外",
    "· 内心可见：看到别人心里没说出口的话",
    "· 节奏 慢热 / 标准 / 直接，尺度 含蓄 / 标准 / 直白：换个写法",
]
SAFETY = [
    "【不舒服的时候】",
    "· 暂停：马上停下",
    "· 换个场景：离开眼前这一幕",
    "· 边界（如“不要 ××”）：记下你的雷区，后续不再触碰",
]
CUSTOM_TITLE = "自定义世界"
CUSTOM_LINES = [
    "想玩预设列表里没有的故事？挑你想到的说两句就行，剩下的交给我补齐，不用每项都填。",
    "",
    "【1 时代与空间】梅雨夜的民国公馆暗房、庆功宴散场后的顶层套房、雾夜停航的私人游艇、仙门禁地冷泉、近未来深空医疗舱",
    "【2 你的处境】握有内幕账册的贴身秘书、受邀夜诊的私人医生、寄人篱下的旧族门客、掌管门禁的安保主管",
    "【3 想遇见的人（两三位）】说说身份与反差即可，例如：端庄冷傲却暗藏软肋的上司、笑里藏刀的旧情人、表面顺从却各怀心思的合伙人；全员均为成年人，不说则随机生成",
    "【4 彼此间的拉扯】未了的私密旧账、上下级权力倒转、一墙之隔的秘密幽会、互握把柄的贴身交易、危机之下的失控靠近",
    "【5 氛围模式】日常（私密相处中的试探升温）/ 压力（开局即有查房、违约、封锁或把柄催逼）",
    "【6 尺度与避雷】例如：节奏直接、尺度直白；或不要流血暴力、不要多人同场",
    "",
    "你可以直接这么发：“民国租界公馆，我是留洋归来的私人医生，想遇到冷傲的公馆女主人和精明的贴身女管事，彼此有旧情与把柄拉扯，压力向，尺度直白。”",
    "觉得满意，开局后随时说“保存世界 名字”（例如：保存世界 公馆暗事）存下来；下次说“我的世界”就能查看与重玩。",
]
MORE = "想看所有能说的话，说“帮助”。"


def lines_before_playing(has_played):
    start = START + ([AGAIN] if has_played else [])
    return WHAT + [""] + start + [""] + FIRST_STEPS + [""] + ANYTIME + [""] + SAFETY + ["", MORE]


def lines_while_playing(world_title):
    return ["你正在玩：《%s》。" % world_title, ""] + HOW + [""] + COMMON + [""] + SAFETY + ["", MORE]


def run(ctx, payload):
    payload, errors = S.validate(specs.GUIDE, payload or {})
    if errors:
        raise AppError(INVALID_INPUT, "输入有 %d 处问题" % len(errors) if len(errors) > 1 else errors[0]["reason"], errors)
    if payload["topic"] == "custom_world":
        out = {"stage": "custom_world", "title": CUSTOM_TITLE, "lines": CUSTOM_LINES}
        out["text"] = "\n".join([CUSTOM_TITLE, ""] + CUSTOM_LINES)
        return out
    conn = ctx.db()
    if payload["session_id"]:
        session = repo.session_summary(conn, payload["session_id"])
        out = {"stage": "playing", "session_id": payload["session_id"], "world_title": session["world_title"]}
        lines = lines_while_playing(session["world_title"])
    else:
        out = {"stage": "start"}
        lines = lines_before_playing(repo.has_sessions(conn))
    out.update({"title": TITLE, "lines": lines, "text": "\n".join([TITLE, ""] + lines)})
    return out
