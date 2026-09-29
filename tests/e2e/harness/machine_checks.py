"""Machine checks for end-to-end records (ACCEPTANCE.md 6.2).

    python tests/e2e/harness/machine_checks.py <record.json> [--json]

Every check reads what the player saw (`text`) against what the engine did
(`runtime_calls`, the engine's own trace). A finding fails the record; the
script's `expect` annotations only tell the checks what kind of step each
turn is and which refusals are part of the script.

checks: the record (every turn finished, with a reply the player saw; every
runtime call the host made is in the trace and came from the Skill
installed for the run), structure (commits legal or
repaired, call budget, ACCEPTANCE 5),
leakage (field names, numbers, error codes, commands, revision), footer and
time words against the engine clock, ventriloquism (the player character's
lines come from the player), unknown people (a named person the engine
never heard of), repetition (the same sentence within 10 turns, the same
line twice in one scene).
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "skill", "adult-tension", "runtime"))
sys.path.insert(0, HERE)

import record as R  # noqa: E402

NARRATIVE_COMMANDS = ("new-game", "commit-turn")
WRITE_COMMANDS = ("new-game", "commit-turn", "undo-turn", "save-slot", "load-slot", "delete-slot", "set-boundary", "set-safety", "set-preferences", "import-save")
# Rejections the model hands to the player instead of correcting the call: a block it tells
# (NARRATIVE_RULES), a slot conflict it asks about (RUNTIME_PROTOCOL 9.2), an opening that
# cannot be had it owns up to (RUNTIME_PROTOCOL 4.3).
PLAYER_DECIDES_CODES = ("SAFETY_BLOCK", "SLOT_CONFLICT", "NO_MATCH")
EXTRA_CALLS_AFTER_REJECTION = 2
REPEAT_WINDOW = 10
MIN_SENTENCE = 10
FOOTER_RE = re.compile(r"【时间】(?P<time>[^｜\n]+)｜【地点】(?P<place>[^｜\n]+)｜回合：(?P<turn>\d+)(?:｜种子：(?P<seed>\d+))?")
RECEIPT_RE = re.compile(r"^(已保存|已另存为|已读取|已撤销|已记下|已暂停|已导出|已导入|已删除|内心可见|叙事助手|离屏推演|已恢复)")
HINT_RE = re.compile(r"^可以：")
NUMBER_LEAK_RE = re.compile(r"(信任|张力|好感度?|欲望值?|自制力?|亲密度|关系值|revision)\s*[:：]?\s*[+\-−]?\s*\d")
TIER_WORDS = ("结果档", "尝试档", "改写档", "继续档", "等待档")
# Engine vocabulary in Chinese: response labels and mechanism phrases.
MECHANISM_WORDS = ("有限配合", "表面配合", "真诚配合", "系统判定", "回合推进", "回合结算", "离屏推演", "引擎判定",
                   # the host telling the player what it does with the runtime (NARRATIVE_RULES: no tool calls in the text)
                   "会话状态", "载入会话", "提交回合", "回合行动", "工具调用", "调用工具", "调用运行时")
ENGINE_WORDS = ("revision", "request_id", "session_id", "expected_revision", "next_request_id", "known_by", "believed_by", "dedupe_key", "action_mode", "desire_level", "self_control")
SNAKE_RE = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]{3,}")
CJK_RE = re.compile(r"[一-鿿]")
QUOTE_RE = re.compile(r"“([^”]{2,})”")
PLAYER_SPEECH_RE = re.compile(r"(?:^|[。！？\n，、])\s*你[^。！？“\n]{0,12}?(?:说|问|道|答|喊|开口|低声|笑着|回了一句|接了一句)[^“\n]{0,6}“([^”]{2,})”")
# the line first, then who said it: “……”你的声音……, “……”你低声说
PLAYER_SPEECH_AFTER_RE = re.compile(r"“([^”]{2,})”[，,]?\s*你(的声音|[^。！？“”\n]{0,8}?(?:说|问|道|答|喊|开口|低声))")
NEGATIONS = ("没", "不", "未", "别")
# a sentence of the player's running into a colon and a line: 你深吸一口气，声音压得极沉：“……”
PLAYER_COLON_RE = re.compile(r"(?:^|[。！？])\s*你([^。！？“”\n]{0,60})[：:]\s*“([^”]{2,})”")
# ... unless someone else is in that sentence (你听见她说：“……”, 你看向秋山，秋山低声道：“……”)
OTHER_SPEAKERS = ("他", "她", "它", "对方", "有人", "众人")
# ... or the sentence says the sound came out of something (你腰间的对讲机爆出一阵杂音：“……”)
SOUND_FROM = ("传来", "传出", "响起", "响了", "爆出", "播出")
TIME_WORDS = {
    "凌晨": [(0, 6)],
    "清晨": [(4, 9)],
    "黎明": [(4, 7)],
    "早晨": [(5, 10)],
    "上午": [(7, 12)],
    "中午": [(11, 14)],
    "正午": [(11, 14)],
    "午后": [(12, 17)],
    "下午": [(12, 18)],
    "傍晚": [(16, 20)],
    "黄昏": [(16, 20)],
    "入夜": [(17, 24), (0, 2)],
    "深夜": [(21, 24), (0, 5)],
    "半夜": [(21, 24), (0, 5)],
    "午夜": [(22, 24), (0, 3)],
}
# A time word is held to the clock only where it says what time it is now.
# Text names other moments in open-ended ways ("天光早在傍晚就沉了底",
# "第三天上午十点就将开幕", "柜子是傍晚塞进来的", "包工头下午就联系不上了"),
# so the check looks for a claim about now instead of listing those:
# - narration: the time word opens a clause ("凌晨两点，风……", "你推开门，
#   傍晚的风灌进来"), or is marked as now;
# - dialogue: only when marked as now ("都凌晨了", "这大半夜的", "现在是傍晚");
#   people speak of schedules and earlier today, and round the hour.
# Marked as now: right after NOW_BEFORE or NOW_IS, or right before 了/啦.
CLAUSE_START_RE = re.compile(r"(?:^|[。！？；，：、…”」])\s*$")
NOW_BEFORE = ("这", "大", "这时", "此时", "此刻", "现在", "眼下", "已经", "已", "正值", "时值")
NOW_IS = ("现在是", "此刻是", "此时是", "已是", "正是")
NOW_AFTER = ("了", "啦")
# Even so, a time word next to one of these is about another moment ...
TIME_OTHER = ("昨", "明", "前", "后", "那天", "那晚", "今天", "今早", "等到", "到了", "直到", "刚才", "之前", "以前", "每天", "每晚", "每到", "天天", "那年", "当年", "上回", "下回", "约", "说好", "早在", "自从", "以来")
# ... and so is one that times some other event ("傍晚就回来", "凌晨才睡").
EVENT_AFTER = ("就", "才", "再", "便")
DIALOGUE_RE = re.compile(r"“[^”]*”?")
DIALOGUE_SLACK = 60


# The opening's first two lines say what the world and its people are
# (NARRATIVE_RULES 9): "凌晨两点所有人必须到控制塔签到" there is a rule of the
# world, not the time now.
OPENING_HEADS = ("世界观：", "人物：")


def _says_now(line, start, end, in_dialogue):
    """How the time word at line[start:end] claims to be the time now:
    "marked" (right after NOW_BEFORE or NOW_IS, or right before 了/啦),
    "clause" (narration where the word opens a clause), or None."""
    near = line[max(0, start - 4) : end + 2]
    if any(other in near for other in TIME_OTHER) or line[end : end + 1] in EVENT_AFTER:
        return None
    head = line[:start]
    if head.endswith(NOW_BEFORE) or head.endswith(NOW_IS) or line[end : end + 1] in NOW_AFTER:
        return "marked"
    if not in_dialogue and CLAUSE_START_RE.search(head) is not None:
        return "clause"
    return None


def _vocabulary():
    from adult_tension import errors
    from adult_tension.application import commands
    from adult_tension.domain import ops

    return {
        "commands": sorted(commands.COMMANDS, key=len, reverse=True),
        "ops": set(ops.SPECS),
        "codes": sorted(errors.ERROR_DESCRIPTIONS, key=len, reverse=True),
    }


VOCAB = _vocabulary()


def finding(check, turn, message):
    return {"check": check, "turn": turn, "message": message}


def narrative_calls(turn):
    return [c for c in turn.get("runtime_calls") or [] if R.command_of(c) in NARRATIVE_COMMANDS and R.ok_data(c) is not None]


def prose_lines(text):
    """The narrative part of a turn's text: no footer, receipts or hint lines."""
    out = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or FOOTER_RE.search(stripped) or RECEIPT_RE.match(stripped) or HINT_RE.match(stripped):
            continue
        out.append(stripped)
    return out


