"""World pack validation (CONTENT_BIBLE.md sections 3, 5, 6; DATA_CONTRACTS.md 8).

validate_world() checks one compiled pack (or a custom world) and returns the
normalized pack plus a list of problems. Each problem names the JSON path, the
reason and a hint. verify_packs() adds the cross-pack checks.
"""

import re

from .. import schema as S
from ..errors import CONTENT_ERROR, detail
from . import structure as ST
from .text import PLACEHOLDER_RE, gendered_pronoun_positions, placeholders, stray_braces

F = S.Field


def _str(lo=1, hi=200):
    return S.Str(lo, hi)


def _texts(min_items=0, hi=200):
    return S.List(_str(1, hi), min_items=min_items)


def _range(lo, hi):
    return S.List(S.Int(lo, hi), 2, 2)


NAME_PATTERN = S.Obj(
    {"pattern": F(_str(1, 20)), "gender": F(S.Enum(*ST.TEMPLATE_GENDERS), required=False, default="any")},
    name="称呼模板",
)
EXIT_OPTION = S.Obj({"option": F(_str(1, 80)), "cost": F(_str(1, 120))})

IDENTITY = S.Obj(
    {
        "id": F(S.Id()),
        "role": F(_str(1, 20), desc="身份名，例如“长住的撰稿人”"),
        "gender": F(S.Enum(*ST.TEMPLATE_GENDERS), required=False, default="any", desc="any 表示按玩家设定"),
        "title_patterns": F(S.List(NAME_PATTERN, min_items=1), desc="别人怎么称呼玩家，例如 {family}老师"),
        "age_range": F(_range(0, 120), desc="年龄范围，下限 ≥ 18"),
        "social_position": F(S.Enum(*ST.SOCIAL_POSITIONS), desc="相对于世界里主要人物的社会位置"),
        "baseline": F(_str(1, 200), desc="玩家眼下的处境"),
        "resources": F(_texts(1, 80), desc="玩家手里有什么"),
        "reputation": F(_str(1, 80), desc="别人眼里的玩家"),
        "risks": F(_texts(1, 120), desc="玩家怕失去什么"),
    },
    name="玩家身份",
)

LOCATION = S.Obj(
    {
        "id": F(S.Id()),
        "name": F(_str(1, 20)),
        "detail": F(_str(1, 200), desc="看得见、摸得着的细节"),
        "privacy": F(S.Enum(*ST.PRIVACY), desc="public 人来人往；semi 半开放；private 关得上门"),
        "visibility": F(_str(1, 120), desc="谁能看见这里发生的事"),
        "witnesses": F(S.List(S.Id(), unique=True), required=False, default=[], desc="常在这里的背景人物 ID"),
        "exits": F(S.List(S.Id(), min_items=1, unique=True), desc="相连的地点 ID"),
        "affordances": F(S.List(_str(1, 60), min_items=2), desc="在这里能做的事"),
        "pressure_modifiers": F(S.Map(_str(1, 120), S.ID_PATTERN, S.ID_HINT), required=False, default={}, desc="压力 ID → 这个压力在这里有什么不同"),
        "tags": F(S.List(S.Id(), unique=True), required=False, default=[]),
    },
    name="地点",
)

TEMPLATE = S.Obj(
    {
        "id": F(S.Id()),
        "gender": F(S.Enum(*ST.TEMPLATE_GENDERS), desc="any 表示由会话的性别偏好决定，文本全部用占位"),
        "gender_reason": F(S.Nullable(_str(1, 120)), required=False, default=None, desc="性别写死时的叙事理由"),
        "age_range": F(_range(0, 120), desc="年龄范围，下限 ≥ 18"),
        "adult_context": F(_str(1, 80), desc="明示成年身份与处境的一句话"),
        "public_role": F(_str(1, 30), desc="别人知道的身份"),
        "appearance_options": F(S.List(_str(1, 120), min_items=2), desc="外貌候选，开局抽一条"),
        "identity": F(
            S.Obj(
                {
                    "authority": F(_str(1, 120), desc="能决定什么"),
                    "resources": F(_texts(1, 80), desc="手里有什么"),
                    "limits": F(_texts(1, 80), desc="做不到什么"),
                    "obligations": F(_texts(0, 80), required=False, default=[], desc="对谁负有什么责任"),
                    "exposure": F(_str(1, 120), desc="一旦被人知道就麻烦的事"),
                    "hidden": F(_str(1, 120), desc="只有自己知道的事"),
                }
            ),
            desc="身份：权力、资源、限制、暴露点、隐藏的事",
        ),
        "decision": F(
            S.Obj(
                {
                    "core_value": F(_str(1, 60), desc="最看重的东西"),
                    "goal_options": F(S.List(_str(1, 80), min_items=2), desc="目标候选，开局抽一条"),
                    "pressure_responses": F(
                        S.Obj({level: F(_str(1, 120)) for level in ("low", "mid", "high", "breaking")}),
                        desc="四档压力下的反应：low、mid、high、breaking",
                    ),
                    "withdrawal": F(_str(1, 120), desc="退缩时的具体表现"),
                    "relationship_stance": F(_str(1, 80), desc="对人的基本态度"),
                    "contrast": F(_str(1, 80), desc="表面和内里的反差"),
                    "prefers": F(_texts(1, 80), desc="偏好的做法"),
                    "avoids": F(_texts(1, 80), desc="回避的事"),
                    "never": F(_texts(1, 80), desc="无论如何不做的事"),
                }
            ),
            desc="决策：NPC 按这些自己做决定",
        ),
        "intimacy_tendency": F(
            S.Obj(
                {
                    "attraction_sources": F(S.List(_str(1, 80), min_items=2), desc="被什么吸引"),
                    "likes": F(_texts(1, 60)),
                    "dislikes": F(_texts(1, 60)),
                    "preconditions": F(_texts(1, 80), desc="靠近之前需要的条件"),
                    "boundaries": F(_texts(1, 80), desc="不越过的线"),
                    "expression": F(_str(1, 80), desc="好感怎么表现出来"),
                    "desire_range": F(_range(0, 5), desc="欲望 0–5 的范围，开局取一个值"),
                    "self_control_range": F(_range(0, 5), desc="自制 0–5 的范围，开局取一个值"),
                    "desired_position": F(_str(1, 40), desc="想要的相处位置"),
                }
            ),
            desc="亲密倾向（不等于许可）",
        ),
        "voices": F(S.Obj({"surface": F(_str(1, 120), desc="说出口的话"), "inner": F(_str(1, 120), desc="心里的话")}), desc="表层与里层语态的示例"),
        "schedule": F(
            S.List(
                S.Obj({"from": F(S.Int(0, 1439)), "to": F(S.Int(0, 1439)), "location_id": F(S.Id())}),
                min_items=1,
            ),
            desc="作息：一天里各时段在哪（从零点起的分钟），离屏推演用",
        ),
        "situation": F(
            S.Obj({"trigger": F(_str(1, 120)), "pressure": F(_str(1, 120)), "exits": F(S.List(EXIT_OPTION, min_items=2))}),
            desc="这个人自己的处境：起因、压力、至少两条各有代价的出路",
        ),
        "tags": F(S.List(S.Id(), unique=True), required=False, default=[]),
    },
    name="人物模板",
)

