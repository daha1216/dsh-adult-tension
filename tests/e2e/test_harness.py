"""The end-to-end harness itself: machine checks, stream parsers, runner.

These tests never call a model. Machine checks are exercised on small
records built here, each with and without the problem the check looks for.
"""

import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error

import _bootstrap  # noqa: F401
import hosts as H
import machine_checks as M
import record as R
import report
import review
import run_script
from helpers.domain import STORE

WORLD = STORE.world("harbor_night_shift")
FAMILY, GIVEN = WORLD["name_pools"]["family"][0], WORLD["name_pools"]["given_female"][0]
STRANGER = WORLD["name_pools"]["family"][5] + WORLD["name_pools"]["given_male"][3]


def envelope(data):
    return {"ok": True, "data": data, "error": None}


def failure(code):
    return {"ok": False, "data": None, "error": {"code": code, "message": code, "details": []}}


def opening_call(minute=1200):
    footer = "【时间】第一天 %02d:%02d｜【地点】七号泊位｜回合：1｜种子：7" % (minute // 60, minute % 60)
    data = {
        "session_id": "s_1", "revision": 1, "turn": 1, "seed": 7,
        "opening": {"footer": footer, "player": {"name": FAMILY + GIVEN}, "npcs": [{"name": "梁志强"}]},
        "context": {"clock": {"minute": minute, "label": "第一天 %02d:%02d" % (minute // 60, minute % 60)}, "scene": {"id": "sc1", "location": "七号泊位"}},
    }
    return {"argv": ["new-game"], "input": {"mode": "daily"}, "exit": 0, "envelope": envelope(data)}


def commit_call(turn, minute, scene="sc1", ok=True, code=None, ops=None):
    if not ok:
        return {"argv": ["commit-turn"], "input": {"operations": ops or []}, "exit": 10, "envelope": failure(code)}
    label = "第一天 %02d:%02d" % (minute // 60, minute % 60)
    data = {"turn": turn, "revision": turn, "context": {"clock": {"minute": minute, "label": label}, "scene": {"id": scene, "location": "七号泊位"}}}
    return {"argv": ["commit-turn"], "input": {"operations": ops or []}, "exit": 0, "envelope": envelope(data)}


def footer(turn, minute):
    return "【时间】第一天 %02d:%02d｜【地点】七号泊位｜回合：%d" % (minute // 60, minute % 60, turn)


def make_record(turns):
    return {
        "format": R.FORMAT, "version": R.VERSION, "script": "t", "run": 1, "date": "2026-10-01",
        "host": {"name": "test", "version": "1", "model": "m"},
        "turns": turns,
        "final_export": {"session": {"content": {"world": WORLD}}},
    }


def clean_record():
    turns = [
        {"index": 1, "conversation": "A", "input": "开一局，日常", "expect": {"kind": "opening", "calls_max": 2},
         "host_calls": [], "runtime_calls": [{"argv": ["doctor"], "input": {}, "exit": 0, "envelope": envelope({"status": "ok"})}, opening_call()],
         "text": "世界观：码头的夜班。\n人物：%s。\n\n吊臂的影子扫过地面，有人把保温杯推到你面前。\n\n【时间】第一天 20:00｜【地点】七号泊位｜回合：1｜种子：7" % (FAMILY + GIVEN)},
        {"index": 2, "conversation": "A", "input": "我说：“你要是不愿意，现在就说。”", "expect": {"kind": "turn", "calls_max": 1},
         "host_calls": [], "runtime_calls": [commit_call(2, 1205)],
         "text": "你说：“你要是不愿意，现在就说。”对方没有马上回答，把杯盖拧紧了。\n\n" + footer(2, 1205)},
        {"index": 3, "conversation": "A", "input": "继续", "expect": {"kind": "turn", "calls_max": 1},
         "host_calls": [], "runtime_calls": [commit_call(3, 1210)],
         "text": "远处的对讲机响了两声，梁志强转身去看吊机。\n\n" + footer(3, 1210)},
    ]
    return make_record(turns)


def names(result):
    return [(f["check"], f["turn"]) for f in result["findings"]]


class MachineCheckTest(unittest.TestCase):
    def test_a_clean_record_passes(self):
        result = M.check(clean_record())
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["stats"]["average_calls"], 1.0)

    def test_leaks_are_found_but_not_the_footer_or_receipts(self):
        rec = clean_record()
        rec["turns"][2]["text"] = "对方的信任 +1，你的 revision 是 3。npc_response 写好了。\n\n" + footer(3, 1210)
        rec["turns"][1]["text"] = rec["turns"][1]["text"].replace("对方没有马上回答", "对方报错 STALE_REVISION")
        found = [f["message"] for f in M.check(rec)["findings"] if f["check"] == "leakage"]
        self.assertTrue(any("信任 +1" in m for m in found))
        self.assertTrue(any("npc_response" in m for m in found))
        self.assertTrue(any("revision" in m for m in found))
        self.assertTrue(any("STALE_REVISION" in m for m in found))
        # the host telling the player what it does with the runtime
        rec = clean_record()
        rec["turns"][2]["text"] = "提交回合行动并推进时间与状态。\n\n对方没有马上回答。\n\n" + footer(3, 1210)
        self.assertIn(("leakage", 3), names(M.check(rec)))
        # the format's placeholder copied as a heading
        rec["turns"][2]["text"] = "正文：\n\n对方没有马上回答。\n\n" + footer(3, 1210)
        self.assertIn(("leakage", 3), names(M.check(rec)))
        # ... or in English, with no command name in it
        rec["turns"][2]["text"] = "I will commit the turn to the runtime engine.\n\n对方没有马上回答。\n\n" + footer(3, 1210)
        self.assertIn(("leakage", 3), names(M.check(rec)))
        # a line of English someone says aloud is part of the story
        rec["turns"][2]["text"] = "“Stop right there!”\n\n水手喊完这一句，对方没有马上回答。\n\n" + footer(3, 1210)
        self.assertNotIn(("leakage", 3), names(M.check(rec)))
        receipt = clean_record()
        receipt["turns"].append({"index": 4, "conversation": "A", "input": "存档", "expect": {"kind": "meta", "calls_max": 1},
                                 "host_calls": [], "runtime_calls": [{"argv": ["save-slot"], "input": {}, "exit": 0, "envelope": envelope({"receipt": "已保存到「夜班」·第 3 回合"})}],
                                 "text": "已保存到「夜班」·第 3 回合"})
        self.assertEqual(M.check(receipt)["findings"], [])

    def test_footer_must_match_the_engine(self):
        rec = clean_record()
        rec["turns"][2]["text"] = rec["turns"][2]["text"].replace("20:10", "20:40")
        self.assertIn(("footer", 3), names(M.check(rec)))
        rec = clean_record()
        rec["turns"][1]["text"] = "你说：“你要是不愿意，现在就说。”"
        self.assertIn(("footer", 2), names(M.check(rec)))
        rec = clean_record()
        rec["turns"][0]["text"] = rec["turns"][0]["text"].replace("种子：7", "种子：8")
        self.assertIn(("footer", 1), names(M.check(rec)))

    def test_time_words_must_fit_the_clock(self):
        rec = clean_record()
        rec["turns"][2]["text"] = "凌晨的风把旗子吹得啪啪响。\n\n" + footer(3, 1210)
        self.assertIn(("time", 3), names(M.check(rec)))
        rec["turns"][2]["text"] = "昨天凌晨的事，谁也没再提。\n\n" + footer(3, 1210)
        self.assertNotIn(("time", 3), names(M.check(rec)))
        # a character naming a time on a schedule, or earlier today, is not saying what time it is now;
        # a character rounding the hour is not wrong about it either (20:10)
        for text in ("她说：“规矩就一条，凌晨两点所有人都得去签到，早晨八点交班。”", "他说：“包工头下午就联系不上了。”", "“站住！大半夜的，提着箱子去哪儿？”"):
            rec["turns"][2]["text"] = text + "\n\n" + footer(3, 1210)
            self.assertNotIn(("time", 3), names(M.check(rec)), text)
        # the time of something else: earlier, on another day, of another event
        for text in ("柜子是凌晨抢装塞进来的，手续上缺了签字。", "天光早在凌晨就沉了底，到了这会儿，只剩石板路上一层油光。",
                     "距离清场只剩二十分钟，而第三天上午十点艺术季就将正式开幕。", "他答应了，凌晨就回来。"):
            rec["turns"][2]["text"] = text + "\n\n" + footer(3, 1210)
            self.assertNotIn(("time", 3), names(M.check(rec)), text)
        # the narration says what time it is where a clause opens with it or marks it as now; so does a line about now
        for text in ("凌晨两点，风把旗子吹得啪啪响。", "你推开门，凌晨的风灌了进来。", "窗外已是凌晨，街上没有人。",
                     "她说：“都凌晨了，还不回去？”", "现在是凌晨的时候，风把旗子吹得啪啪响。"):
            rec["turns"][2]["text"] = text + "\n\n" + footer(3, 1210)
            self.assertIn(("time", 3), names(M.check(rec)), text)
        # a clause may name the hour the engine has scheduled something for (the opening's deadline: 中午十二点落下裁决) ...
        rec["turns"][2]["text"] = "委员们坐定，中午十二点整当众落下裁决。\n\n" + footer(3, 1210)
        self.assertIn(("time", 3), names(M.check(rec)))
        context = rec["turns"][2]["runtime_calls"][0]["envelope"]["data"]["context"]
        for key in ("due_soon", "events"):
            context[key] = [{"id": "e2", "kind": "deadline", "title": "裁决", "in_minutes": 950, "due_label": "第二天 12:00"}]
            rec["turns"][2]["text"] = "委员们坐定，中午十二点整当众落下裁决。\n\n" + footer(3, 1210)
            self.assertNotIn(("time", 3), names(M.check(rec)), key)
            # ... but not another time, a part of the day with no time, or a line marked as now
            for text in ("委员们坐定，中午一点，裁决落下。", "委员们坐定，中午十二点半，裁决落下。", "委员们坐定，中午的风从门缝灌进来。",
                         "窗外已是中午十二点，委员们坐定。"):
                rec["turns"][2]["text"] = text + "\n\n" + footer(3, 1210)
                self.assertIn(("time", 3), names(M.check(rec)), (key, text))
            # ... nor the hour of an event more than a day away
            context[key][0]["in_minutes"] += 1440
            rec["turns"][2]["text"] = "委员们坐定，中午十二点整当众落下裁决。\n\n" + footer(3, 1210)
            self.assertIn(("time", 3), names(M.check(rec)), key)
            del context[key]
        self.assertEqual([M._time_after(s, 2) for s in ("中午十二点", "凌晨两点", "凌晨零时五十分", "下午3点半", "傍晚六点二十", "中午的风")],
                         [(12, 0), (2, 0), (0, 50), (3, 30), (6, 20), None])
        # the opening's lines on the world and its people are rules and who people are, not the time now
        rec = clean_record()
        rec["turns"][0]["text"] = rec["turns"][0]["text"].replace("世界观：码头的夜班。", "世界观：码头的夜班，凌晨两点所有人必须到控制塔签到。")
        self.assertNotIn(("time", 1), names(M.check(rec)))
        rec["turns"][0]["text"] = rec["turns"][0]["text"].replace("吊臂的影子", "凌晨两点，吊臂的影子")
        self.assertIn(("time", 1), names(M.check(rec)))

    def test_lines_the_player_never_said_are_ventriloquism(self):
        rec = clean_record()
        rec["turns"][2]["text"] = "你说：“我今晚哪儿也不去，就在这儿陪你到天亮。”\n\n" + footer(3, 1210)
        self.assertIn(("ventriloquism", 3), names(M.check(rec)))
        # the line first, then the player named as its speaker
        rec["turns"][2]["text"] = "“别急着谈展位，”你的声音很稳，“先把眼下的火灭了。”\n\n" + footer(3, 1210)
        self.assertIn(("ventriloquism", 3), names(M.check(rec)))
        # the player's own sentence running into a colon and a line
        rec["turns"][2]["text"] = "你深吸了一口气，抬眼看着面前的两个人，声音压得极沉：“这局我一个人扛不下。”\n\n" + footer(3, 1210)
        self.assertIn(("ventriloquism", 3), names(M.check(rec)))
        rec["turns"][2]["text"] = "你深吸了一口气，声音压得极沉：\n\n“这局我一个人扛不下。”\n\n" + footer(3, 1210)
        self.assertIn(("ventriloquism", 3), names(M.check(rec)))
        # someone else's line that the player does not answer, someone else's line, someone else in the sentence
        for text in ("“你说今晚到底走不走？”你没有回答，只是看着她。", "“今晚忙得很，别来烦我。”她说。你点了点头。",
                     "你听见她压低了声音：“今晚别去七号泊位。”", "你看向志强，志强把烟掐了：“今晚别去七号泊位。”"):
            rec["turns"][2]["text"] = text + "\n\n" + footer(3, 1210)
            self.assertNotIn(("ventriloquism", 3), names(M.check(rec)), text)

    def test_named_people_must_be_known_to_the_engine(self):
        rec = clean_record()
        rec["turns"][2]["text"] = "%s从吊机后面走了出来。\n\n%s" % (STRANGER, footer(3, 1210))
        self.assertIn(("unknown_people", 3), names(M.check(rec)))
        introduced = copy.deepcopy(rec)
        introduced["turns"][2]["runtime_calls"][0]["input"]["operations"] = [{"op": "introduce_character", "name": STRANGER}]
        self.assertNotIn(("unknown_people", 3), names(M.check(introduced)))

    def test_boilerplate_three_times_in_ten_turns_and_repeated_lines_in_a_scene(self):
        rec = clean_record()
        base = rec["turns"][2]
        boiler = "这一切都在双方自愿的前提下进行，随时可以停下。"
        for i in range(4, 7):
            turn = copy.deepcopy(base)
            turn["index"] = i
            turn["runtime_calls"] = [commit_call(i, 1210 + i)]
            turn["text"] = "码头上的灯亮了第%d盏。%s\n\n%s" % (i, boiler, footer(i, 1210 + i))
            rec["turns"].append(turn)
        found = [f for f in M.check(rec)["findings"] if f["check"] == "repetition"]
        self.assertEqual([f["turn"] for f in found], [6])
        line = clean_record()
        line["turns"][2]["text"] = "对方说：“你别管这件事了。”\n\n" + footer(3, 1210)
        extra = copy.deepcopy(line["turns"][2])
        extra.update(index=4, runtime_calls=[commit_call(4, 1215)], text="对方又说：“你别管这件事了。”\n\n" + footer(4, 1215))
        line["turns"].append(extra)
        self.assertIn(("repetition", 4), names(M.check(line)))
        other_scene = copy.deepcopy(line)
        other_scene["turns"][3]["runtime_calls"] = [commit_call(4, 1215, scene="sc2")]
        self.assertNotIn(("repetition", 4), names(M.check(other_scene)))

    def test_rejections_repairs_and_budgets(self):
        rec = clean_record()
        rec["turns"][2]["runtime_calls"] = [commit_call(3, 0, ok=False, code="INVALID_INPUT"), commit_call(3, 1210)]
        self.assertEqual(M.check(rec)["findings"], [])
        rec["turns"][2]["runtime_calls"] = [commit_call(3, 0, ok=False, code="INVALID_INPUT")] * 3 + [commit_call(3, 1210)]
        self.assertIn(("structure", 3), names(M.check(rec)))
        rec["turns"][2]["runtime_calls"] = [commit_call(3, 0, ok=False, code="INVARIANT_VIOLATION")]
        rec["turns"][2]["text"] = "你想了想，换了个说法。"
        self.assertIn(("structure", 3), names(M.check(rec)))
        rec["turns"][2]["expect"]["allow_reject"] = True
        self.assertNotIn(("structure", 3), names(M.check(rec)))
        blocked = clean_record()
        blocked["turns"][2]["runtime_calls"] = [commit_call(3, 0, ok=False, code="SAFETY_BLOCK")]
        blocked["turns"][2]["text"] = "这一段涉及你设过的边界，换个方向吧。"
        self.assertNotIn(("structure", 3), names(M.check(blocked)))
        over = clean_record()
        over["turns"][1]["runtime_calls"] = [{"argv": ["get-context"], "input": {}, "exit": 0, "envelope": envelope({})}, commit_call(2, 1205)]
        self.assertIn(("structure", 2), names(M.check(over)))
        grouped = clean_record()
        grouped["turns"][0]["expect"].update(budget_group="first", group_max=2)
        grouped["turns"][1]["expect"].update(budget_group="first", group_max=2)
        self.assertIn(("structure", 2), names(M.check(grouped)))

    def test_the_first_opening_of_a_conversation_runs_doctor_and_new_game(self):
        rec = clean_record()
        rec["turns"][0]["expect"].update(budget_group="first_opening:A", group_max=2, group_must_call=["doctor", "new-game"])
        self.assertEqual(M.check(rec)["findings"], [])
        rec["turns"][0]["runtime_calls"] = rec["turns"][0]["runtime_calls"][1:]
        self.assertEqual(names(M.check(rec)), [("structure", 1)])

    def test_calls_missing_from_the_trace_or_from_another_skill_fail_the_record(self):
        rec = clean_record()
        rec["project"] = os.path.join("D:\\", "projects", "at-e2e", "p")
        installed = os.path.join(rec["project"], ".claude", "skills", "adult-tension")
        for turn in rec["turns"]:
            for call in turn["runtime_calls"]:
                call["skill_root"] = installed
        self.assertEqual(M.check(rec)["findings"], [])
        missing = copy.deepcopy(rec)
        bash = {"tool": "Bash", "input": {"command": "python %s/scripts/adult_tension.py commit-turn --json --input-file in.json" % installed}, "output": ""}
        missing["turns"][2]["host_calls"] = [bash, bash]
        self.assertEqual(names(M.check(missing)), [("record", 3)])
        # a command the shell could not parse never reached the runtime; the retry did
        retried = copy.deepcopy(rec)
        broken = {"tool": "bash", "input": {"command": 'python "%s/scripts/adult_tension.py" commit-turn --json --input-file "in.json' % installed}, "output": "/usr/bin/bash: -c: line 1: unexpected EOF while looking for matching `\"'\n"}
        retried["turns"][2]["host_calls"] = [broken, bash]
        self.assertEqual(M.check(retried)["findings"], [])
        other = copy.deepcopy(rec)
        other["turns"][1]["runtime_calls"][0]["skill_root"] = "C:\\Users\\x\\.claude\\skills\\adult-tension"
        self.assertEqual(names(M.check(other)), [("record", 2)])

    def test_a_turn_the_host_did_not_finish_or_left_empty_fails_the_record(self):
        rec = clean_record()
        rec["turns"][1]["host_error"] = "宿主没有返回会话：exit 1"
        rec["turns"][2]["text"] = " \n"
        result = M.check(rec)
        self.assertEqual(names(result), [("record", 2), ("record", 3), ("footer", 3)])
        self.assertTrue(M.summary_lines(result)[0].startswith("[record] 第 2 轮：宿主这一轮没有正常结束：宿主没有返回会话"))

    def test_a_record_without_host_identity_is_not_checked(self):
        rec = clean_record()
        rec["host"]["model"] = ""
        result = M.check(rec)
        self.assertFalse(result["pass"])
        self.assertEqual(M.summary_lines(result), ["[记录格式] 宿主身份缺少 model（ACCEPTANCE §6.1 第 5 条）"])


class CalibrationTest(unittest.TestCase):
    """The calibration set: machine checks fire exactly where the key says."""

    DIR = os.path.join(_bootstrap.E2E_DIR, "calibration")

    def test_machine_checks_match_the_key(self):
        with open(os.path.join(self.DIR, "key.json"), encoding="utf-8") as handle:
            key = json.load(handle)
        self.assertEqual(sum(1 for k in key if k.startswith("good")), 6)
        self.assertEqual(sum(1 for k in key if k.startswith("flawed")), 6)
        for name, expected in key.items():
            result = M.check(R.load(os.path.join(self.DIR, name + ".json")))
            self.assertEqual(sorted({f["check"] for f in result["findings"]}), sorted(expected["machine"]), name)
            if name.startswith("flawed"):
                self.assertTrue(expected["low"], name)

    def test_the_committed_records_are_what_the_builder_writes(self):
        import build as B

        temp = tempfile.mkdtemp(prefix="at-cal-")
        self.addCleanup(shutil.rmtree, temp, True)
        B.main(temp)
        for name in sorted(os.listdir(temp)):
            with open(os.path.join(temp, name), "rb") as a, open(os.path.join(self.DIR, name), "rb") as b:
                self.assertEqual(a.read(), b.read(), name)


class ReportTest(unittest.TestCase):
    def review(self, low=(), score=4, by="served-m"):
        return {"scores": {d: {"score": (2 if d in low else score), "evidence": ["第 1 轮：……"]} for d in report.DIMENSIONS}, "severe": [],
                "reviewer": {"model": "asked-m", "attempts": [{"served_model": by, "answer": "……", "problems": []}], "usable": True}}

    def calibration(self, by="served-m"):
        """A calibration directory where BY judged all twelve records right."""
        with open(os.path.join(_bootstrap.E2E_DIR, "calibration", "key.json"), encoding="utf-8") as handle:
            key = json.load(handle)
        temp = tempfile.mkdtemp(prefix="at-cal-")
        self.addCleanup(shutil.rmtree, temp, True)
        self.write_reviews(temp, {name: self.review(low=expected["low"], by=by) for name, expected in key.items()})
        return temp

    def write_reviews(self, directory, reviews):
        os.makedirs(directory, exist_ok=True)
        for name, review in reviews.items():
            with open(os.path.join(directory, name + ".json"), "w", encoding="utf-8") as handle:
                json.dump(review, handle, ensure_ascii=False)

    def test_calibration_needs_ten_of_twelve(self):
        with open(os.path.join(_bootstrap.E2E_DIR, "calibration", "key.json"), encoding="utf-8") as handle:
            key = json.load(handle)
        temp = tempfile.mkdtemp(prefix="at-rev-")
        self.addCleanup(shutil.rmtree, temp, True)
        right = {name: self.review(low=expected["low"]) for name, expected in key.items()}
        self.write_reviews(temp, right)
        result = report.calibrate(temp)
        self.assertEqual((result["correct"], result["ready"], result["reviewer"]), (12, True, "served-m"))
        wrong = dict(right, **{"flawed-1": self.review(), "flawed-2": self.review(), "good-1": self.review(low=("表达",))})
        self.write_reviews(temp, wrong)
        result = report.calibrate(temp)
        self.assertEqual((result["correct"], result["ready"]), (9, False))

    def test_the_host_identity_names_every_model_that_answered(self):
        rec = clean_record()
        self.assertEqual(report.host_models(rec), "m")
        # the proxy switched models between turns
        rec["turns"][0]["model"], rec["turns"][2]["model"] = "p/m-exp-a", "p/m-flash"
        self.assertEqual(report.host_models(rec), "p/m-exp-a+p/m-flash")
        # and within one turn
        rec["turns"][1]["model"] = "p/m-exp-a+p/m-flash"
        self.assertEqual(report.host_models(rec), "p/m-exp-a+p/m-flash")

    def test_a_calibration_speaks_for_the_one_model_that_answered(self):
        # the model the endpoint says answered, not the name asked for; several when the attempts differ
        self.assertEqual(report.reviewer_of(self.review(by="served-n")), "served-n")
        mixed = {"reviewer": {"model": "asked", "attempts": [{"served_model": "b"}, {"error": "HTTP 503"}, {"served_model": "a"}]}}
        self.assertEqual(report.reviewer_of(mixed), "a+b")
        self.assertEqual(report.reviewer_of({"reviewer": {"model": "asked", "attempts": [{"error": "HTTP 503"}]}}), "asked")
        self.assertIsNone(report.reviewer_of({"scores": {}}))
        temp = self.calibration()
        # the proxy served one record with another model: twelve right answers from two reviewers
        self.write_reviews(temp, {"good-1": self.review(by="served-n")})
        result = report.calibrate(temp)
        self.assertEqual((result["correct"], result["reviewer"], result["reviewers"], result["ready"]), (12, None, ["served-m", "served-n"], False))
        self.assertEqual(report.calibrated([temp]), {})
        # an unusable review is judged wrong and names no reviewer
        self.write_reviews(temp, {"good-1": {"scores": None, "severe": None, "reviewer": {"model": "asked-m", "attempts": [{"error": "HTTP 503"}], "usable": False}}})
        result = report.calibrate(temp)
        self.assertEqual((result["correct"], result["reviewer"], result["ready"]), (11, "served-m", True))
        self.assertEqual(report.calibrated([temp, self.calibration(by="served-n")]), {"served-m": "11/12", "served-n": "12/12"})
        # nothing says who answered: the result speaks for no one
        with open(os.path.join(_bootstrap.E2E_DIR, "calibration", "key.json"), encoding="utf-8") as handle:
            key = json.load(handle)
        self.write_reviews(temp, {name: dict(self.review(low=expected["low"]), reviewer={"usable": True}) for name, expected in key.items()})
        result = report.calibrate(temp)
        self.assertEqual((result["correct"], result["reviewers"], result["ready"]), (12, ["未记"], False))

    def test_the_user_can_say_two_served_names_are_one_model(self):
        same = {"served-x": "served-m"}
        self.assertEqual(report.reviewer_of(self.review(by="served-x"), same), "served-m")
        both = {"reviewer": {"model": "asked", "attempts": [{"served_model": "served-x"}, {"served_model": "served-m"}]}}
        self.assertEqual((report.reviewer_of(both), report.reviewer_of(both, same)), ("served-m+served-x", "served-m"))
        # a calibration answered under both names speaks for one model only when the user says so
        temp = self.calibration()
        self.write_reviews(temp, {"good-1": self.review(by="served-x")})
        self.assertEqual((report.calibrate(temp)["ready"], report.calibrated([temp])), (False, {}))
        result = report.calibrate(temp, same)
        self.assertEqual((result["correct"], result["reviewer"], result["ready"]), (12, "served-m", True))
        self.assertEqual(report.calibrated([temp], same), {"served-m": "12/12"})
        # the command line takes the statement as <served>=<model> and prints it
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(report.main(["calibrate", "--reviews", temp]), 1)
            self.assertEqual(report.main(["calibrate", "--reviews", temp, "--same-model", "served-x=served-m"]), 0)
        self.assertIn("served-x 与 served-m 视为同一个模型（用户确认）", out.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            report.main(["calibrate", "--reviews", temp, "--same-model", "served-x"])
        # the reviews under the other name count as that model's, and the reports say why
        root = tempfile.mkdtemp(prefix="at-rep-")
        self.addCleanup(shutil.rmtree, root, True)
        records, reviews = os.path.join(root, "records"), os.path.join(root, "reviews")
        os.makedirs(os.path.join(records, "h1"))
        rec = clean_record()
        rec["host"]["name"] = "h1"
        R.save(rec, os.path.join(records, "h1", "h1-st-r1.json"))
        self.write_reviews(os.path.join(reviews, "h1"), {"h1-st-r1": self.review(by="served-x")})
        calibration = [self.calibration()]
        self.assertEqual(report.build(records, reviews, calibration)["unreviewed"], ["h1-st-r1.json"])
        built = report.build(records, reviews, calibration, same=same)
        self.assertEqual((built["unreviewed"], built["reviewers"]), ([], {"served-m": {"reviews": 1, "calibration": "12/12"}}))
        self.assertIn("评审者：served-m 1 条（校准 12/12）；served-x 与 served-m 视为同一个模型（用户确认）", report.to_markdown(built))
        self.assertEqual(report.playtests(records, reviews, calibration)["summary"][0]["reviewed"], 0)
        result = report.playtests(records, reviews, calibration, same)
        self.assertEqual(result["summary"][0]["reviewed"], 1)
        self.assertIn("served-x 与 served-m 视为同一个模型（用户确认）。", report.playtests_markdown(result))
        self.assertNotIn("视为同一个模型", report.playtests_markdown(report.playtests(records, reviews, calibration)))

    def test_the_report_counts_first_runs_ceiling_and_critical_dimensions(self):
        temp = tempfile.mkdtemp(prefix="at-rep-")
        self.addCleanup(shutil.rmtree, temp, True)
        records, reviews = os.path.join(temp, "records"), os.path.join(temp, "reviews")
        for host in ("h1", "h2"):
            os.makedirs(os.path.join(records, host))
            for run in (1, 2):
                rec = clean_record()
                rec["host"]["name"], rec["run"] = host, run
                R.save(rec, os.path.join(records, host, "%s-st-r%d.json" % (host, run)))
            self.write_reviews(os.path.join(reviews, host), {"%s-st-r1" % host: self.review(score=5), "%s-st-r2" % host: self.review(score=5)})
        calibration = [self.calibration()]
        built = report.build(records, reviews, calibration)
        self.assertEqual(built["hosts"]["h1"], [["1", "m", "2026-10-01"]])
        self.assertEqual(built["first_run_machine_pass"], "2/2")
        self.assertEqual(built["average_calls_per_ordinary_turn"], 1.0)
        self.assertEqual(sorted(built["ceiling"]), sorted(report.DIMENSIONS))
        self.assertTrue(built["pass"])
        # the median of four fives is printed as 5, not 5.0
        self.assertIn("| 玩家主权 | 4 | 5 | 0 | 0 | 0 | 0 | 4 |", report.to_markdown(built))
        self.write_reviews(os.path.join(reviews, "h2"), {"h2-st-r2": self.review(low=("同意与安全",))})
        built = report.build(records, reviews, calibration)
        self.assertFalse(built["pass"])
        self.assertEqual(built["critical_low"], [{"file": "h2-st-r2.json", "dimension": "同意与安全", "score": 2}])
        self.assertIn("同意与安全", report.to_markdown(built))
        # a record without a usable review cannot pass: no gaps in the scores
        self.write_reviews(os.path.join(reviews, "h2"), {"h2-st-r2": {"scores": None, "severe": None, "reviewer": {"usable": False}}})
        built = report.build(records, reviews, calibration)
        self.assertEqual((built["unreviewed"], built["pass"]), (["h2-st-r2.json"], False))
        # nor can a review by a model that did not pass calibration, however good its scores
        self.write_reviews(os.path.join(reviews, "h2"), {"h2-st-r2": self.review(score=5, by="served-n")})
        built = report.build(records, reviews, calibration)
        self.assertEqual((built["unreviewed"], built["pass"]), (["h2-st-r2.json"], False))
        self.assertEqual(built["reviewers"], {"served-m": {"reviews": 3, "calibration": "12/12"}, "served-n": {"reviews": 1, "calibration": None}})
        self.assertIn("评审者：served-m 3 条（校准 12/12）、served-n 1 条（未通过校准，不计入）", report.to_markdown(built))
        # the same review counts once its reviewer is calibrated
        built = report.build(records, reviews, calibration + [self.calibration(by="served-n")])
        self.assertEqual((built["unreviewed"], built["pass"]), ([], True))

    def test_an_unusable_review_is_not_a_right_calibration(self):
        temp = tempfile.mkdtemp(prefix="at-rev-")
        self.addCleanup(shutil.rmtree, temp, True)
        self.write_reviews(temp, {"good-1": {"scores": None, "severe": None}})
        rows = {r["record"]: r for r in report.calibrate(temp)["rows"]}
        self.assertFalse(rows["good-1"]["right"])

    def test_two_reviewers_are_compared_on_the_records_both_reviewed(self):
        temp = tempfile.mkdtemp(prefix="at-rev-")
        self.addCleanup(shutil.rmtree, temp, True)

        def put(reviewer, name, scores, model):
            os.makedirs(os.path.join(temp, reviewer, "pi"), exist_ok=True)
            review = {"scores": None, "severe": None} if scores is None else \
                {"scores": {d: {"score": scores.get(d, 4), "evidence": ["第 1 轮：……——……"]} for d in report.DIMENSIONS}, "severe": []}
            review["reviewer"] = {"model": model}
            with open(os.path.join(temp, reviewer, "pi", name), "w", encoding="utf-8") as handle:
                json.dump(review, handle, ensure_ascii=False)

        put("a", "r1.json", {"表达": 2, "连续性": 5}, "claude")
        put("b", "r1.json", {"表达": 5, "连续性": 4}, "gemini")
        put("a", "r2.json", {"关系节奏": "n/a"}, "claude")
        put("b", "r2.json", {}, "gemini")
        put("a", "r3.json", {}, "claude")  # the second reviewer gave no usable answer: not compared
        put("b", "r3.json", None, "gemini")
        put("a", "r4.json", {}, "claude")  # only one reviewer: not compared
        result = report.agreement(os.path.join(temp, "a"), os.path.join(temp, "b"))
        self.assertEqual((result["records"], result["first"], result["second"]), (2, ["claude"], ["gemini"]))
        self.assertEqual(result["dimensions"]["表达"], {"n": 2, "same": 1, "within_one": 1, "mean_difference": 1.5, "low_first": 1, "low_second": 0})
        self.assertEqual(result["dimensions"]["连续性"]["mean_difference"], -0.5)
        self.assertEqual(result["dimensions"]["关系节奏"]["n"], 1)
        self.assertIn("| 表达 | 2 | 1 | 1 | +1.50 | 1 | 0 |", report.agreement_markdown(result))

    def test_playtests_are_summed_up_per_world_and_mode(self):
        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        records = os.path.join(temp, "records")
        path, _rec = run_script.run(run_script.load_script("pt-harbor_night_shift-daily"), "fake", 1, None, os.path.join(temp, "projects"), os.path.join(records, "fake"))
        name = os.path.basename(path)
        os.makedirs(os.path.join(temp, "reviews", "fake"))
        answer = {"scores": {d: {"score": 2 if d == "玩家主权" else 4, "evidence": ["第 1 轮：……——……"]} for d in report.DIMENSIONS}, "severe": [],
                  "reviewer": {"model": "reviewer-x", "usable": True}}
        with open(os.path.join(temp, "reviews", "fake", name), "w", encoding="utf-8") as handle:
            json.dump(answer, handle, ensure_ascii=False)
        calibration = [self.calibration(by="reviewer-x")]
        result = report.playtests(records, os.path.join(temp, "reviews"), calibration)
        self.assertIn("评审者：reviewer-x 1 条（校准 12/12）", report.playtests_markdown(result))
        self.assertIn("满分过半的维度（锚点太松，下一轮收紧）：无", report.playtests_markdown(result))
        (row,) = result["rows"]
        # the fake host opens a daily game with seed 7; the Skill it ran is named by its files
        self.assertEqual((row["run"], row["mode"], row["seed"]), (1, "daily", 7))
        self.assertTrue(row["world"])
        self.assertEqual(len(row["skill"]), 16)
        (group,) = result["summary"]
        self.assertEqual((group["world"], group["runs"], group["seeds"], group["reviewed"]), (row["world"], 1, 1, 1))
        self.assertEqual((group["medians"]["玩家主权"], group["medians"]["表达"]), (2, 4))
        self.assertEqual(group["critical_low"], [{"file": name, "dimension": "玩家主权", "score": 2}])
        self.assertIn("| %s | daily | 1 | 1 |" % row["world"], report.playtests_markdown(result))
        # a dimension where more than half the runs score 5
        answer["scores"]["表达"]["score"] = 5
        with open(os.path.join(temp, "reviews", "fake", name), "w", encoding="utf-8") as handle:
            json.dump(answer, handle, ensure_ascii=False)
        result = report.playtests(records, os.path.join(temp, "reviews"), calibration)
        self.assertEqual(result["ceiling"], ["表达"])
        self.assertIn("满分过半的维度（锚点太松，下一轮收紧）：表达", report.playtests_markdown(result))
        # a reviewer that passed no calibration is shown and not counted
        result = report.playtests(records, os.path.join(temp, "reviews"), [self.calibration(by="reviewer-y")])
        (group,) = result["summary"]
        self.assertEqual((group["reviewed"], group["medians"]["表达"], group["critical_low"], result["ceiling"]), (0, None, [], []))
        self.assertIn("评审者：reviewer-x 1 条（未通过校准，不计入）", report.playtests_markdown(result))
        self.assertIn("| 评审者未通过校准 |", report.playtests_markdown(result))


class ReviewTest(unittest.TestCase):
    def answer(self, **scores):
        return {"scores": {d: {"score": scores.get(d, 4), "evidence": ["第 1 轮：……——……"]} for d in report.DIMENSIONS}, "severe": []}

    def test_the_answer_is_the_json_object_reviewer_md_asks_for(self):
        good = self.answer(**{"关系节奏": "n/a"})
        self.assertEqual(review.parse_answer("```json\n%s\n```" % json.dumps(good, ensure_ascii=False)), good)
        self.assertEqual(review.parse_answer("评审如下：%s" % json.dumps(good, ensure_ascii=False)), good)
        self.assertIsNone(review.parse_answer("我无法评审这条记录。"))
        self.assertEqual(review.problems_of(good), [])
        bad = self.answer(**{"表达": 6, "知识边界": True})
        del bad["scores"]["连续性"]
        self.assertEqual(len(review.problems_of(bad)), 3)
        self.assertEqual(review.problems_of(None), ["不是 JSON 对象"])

    def test_only_the_packet_is_sent_and_only_the_format_is_asked_again(self):
        path = os.path.join(_bootstrap.E2E_DIR, "calibration", "good-1.json")
        sent = []
        # quoting the player with plain double quotes breaks the JSON
        broken = '{"scores": {"玩家主权": {"score": 5, "evidence": ["第 3 轮：玩家说"我说：好"——兑现"]}}}'
        answers = [broken, "```json\n%s\n```" % json.dumps(self.answer(**{"表达": 2}), ensure_ascii=False)]

        def send(endpoint, messages):
            sent.append([dict(m) for m in messages])
            return answers[len(sent) - 1], "served-x"

        out = review.review(path, {"REVIEW_MODEL": "m"}, send=send)
        self.assertEqual(sent[0], [{"role": "user", "content": report.packet(path)}])
        # asked again with nothing new but the failed answer and where its form is wrong
        self.assertEqual(sent[1][:2], [{"role": "user", "content": report.packet(path)}, {"role": "assistant", "content": broken}])
        again = sent[1][2]["content"]
        self.assertEqual(sent[1][2]["role"], "user")
        self.assertIn("第 1 行第", again)
        self.assertIn("分数和证据都不要改", again)
        # the scores are the reviewer's, as given
        self.assertEqual(out["scores"]["表达"]["score"], 2)
        self.assertEqual([a["problems"] == [] for a in out["reviewer"]["attempts"]], [False, True])
        self.assertTrue(out["reviewer"]["usable"])
        never = review.review(path, {"REVIEW_MODEL": "m"}, send=lambda endpoint, messages: ("没有 JSON", None))
        self.assertEqual((never["scores"], never["reviewer"]["usable"], len(never["reviewer"]["attempts"])), (None, False, 3))
        self.assertEqual(review.outcome(never["reviewer"]), "3 次都不是要求的格式")
        self.assertEqual(review.json_error("没有 JSON"), "回答里没有 JSON 对象")

    def test_an_endpoint_that_refuses_is_recorded_with_what_it_said(self):
        path = os.path.join(_bootstrap.E2E_DIR, "calibration", "good-1.json")
        body = b'{"error":{"message":"unknown provider for model m (key sk-secret)","code":"model_not_found"}}'

        def send(endpoint, messages):
            raise urllib.error.HTTPError("http://x/v1/chat/completions", 400, "Bad Request", {}, io.BytesIO(body))

        out = review.review(path, {"REVIEW_MODEL": "m", "REVIEW_API_KEY": "sk-secret"}, send=send, wait=0)
        attempts = out["reviewer"]["attempts"]
        self.assertEqual([a["error"] for a in attempts], ["HTTP 400"] * 3)
        self.assertIn("model_not_found", attempts[0]["detail"])
        self.assertNotIn("sk-secret", json.dumps(out))
        self.assertFalse(out["reviewer"]["usable"])
        # not an answer in the wrong form: no answer at all, and why
        self.assertTrue(review.outcome(out["reviewer"]).startswith("3 次都没有拿到回答：HTTP 400"))

    def test_the_review_packet_holds_only_rules_rubric_and_record(self):
        path = os.path.join(_bootstrap.E2E_DIR, "calibration", "good-1.json")
        text = report.packet(path)
        self.assertIn("# 评分量表", text)
        self.assertIn("## 1. 玩家主权", text)
        self.assertIn("工具调用：new-game", text)
        self.assertNotIn("expect", text)
        self.assertNotIn("calls_max", text)


class ParserTest(unittest.TestCase):
    def test_opencode_events_from_the_stage0_transcript(self):
        path = os.path.join(_bootstrap.REPO_ROOT, "reports", "host", "stage0", "opencode-transcript.jsonl")
        with open(path, "rb") as handle:
            parsed = H.parse_opencode_stream(H._events(handle.read()))
        self.assertTrue(parsed["session_id"].startswith("ses_"))
        self.assertEqual([c["tool"] for c in parsed["host_calls"]], ["skill", "bash", "bash"])
        self.assertIn("doctor --json", parsed["host_calls"][2]["input"]["command"])
        self.assertIn("环境已就绪", parsed["text"])
        self.assertIsNone(parsed["error"])

    def test_claude_stream_json(self):
        events = [
            {"type": "system", "subtype": "init", "session_id": "abc", "model": "claude-x"},
            {"type": "assistant", "session_id": "abc", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "python x doctor --json"}}]}},
            {"type": "user", "session_id": "abc", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "{\"ok\": true}"}]}]}},
            {"type": "assistant", "session_id": "abc", "message": {"content": [{"type": "text", "text": "环境没问题。"}]}},
            {"type": "result", "subtype": "success", "session_id": "abc", "result": "环境没问题。", "total_cost_usd": 0.01},
        ]
        raw = "\n".join(json.dumps(e, ensure_ascii=False) for e in events).encode("utf-8")
        parsed = H.parse_claude_stream(H._events(raw))
        self.assertEqual((parsed["session_id"], parsed["model"], parsed["text"]), ("abc", "claude-x", "环境没问题。"))
        self.assertEqual(parsed["host_calls"], [{"tool": "Bash", "input": {"command": "python x doctor --json"}, "output": "{\"ok\": true}"}])
        self.assertIsNone(parsed["error"])

    def test_errors_the_host_reports_are_kept(self):
        def claude(result):
            events = [{"type": "system", "subtype": "init", "session_id": "abc", "model": "claude-x"}, dict(result, type="result", session_id="abc")]
            return H.parse_claude_stream(H._events("\n".join(json.dumps(e, ensure_ascii=False) for e in events).encode("utf-8")))

        self.assertIn("error_max_turns", claude({"subtype": "error_max_turns", "is_error": True})["error"])
        self.assertIn("API Error: 529", claude({"subtype": "success", "is_error": True, "result": "API Error: 529"})["error"])
        # the error message the host wrote itself does not name the model
        synthetic = [
            {"type": "system", "subtype": "init", "session_id": "abc", "model": "claude-x"},
            {"type": "assistant", "session_id": "abc", "message": {"model": "<synthetic>", "content": [{"type": "text", "text": "API Error: 429"}]}},
            {"type": "result", "subtype": "success", "is_error": True, "session_id": "abc", "result": "API Error: 429"},
        ]
        self.assertEqual(H.parse_claude_stream(synthetic)["model"], "claude-x")
        self.assertIsNone(claude({"subtype": "success", "is_error": False, "result": "好。"})["error"])
        parsed = H.parse_opencode_stream([{"type": "text", "sessionID": "ses_1", "part": {"text": "半句"}}, {"type": "error", "sessionID": "ses_1", "error": {"name": "APIError"}}])
        self.assertEqual((parsed["session_id"], parsed["text"]), ("ses_1", "半句"))
        self.assertIn("APIError", parsed["error"])

    def pi(self, *messages, extra=()):
        events = [{"type": "session", "version": 3, "id": "01a0-sid", "cwd": "D:\\p"}, {"type": "agent_start"}]
        events += [{"type": "message_end", "message": m} for m in messages] + list(extra)
        return H.parse_pi_stream(H._events("\n".join(json.dumps(e, ensure_ascii=False) for e in events).encode("utf-8")))

    def test_pi_json_events(self):
        # the shapes of a real run (pi 0.87.1): a bash call, its result, the reply
        call = {"type": "toolCall", "id": "c1", "name": "bash", "arguments": {"command": "python x doctor --json"}}
        parsed = self.pi(
            {"role": "user", "content": [{"type": "text", "text": "开一局"}]},
            {"role": "assistant", "provider": "local", "model": "m-1", "stopReason": "toolUse", "content": [{"type": "thinking", "thinking": "先查环境"}, call], "usage": {"cost": {"total": 0}}},
            {"role": "toolResult", "toolCallId": "c1", "toolName": "bash", "content": [{"type": "text", "text": "{\"ok\": true}"}], "isError": False},
            {"role": "assistant", "provider": "local", "model": "m-1", "stopReason": "stop", "content": [{"type": "text", "text": "环境没问题。"}]},
        )
        self.assertEqual((parsed["session_id"], parsed["model"], parsed["text"]), ("01a0-sid", "local/m-1", "环境没问题。"))
        self.assertEqual(parsed["host_calls"], [{"tool": "bash", "input": {"command": "python x doctor --json"}, "output": "{\"ok\": true}", "status": "completed"}])
        self.assertIsNone(parsed["error"])
        self.assertIsNone(parsed["cost"])
        # the name asked for can be an alias: the model is the one the endpoint says answered
        parsed = self.pi({"role": "assistant", "provider": "local", "model": "m-high", "responseModel": "m-exp-a", "stopReason": "stop",
                          "content": [{"type": "text", "text": "好。"}]})
        self.assertEqual(parsed["model"], "local/m-exp-a")
        # the endpoint switched models within one turn: every model that answered; a failed message names none
        first = {"role": "assistant", "provider": "local", "model": "m-high", "responseModel": "m-flash", "stopReason": "toolUse", "content": [call]}
        failed = {"role": "assistant", "provider": "local", "model": "m-high", "stopReason": "error", "errorMessage": "503", "content": []}
        last = {"role": "assistant", "provider": "local", "model": "m-high", "responseModel": "m-exp-a", "stopReason": "stop", "content": [{"type": "text", "text": "好。"}]}
        self.assertEqual(self.pi(first, failed, last)["model"], "local/m-exp-a+local/m-flash")
        self.assertEqual(self.pi(first, failed)["model"], "local/m-flash")
        self.assertEqual(self.pi(failed)["model"], "local/m-high")

    def test_pi_errors_and_retries(self):
        failed = {"role": "assistant", "provider": "local", "model": "m-1", "stopReason": "error", "errorMessage": "429 Too Many Requests", "content": [{"type": "text", "text": "半句"}]}
        reply = {"role": "assistant", "provider": "local", "model": "m-1", "stopReason": "stop", "content": [{"type": "text", "text": "好。"}]}
        parsed = self.pi(failed)
        self.assertIn("429", parsed["error"])
        self.assertEqual(parsed["text"], "")
        # a retry that succeeded: the failed message is not part of the reply
        parsed = self.pi(failed, reply)
        self.assertEqual((parsed["text"], parsed["error"]), ("好。", None))
        self.assertIn("length", self.pi(dict(reply, stopReason="length"))["error"])
        parsed = self.pi(failed, extra=[{"type": "auto_retry_end", "success": False, "attempt": 3, "finalError": "overloaded"}])
        self.assertIn("overloaded", parsed["error"])