# -- structure and call budget ----------------------------------------------------------


def check_structure(record):
    out = []
    ordinary = []
    groups = {}
    for turn in record["turns"]:
        calls = turn.get("runtime_calls") or []
        expect = turn.get("expect") or {}
        index = turn["index"]
        commands = [R.command_of(c) for c in calls]
        for name in expect.get("must_call", []):
            if name not in commands:
                out.append(finding("structure", index, "这一步应当调用 %s，实际调用：%s" % (name, commands or "无")))
        for name in expect.get("must_not_call", []):
            if name in commands:
                out.append(finding("structure", index, "这一步不应当调用 %s" % name))
        rejections = [i for i, c in enumerate(calls) if R.command_of(c) in WRITE_COMMANDS and R.error_code(c)]
        if expect.get("budget_group"):
            group = groups.setdefault(expect["budget_group"], {"calls": 0, "max": expect.get("group_max"), "must": set(), "commands": set(), "turns": []})
            group["calls"] += len(calls)
            group["must"].update(expect.get("group_must_call", []))
            group["commands"].update(commands)
            group["turns"].append(index)
        budget = expect.get("calls_max")
        if budget is not None:
            allowed = budget + (EXTRA_CALLS_AFTER_REJECTION if rejections else 0)
            if len(calls) > allowed:
                out.append(finding("structure", index, "工具调用 %d 次，超过这一步的预算 %d（ACCEPTANCE §5）" % (len(calls), allowed)))
        if rejections:
            after = len(calls) - 1 - rejections[0]
            if after > EXTRA_CALLS_AFTER_REJECTION:
                out.append(finding("structure", index, "提交被拒后又调用了 %d 次，超过 %d 次的自动修正" % (after, EXTRA_CALLS_AFTER_REJECTION)))
            last_write = [c for c in calls if R.command_of(c) in WRITE_COMMANDS][-1]
            code = R.error_code(last_write)
            if code and code not in PLAYER_DECIDES_CODES and not expect.get("allow_reject"):
                out.append(finding("structure", index, "%s 被拒（%s）后没有修正成功" % (R.command_of(last_write), code)))
        for call in calls:
            if R.error_code(call) == "INTERNAL_ERROR":
                out.append(finding("structure", index, "运行时内部错误：%s" % (call.get("envelope") or {}).get("error", {}).get("message")))
        if expect.get("kind") == "turn":
            ordinary.append(len(calls))
    for name, group in groups.items():
        if group["max"] is not None and group["calls"] > group["max"]:
            out.append(finding("structure", group["turns"][-1], "%s 共调用 %d 次，超过 %d（ACCEPTANCE §5）" % (name, group["calls"], group["max"])))
        for command in sorted(group["must"] - group["commands"]):
            out.append(finding("structure", group["turns"][-1], "%s 里没有调用 %s（ACCEPTANCE §5：本对话第一次开局是 doctor + new-game）" % (name, command)))
    average = round(sum(ordinary) / float(len(ordinary)), 3) if ordinary else None
    return out, {"ordinary_turns": len(ordinary), "average_calls": average}