BACKGROUND = S.Obj(
    {
        "id": F(S.Id()),
        "role": F(_str(1, 20)),
        "function": F(S.Enum(*ST.BACKGROUND_FUNCTIONS), desc="在剧情里起什么作用"),
        "location_ids": F(S.List(S.Id(), min_items=1, unique=True), desc="常在的地点"),
        "line": F(_str(1, 120), desc="一句描写，用 {npc.name}"),
        "gender": F(S.Enum(*ST.TEMPLATE_GENDERS)),
        "age_range": F(_range(0, 120), desc="年龄范围，下限 ≥ 18"),
        "adult_context": F(_str(1, 80), desc="明示成年身份的一句话"),
        "name": F(S.Nullable(_str(1, 8)), required=False, default=None, desc="固定名字；省略时开局生成"),
    },
    name="背景人物",
)

CHANNEL = S.Obj(
    {
        "id": F(S.Id()),
        "text": F(_str(1, 60), desc="渠道，例如“茶餐厅的熟客”"),
        "reach": F(_str(1, 80), desc="传到谁、多快"),
        "fidelity": F(S.Enum(*ST.CHANNEL_FIDELITY), desc="exact 原样传；distorted 传走样"),
    },
    name="关系渠道",
)
ENGINE = S.Obj({"id": F(S.Id()), "text": F(_str(1, 120), desc="不靠外部压力也持续制造张力的结构")}, name="张力引擎")
RULE = S.Obj({"id": F(S.Id()), "text": F(_str(1, 200), desc="能在回合里改变一个选择的规则")}, name="世界规则")
EDGE_VALUES = S.Obj({"trust": F(S.Int(-5, 5), desc="信任"), "tension": F(S.Int(0, 5), desc="张力")})

COMBO = S.Obj(
    {
        "id": F(S.Id()),
        "power_structure": F(S.Enum(*ST.POWER_STRUCTURES), desc="玩家占上风、NPC 占上风、平等、可反转"),
        "player_positions": F(S.List(S.Enum(*ST.SOCIAL_POSITIONS), min_items=1, unique=True), desc="配得上的玩家社会位置"),
        "identity_ids": F(S.List(S.Id(), unique=True), required=False, default=[], desc="只配这些玩家身份；省略表示不限"),
        "slots": F(S.List(S.Id(), 1, 4, unique=True), desc="同场的人物模板 ID"),
        "tension_engine_ids": F(S.List(S.Id(), min_items=1, unique=True), desc="用到的张力引擎"),
        "chemistry": F(_str(1, 200), desc="人物之间的化学反应，用 {槽位.name}"),
        "stakes": F(
            S.Obj(
                {
                    "resource_gap": F(_str(1, 120), desc="资源差异"),
                    "limit_gap": F(_str(1, 120), desc="限制差异"),
                    "meeting_reason": F(_str(1, 120), desc="为什么会遇到"),
                    "irreplaceable_goal": F(_str(1, 120), desc="一条不可被替代的个人目标"),
                }
            )
        ),
        "relations": F(
            S.List(
                S.Obj(
                    {
                        "a": F(S.Id(), desc="player 或槽位"),
                        "b": F(S.Id(), desc="player 或槽位"),
                        "stage": F(S.Enum(*ST.STAGES)),
                        "a_to_b": F(EDGE_VALUES),
                        "b_to_a": F(EDGE_VALUES),
                        "reason": F(_str(1, 80)),
                    }
                ),
                min_items=1,
            )
        ),
        "tags": F(S.List(S.Id(), unique=True), required=False, default=[]),
    },
    name="人物组合",
)

ACTIVITY = S.Obj(
    {
        "id": F(S.Id()),
        "title": F(_str(1, 20)),
        "location_ids": F(S.List(S.Id(), min_items=1, unique=True), desc="可以发生的地点"),
        "duration_minutes": F(S.Int(5, 600), desc="时长（分钟）"),
        "beats": F(S.List(_str(1, 80), min_items=2), desc="活动里会发生的小事"),
        "hook_ids": F(S.List(S.Id(), unique=True), required=False, default=[], desc="偏好的钩子"),
        "start_minute": F(S.Nullable(S.Int(0, 1439)), required=False, default=None, desc="开局时刻（从零点起的分钟）；省略时用世界的起始时刻"),
        "tags": F(S.List(S.Id(), unique=True), required=False, default=[]),
    },
    name="日常活动",
)

PRESSURE = S.Obj(
    {
        "id": F(S.Id()),
        "title": F(_str(1, 20)),
        "source": F(S.Enum(*ST.PRESSURE_SOURCES), desc="压力来自哪里"),
        "flags": F(S.List(S.Enum(*ST.PRESSURE_FLAGS), unique=True), required=False, default=[], desc="timed 有明确倒计时；leverage 一方握有另一方的把柄或生计"),
        "location_ids": F(S.List(S.Id(), min_items=1, unique=True), desc="可以发生的地点"),
        "trigger": F(_str(1, 120), desc="发生了什么"),
        "objective": F(_str(1, 120), desc="要在什么之前做到什么"),
        "choice": F(_str(1, 120), desc="真正的两难"),
        "immediate": F(S.Obj({"text": F(_str(1, 120)), "minutes": F(S.Int(1, 240), desc="本场景的时长")}), desc="立即层：本场景内看得见的压力"),
        "near": F(S.Obj({"text": F(_str(1, 120)), "deadline_minutes": F(S.Int(1, 4320), desc="从开局算起，大于 immediate.minutes")}), desc="近期层：带期限"),
        "far": F(S.Obj({"trigger": F(_str(1, 120)), "consequence": F(_str(1, 120)), "due_days": F(S.Int(1, 30), desc="几天后")}), desc="远期层：开局只作伏笔"),
        "exits": F(S.List(EXIT_OPTION, min_items=2), desc="出路，至少两条，各有代价"),
        "leverage": F(
            S.Nullable(S.Obj({"holder": F(S.Id()), "subject": F(S.Id()), "basis": F(_str(1, 120), desc="构成把柄的一句事实")})),
            required=False,
            default=None,
            desc="带 leverage 标记时必填：holder、subject 取槽位或 player",
        ),
        "hook_ids": F(S.List(S.Id(), unique=True), required=False, default=[], desc="偏好的钩子"),
        "start_minute": F(S.Nullable(S.Int(0, 1439)), required=False, default=None, desc="开局时刻（从零点起的分钟）；省略时用世界的起始时刻"),
        "tags": F(S.List(S.Id(), unique=True), required=False, default=[]),
    },
    name="压力",
)

