"""The end-to-end harness itself: machine checks, stream parsers, runner.

These tests never call a model. Machine checks are exercised on small
records built here, each with and without the problem the check looks for.
"""

import copy
import json
import os
import shutil
import tempfile
import unittest

import _bootstrap  # noqa: F401
import hosts as H
import machine_checks as M
import record as R
import report
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

    def test_lines_the_player_never_said_are_ventriloquism(self):
        rec = clean_record()
        rec["turns"][2]["text"] = "你说：“我今晚哪儿也不去，就在这儿陪你到天亮。”\n\n" + footer(3, 1210)
        self.assertIn(("ventriloquism", 3), names(M.check(rec)))

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
    def review(self, low=(), score=4):
        return {"scores": {d: {"score": (2 if d in low else score), "evidence": ["第 1 轮：……"]} for d in report.DIMENSIONS}, "severe": []}

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
        self.assertEqual((result["correct"], result["ready"]), (12, True))
        wrong = dict(right, **{"flawed-1": self.review(), "flawed-2": self.review(), "good-1": self.review(low=("表达",))})
        self.write_reviews(temp, wrong)
        result = report.calibrate(temp)
        self.assertEqual((result["correct"], result["ready"]), (9, False))

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
        built = report.build(records, reviews)
        self.assertEqual(built["first_run_machine_pass"], "2/2")
        self.assertEqual(built["average_calls_per_ordinary_turn"], 1.0)
        self.assertEqual(sorted(built["ceiling"]), sorted(report.DIMENSIONS))
        self.assertTrue(built["pass"])
        self.write_reviews(os.path.join(reviews, "h2"), {"h2-st-r2": self.review(low=("同意与安全",))})
        built = report.build(records, reviews)
        self.assertFalse(built["pass"])
        self.assertEqual(built["critical_low"], [{"file": "h2-st-r2.json", "dimension": "同意与安全", "score": 2}])
        self.assertIn("同意与安全", report.to_markdown(built))

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
        self.assertIsNone(claude({"subtype": "success", "is_error": False, "result": "好。"})["error"])
        parsed = H.parse_opencode_stream([{"type": "text", "sessionID": "ses_1", "part": {"text": "半句"}}, {"type": "error", "sessionID": "ses_1", "error": {"name": "APIError"}}])
        self.assertEqual((parsed["session_id"], parsed["text"]), ("ses_1", "半句"))
        self.assertIn("APIError", parsed["error"])


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


class RunnerTest(unittest.TestCase):
    def test_seed_placeholders_come_from_the_opening_of_that_turn(self):
        turns = [{"index": 8, "runtime_calls": [{"argv": ["new-game"], "envelope": envelope({"seed": 4242})}]}]
        self.assertEqual(run_script.fill_placeholders("不存档，重开 {seed:8} 号", turns), "不存档，重开 4242 号")
        self.assertEqual(run_script.fill_placeholders("重开 {seed:3} 号", turns), "重开 ? 号")

    def test_every_script_is_player_voice_with_valid_annotations(self):
        banned = ["result", "attempt", "commit", "npc_", "字段", "档位", "revision", "请注意"]
        paths = [os.path.join(run_script.SCRIPTS, n) for n in os.listdir(run_script.SCRIPTS)] + [os.path.join(run_script.DRILLS, n) for n in os.listdir(run_script.DRILLS)]
        for name in sorted(paths):
            script = run_script.load_script(name)
            says = [s["say"] for s in script["steps"] if "say" in s]
            self.assertEqual(len(says), script["player_turns"], name)
            for say in says:
                self.assertFalse(any(b in say for b in banned), (name, say))
            for step in script["steps"]:
                self.assertTrue("say" in step or step.get("harness") == "upgrade_skill", (name, step))
        self.assertEqual(len(os.listdir(run_script.SCRIPTS)), 16)

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
            (env["ADULT_TENSION_HOME"], env["ADULT_TENSION_INCLUDE_DRAFTS"], env["ADULT_TENSION_TRACE"], env["PATH"]),
            (os.path.join(project, ".at-data"), "1", os.path.join(project, "trace.jsonl"), "x"),
        )
        drill = run_script.host_env({"data_dir": "default", "include_drafts": False}, project, base)
        self.assertNotIn("ADULT_TENSION_HOME", drill)
        self.assertNotIn("ADULT_TENSION_INCLUDE_DRAFTS", drill)
        self.assertEqual(drill["ADULT_TENSION_TRACE"], os.path.join(project, "trace.jsonl"))
        self.assertEqual(base["ADULT_TENSION_HOME"], "D:\\elsewhere")

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

    def test_an_older_skill_without_the_trace_is_recorded_from_host_calls_and_upgraded(self):
        import adult_tension

        temp = tempfile.mkdtemp(prefix="at-e2e-")
        self.addCleanup(shutil.rmtree, temp, True)
        script = {
            "id": "up", "setup": {"install": "previous"}, "player_turns": 5,
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
