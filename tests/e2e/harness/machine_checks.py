"""Machine checks for end-to-end records (ACCEPTANCE.md 6.2).

    python tests/e2e/harness/machine_checks.py <record.json> [--json]

Every check reads what the player saw (`text`) against what the engine did
(`runtime_calls`, the engine's own trace). A finding fails the record; the
script's `expect` annotations only tell the checks what kind of step each
turn is and which refusals are part of the script.

checks: structure (commits legal or repaired, call budget, ACCEPTANCE 5),
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
BLOCKING_CODES = ("SAFETY_BLOCK",)
EXTRA_CALLS_AFTER_REJECTION = 2
REPEAT_WINDOW = 10
MIN_SENTENCE = 10
FOOTER_RE = re.compile(r"【时间】(?P<time>[^｜\n]+)｜【地点】(?P<place>[^｜\n]+)｜回合：(?P<turn>\d+)(?:｜种子：(?P<seed>\d+))?")
RECEIPT_RE = re.compile(r"^(已保存|已另存为|已读取|已撤销|已记下|已暂停|已导出|已导入|已删除|内心可见|叙事助手|离屏推演|已恢复)")
HINT_RE = re.compile(r"^可以：")
NUMBER_LEAK_RE = re.compile(r"(信任|张力|好感度?|欲望值?|自制力?|亲密度|关系值|revision)\s*[:：]?\s*[+\-−]?\s*\d")
TIER_WORDS = ("结果档", "尝试档", "改写档", "继续档", "等待档")
# Engine vocabulary in Chinese: response labels and mechanism phrases.
MECHANISM_WORDS = ("有限配合", "表面配合", "真诚配合", "系统判定", "回合推进", "回合结算", "离屏推演", "引擎判定")
ENGINE_WORDS = ("revision", "request_id", "session_id", "expected_revision", "next_request_id", "known_by", "believed_by", "dedupe_key", "action_mode", "desire_level", "self_control")
SNAKE_RE = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")
QUOTE_RE = re.compile(r"“([^”]{2,})”")
PLAYER_SPEECH_RE = re.compile(r"(?:^|[。！？\n，、])\s*你[^。！？“\n]{0,12}?(?:说|问|道|答|喊|开口|低声|笑着|回了一句|接了一句)[^“\n]{0,6}“([^”]{2,})”")
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
# A time word next to one of these is about another moment, not about now.
TIME_OTHER = ("昨", "明", "前", "后", "那天", "那晚", "今天", "今早", "等到", "到了", "直到", "刚才", "之前", "以前", "每天", "每晚", "每到", "天天", "那年", "当年", "上回", "下回", "约", "说好")


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
            group = groups.setdefault(expect["budget_group"], {"calls": 0, "max": expect.get("group_max"), "turns": []})
            group["calls"] += len(calls)
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
            if code and code not in BLOCKING_CODES and not expect.get("allow_reject"):
                out.append(finding("structure", index, "%s 被拒（%s）后没有修正成功" % (R.command_of(last_write), code)))
        for call in calls:
            if R.error_code(call) == "INTERNAL_ERROR":
                out.append(finding("structure", index, "运行时内部错误：%s" % (call.get("envelope") or {}).get("error", {}).get("message")))
        if expect.get("kind") == "turn":
            ordinary.append(len(calls))
    for name, group in groups.items():
        if group["max"] is not None and group["calls"] > group["max"]:
            out.append(finding("structure", group["turns"][-1], "%s 共调用 %d 次，超过 %d（ACCEPTANCE §5）" % (name, group["calls"], group["max"])))
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


def _hours_ok(word, minute):
    hour = (minute // 60) % 24
    return any(lo <= hour < hi for lo, hi in TIME_WORDS[word])


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
            for line in prose_lines(turn.get("text")):
                for word in TIME_WORDS:
                    for match in re.finditer(word, line):
                        near = line[max(0, match.start() - 4) : match.end() + 2]
                        if any(other in near for other in TIME_OTHER):
                            continue
                        if not any(_hours_ok(word, m) for m in minutes):
                            out.append(finding("time", index, "正文说“%s”，引擎时钟是 %s" % (word, clock.get("label"))))
            before = clock
    return out


# -- ventriloquism -------------------------------------------------------------------------------


def _bigrams(text):
    text = re.sub(r"[\s，。！？、“”‘’：；…—,.!?:;\"']", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)}


def check_ventriloquism(record):
    out = []
    for turn in record["turns"]:
        if not narrative_calls(turn):
            continue
        source = _bigrams(turn.get("input") or "")
        for line in prose_lines(turn.get("text")):
            for match in PLAYER_SPEECH_RE.finditer(line):
                quote = match.group(1)
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


def check(record):
    problems = R.validate(record)
    if problems:
        return {"pass": False, "invalid_record": problems, "findings": [], "stats": {}}
    findings = []
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


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = check(R.load(argv[0]))
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for item in result["findings"]:
            print("[%s] 第 %s 轮：%s" % (item["check"], item["turn"], item["message"]))
        print("PASS" if result["pass"] else "FAIL")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