HOOK = S.Obj(
    {
        "id": F(S.Id()),
        "kind": F(S.Enum(*ST.HOOK_KINDS), desc="approach 非交易性的靠近（优先）；observe；request；accident"),
        "slot": F(S.Id(), desc="发出钩子的人物模板 ID"),
        "location_ids": F(S.List(S.Id(), unique=True), required=False, default=[], desc="只在这些地点；省略表示不限"),
        "text": F(_str(1, 120), desc="开局收尾的动作，用 {npc.name}"),
    },
    name="钩子",
)
TWIST = S.Obj(
    {
        "id": F(S.Id()),
        "category": F(S.Enum(*ST.TWIST_CATEGORIES)),
        "requires": F(S.List(S.Str(1, 40), unique=True), required=False, default=[], desc="前提：pressure 或 daily（只在该模式）、人物模板 ID（该人物在局）、压力 ID"),
        "text": F(_str(1, 160)),
    },
    name="转折",
)

WORLD = S.Obj(
    {
        "schema_version": F(S.Int(1, 1)),
        "id": F(S.Id()),
        "title": F(_str(1, 20)),
        "extends": F(S.Nullable(S.Id()), required=False, default=None, desc="时代底包 ID，编译期展开；自定义世界不写"),
        "custom": F(S.Bool(), required=False, default=False, desc="自定义世界必须为 true"),
        "era": F(_str(1, 40), desc="具体的时代"),
        "region": F(_str(1, 40), desc="具体的地方"),
        "premise": F(_str(1, 200), desc="人为什么同在此处、一天怎么过"),
        "tone": F(S.List(_str(1, 12), 1, 8), desc="基调词"),
        "style_hint": F(_str(1, 120), desc="一句写给叙事者的文风提示，具体到句式或感官"),
        "clock_start": F(
            S.Obj(
                {
                    "label": F(S.Nullable(_str(1, 40)), required=False, default=None, desc="起始日的显示标签"),
                    "minute": F(S.Int(0, 1439), desc="开局时刻：从零点起的分钟（1140 即 19:00）"),
                }
            )
        ),
        "clock_style": F(S.Enum("hm", "shichen"), required=False, default="hm", desc="hm 显示 19:00；shichen 显示时辰"),
        "default_person": F(S.Enum(*ST.PERSONS), required=False, default="second", desc="叙述人称"),
        "default_npc_gender_mix": F(
            S.Obj(
                {
                    "female": F(S.Num(0, 1)),
                    "male": F(S.Num(0, 1)),
                    "nonbinary": F(S.Num(0, 1), required=False, default=0.0),
                }
            ),
            desc="性别可变的人物按这个比例定性别，之和为 1",
        ),
        "stage_labels": F(
            S.Nullable(S.Obj({stage: F(_str(1, 8), required=False) for stage in ST.STAGES})),
            required=False,
            default=None,
            desc="按本世界的说法给关系阶段改名",
        ),
        "name_pools": F(
            S.Obj(
                {
                    "family": F(S.List(_str(1, 4), unique=True)),
                    "given_female": F(S.List(_str(1, 4), unique=True)),
                    "given_male": F(S.List(_str(1, 4), unique=True)),
                    "given_neutral": F(S.List(_str(1, 4), unique=True)),
                    "nickname_patterns": F(S.List(NAME_PATTERN), desc="昵称规则，例如 小{family}"),
                }
            )
        ),
        "rules": F(S.List(RULE), required=False, default=[], desc="影响剧情的世界规则"),
        "customs": F(S.List(_str(1, 200)), required=False, default=[], desc="可以直接写进正文的风俗与礼节"),
        "player_identities": F(S.List(IDENTITY), required=False, default=[], desc="玩家身份池；玩家没指定时从这里抽"),
        "locations": F(S.List(LOCATION), required=False, default=[], desc="地点档案"),
        "character_templates": F(S.List(TEMPLATE), required=False, default=[], desc="主要人物；具体姓名与年龄开局时生成"),
        "background_cast": F(S.List(BACKGROUND), required=False, default=[], desc="背景人物：只有角色与功能，可以被升格"),
        "channels": F(S.List(CHANNEL), required=False, default=[], desc="消息传播的路径"),
        "tension_engines": F(S.List(ENGINE), required=False, default=[], desc="张力引擎"),
        "cast_combos": F(S.List(COMBO), required=False, default=[], desc="谁和谁同场"),
        "daily_activities": F(S.List(ACTIVITY), required=False, default=[], desc="日常模式的开局活动"),
        "pressures": F(S.List(PRESSURE), required=False, default=[], desc="压力模式的开局压力"),
        "hooks": F(S.List(HOOK), required=False, default=[], desc="开局收尾的钩子"),
        "twists": F(S.List(TWIST), required=False, default=[], desc="转折候选"),
        "forbidden_terms": F(S.List(_str(1, 20), unique=True), required=False, default=[], desc="本世界不该出现的词"),
        "content_tags": F(S.List(S.Id(), unique=True), required=False, default=[], desc="本世界涉及的内容标签"),
        "status": F(S.Enum("draft", "review", "released"), desc="自定义世界写 draft"),
        "notes": F(S.Str(0, 2000), required=False, default="", desc="作者备注，运行时不读"),
    },
    name="世界包",
)

PLACEHOLDER_JUNK = {"—", "-", "--", "待补", "待定", "TODO", "TBD", "todo", "tbd", "...", "……", "无", "暂无", "占位", "xxx", "XXX", "N/A"}
MINOR_TERMS = ("学生", "师生", "校园", "学徒", "徒弟", "门生", "弟子", "少年", "少女", "幼", "童")
ADULT_MARKERS = ("成年", "成人", "研究生", "夜校", "驻留", "年满", "已婚", "正式工", "正式雇员", "持证")