# -- leakage ---------------------------------------------------------------------------------


def check_leakage(record):
    out = []
    for turn in record["turns"]:
        index = turn["index"]
        narrative = bool(narrative_calls(turn))
        lines = prose_lines(turn.get("text"))
        text = "\n".join(lines)
        for name in VOCAB["codes"]:
            if name in text:
                out.append(finding("leakage", index, "正文里出现错误码 %s" % name))
        for name in VOCAB["commands"]:
            if re.search(r"(?<![A-Za-z_-])%s(?![A-Za-z_-])" % re.escape(name), text):
                out.append(finding("leakage", index, "正文里出现命令名 %s" % name))
        for word in SNAKE_RE.findall(text):
            if word in VOCAB["ops"] or word in ENGINE_WORDS:
                out.append(finding("leakage", index, "正文里出现字段或操作名 %s" % word))
        for word in ENGINE_WORDS:
            if "_" not in word and re.search(r"\b%s\b" % word, text, re.I):
                out.append(finding("leakage", index, "正文里出现引擎术语 %s" % word))
        # the host explaining its tool calls in English: a line with no Chinese outside what someone says
        for line in lines:
            bare = DIALOGUE_RE.sub("", line)
            if ENGLISH_WORD_RE.search(bare) and not CJK_RE.search(bare):
                out.append(finding("leakage", index, "正文里有一整行英文：%s" % line[:60]))
                break
        if narrative:
            match = NUMBER_LEAK_RE.search(text)
            if match:
                out.append(finding("leakage", index, "正文里出现数值：%s" % match.group(0)))
            for word in TIER_WORDS:
                if word in text:
                    out.append(finding("leakage", index, "正文里出现档位名 %s" % word))
            for word in MECHANISM_WORDS:
                if word in text:
                    out.append(finding("leakage", index, "正文里出现机制用语 %s" % word))
            # the opening format's placeholder copied as a heading
            if any(re.match(r"\**正文\**[:：]", line) for line in lines):
                out.append(finding("leakage", index, "正文前照抄了格式里的“正文：”"))
            if re.search(r"[{\[]\s*\"[a-z_]+\"\s*:", text):
                out.append(finding("leakage", index, "正文里出现 JSON"))
    return out