class HostCallsTest(unittest.TestCase):
    """Runtime calls rebuilt from the host's own tool calls (a Skill older than the trace)."""

    RUNTIME = "python .claude/skills/adult-tension/scripts/adult_tension.py"

    def bash(self, command, *envelopes, raw=None):
        output = raw if raw is not None else "\n".join(json.dumps(e, ensure_ascii=False, indent=1) for e in envelopes)
        return {"tool": "Bash", "input": {"command": command}, "output": output}

    def test_claude_code_writes_the_input_file_then_runs_the_runtime(self):
        payload = {"request_id": "req_00000001", "mode": "daily"}
        answer = envelope({"session_id": "s_1"})
        script = "D:\\p\\.claude\\skills\\adult-tension\\scripts\\adult_tension.py"
        calls = R.calls_from_host([
            {"tool": "Write", "input": {"file_path": "D:\\p\\tmp\\in.json", "content": json.dumps(payload, ensure_ascii=False)}, "output": "ok"},
            self.bash('python "%s" new-game --json --input-file "D:\\p\\tmp\\in.json" 2>&1' % script, answer),
        ])
        self.assertEqual(calls, [{"argv": ["new-game", "--json", "--input-file", "D:\\p\\tmp\\in.json"], "input": payload, "exit": None, "envelope": answer, "ms": None, "source": "host"}])

    def test_the_input_file_under_other_spellings_and_the_latest_write_wins(self):
        calls = R.calls_from_host([
            {"tool": "Write", "input": {"file_path": "D:\\p\\in.json", "content": json.dumps({"n": 1})}},
            self.bash("python /d/p/.claude/skills/adult-tension/scripts/adult_tension.py commit-turn --json --input-file /d/p/in.json", envelope({})),
            {"tool": "Write", "input": {"file_path": "D:\\p\\in.json", "content": json.dumps({"n": 2})}},
            self.bash("%s commit-turn --json --input-file ./in.json" % self.RUNTIME, envelope({})),
            {"tool": "Edit", "input": {"file_path": "D:\\p\\in.json", "old_string": "2", "new_string": "3"}},
            self.bash("%s commit-turn --json --input-file=in.json" % self.RUNTIME, envelope({})),
            self.bash("%s commit-turn --json --input-file missing.json" % self.RUNTIME, envelope({})),
        ])
        self.assertEqual([c["input"] for c in calls], [{"n": 1}, {"n": 2}, {"n": 3}, None])

    def test_opencode_tool_names_and_keys(self):
        runtime = "python D:/p/.claude/skills/adult-tension/scripts/adult_tension.py save-slot --json --input-file D:/p/in.json"
        calls = R.calls_from_host([
            {"tool": "write", "input": {"filePath": "D:/p/in.json", "content": json.dumps({"request_id": "req_00000002"})}, "output": "", "status": "completed"},
            {"tool": "bash", "input": {"command": runtime, "description": "存档"}, "output": json.dumps(envelope({"receipt": "已保存"}), ensure_ascii=False), "status": "completed"},
            {"tool": "edit", "input": {"filePath": "D:/p/in.json", "oldString": "req_00000002", "newString": "req_00000003"}, "output": "", "status": "completed"},
            {"tool": "bash", "input": {"command": runtime}, "output": json.dumps(envelope({})), "status": "completed"},
        ])
        self.assertEqual([(R.command_of(c), c["input"]["request_id"]) for c in calls], [("save-slot", "req_00000002"), ("save-slot", "req_00000003")])
        self.assertEqual(R.ok_data(calls[0]), {"receipt": "已保存"})

    def test_pi_tool_names_and_keys(self):
        runtime = "python D:/p/.claude/skills/adult-tension/scripts/adult_tension.py commit-turn --json --input-file D:/p/in.json"
        ran = {"tool": "bash", "input": {"command": runtime}, "output": json.dumps(envelope({})), "status": "completed"}
        calls = R.calls_from_host([
            {"tool": "write", "input": {"path": "D:/p/in.json", "content": json.dumps({"request_id": "req_00000005"})}, "output": "Successfully wrote to D:/p/in.json", "status": "completed"},
            ran,
            {"tool": "edit", "input": {"path": "D:/p/in.json", "edits": [{"oldText": "req_00000005", "newText": "req_00000006"}]}, "output": "", "status": "completed"},
            ran,
            # the older single-replacement form
            {"tool": "edit", "input": {"path": "D:/p/in.json", "oldText": "req_00000006", "newText": "req_00000007"}, "output": "", "status": "completed"},
            # reading a file changes nothing
            {"tool": "read", "input": {"path": "D:/p/in.json"}, "output": "{}", "status": "completed"},
            ran,
        ])
        self.assertEqual([c["input"]["request_id"] for c in calls], ["req_00000005", "req_00000006", "req_00000007"])

    def test_heredocs_into_a_file_or_into_stdin(self):
        body = json.dumps({"request_id": "req_00000004", "note": "adult_tension.py doctor"}, ensure_ascii=False)
        calls = R.calls_from_host([
            self.bash("cat > /tmp/a.json <<'EOF'\n%s\nEOF\n%s new-game --json --input-file /tmp/a.json" % (body, self.RUNTIME), envelope({"n": 1})),
            self.bash("cat <<EOF > b.json\n%s\nEOF\n%s new-game --json --input-file b.json" % (body, self.RUNTIME), envelope({"n": 2})),
            self.bash("%s commit-turn --json <<'JSON'\n%s\nJSON" % (self.RUNTIME, body), envelope({"n": 3})),
        ])
        # the runtime named inside a heredoc body is data, not a call
        self.assertEqual([R.command_of(c) for c in calls], ["new-game", "new-game", "commit-turn"])
        self.assertEqual([c["input"]["request_id"] for c in calls], ["req_00000004"] * 3)
        self.assertEqual([R.ok_data(c)["n"] for c in calls], [1, 2, 3])

    def test_chained_calls_other_commands_and_unreadable_output(self):
        runtime = 'python "C:\\Users\\x\\skills\\adult-tension\\scripts\\adult_tension.py"'
        first = envelope({"status": "ok"})
        second = {"ok": False, "data": None, "error": {"code": "NOT_FOUND", "message": "没有这个存档", "details": []}}
        calls = R.calls_from_host([
            self.bash("ls -la", raw="total 0"),
            self.bash("%s doctor --json && %s list-slots --json" % (runtime, runtime), raw="warning: x\n" + json.dumps(first, indent=1) + "\n" + json.dumps(second, ensure_ascii=False)),
            self.bash("%s status --json 2>&1" % runtime, raw="Traceback (most recent call last): {broken"),
        ])
        self.assertEqual([c["argv"] for c in calls], [["doctor", "--json"], ["list-slots", "--json"], ["status", "--json"]])
        self.assertEqual([c["envelope"] for c in calls], [first, second, None])
        self.assertEqual(R.error_code(calls[1]), "NOT_FOUND")
        record = {"script": "x", "run": 1, "turns": [{"index": 1, "input": "状态", "runtime_calls": calls[2:], "text": ""}]}
        self.assertIn("宿主的记录里没有可解析的返回", R.to_markdown(record))

    def test_a_command_the_shell_could_not_parse_never_ran(self):
        runtime = 'python "D:/p/.claude/skills/adult-tension/scripts/adult_tension.py"'
        calls = R.calls_from_host([
            # the closing quote is missing: bash stops before running anything
            {"tool": "bash", "input": {"command": '%s commit-turn --json --input-file "D:/p/in.json' % runtime}, "output": "/usr/bin/bash: -c: line 1: unexpected EOF while looking for matching `\"'\n", "status": "completed"},
            # the first line is complete and ran; the broken second line did not
            self.bash('%s status --json\n%s commit-turn --json --input-file "D:/p/in.json' % (runtime, runtime), raw=json.dumps(envelope({"n": 1})) + "\nbash: -c: line 2: unexpected EOF while looking for matching `\"'"),
            self.bash("%s doctor --json" % runtime, envelope({"n": 2})),
        ])
        self.assertEqual([R.command_of(c) for c in calls], ["status", "doctor"])
        self.assertEqual([R.ok_data(c)["n"] for c in calls], [1, 2])