# Names of real people and well-known fictional characters that must never
# appear (CONTENT_BIBLE.md section 6). Best effort; extended as found.
DENIED_NAMES = (
    "鲁迅",
    "孙中山",
    "蒋介石",
    "毛泽东",
    "周恩来",
    "邓小平",
    "张爱玲",
    "梅兰芳",
    "坂本龙马",
    "近藤勇",
    "土方岁三",
    "冲田总司",
    "西乡隆盛",
    "胜海舟",
    "德川庆喜",
    "贾宝玉",
    "林黛玉",
    "薛宝钗",
    "孙悟空",
    "猪八戒",
    "哈利",
    "福尔摩斯",
    "柯南",
    "路飞",
    "鸣人",
    "黄飞鸿",
    "叶问",
    "李小龙",
    "周星驰",
    "刘德华",
    "张国荣",
    "梅艳芳",
    "李嘉欣",
    "李丽珊",
    "苏永康",
    "黄家驹",
    "周润发",
    "梁朝伟",
    "张学友",
    "郭富城",
    "王菲",
    "陈少华",
    "陈慧娴",
    "叶倩文",
    "谭咏麟",
    "陈百强",
    "梁咏琪",
    "郑秀文",
    "陈奕迅",
    "翁美玲",
    "周慧敏",
    "黄日华",
    "成龙",
    "李连杰",
    "甄子丹",
    # 1920s treaty ports
    "杜月笙",
    "黄金荣",
    "张啸林",
    "徐志摩",
    "陆小曼",
    "阮玲玉",
    "胡适",
    "宋美龄",
    "宋庆龄",
    "张学良",
    "袁世凯",
    # Bakumatsu Kyoto
    "桂小五郎",
    "高杉晋作",
    "吉田松阴",
    "久坂玄瑞",
    "中冈慎太郎",
    "冈田以藏",
    "芹泽鸭",
    "永仓新八",
    "山南敬助",
    "岩仓具视",
    "孝明天皇",
    "松平容保",
    "德川家茂",
    # well-known folk-tale and fantasy works
    "聂小倩",
    "宁采臣",
    "白素贞",
    "许仙",
    "法海",
    "哪吒",
    "犬夜叉",
    "夏目贵志",
    "千寻",
    "无脸男",
)

SENTENCE_SPLIT = re.compile(r"[。！？；!?;\n]")
ITEM_PATH_RE = re.compile(r"\$\.(\w+)\[(\d+)\]")

# Fields the opening copies onto the character card or scene as written, so
# a placeholder in them would reach the player unrendered.
SHOWN_AS_WRITTEN = {
    "character_templates": ("adult_context", "public_role", "gender_reason"),
    "background_cast": ("adult_context", "role", "name"),
    "daily_activities": ("title",),
}


def _field_after(path, match):
    rest = path[match.end():].lstrip(".")
    return re.split(r"[.\[]", rest, 1)[0]


def _shown_as_written(path):
    match = re.match(r"\$\.(\w+)\[(\d+)\]", path)
    return bool(match) and _field_after(path, match) in SHOWN_AS_WRITTEN.get(match.group(1), ())
NEAR_DUP_THRESHOLD = 0.85
NEAR_DUP_MIN_LEN = 16


def _problem(path, reason, hint=None):
    return detail(path, reason, hint, CONTENT_ERROR)