# -- footer and time words ---------------------------------------------------------------


def _clock_of(call):
    data = R.ok_data(call) or {}
    if R.command_of(call) == "new-game":
        opening = data.get("opening") or {}
        return opening.get("footer"), (data.get("context") or {}).get("clock")
    context = data.get("context") or {}
    return None, context.get("clock")


def _scheduled(call):
    """The minutes at which the events the engine told the model about fall due within
    the next day (the context's due_soon and events: "中午十二点落下裁决"); prose names a
    later one by its day ("第三天上午十点")."""
    context = (R.ok_data(call) or {}).get("context") or {}
    now = (context.get("clock") or {}).get("minute")
    if not isinstance(now, int):
        return []
    items = list(context.get("due_soon") or []) + list(context.get("events") or [])
    return [now + item["in_minutes"] for item in items if isinstance(item.get("in_minutes"), int) and 0 <= item["in_minutes"] < 1440]


CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_NUMBER = r"(?:\d{1,2}|[零〇一二两三四五六七八九十]{1,3})"
CLOCK_TIME_RE = re.compile(r"\s*(%s)\s*[点时]\s*(整|半|一刻|三刻|(%s)\s*分?)?" % (CN_NUMBER, CN_NUMBER))
QUARTERS = {"整": 0, "半": 30, "一刻": 15, "三刻": 45}


def _number(text):
    """0-59 written in digits or Chinese ("两", "十二", "二十", "五十五"), or None."""
    if text.isdigit():
        return int(text)
    tens, ten, ones = text.partition("十")
    if not ten:
        return CN_DIGITS.get(text) if len(text) == 1 else None
    if len(tens) > 1 or len(ones) > 1 or (tens and tens not in CN_DIGITS) or (ones and ones not in CN_DIGITS):
        return None
    return (CN_DIGITS[tens] if tens else 1) * 10 + (CN_DIGITS[ones] if ones else 0)