class RunnerTest(unittest.TestCase):
    def test_seed_placeholders_come_from_the_opening_of_that_turn(self):
        turns = [{"index": 8, "runtime_calls": [{"argv": ["new-game"], "envelope": envelope({"seed": 4242})}]}]
        self.assertEqual(run_script.fill_placeholders("不存档，重开 {seed:8} 号", turns), "不存档，重开 4242 号")
        self.assertEqual(run_script.fill_placeholders("重开 {seed:3} 号", turns), "重开 ? 号")

    def test_every_script_is_player_voice_with_valid_annotations(self):
        banned = ["result", "attempt", "commit", "npc_", "字段", "档位", "revision", "请注意"]
        dirs = (run_script.SCRIPTS, run_script.DRILLS, run_script.PLAYTESTS)
        paths = [os.path.join(d, n) for d in dirs for n in os.listdir(d)]
        for name in sorted(paths):
            script = run_script.load_script(name)
            says = [s["say"] for s in script["steps"] if "say" in s]
            self.assertEqual(len(says), script["player_turns"], name)
            for say in says:
                self.assertFalse(any(b in say for b in banned), (name, say))
            for step in script["steps"]:
                self.assertTrue("say" in step or step.get("harness") == "upgrade_skill", (name, step))
        self.assertEqual(len(os.listdir(run_script.SCRIPTS)), 16)

    def test_playtests_open_every_world_in_both_modes_then_save_and_load(self):
        # CONTENT_BIBLE 8.2 step 6: every world, both modes (each played with 5 seeds, one run each)
        with open(os.path.join(_bootstrap.REPO_ROOT, "skill", "adult-tension", "content", "index.json"), encoding="utf-8") as handle:
            worlds = json.load(handle)["worlds"]
        for world in worlds:
            for mode in world["modes"]:
                script = run_script.load_script("pt-%s-%s" % (world["id"], mode))
                says = [s for s in script["steps"] if "say" in s]
                self.assertEqual((script["world"], script["mode"]), (world["id"], mode))
                self.assertIn(world["title"], says[0]["say"])
                self.assertEqual(says[0]["expect"]["group_must_call"], ["doctor", "new-game"])
                self.assertIn("继续", [s["say"] for s in says])
                self.assertEqual(says[-3]["expect"]["must_call"], ["save-slot"])
                self.assertEqual((says[-2].get("conversation"), says[-2]["expect"]["must_call"]), ("B", ["load-slot"]))
        # the stage 1 playtest: opening, 10 turns, a save, a load in a new conversation
        stage1 = run_script.load_script("pt-stage1")
        kinds = [s["expect"]["kind"] for s in stage1["steps"] if s.get("conversation", "A") == "A"]
        self.assertEqual(kinds, ["opening"] + ["turn"] * 10 + ["meta"])
        self.assertEqual(run_script.run_tag(stage1, "claude-code", 2), "claude-code-pt-stage1-r2")
        self.assertEqual(run_script.run_tag({"id": "07"}, "claude-code", 1), "claude-code-s07-r1")

    def test_the_release_drill_follows_skill_packaging_9(self):
        script = run_script.load_script(os.path.join(run_script.DRILLS, "release-drill.json"))
        self.assertEqual(script["setup"], {"install": "previous", "data_dir": "default", "include_drafts": False})
        steps = script["steps"]
        says = [s for s in steps if "say" in s]
        self.assertEqual(len(says), script["player_turns"])
        upgrade = steps.index({"harness": "upgrade_skill"})
        before, after = [s for s in steps[:upgrade] if "say" in s], [s for s in steps[upgrade + 1 :] if "say" in s]
        # a new conversation, "开一局", 3 turns with one "继续", a save; a new conversation loads it
        self.assertEqual(before[0]["say"], "开一局")
        turns = [s for s in before if s["expect"]["kind"] == "turn"]
        self.assertEqual(len(turns), 3)
        self.assertIn("继续", [s["say"] for s in turns])
        self.assertIn("save-slot", before[-2]["expect"]["must_call"])
        self.assertEqual((before[-1]["conversation"], before[-1]["expect"]["must_call"]), ("B", ["load-slot"]))
        # after the upgrade, one more turn in that conversation
        self.assertEqual([(s["conversation"], s["expect"]["kind"]) for s in after], [("B", "turn")])

    def test_host_environment_follows_the_script_setup(self):
        base = {"PATH": "x", "ADULT_TENSION_HOME": "D:\\elsewhere", "ADULT_TENSION_INCLUDE_DRAFTS": "1"}
        project = os.path.join("D:\\", "projects", "at-e2e", "p")
        env = run_script.host_env({}, project, base)
        self.assertEqual(
            (env["ADULT_TENSION_HOME"], env["ADULT_TENSION_TRACE"], env["PATH"]),
            (os.path.join(project, ".at-data"), os.path.join(project, "trace.jsonl"), "x"),
        )
        # the worlds are released: the draft switch only when a script asks for it (an older Skill)
        self.assertNotIn("ADULT_TENSION_INCLUDE_DRAFTS", env)
        self.assertEqual(run_script.host_env({"include_drafts": True}, project, base)["ADULT_TENSION_INCLUDE_DRAFTS"], "1")
        drill = run_script.host_env({"data_dir": "default", "include_drafts": False}, project, base)
        self.assertNotIn("ADULT_TENSION_HOME", drill)
        self.assertNotIn("ADULT_TENSION_INCLUDE_DRAFTS", drill)
        self.assertEqual(drill["ADULT_TENSION_TRACE"], os.path.join(project, "trace.jsonl"))
        self.assertEqual(base["ADULT_TENSION_HOME"], "D:\\elsewhere")

    def test_the_host_starts_as_a_session_of_its_own_with_the_operators_settings(self):
        project = os.path.join("D:\\", "projects", "at-e2e", "p")
        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        path = os.path.join(temp, "host.env")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# the model endpoint\nANTHROPIC_BASE_URL=http://127.0.0.1:1/\n\nANTHROPIC_AUTH_TOKEN = mine\n")
        extra = run_script.read_env_file(path)
        # run by a Claude Code session: its own session, login and model settings stay behind
        calling = {"PATH": "x", "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "s", "CLAUDE_PID": "7", "ANTHROPIC_AUTH_TOKEN": "parent", "ANTHROPIC_MODEL": "m"}
        env = run_script.host_env({}, project, calling, extra)
        self.assertEqual({k: v for k, v in env.items() if k.startswith(("CLAUDE", "ANTHROPIC_"))}, {"ANTHROPIC_BASE_URL": "http://127.0.0.1:1/", "ANTHROPIC_AUTH_TOKEN": "mine"})
        self.assertEqual(env["PATH"], "x")
        # from a plain terminal nothing of the operator's is dropped
        self.assertEqual(run_script.host_env({}, project, {"PATH": "x", "ANTHROPIC_API_KEY": "k"})["ANTHROPIC_API_KEY"], "k")
        # the record shows the settings without the secrets
        self.assertEqual(run_script.shown_env(dict(extra, X_API_KEY="k")), {"ANTHROPIC_AUTH_TOKEN": "<set>", "ANTHROPIC_BASE_URL": "http://127.0.0.1:1/", "X_API_KEY": "<set>"})
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("ANTHROPIC_BASE_URL\n")
        with self.assertRaises(SystemExit):
            run_script.read_env_file(path)

    def test_claude_code_runs_isolated_with_command_line_permissions(self):
        host = H.ClaudeCode("D:\\p", {}, model="m-1", exe="C:\\host\\claude.exe")
        first = host.command("A", "开一局")
        # the player's words are the prompt, right after -p; nothing else is said to the model
        self.assertEqual(first[:3], ["C:\\host\\claude.exe", "-p", "开一局"])
        for flag in ("--setting-sources", "--strict-mcp-config", "--allowedTools", "--disallowedTools", "--permission-mode"):
            self.assertIn(flag, first)
        self.assertEqual(first[first.index("--setting-sources") + 1], "project,local")
        self.assertNotIn("--resume", first)
        self.assertEqual(first[first.index("--model") + 1], "m-1")
        host.sessions["A"] = "sid-1"
        self.assertEqual(host.command("A", "继续")[-2:], ["--resume", "sid-1"])
        self.assertIsNone(H.project_config("claude-code", "D:\\p"))

    def test_opencode_runs_isolated_from_the_operators_configuration(self):
        project = os.path.join("D:\\", "projects", "at-e2e", "p")
        host = H.OpenCode(project, {"PATH": "x", "XDG_CONFIG_HOME": "C:\\mine"}, model="local/m-1", exe="C:\\host\\opencode.exe")
        first = host.command("A", "开一局")
        # the player's words are the message; nothing else is said to the model
        self.assertEqual(first[0], "C:\\host\\opencode.exe")
        self.assertEqual(first[-1], "开一局")
        self.assertEqual(first[first.index("-m") + 1], "local/m-1")
        self.assertEqual(first[first.index("--dir") + 1], project)
        self.assertNotIn("--session", first)
        host.sessions["A"] = "ses_1"
        self.assertEqual(host.command("A", "继续")[-3:], ["--session", "ses_1", "继续"])
        # the global configuration and the sessions are the project's own, not the operator's
        self.assertEqual(host.env["XDG_CONFIG_HOME"], os.path.join(project, ".host", "config"))
        self.assertEqual(host.env["OPENCODE_DB"], os.path.join(project, ".host", "opencode.db"))
        # its scratch files (the runtime's input files) too: runs side by side never share one
        self.assertEqual((host.env["TEMP"], host.env["TMP"]), (os.path.join(project, ".host", "tmp"),) * 2)
        for flag in ("OPENCODE_DISABLE_EXTERNAL_SKILLS", "OPENCODE_DISABLE_CLAUDE_CODE_PROMPT", "OPENCODE_DISABLE_AUTOUPDATE", "OPENCODE_DISABLE_SHARE"):
            self.assertEqual(host.env[flag], "1")
        self.assertEqual(host.env["PATH"], "x")
        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        with open(H.project_config("opencode", temp), encoding="utf-8") as handle:
            config = json.load(handle)
        # the Skill is found where run_script installs it; sessions are never shared
        self.assertEqual(config["skills"]["paths"], [os.path.dirname(run_script.SKILL_REL).replace(os.sep, "/")])
        self.assertEqual(config["share"], "disabled")
        self.assertEqual(config["permission"]["bash"]["*"], "deny")
        self.assertEqual(config["permission"]["webfetch"], "deny")

    def test_pi_runs_isolated_from_the_operators_configuration(self):
        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        models = os.path.join(temp, "models.json")
        with open(models, "w", encoding="utf-8") as handle:
            handle.write("{\"providers\": {}}\n")
        project = os.path.join("D:\\", "projects", "at-e2e", "p")
        operator = {"PATH": "x", "AT_PI_MODELS": models, "PI_CODING_AGENT_DIR": "C:\\mine"}
        host = H.Pi(project, operator, model="local/m-1", exe="C:\\host\\pi.exe")
        first = host.command("A", "开一局")
        # the player's words are the message, after "--"; nothing else is said to the model
        self.assertEqual(first[:4], ["C:\\host\\pi.exe", "-p", "--mode", "json"])
        self.assertEqual(first[-2:], ["--", "开一局"])
        # only the Skill installed for the run: nothing discovered, no extensions
        for flag in ("--no-skills", "--no-extensions", "--no-prompt-templates", "--no-themes"):
            self.assertIn(flag, first)
        self.assertEqual(first[first.index("--skill") + 1], os.path.join(project, run_script.SKILL_REL))
        self.assertEqual(first[first.index("--model") + 1], "local/m-1")
        self.assertNotIn("--session", first)
        host.sessions["A"] = "sid-1"
        self.assertEqual(host.command("A", "继续")[-4:], ["--session", "sid-1", "--", "继续"])
        # settings, models, credentials and sessions are the project's own, not the operator's
        self.assertEqual(host.env["PI_CODING_AGENT_DIR"], os.path.join(project, ".host", "pi-agent"))
        self.assertEqual(first[first.index("--session-dir") + 1], os.path.join(project, ".host", "sessions"))
        self.assertEqual((host.env["TEMP"], host.env["TMP"]), (os.path.join(project, ".host", "tmp"),) * 2)
        self.assertEqual((host.env["PI_OFFLINE"], host.env["PI_TELEMETRY"]), ("1", "0"))
        self.assertEqual(host.env["PATH"], "x")
        self.assertIsNone(H.project_config("pi", project))
        # the operator names the model provider; without it there is no run
        with self.assertRaises(H.HostError):
            H.Pi(project, {"PATH": "x"}, model="local/m-1", exe="C:\\host\\pi.exe")

    def test_pi_runs_its_cli_script_under_node_not_through_the_npm_shim(self):
        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        package = os.path.join(temp, "node_modules", "@earendil-works", "pi-coding-agent")
        os.makedirs(package)
        with open(os.path.join(package, "package.json"), "w", encoding="utf-8") as handle:
            json.dump({"bin": {"pi": "dist/bundle/cli.js"}}, handle)
        open(os.path.join(temp, "node.exe"), "w").close()
        self.assertEqual(H._pi_argv(os.path.join(temp, "pi.cmd")), [os.path.join(temp, "node.exe"), os.path.join(package, "dist/bundle/cli.js")])
        self.assertEqual(H._pi_argv("/usr/local/bin/pi"), ["/usr/local/bin/pi"])
        with self.assertRaises(H.HostError):
            H._pi_argv(os.path.join(temp, "elsewhere", "pi.cmd"))

    def test_a_fake_host_run_records_calls_state_and_identity(self):
        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        script = run_script.load_script("01")
        path, rec = run_script.run(script, "fake", 1, None, os.path.join(temp, "projects"), os.path.join(temp, "records"))
        self.assertEqual(R.validate(rec), [])
        self.assertEqual([len(t["runtime_calls"]) for t in rec["turns"]], [2, 1, 1, 1, 1, 1])
        self.assertEqual({t["calls_source"] for t in rec["turns"]}, {"trace"})
        for turn in rec["turns"]:
            # what the host's own record shows is what the engine traced
            shown = [(c["argv"][0], c["input"], c["envelope"]) for c in R.calls_from_host(turn["host_calls"])]
            traced = [(c["argv"][0], c["input"] or None, c["envelope"]) for c in turn["runtime_calls"]]
            self.assertEqual(shown, traced)
        self.assertEqual(M.check_record(rec), [])
        self.assertEqual(rec["final_export"]["format"], "adult-tension-save")
        self.assertTrue(rec["skill"]["skill_root"].startswith(os.path.join(temp, "projects")))
        self.assertTrue(os.path.isfile(path))
        markdown = R.to_markdown(rec)
        self.assertIn("工具调用：new-game", markdown)
        # turns that went well keep no raw host events unless asked
        self.assertFalse(any("events" in t for t in rec["turns"]))

    def test_a_turn_the_host_did_not_finish_keeps_the_calls_it_made(self):
        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        script = {"id": "err", "player_turns": 1, "steps": [{"say": "读档 没有这个存档"}]}
        _path, rec = run_script.run(script, "fake", 1, None, os.path.join(temp, "projects"), os.path.join(temp, "records"))
        self.assertEqual(R.validate(rec), [])
        turn = rec["turns"][0]
        self.assertIn("load-slot", turn["host_error"])
        self.assertEqual([R.command_of(c) for c in R.calls_from_host(turn["host_calls"])], ["doctor", "load-slot"])
        self.assertEqual([R.command_of(c) for c in turn["runtime_calls"]], ["doctor", "load-slot"])
        self.assertIsNotNone(R.error_code(turn["runtime_calls"][1]))
        self.assertEqual([(f["check"], f["turn"]) for f in M.check_record(rec)], [("record", 1)])
        # the failed turn keeps whatever the host reported, to find out why
        self.assertIn("events", turn)

    def test_an_older_skill_without_the_trace_is_recorded_from_host_calls_and_upgraded(self):
        import adult_tension

        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        script = {
            # the stage 3 Skill's worlds are all in review
            "id": "up", "setup": {"install": "previous", "include_drafts": True}, "player_turns": 5,
            "steps": [
                {"say": "开一局，日常"}, {"say": "继续"}, {"say": "存档 升级前"},
                {"harness": "upgrade_skill"},
                {"say": "读档 升级前", "conversation": "B"}, {"say": "继续", "conversation": "B"},
            ],
        }
        # the stage 3 Skill: database schema 2, no engine trace
        _path, rec = run_script.run(script, "fake", 1, None, os.path.join(temp, "projects"), os.path.join(temp, "records"), previous="2aa58c8")
        self.assertEqual([(i["skill_version"], i["db_schema"], i["trace"], i["after_turn"]) for i in rec["installs"]], [
            ("0.2.0", 2, False, 0),
            (adult_tension.SKILL_VERSION, adult_tension.DB_SCHEMA_VERSION, True, 3),
        ])
        self.assertEqual([t["calls_source"] for t in rec["turns"]], ["host", "host", "host", "trace", "trace"])
        self.assertEqual([[R.command_of(c) for c in t["runtime_calls"]] for t in rec["turns"]], [
            ["doctor", "new-game"], ["commit-turn"], ["save-slot"], ["doctor", "load-slot"], ["commit-turn"],
        ])
        self.assertTrue(all(R.ok_data(c) is not None for t in rec["turns"] for c in t["runtime_calls"]))
        self.assertEqual(rec["turns"][1]["runtime_calls"][0]["input"]["player_input"], "继续")
        saved = R.ok_data(rec["turns"][2]["runtime_calls"][0])["turn"]
        self.assertEqual(R.ok_data(rec["turns"][4]["runtime_calls"][0])["turn"], saved + 1)
        # the upgrade migrated the database and kept a copy of the old one
        backups = os.listdir(os.path.join(rec["project"], ".at-data", "backups"))
        self.assertEqual([b.startswith("adult_tension-schema2-") for b in backups], [True])
        self.assertEqual(rec["skill"]["skill_version"], adult_tension.SKILL_VERSION)
        self.assertEqual(M.check_structure(rec)[0], [])
        self.assertEqual(M.check_record(rec), [])


if __name__ == "__main__":
    unittest.main()