def walk_texts(pack):
    """Yield (path, text) for every string in the pack except ids and enums."""
    skip_keys = {
        "id",
        "schema_version",
        "extends",
        "status",
        "notes",
        "gender",
        "privacy",
        "fidelity",
        "function",
        "kind",
        "category",
        "power_structure",
        "social_position",
        "source",
        "slot",
        "stage",
        "a",
        "b",
        "holder",
        "subject",
        "clock_style",
        "default_person",
        "forbidden_terms",
        "content_tags",
        "tags",
        "flags",
        "requires",
        "slots",
        "tension_engine_ids",
        "location_ids",
        "hook_ids",
        "exits",
        "witnesses",
        "location_id",
        "player_positions",
        "identity_ids",
    }

    def rec(node, path, key):
        if isinstance(node, str):
            if key not in skip_keys:
                yield path, node
        elif isinstance(node, dict):
            for k, v in node.items():
                if k in skip_keys and not (k == "exits" and isinstance(v, list) and v and isinstance(v[0], dict)):
                    continue
                if k == "pressure_modifiers":
                    for pk, pv in v.items():
                        yield "%s.%s.%s" % (path, k, pk), pv
                    continue
                yield from rec(v, "%s.%s" % (path, k), k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from rec(v, "%s[%d]" % (path, i), key)

    yield from rec(pack, "$", None)


def _ids(items):
    return [item["id"] for item in items]


class _Checker:
    def __init__(self, pack, custom):
        self.pack = pack
        self.custom = custom
        self.minimums = ST.CUSTOM_MINIMUMS if custom else ST.FULL_MINIMUMS
        self.problems = []
        self.templates = {t["id"]: t for t in pack["character_templates"]}
        self.locations = {loc["id"]: loc for loc in pack["locations"]}
        self.background = {b["id"]: b for b in pack["background_cast"]}
        self.hooks = {h["id"]: h for h in pack["hooks"]}
        self.pressures = {p["id"]: p for p in pack["pressures"]}
        self.engines = {e["id"]: e for e in pack["tension_engines"]}

    def add(self, path, reason, hint=None):
        self.problems.append(_problem(path, reason, hint))

    # -- counts --------------------------------------------------------------

    def counts(self):
        p, m = self.pack, self.minimums
        pools = p["name_pools"]
        checks = [
            ("$.rules", len(p["rules"]), m["rules"], "世界规则"),
            ("$.customs", len(p["customs"]), m["customs"], "风俗"),
            ("$.name_pools.family", len(pools["family"]), m["family"], "姓"),
            ("$.name_pools.given_female", len(pools["given_female"]), m["given_female"], "女性名"),
            ("$.name_pools.given_male", len(pools["given_male"]), m["given_male"], "男性名"),
            ("$.name_pools.given_neutral", len(pools["given_neutral"]), m["given_neutral"], "中性名"),
            ("$.name_pools.nickname_patterns", len(pools["nickname_patterns"]), m["nickname_patterns"], "昵称规则"),
            ("$.player_identities", len(p["player_identities"]), m["player_identities"], "玩家身份"),
            ("$.locations", len(p["locations"]), m["locations"], "地点"),
            ("$.character_templates", len(p["character_templates"]), m["character_templates"], "人物模板"),
            ("$.background_cast", len(p["background_cast"]), m["background_cast"], "背景人物"),
            ("$.channels", len(p["channels"]), m["channels"], "关系渠道"),
            ("$.tension_engines", len(p["tension_engines"]), m["tension_engines"], "张力引擎"),
            ("$.cast_combos", len(p["cast_combos"]), m["cast_combos"], "人物组合"),
            ("$.daily_activities", len(p["daily_activities"]), m["daily_activities"], "日常活动"),
            ("$.pressures", len(p["pressures"]), m["pressures"], "压力"),
            ("$.hooks", len(p["hooks"]), m["hooks"], "钩子"),
            ("$.twists", len(p["twists"]), m["twists"], "转折"),
        ]
        for path, have, need, label in checks:
            if have < need:
                self.add(path, "%s数量不足：%d < %d" % (label, have, need), "补到至少 %d 条（下限是地板，不是目标）" % need)
        if self.custom:
            total = len(pools["given_female"]) + len(pools["given_male"]) + len(pools["given_neutral"])
            if total < m["given_total"]:
                self.add("$.name_pools", "名字数量不足：%d < %d" % (total, m["given_total"]), "至少给 %d 个名" % m["given_total"])
            if len(p["daily_activities"]) < m["mode_items"] and len(p["pressures"]) < m["mode_items"]:
                self.add("$.daily_activities", "日常活动或压力至少要有一种达到 %d 条" % m["mode_items"], "按要开的模式补齐")
        functions = {b["function"] for b in p["background_cast"]}
        if len(functions) < m["background_functions"]:
            self.add("$.background_cast", "背景人物只覆盖 %d 种功能，至少 %d 种" % (len(functions), m["background_functions"]), "witness/messenger/obstacle/rumor_source/helper")
        categories = {t["category"] for t in p["twists"]}
        if len(categories) < m["twist_categories"]:
            self.add("$.twists", "转折只覆盖 %d 类，至少 %d 类" % (len(categories), m["twist_categories"]), "七类：%s" % "、".join(ST.TWIST_CATEGORIES))
        if not self.custom:
            structures = {c["power_structure"] for c in p["cast_combos"]}
            missing = [s for s in ST.POWER_STRUCTURES if s not in structures]
            if missing:
                self.add("$.cast_combos", "人物组合没有覆盖全部权力结构，缺少：%s" % "、".join(missing), "四种都要有：player_high、npc_high、equal、switchable")
            positions = {i["social_position"] for i in p["player_identities"]}
            missing = [s for s in ST.SOCIAL_POSITIONS if s not in positions]
            if missing:
                self.add("$.player_identities", "玩家身份没有覆盖全部社会位置，缺少：%s" % "、".join(missing), "low、equal、high 各至少一个")
            fidelities = {c["fidelity"] for c in p["channels"]}
            if fidelities != {"exact", "distorted"}:
                self.add("$.channels", "关系渠道需要至少一个精确、一个走样", "fidelity 取 exact 与 distorted")
            approach = sum(1 for h in p["hooks"] if h["kind"] == "approach")
            if p["hooks"] and approach * 2 <= len(p["hooks"]):
                self.add("$.hooks", "钩子应以 approach（非交易性的靠近）为主：%d/%d" % (approach, len(p["hooks"])), "增加 approach 类钩子")

    # -- identity, uniqueness, references -------------------------------------

    def uniqueness(self):
        seen = {}
        groups = (
            "rules",
            "player_identities",
            "locations",
            "character_templates",
            "background_cast",
            "channels",
            "tension_engines",
            "cast_combos",
            "daily_activities",
            "pressures",
            "hooks",
            "twists",
        )
        for group in groups:
            for index, item in enumerate(self.pack[group]):
                path = "$.%s[%d].id" % (group, index)
                if item["id"] == "player":
                    self.add(path, "ID player 是保留字", "换一个 ID")
                if item["id"] in seen:
                    self.add(path, "ID 重复：%s（已用于 %s）" % (item["id"], seen[item["id"]]), "同一世界包内的 ID 必须唯一")
                else:
                    seen[item["id"]] = path
        pools = self.pack["name_pools"]
        names = pools["given_female"] + pools["given_male"] + pools["given_neutral"]
        dup = {n for n in names if names.count(n) > 1}
        for name in sorted(dup):
            self.add("$.name_pools", "名字在多个名池里重复：%s" % name, "每个名只放进一个名池")

    def references(self):
        p = self.pack
        for i, loc in enumerate(p["locations"]):
            for j, target in enumerate(loc["exits"]):
                if target not in self.locations:
                    self.add("$.locations[%d].exits[%d]" % (i, j), "出口指向不存在的地点：%s" % target, "改成已有地点的 ID")
                elif target == loc["id"]:
                    self.add("$.locations[%d].exits[%d]" % (i, j), "出口指向自己", None)
                elif loc["id"] not in self.locations[target]["exits"]:
                    self.add("$.locations[%d].exits[%d]" % (i, j), "出口不是双向的：%s 没有回到 %s 的出口" % (target, loc["id"]), "在对方的 exits 里补上")
            for j, witness in enumerate(loc["witnesses"]):
                if witness not in self.background:
                    self.add("$.locations[%d].witnesses[%d]" % (i, j), "目击者不是背景人物：%s" % witness, "引用 background_cast 的 ID")
            for key in loc["pressure_modifiers"]:
                if key not in self.pressures:
                    self.add("$.locations[%d].pressure_modifiers.%s" % (i, key), "压力不存在：%s" % key, "引用 pressures 的 ID")
        self._connectivity()
        for i, bg in enumerate(p["background_cast"]):
            for j, loc in enumerate(bg["location_ids"]):
                if loc not in self.locations:
                    self.add("$.background_cast[%d].location_ids[%d]" % (i, j), "地点不存在：%s" % loc, None)
        for i, tpl in enumerate(p["character_templates"]):
            for j, slot in enumerate(tpl["schedule"]):
                if slot["location_id"] not in self.locations:
                    self.add("$.character_templates[%d].schedule[%d].location_id" % (i, j), "地点不存在：%s" % slot["location_id"], None)
        combo_slots = set()
        for i, combo in enumerate(p["cast_combos"]):
            base = "$.cast_combos[%d]" % i
            for j, slot in enumerate(combo["slots"]):
                combo_slots.add(slot)
                if slot not in self.templates:
                    self.add("%s.slots[%d]" % (base, j), "槽位不是人物模板：%s" % slot, "引用 character_templates 的 ID")
            identities = {i["id"]: i for i in p["player_identities"]}
            for j, ident in enumerate(combo["identity_ids"]):
                if ident not in identities:
                    self.add("%s.identity_ids[%d]" % (base, j), "玩家身份不存在：%s" % ident, None)
                elif identities[ident]["social_position"] not in combo["player_positions"]:
                    self.add("%s.identity_ids[%d]" % (base, j), "身份 %s 的社会位置不在 player_positions 里" % ident, None)
            if not self.custom and not [
                i for i in p["player_identities"]
                if i["social_position"] in combo["player_positions"] and (not combo["identity_ids"] or i["id"] in combo["identity_ids"])
            ]:
                self.add("%s.player_positions" % base, "没有任何玩家身份适合这个组合", None)
            for j, engine in enumerate(combo["tension_engine_ids"]):
                if engine not in self.engines:
                    self.add("%s.tension_engine_ids[%d]" % (base, j), "张力引擎不存在：%s" % engine, None)
            members = ["player"] + list(combo["slots"])
            covered = set()
            for j, rel in enumerate(combo["relations"]):
                for end in ("a", "b"):
                    if rel[end] not in members:
                        self.add("%s.relations[%d].%s" % (base, j, end), "关系一端不在组合里：%s" % rel[end], "只能是 player 或本组合的槽位")
                pair = frozenset((rel["a"], rel["b"]))
                if len(pair) != 2:
                    self.add("%s.relations[%d]" % (base, j), "关系两端相同", None)
                if pair in covered:
                    self.add("%s.relations[%d]" % (base, j), "同一对人物的关系写了两次", None)
                covered.add(pair)
            for x in range(len(members)):
                for y in range(x + 1, len(members)):
                    if frozenset((members[x], members[y])) not in covered:
                        self.add("%s.relations" % base, "缺少 %s 与 %s 之间的初始关系" % (members[x], members[y]), "开局时每一对人物都要有关系边与一句原因")
        for i, act in enumerate(p["daily_activities"]):
            for j, loc in enumerate(act["location_ids"]):
                if loc not in self.locations:
                    self.add("$.daily_activities[%d].location_ids[%d]" % (i, j), "地点不存在：%s" % loc, None)
            for j, hook in enumerate(act["hook_ids"]):
                if hook not in self.hooks:
                    self.add("$.daily_activities[%d].hook_ids[%d]" % (i, j), "钩子不存在：%s" % hook, None)
        for i, pr in enumerate(p["pressures"]):
            base = "$.pressures[%d]" % i
            for j, loc in enumerate(pr["location_ids"]):
                if loc not in self.locations:
                    self.add("%s.location_ids[%d]" % (base, j), "地点不存在：%s" % loc, None)
            for j, hook in enumerate(pr["hook_ids"]):
                if hook not in self.hooks:
                    self.add("%s.hook_ids[%d]" % (base, j), "钩子不存在：%s" % hook, None)
        for i, hook in enumerate(p["hooks"]):
            for j, loc in enumerate(hook["location_ids"]):
                if loc not in self.locations:
                    self.add("$.hooks[%d].location_ids[%d]" % (i, j), "地点不存在：%s" % loc, None)
            if hook["slot"] not in self.templates:
                self.add("$.hooks[%d].slot" % i, "钩子的槽位不是人物模板：%s" % hook["slot"], None)
            elif hook["slot"] not in combo_slots:
                self.add("$.hooks[%d].slot" % i, "没有任何人物组合包含槽位 %s，这个钩子永远用不上" % hook["slot"], None)
        tokens = {"pressure", "daily"} | set(self.templates) | set(self.pressures)
        for i, twist in enumerate(p["twists"]):
            for j, token in enumerate(twist["requires"]):
                if token not in tokens:
                    self.add("$.twists[%d].requires[%d]" % (i, j), "前提无法解析：%s" % token, "可用：pressure、daily、人物模板 ID、压力 ID")
            if "pressure" in twist["requires"] and "daily" in twist["requires"]:
                self.add("$.twists[%d].requires" % i, "同时要求 pressure 与 daily，永远不会出现", None)

    def _connectivity(self):
        ids = list(self.locations)
        if not ids:
            return
        seen = {ids[0]}
        frontier = [ids[0]]
        while frontier:
            current = frontier.pop()
            for nxt in self.locations[current]["exits"]:
                if nxt in self.locations and nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        unreachable = [loc for loc in ids if loc not in seen]
        if unreachable:
            self.add("$.locations", "地点之间不连通：%s 到不了" % "、".join(unreachable), "补出口，让所有地点互相连通")

    # -- semantics ------------------------------------------------------------

    def semantics(self):
        p = self.pack
        for group in ("character_templates", "background_cast", "player_identities"):
            for i, item in enumerate(p[group]):
                lo, hi = item["age_range"]
                if lo < 18:
                    self.add("$.%s[%d].age_range" % (group, i), "年龄下限 %d 小于 18" % lo, "所有角色都必须是明确的成年人")
                if lo > hi:
                    self.add("$.%s[%d].age_range" % (group, i), "年龄范围倒置：%d > %d" % (lo, hi), None)
        for i, tpl in enumerate(p["character_templates"]):
            base = "$.character_templates[%d]" % i
            if tpl["gender"] != "any" and not tpl["gender_reason"]:
                self.add("%s.gender_reason" % base, "固定性别的人物模板必须写明叙事理由", "否则用 gender: any 并在文本里用 {npc.ta}")
            for key in ("desire_range", "self_control_range"):
                lo, hi = tpl["intimacy_tendency"][key]
                if lo > hi:
                    self.add("%s.intimacy_tendency.%s" % (base, key), "范围倒置", None)
            for j, slot in enumerate(tpl["schedule"]):
                if slot["from"] == slot["to"]:
                    self.add("%s.schedule[%d]" % (base, j), "作息时段长度为零", None)
        for i, pr in enumerate(p["pressures"]):
            base = "$.pressures[%d]" % i
            if pr["near"]["deadline_minutes"] <= pr["immediate"]["minutes"]:
                self.add("%s.near.deadline_minutes" % base, "近期期限（%d 分钟）必须晚于立即层的场景时长（%d 分钟）" % (pr["near"]["deadline_minutes"], pr["immediate"]["minutes"]), None)
            has_flag = "leverage" in pr["flags"]
            if has_flag != (pr["leverage"] is not None):
                self.add("%s.leverage" % base, "flags 含 leverage 时必须声明 leverage（holder、subject、basis），反之亦然", None)
            if pr["leverage"]:
                lv = pr["leverage"]
                for end in ("holder", "subject"):
                    if lv[end] != "player" and lv[end] not in self.templates:
                        self.add("%s.leverage.%s" % (base, end), "把柄一方必须是 player 或人物模板：%s" % lv[end], None)
                if lv["holder"] == lv["subject"]:
                    self.add("%s.leverage" % base, "把柄的持有方与对象相同", None)
                needed = {lv["holder"], lv["subject"]} - {"player"}
                if not any(needed <= set(c["slots"]) for c in p["cast_combos"]):
                    self.add("%s.leverage" % base, "没有任何人物组合同时包含把柄双方，这个压力永远无法开局", None)
        mix = p["default_npc_gender_mix"]
        total = mix["female"] + mix["male"] + mix["nonbinary"]
        if abs(total - 1.0) > 0.01:
            self.add("$.default_npc_gender_mix", "性别分布之和应为 1，实际 %.2f" % total, None)
        if p["stage_labels"]:
            labels = list(p["stage_labels"].values())
            if len(set(labels)) != len(labels):
                self.add("$.stage_labels", "阶段名称重复", None)
        locs = p["locations"]
        privacies = {loc["privacy"] for loc in locs}
        if locs and ("public" not in privacies or not privacies & {"semi", "private"}):
            self.add("$.locations", "地点至少要有一个 public，以及一个 semi 或 private", None)
        signatures = {}
        for i, loc in enumerate(locs):
            key = (loc["privacy"], loc["visibility"], tuple(sorted(loc["affordances"])))
            if key in signatures:
                self.add("$.locations[%d]" % i, "与 %s 的 privacy、visibility、affordances 完全相同" % signatures[key], "让每个地点有自己的用法")
            signatures[key] = loc["id"]
        self._openability()

    def _openability(self):
        """Every combo must be able to open in the modes the pack offers."""
        p = self.pack
        for i, combo in enumerate(p["cast_combos"]):
            slots = set(combo["slots"])
            hooks = [h for h in p["hooks"] if h["slot"] in slots]
            if not hooks:
                self.add("$.cast_combos[%d]" % i, "没有任何钩子属于这个组合的槽位", "为组合里的人物写至少一个钩子")
                continue
            if p["daily_activities"] and not any(
                not act["hook_ids"] or any(h["id"] in act["hook_ids"] for h in hooks) for act in p["daily_activities"]
            ):
                self.add("$.cast_combos[%d]" % i, "日常模式下没有能与这个组合配上的活动与钩子", None)
            if p["pressures"]:
                usable = [
                    pr
                    for pr in p["pressures"]
                    if (not pr["leverage"] or ({pr["leverage"]["holder"], pr["leverage"]["subject"]} - {"player"}) <= slots)
                    and (not pr["hook_ids"] or any(h["id"] in pr["hook_ids"] for h in hooks))
                ]
                if not usable:
                    self.add("$.cast_combos[%d]" % i, "压力模式下没有能与这个组合配上的压力与钩子", None)

    # -- text ------------------------------------------------------------------

    def text_checks(self):
        p = self.pack
        template_gender = {t["id"]: t["gender"] for t in p["character_templates"]}
        seen_sentences = {}
        for path, text in walk_texts(p):
            stripped = text.strip()
            if stripped in PLACEHOLDER_JUNK or stripped.lower() == path.rsplit(".", 1)[-1].split("[")[0].lower():
                self.add(path, "占位式内容：%r" % text, "写成真正可以进入回合的内容")
            for brace in stray_braces(text):
                self.add(path, "无法识别的占位：%s" % brace, "可用：{npc.name}、{npc.ta}、{槽位.name}、{player.name} 等")
            allowed = self._scopes_for(path)
            for scope, attr in placeholders(text):
                if scope is None:
                    if not (".nickname_patterns" in path or ".title_patterns" in path):
                        self.add(path, "{%s} 只能用在称呼模板里" % attr, None)
                    continue
                if scope not in allowed:
                    if path.startswith("$.twists[") and scope in self.templates:
                        hint = "把 %s 写进这个转折的 requires，它只在这个人物在局时出现" % scope
                    elif _shown_as_written(path):
                        hint = "这个字段原样显示，不做占位替换；直接写，不用代词"
                    else:
                        hint = "这里可用的作用域：%s" % ("、".join(sorted(allowed)) or "无")
                    self.add(path, "占位 {%s.%s} 在这里无法解析" % (scope, attr), hint)
                elif attr not in ("name", "ta", "family", "given", "call", "role", "title", "称呼"):
                    self.add(path, "未知占位属性：%s" % attr, "可用：name、ta、family、given、call、role、title")
            if self._pronoun_checked(path, template_gender) and gendered_pronoun_positions(text):
                self.add(path, "可变性别的文本里写死了“他/她”：%s" % text[:40], "用 {npc.ta} 或 {槽位.ta} 代替，或直接写名字")
            if path.endswith(".pattern"):
                continue
            for sentence in SENTENCE_SPLIT.split(text):
                sentence = sentence.strip()
                if len(sentence) >= 8:
                    if sentence in seen_sentences and seen_sentences[sentence] != path:
                        self.add(path, "与 %s 重复整句：%s" % (seen_sentences[sentence], sentence[:30]), "同一包内不写重复的句子")
                    seen_sentences.setdefault(sentence, path)

    def _scopes_for(self, path):
        p = self.pack
        match = re.match(r"\$\.(\w+)\[(\d+)\]", path)
        if not match:
            return set()
        group, index = match.group(1), int(match.group(2))
        if _field_after(path, match) in SHOWN_AS_WRITTEN.get(group, ()):
            return set()
        item = p[group][index]
        if group in ("character_templates", "background_cast"):
            return {"npc", "player"}
        if group == "hooks":
            return {"npc", "player", item["slot"]}
        if group == "cast_combos":
            return {"player"} | set(item["slots"])
        if group == "twists":
            # A twist is offered only when the characters in `requires` are in
            # the game, so only those can be named in its text.
            return {"player"} | (set(item["requires"]) & set(self.templates))
        if group == "pressures":
            scopes = {"player"}
            if item["leverage"]:
                scopes |= {item["leverage"]["holder"], item["leverage"]["subject"]}
            return scopes
        if group in ("daily_activities",):
            return {"player"}
        return set()

    def _pronoun_checked(self, path, template_gender):
        match = re.match(r"\$\.(\w+)\[(\d+)\]", path)
        if match and match.group(1) in ("character_templates", "background_cast"):
            item = self.pack[match.group(1)][int(match.group(2))]
            return item["gender"] == "any"
        return True

    def forbidden_terms(self):
        terms = self.pack["forbidden_terms"]
        for path, text in walk_texts(self.pack):
            for term in terms:
                if term in text:
                    self.add(path, "出现本世界的禁用词“%s”" % term, "这个词不属于本世界的时代与地域")
            for name in DENIED_NAMES:
                if name in text:
                    self.add(path, "出现真实人物或已知作品角色的名字“%s”" % name, "换成原创名字")
            if any(term in text for term in MINOR_TERMS):
                context = text + self._adult_context_for(path)
                if not any(marker in context for marker in ADULT_MARKERS):
                    self.add(path, "出现校园、师生、学徒类意象却没有明示成年语境：%s" % text[:30], "写明成年身份（如成人夜校、研究生、年满十八的正式学徒）")
        pools = self.pack["name_pools"]
        full_names = set()
        for family in pools["family"]:
            for given in pools["given_female"] + pools["given_male"] + pools["given_neutral"]:
                full_names.add(family + given)
        for name in DENIED_NAMES:
            if name in full_names:
                self.add("$.name_pools", "名池可能组合出真实人物或已知角色的名字：%s" % name, "从名池里去掉对应的姓或名")

    def _adult_context_for(self, path):
        match = re.match(r"\$\.(\w+)\[(\d+)\]", path)
        if match and match.group(1) in ("character_templates", "background_cast"):
            return self.pack[match.group(1)][int(match.group(2))].get("adult_context", "")
        return ""


def _tag_checks(pack, tag_ids):
    problems = []
    refs = [("$.content_tags[%d]" % i, t) for i, t in enumerate(pack["content_tags"])]
    for group in ("locations", "character_templates", "cast_combos", "daily_activities", "pressures"):
        for i, item in enumerate(pack[group]):
            refs.extend(("$.%s[%d].tags[%d]" % (group, i, j), t) for j, t in enumerate(item.get("tags", [])))
    for path, tag in refs:
        if tag not in tag_ids:
            problems.append(_problem(path, "未知内容标签：%s" % tag, "只能用标签表里的 ID"))
    return problems


def with_item_ids(problems, raw):
    """Name the entry each problem sits in ("item": its id), so an author can
    find it by id as well as by JSON path (ACCEPTANCE.md 3)."""
    for problem in problems:
        match = ITEM_PATH_RE.match(problem.get("path") or "")
        if not match or not isinstance(raw, dict):
            continue
        group, index = raw.get(match.group(1)), int(match.group(2))
        if isinstance(group, list) and index < len(group) and isinstance(group[index], dict):
            item_id = group[index].get("id")
            if isinstance(item_id, str):
                problem.setdefault("item", item_id)
    return problems


def validate_world(raw, custom=None, tag_ids=None):
    """Validate one pack. Returns (pack or None, problems)."""
    pack, problems = _validate_world(raw, custom, tag_ids)
    return pack, with_item_ids(problems, raw)


def _validate_world(raw, custom, tag_ids):
    pack, errors = S.validate(WORLD, raw)
    problems = [dict(e, code=CONTENT_ERROR) for e in errors]
    if pack is None:
        return None, problems
    if custom is None:
        custom = pack["custom"]
    if custom and not pack["custom"]:
        problems.append(_problem("$.custom", "自定义世界必须带 custom: true", None))
    checker = _Checker(pack, custom)
    checker.counts()
    checker.uniqueness()
    checker.references()
    checker.semantics()
    checker.text_checks()
    checker.forbidden_terms()
    problems.extend(checker.problems)
    if tag_ids is not None:
        problems.extend(_tag_checks(pack, tag_ids))
    return (pack if not problems else None), problems


def _bigrams(text):
    return {text[i : i + 2] for i in range(len(text) - 1)}


def near_duplicates(entries, threshold=NEAR_DUP_THRESHOLD, min_len=NEAR_DUP_MIN_LEN):
    """entries: list of (label, text). Returns pairs above the similarity threshold."""
    grams = [(label, text, _bigrams(text)) for label, text in entries if len(text) >= min_len]
    found = []
    for i in range(len(grams)):
        for j in range(i + 1, len(grams)):
            a, b = grams[i][2], grams[j][2]
            union = len(a | b)
            if not union:
                continue
            score = len(a & b) / union
            if score >= threshold and grams[i][1] != grams[j][1]:
                found.append((grams[i][0], grams[j][0], round(score, 3)))
    return found


def cross_checks(packs, generic_strings):
    """Checks across packs: generic layer vs every forbidden list; near duplicates."""
    problems = []
    for world_id, pack in packs.items():
        for term in pack["forbidden_terms"]:
            for text in generic_strings:
                if term in text:
                    problems.append(dict(_problem("generic", "通用结构层的文本“%s”含有世界 %s 的禁用词“%s”" % (text, world_id, term), "通用层只能放不带时代感的结构文本"), world="generic"))
    entries = []
    for world_id, pack in packs.items():
        for path, text in walk_texts(pack):
            if ".name_pools" in path or ".title_patterns" in path:
                continue
            entries.append(("%s %s" % (world_id, path), text))
    for left, right, score in near_duplicates(entries):
        world, path = right.split(" ", 1)
        found = _problem(path, "与 %s 高度相似（相似度 %.2f ≥ %.2f）" % (left, score, NEAR_DUP_THRESHOLD), "改写其中一条，避免同形框架")
        problems.append(dict(with_item_ids([found], packs[world])[0], world=world))
    return problems


def world_stats(pack):
    from collections import Counter

    return {
        "counts": {
            key: len(pack[key])
            for key in (
                "rules",
                "customs",
                "player_identities",
                "locations",
                "character_templates",
                "background_cast",
                "channels",
                "tension_engines",
                "cast_combos",
                "daily_activities",
                "pressures",
                "hooks",
                "twists",
            )
        },
        "names": {key: len(value) for key, value in pack["name_pools"].items()},
        "power_structures": dict(Counter(c["power_structure"] for c in pack["cast_combos"])),
        "twist_categories": dict(Counter(t["category"] for t in pack["twists"])),
        "hook_kinds": dict(Counter(h["kind"] for h in pack["hooks"])),
        "social_positions": dict(Counter(i["social_position"] for i in pack["player_identities"])),
        "background_functions": dict(Counter(b["function"] for b in pack["background_cast"])),
    }