def _time_after(line, end):
    """The clock time named right after a time word, as (hour, minute): "中午十二点" ->
    (12, 0), "凌晨零时五十分" -> (0, 50), "下午3点半" -> (3, 30); None when there is none."""
    match = CLOCK_TIME_RE.match(line, end)
    if not match:
        return None
    hour = _number(match.group(1))
    minute = QUARTERS.get(match.group(2) or "整")
    if minute is None:
        minute = _number(match.group(3))
    if hour is None or minute is None:
        return None
    return hour, minute


def _names_scheduled(word, named, scheduled):
    """The time word with its clock time ("中午十二点") is when one of the scheduled events
    falls due, to within 5 minutes (on a 12-hour dial: the word says which half of the day)."""
    if named is None:
        return False
    at = (named[0] % 12) * 60 + named[1]
    return any(_hours_ok(word, m) and min(abs(at - m % 720), 720 - abs(at - m % 720)) <= 5 for m in scheduled)


def _hours_ok(word, minute, slack=0):
    """The clock minute falls within the word's hours, widened by slack minutes each side."""
    minute %= 1440
    return any((minute - (lo * 60 - slack)) % 1440 < (hi - lo) * 60 + 2 * slack for lo, hi in TIME_WORDS[word])


def check_footer_and_time(record):
    out = []
    before = None
    for turn in record["turns"]:
        index = turn["index"]
        calls = narrative_calls(turn)
        if not calls:
            continue
        last = calls[-1]
        data = R.ok_data(last)
        footer_expected, clock = _clock_of(last)
        found = [m for m in FOOTER_RE.finditer(turn.get("text") or "")]
        if not found:
            out.append(finding("footer", index, "叙事回合没有页脚"))
        else:
            got = found[-1]
            if footer_expected is not None:
                if got.group(0) != footer_expected:
                    out.append(finding("footer", index, "开局页脚与引擎给的不一致：%s ≠ %s" % (got.group(0), footer_expected)))
            else:
                context = data.get("context") or {}
                want_time = (context.get("clock") or {}).get("label")
                want_place = (context.get("scene") or {}).get("location")
                want_turn = str(data.get("turn"))
                if got.group("time").strip() != want_time:
                    out.append(finding("footer", index, "页脚时间 %s 与引擎时钟 %s 不一致" % (got.group("time").strip(), want_time)))
                if got.group("place").strip() != want_place:
                    out.append(finding("footer", index, "页脚地点 %s 与引擎的 %s 不一致" % (got.group("place").strip(), want_place)))
                if got.group("turn") != want_turn:
                    out.append(finding("footer", index, "页脚回合 %s 与引擎的 %s 不一致" % (got.group("turn"), want_turn)))
        if clock:
            minutes = [clock["minute"]] + ([before["minute"]] if before else [])
            scheduled = _scheduled(last)
            for line in prose_lines(turn.get("text")):
                if line.startswith(OPENING_HEADS):
                    continue
                dialogue = [m.span() for m in DIALOGUE_RE.finditer(line)]
                for word in TIME_WORDS:
                    for match in re.finditer(word, line):
                        in_dialogue = any(a < match.start() < b for a, b in dialogue)
                        claim = _says_now(line, match.start(), match.end(), in_dialogue)
                        if not claim:
                            continue
                        # an unmarked clause naming the hour the engine has scheduled something for is
                        # about that ("中午十二点整当众落下裁决", the verdict due at 12:00)
                        if claim == "clause" and _names_scheduled(word, _time_after(line, match.end()), scheduled):
                            continue
                        slack = DIALOGUE_SLACK if in_dialogue else 0
                        if not any(_hours_ok(word, m, slack) for m in minutes):
                            out.append(finding("time", index, "正文说“%s”，引擎时钟是 %s" % (word, clock.get("label"))))
            before = clock
    return out


# -- ventriloquism -------------------------------------------------------------------------------


def _bigrams(text):
    text = re.sub(r"[\s，。！？、“”‘’：；…—,.!?:;\"']", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _npc_name_parts(record):
    """Two-character pieces of every NPC's name: a sentence holding one of
    them may be that NPC's (秋山 for 秋山源次郎)."""
    players = {(_opening_player(record) or {}).get("name")}
    return {name[i : i + 2] for name in _known_names(record) - players for i in range(len(name) - 1)}


def _opening_player(record):
    for turn in record["turns"]:
        for call in turn.get("runtime_calls") or []:
            player = ((R.ok_data(call) or {}).get("opening") or {}).get("player")
            if player:
                return player
    return None


def check_ventriloquism(record):
    out = []
    others = None
    for turn in record["turns"]:
        if not narrative_calls(turn):
            continue
        source = _bigrams(turn.get("input") or "")
        # a line introduced by a colon may start the next paragraph
        text = re.sub(r"([：:])\s*\n+\s*(?=“)", r"\1", turn.get("text") or "")
        for line in prose_lines(text):
            quotes = [m.group(1) for m in PLAYER_SPEECH_RE.finditer(line)]
            # “……”你没有回答: someone else's line
            quotes += [m.group(1) for m in PLAYER_SPEECH_AFTER_RE.finditer(line) if not any(n in m.group(2) for n in NEGATIONS)]
            for match in PLAYER_COLON_RE.finditer(line):
                if others is None:
                    others = set(OTHER_SPEAKERS) | _npc_name_parts(record)
                if not any(o in match.group(1) for o in others) and not any(s in match.group(1) for s in SOUND_FROM):
                    quotes.append(match.group(2))
            quotes = list(dict.fromkeys(quotes))
            for quote in quotes:
                grams = _bigrams(quote)
                if len(grams) < 4:
                    continue
                overlap = len(grams & source) / float(len(grams))
                if overlap < 0.5:
                    out.append(finding("ventriloquism", turn["index"], "玩家角色说了玩家没说过的话：“%s”" % quote[:40]))
    return out


# -- unknown people ------------------------------------------------------------------------------


def _known_names(record):
    names = set()
    for turn in record["turns"]:
        for call in turn.get("runtime_calls") or []:
            data = R.ok_data(call) or {}
            opening = data.get("opening") or {}
            for person in [opening.get("player") or {}] + list(opening.get("npcs") or []):
                if person.get("name"):
                    names.add(person["name"])
            context = data.get("context") or {}
            for group in ("characters", "background", "present_npcs", "nearby"):
                for person in context.get(group) or []:
                    if person.get("name"):
                        names.add(person["name"])
            if (context.get("player") or {}).get("name"):
                names.add(context["player"]["name"])
            for op in (call.get("input") or {}).get("operations") or []:
                if op.get("op") == "introduce_character" and R.ok_data(call) is not None:
                    names.add(op.get("name"))
    names.discard(None)
    return names


def check_unknown_people(record):
    world = (((record.get("final_export") or {}).get("session") or {}).get("content") or {}).get("world")
    if not world:
        return [], {"ran": False}
    pools = world["name_pools"]
    givens = pools["given_female"] + pools["given_male"] + pools["given_neutral"]
    known = _known_names(record)
    out = []
    seen = set()
    for turn in record["turns"]:
        text = "\n".join(prose_lines(turn.get("text")))
        for family in pools["family"]:
            for given in givens:
                name = family + given
                if name in text and name not in known and name not in seen:
                    seen.add(name)
                    out.append(finding("unknown_people", turn["index"], "正文里出现了引擎不知道的人：%s（新人物要先登场）" % name))
    return out, {"ran": True}


# -- repetition ------------------------------------------------------------------------------------


def _sentences(lines):
    for line in lines:
        for part in re.split(r"[。！？!?…]+", line):
            part = part.strip("“”‘’ 　")
            if len(part) >= MIN_SENTENCE:
                yield part


def check_repetition(record):
    """ACCEPTANCE 6.2: a sentence repeated two or more times within 10 turns
    (three occurrences: boilerplate, safety reminders, exit descriptions),
    or any dialogue line repeated within one scene. Narrative turns only."""
    out = []
    history = []  # (turn index, sentence, bigrams)
    scene_lines = {}
    for turn in record["turns"]:
        index = turn["index"]
        calls = narrative_calls(turn)
        if not calls:
            continue
        lines = prose_lines(turn.get("text"))
        for sentence in set(_sentences(lines)):
            grams = _bigrams(sentence)
            earlier_turns = set()
            for earlier_index, _earlier, earlier_grams in history:
                if index - earlier_index > REPEAT_WINDOW or earlier_index == index:
                    continue
                union = grams | earlier_grams
                if union and len(grams & earlier_grams) / float(len(union)) >= 0.9:
                    earlier_turns.add(earlier_index)
            if len(earlier_turns) >= 2:
                out.append(finding("repetition", index, "10 个回合内第 %d 次出现（第 %s 轮已有）：%s" % (len(earlier_turns) + 1, "、".join(str(t) for t in sorted(earlier_turns)), sentence[:30])))
            history.append((index, sentence, grams))
        context = (R.ok_data(calls[-1]) or {}).get("context") or {}
        scene = (context.get("scene") or {}).get("id")
        seen = scene_lines.setdefault(scene, {})
        for line in lines:
            for quote in QUOTE_RE.findall(line):
                if len(quote) < 6:
                    continue
                if quote in seen and seen[quote] != index:
                    out.append(finding("repetition", index, "同一场景里重复的台词（第 %d 轮已出现）：“%s”" % (seen[quote], quote[:30])))
                seen.setdefault(quote, index)
    return out


# -- the record itself -------------------------------------------------------------------------------

SKILL_REL = os.path.join(".claude", "skills", "adult-tension")


def _same_path(a, b):
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def check_record(record):
    """Every turn finished with a reply the player saw (ACCEPTANCE 6.1 item 3:
    a turn the host failed, timed out or reported as an error is not a
    complete record). Every runtime call the host made is in the engine
    trace, and came from the Skill installed for this run (ACCEPTANCE 6.1
    item 1): more calls in the host's record than in the trace means an
    unwritten trace or another copy of the Skill somewhere."""
    out = []
    installed = os.path.join(record["project"], SKILL_REL) if record.get("project") else None
    for turn in record["turns"]:
        if turn.get("host_error"):
            out.append(finding("record", turn["index"], "宿主这一轮没有正常结束：%s（记录不完整，ACCEPTANCE §6.1 第 3 条）" % turn["host_error"][:200]))
        elif not (turn.get("text") or "").strip():
            out.append(finding("record", turn["index"], "玩家这一轮什么也没看到"))
        if turn.get("calls_source", "trace") != "trace":
            continue
        calls = turn.get("runtime_calls") or []
        shown = len(R.calls_from_host(turn.get("host_calls")))
        if shown > len(calls):
            out.append(finding("record", turn["index"], "宿主调用了 %d 次运行时，引擎记录里只有 %d 次（记录没写全，或宿主调用了另一份 Skill）" % (shown, len(calls))))
        for call in calls:
            root = call.get("skill_root")
            if installed and root and not _same_path(root, installed):
                out.append(finding("record", turn["index"], "%s 来自另一份 Skill：%s" % (R.command_of(call), root)))
    return out


def check(record):
    problems = R.validate(record)
    if problems:
        return {"pass": False, "invalid_record": problems, "findings": [], "stats": {}}
    findings = check_record(record)
    structure, stats = check_structure(record)
    findings.extend(structure)
    findings.extend(check_leakage(record))
    findings.extend(check_footer_and_time(record))
    findings.extend(check_ventriloquism(record))
    people, people_stats = check_unknown_people(record)
    findings.extend(people)
    findings.extend(check_repetition(record))
    stats["unknown_people_check"] = people_stats["ran"]
    return {"pass": not findings, "findings": findings, "stats": stats}


def summary_lines(result):
    """What a person reads: why the record could not be checked, or each finding."""
    lines = ["[记录格式] %s" % problem for problem in result.get("invalid_record") or []]
    lines += ["[%s] 第 %s 轮：%s" % (item["check"], item["turn"], item["message"]) for item in result["findings"]]
    return lines


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = check(R.load(argv[0]))
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for line in summary_lines(result):
            print(line)
        print("PASS" if result["pass"] else "FAIL")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
