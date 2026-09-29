"""The end-to-end report (ACCEPTANCE.md 6) and the reviewer calibration.

    python tests/e2e/harness/report.py packet --record <record.json> --out <file.md>
    python tests/e2e/harness/report.py calibrate --reviews <dir> [--same-model <served>=<model> ...]
    python tests/e2e/harness/report.py build --records <dir> --reviews <dir> --calibration <dir> [--calibration <dir> ...]
                                        [--same-model <served>=<model> ...] [--fixes <fixes.json>] [--candidate <digest>]
                                        [--note <text> ...] [--out <dir>]
    python tests/e2e/harness/report.py playtests --records <dir> --reviews <dir> --calibration <dir> [...]
                                        [--same-model <served>=<model> ...] [--out <dir>]
    python tests/e2e/harness/report.py agreement --first <reviews dir> --second <reviews dir> [--out <file.md>]

packet: what an independent reviewer gets, as one document: the reviewer
instructions, the rubric, NARRATIVE_RULES.md and the record. Nothing else:
no script focus, no expectations, no implementation (ACCEPTANCE 6.1 item 7).

The reviewer is the model the endpoint says answered (each attempt's
served_model), not the name asked for: a proxy can serve one name with
different models, even within one batch. --same-model says that two served
names are one model (the user's word on their own endpoint); the reports
print every such statement. A review is also known by the rubric version it
was made with (rubric.md states it; rubric_versions.json holds what each
version was), so a reviewer reads as "model（量表 N）".

calibrate: the reviewer's scores on the calibration set against key.json.
A good record is judged right when no dimension is <= 2; a record with a
planted defect when every planted dimension is <= 2. Below 10 of 12, fix the
anchors before the formal review (ACCEPTANCE 6.3). A calibration speaks for
one reviewer: all twelve answered by the same model under the same rubric
version. A new rubric version needs its own calibration.

playtests and build count a review only when its reviewer passed one of the
calibrations given; the others are shown and not counted.

agreement: two reviewers on the same records (<dir>/<host>/<file>): per
dimension how often they give the same score or differ by one, the mean of
second minus first, and how many scores of 2 or less each gives. A check on
a reviewer that is the model under test.

build: records are <records>/<host>/<host>-s<script>-r<run>.json, reviews
the reviewer's JSON for the same file name under <reviews>/<host>/. Run 1 of
each script on each host is the first run; later runs are kept and shown,
never substituted. fixes.json maps a record file name to what fixed it
({"commit": "...", "note": "..."}), so failures link to their fixes.

The verdict is on the candidate: the runs of the Skill a release would ship
(by default the repository's Skill directory, by the digest the records
carry; --candidate names another) of the scripts as they are now (the same
setup, player inputs, expectations and harness steps). All of those count, none is
picked; the other runs, from before a fix, are shown and not counted
(ACCEPTANCE 6.1 item 6). The first-run pass rate is over run 1 of every
script, whatever came after. Nor does a run count that failed only on turns
where the host gave the player nothing (no tool call, no text: the model
answered with an empty message): the user decided on 2026-09-29 that such a
run is made up by another run of the script (PROGRESS P10); a failure on any
other turn counts. The report passes only when every condition
holds, and it names each one that does not: at least two hosts, every
script (tests/e2e/scripts) at least three times on every host, no
machine-check failure, a counted review for every run, medians, critical
dimensions, the call budget. Each script's scores are shown run by run
(ACCEPTANCE 6.3: the spread, not only the mean). --note adds the operator's
word on a condition left unmet (for example a user's decision); it is
printed, and it changes no verdict.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E2E = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import machine_checks  # noqa: E402
import record as R  # noqa: E402
import run_script  # noqa: E402

DIMENSIONS = ("玩家主权", "NPC 意志", "知识边界", "关系节奏", "同意与安全", "世界具体性", "连续性", "表达")
CRITICAL = ("玩家主权", "同意与安全", "知识边界")
AVERAGE_CALLS_LIMIT = 1.2
MIN_HOSTS = 2  # ACCEPTANCE 6.1 item 4
RUNS_PER_SCRIPT = 3


REPO = os.path.dirname(os.path.dirname(E2E))
VERSION_RE = re.compile(r"^量表版本：(\d+)\s*$", re.M)


def _instructions():
    """reviewer.md and rubric.md as the packet holds them."""
    parts = []
    for name in ("reviewer.md", "rubric.md"):
        with open(os.path.join(E2E, name), encoding="utf-8") as handle:
            parts.append(handle.read().strip())
    return parts


def rubric_version():
    """The version rubric.md states. It covers reviewer.md as well: a change
    to either is a new version (rubric_versions.json)."""
    match = VERSION_RE.search(_instructions()[1])
    if not match:
        raise ValueError("rubric.md 没有写“量表版本：N”")
    return match.group(1)


def instructions_sha256():
    """What a rubric version stands for: the digest of reviewer.md and rubric.md."""
    return hashlib.sha256("\n\n---\n\n".join(_instructions()).encode("utf-8")).hexdigest()


def packet(record_path):
    rec = R.load(record_path)
    parts = []
    for path in (os.path.join(E2E, "reviewer.md"), os.path.join(E2E, "rubric.md"), os.path.join(REPO, "spec", "NARRATIVE_RULES.md")):
        with open(path, encoding="utf-8") as handle:
            parts.append(handle.read().strip())
    parts.append(R.to_markdown(rec).strip())
    return "\n\n---\n\n".join(parts) + "\n"


def _score(review, dimension):
    value = ((review or {}).get("scores") or {}).get(dimension, {}).get("score")
    return value if isinstance(value, int) else None


def usable(review):
    """A review with scores (review.py keeps unusable answers with scores None)."""
    return bool(review) and isinstance(review.get("scores"), dict)


def reviewer_of(review, same=None):
    """The model that answered: every served_model in the attempts (joined
    with + when they differ), the name asked for when no attempt names one
    (reviews written by hand), None when nothing is recorded. A served name
    in SAME ({served name: model}) counts as that model."""
    reviewer = (review or {}).get("reviewer") or {}
    same = same or {}
    served = sorted({same.get(a["served_model"], a["served_model"]) for a in reviewer.get("attempts") or [] if a.get("served_model")})
    return "+".join(served) if served else reviewer.get("model")


def rubric_of(review):
    """The rubric version the review was made with. Reviews from before the
    version was recorded all used version 1: the instructions from a50c76a
    on (the four reviews of calibration round 1 are older and part of no
    judgement)."""
    return str(((review or {}).get("reviewer") or {}).get("rubric_version") or 1)


def judge_of(review, same=None):
    """Who judged, as calibration and the reports count it: the model that
    answered and the rubric version it used; None when no model is recorded."""
    model = reviewer_of(review, same)
    return "%s（量表 %s）" % (model, rubric_of(review)) if model else None


def calibrate(reviews_dir, same=None):
    with open(os.path.join(E2E, "calibration", "key.json"), encoding="utf-8") as handle:
        key = json.load(handle)
    rows = []
    reviewers = set()
    for name, expected in sorted(key.items()):
        path = os.path.join(reviews_dir, name + ".json")
        if not os.path.exists(path):
            rows.append({"record": name, "right": False, "why": "没有评审结果"})
            continue
        with open(path, encoding="utf-8") as handle:
            review = json.load(handle)
        if not usable(review):
            rows.append({"record": name, "right": False, "why": "评审结果不可用（不是要求的格式）"})
            continue
        # who gave the scores; an unusable review is judged wrong and names no one
        reviewers.add(judge_of(review, same))
        low = [d for d in DIMENSIONS if (_score(review, d) or 5) <= 2]
        if expected["low"]:
            right = all(d in low for d in expected["low"])
            why = "植入的缺陷维度 %s；评审判为 ≤ 2 的：%s" % ("、".join(expected["low"]), "、".join(low) or "无")
        else:
            right = not low
            why = "好的记录；评审判为 ≤ 2 的：%s" % ("、".join(low) or "无")
        rows.append({"record": name, "right": right, "why": why})
    correct = sum(1 for r in rows if r["right"])
    # the result speaks for one reviewer only: the same known model, under one rubric version, answered every record
    reviewer = next(iter(reviewers)) if len(reviewers) == 1 else None
    return {"correct": correct, "total": len(rows), "reviewer": reviewer, "reviewers": sorted(r or "未记" for r in reviewers),
            "ready": correct >= 10 and reviewer is not None, "rows": rows}


def calibrated(calibration_dirs, same=None):
    """The reviewers that passed a calibration, each with its result ("12/12")."""
    out = {}
    for directory in calibration_dirs:
        result = calibrate(directory, same)
        if result["ready"]:
            out[result["reviewer"]] = "%d/%d" % (result["correct"], result["total"])
    return out


def _reviewers(rows, trusted):
    """Who reviewed how many records, and the calibration each passed (None: not calibrated, not counted)."""
    out = {}
    for row in rows:
        if row["reviewed_by"]:
            entry = out.setdefault(row["reviewed_by"], {"reviews": 0, "calibration": trusted.get(row["reviewed_by"])})
            entry["reviews"] += 1
    return out


def _number(value):
    """A median as the reports print it: 5 rather than 5.0, a dash for none."""
    return "—" if value is None else "%g" % value


def _same_text(same):
    """The served names taken as one model, as the reports print them."""
    return "；".join("%s 与 %s 视为同一个模型（用户确认）" % (served, model) for served, model in sorted((same or {}).items()))


def _reviewers_text(reviewers):
    return "；".join("%s，%d 条（%s）" % (name, v["reviews"], "校准 %s" % v["calibration"] if v["calibration"] else "未通过校准，不计入")
                    for name, v in sorted(reviewers.items())) or "无"


def host_models(rec):
    """Every model the host reported answering in the run, joined with + (a
    proxy can switch models between turns); else the one the record names."""
    models = sorted({m for t in rec["turns"] if t.get("model") for m in t["model"].split("+")})
    return "+".join(models) if models else rec["host"].get("model")


def formal_scripts():
    """The formal scripts (ACCEPTANCE 6.4) by id, from tests/e2e/scripts."""
    out = {}
    for path in sorted(glob.glob(os.path.join(E2E, "scripts", "*.json"))):
        with open(path, encoding="utf-8") as handle:
            script = json.load(handle)
        out[script["id"]] = script
    return out


def script_ids():
    return sorted(formal_scripts())


def candidate_digest():
    """The Skill a release would ship: the repository's Skill directory, by
    the digest run_script records for an installed Skill."""
    return run_script.tree_digest(os.path.join(REPO, "skill", "adult-tension"))


def ran_script(rec, script):
    """Whether the record ran SCRIPT as it is now: the same setup, player
    inputs (placeholders filled from the record's own openings),
    conversations, expectations and harness steps, in order."""
    if not script:
        return False
    setup, ran = script.get("setup") or {}, rec.get("setup") or {}
    first = (rec.get("installs") or [{}])[0].get("source") or ""
    if [ran.get("data_dir") == "default", bool(ran.get("include_drafts")), first.startswith("git:")] != \
            [setup.get("data_dir") == "default", bool(setup.get("include_drafts")), setup.get("install") == "previous"]:
        return False
    wanted, harness, index = [], [], 0
    for step in script["steps"]:
        if "harness" in step:
            harness.append([index, step["harness"]])
            continue
        index += 1
        wanted.append([index, step.get("conversation", "A"), run_script.fill_placeholders(step["say"], rec["turns"]), step.get("expect") or {}])
    seen = [[t["index"], t.get("conversation", "A"), t["input"], t.get("expect") or {}] for t in rec["turns"]]
    events = [[e.get("after_turn"), e.get("event")] for e in rec.get("harness_events") or []]
    return seen == wanted and events == harness


def empty_replies(rec):
    """The turns where the host gave the player nothing: no tool call, no
    text, no error (the model answered with an empty message)."""
    return [t["index"] for t in rec["turns"]
            if not (t.get("text") or "").strip() and not t.get("host_calls") and not t.get("runtime_calls") and not t.get("host_error")]


def made_up(rec, checks):
    """The empty replies a run failed on, when they are all it failed on (the
    user's decision of 2026-09-29: such a run is made up by another run of
    the script, not counted); else []. A failure on any other turn counts."""
    empty = empty_replies(rec)
    if checks["pass"] or not empty or not checks["findings"] or checks.get("invalid_record"):
        return []
    return empty if all(f["turn"] in empty for f in checks["findings"]) else []


def _runs(records_dir):
    out = []
    for path in sorted(glob.glob(os.path.join(records_dir, "*", "*.json"))):
        rec = R.load(path)
        out.append((os.path.basename(path), rec))
    return out


def _review(reviews_dir, host, name):
    """The usable review of one record, or None."""
    path = os.path.join(reviews_dir, host, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        review = json.load(handle)
    return review if usable(review) else None


def _counted_review(reviews_dir, host, name, trusted, same=None):
    """Who gave the usable review of one record ("未记" when nothing says so),
    and the review when that reviewer passed calibration, else None."""
    review = _review(reviews_dir, host, name)
    if review is None:
        return None, None
    by = judge_of(review, same) or "未记"
    return by, (review if by in trusted else None)


def _opening_data(rec):
    for turn in rec["turns"]:
        for call in turn.get("runtime_calls") or []:
            data = R.ok_data(call)
            if R.command_of(call) == "new-game" and data:
                return data
    return {}


def playtests(records_dir, reviews_dir, calibration_dirs, same=None):
    """World playtests (CONTENT_BIBLE.md 7): each run with its world, mode,
    seed, the Skill it ran (digest and commit), machine checks and review;
    then per world and mode the runs, distinct seeds, passes and the median
    of each dimension. Every run is shown; none replaces another. Only
    reviews by a calibrated reviewer count."""
    trusted = calibrated(calibration_dirs, same)
    rows = []
    for name, rec in _runs(records_dir):
        opening = _opening_data(rec)
        content = ((rec.get("final_export") or {}).get("session") or {}).get("content") or {}
        install = (rec.get("installs") or [{}])[-1]
        checks = machine_checks.check(rec)
        by, review = _counted_review(reviews_dir, rec["host"]["name"], name, trusted, same)
        rows.append({
            "file": name, "script": rec["script"], "run": rec["run"],
            "world": (content.get("world") or {}).get("id"), "mode": (opening.get("opening") or {}).get("mode"), "seed": opening.get("seed"),
            "skill": install.get("digest"), "commit": (install.get("repository") or {}).get("commit"),
            "machine_pass": checks["pass"], "findings": [f["message"] for f in checks["findings"]],
            "reviewed_by": by, "review": review,
        })
    groups = {}
    for row in rows:
        groups.setdefault((str(row["world"]), str(row["mode"])), []).append(row)
    summary = []
    for (world, mode), group in sorted(groups.items()):
        reviewed = [r for r in group if r["review"]]
        medians = {}
        for dimension in DIMENSIONS:
            scores = [s for s in (_score(r["review"], dimension) for r in reviewed) if s is not None]
            medians[dimension] = statistics.median(scores) if scores else None
        summary.append({
            "world": world, "mode": mode, "runs": len(group), "seeds": len({r["seed"] for r in group}),
            "machine_pass": sum(1 for r in group if r["machine_pass"]), "reviewed": len(reviewed), "medians": medians,
            "critical_low": [{"file": r["file"], "dimension": d, "score": _score(r["review"], d)}
                             for r in reviewed for d in CRITICAL if (_score(r["review"], d) or 5) <= 2],
        })
    # who reviewed: a reader has to know when the model under test graded its own runs
    reviewers = _reviewers(rows, trusted)
    # ACCEPTANCE 6.3: a dimension where more than half the runs score 5 has anchors too loose
    ceiling = []
    for dimension in DIMENSIONS:
        scores = [s for s in (_score(r["review"], dimension) for r in rows if r["review"]) if s is not None]
        if scores and scores.count(5) * 2 > len(scores):
            ceiling.append(dimension)
    return {"rows": rows, "summary": summary, "reviewers": reviewers, "same_model": dict(same or {}), "ceiling": ceiling}


def playtests_markdown(result):
    lines = ["# 世界试玩", "", "| 世界 | 模式 | 局数 | 种子数 | 机器检查通过 | 已评审 | %s |" % " | ".join(DIMENSIONS),
             "|---|---|---|---|---|---|%s" % ("---|" * len(DIMENSIONS))]
    for s in result["summary"]:
        lines.append("| %s | %s | %d | %d | %d | %d | %s |" % (s["world"], s["mode"], s["runs"], s["seeds"], s["machine_pass"], s["reviewed"],
                                                           " | ".join(_number(s["medians"][d]) for d in DIMENSIONS)))
    lines += ["", "（维度一栏是评审分数的中位数。评审者：%s。）" % _reviewers_text(result["reviewers"]), ""]
    if result["same_model"]:
        lines += [_same_text(result["same_model"]) + "。", ""]
    lines += ["满分过半的维度（锚点太松，下一轮收紧）：%s" % ("、".join(result["ceiling"]) or "无"), "",
              "| 记录 | 种子 | Skill（提交） | 机器检查 | 评审 ≤ 2 的维度 |", "|---|---|---|---|---|"]
    for r in result["rows"]:
        low = [d for d in DIMENSIONS if r["review"] and (_score(r["review"], d) or 5) <= 2]
        lines.append("| %s | %s | %s（%s） | %s | %s |" % (r["file"], r["seed"], r["skill"] or "未记", r["commit"] or "未记",
                                                       "通过" if r["machine_pass"] else "未通过：" + "；".join(r["findings"][:3]),
                                                       "、".join(low) or ("无" if r["review"] else "评审者未通过校准" if r["reviewed_by"] else "未评审")))
    return "\n".join(lines) + "\n"


def agreement(first_dir, second_dir):
    pairs = {d: [] for d in DIMENSIONS}
    records = 0
    models = [set(), set()]
    for path in sorted(glob.glob(os.path.join(first_dir, "*", "*.json"))):
        host, name = os.path.basename(os.path.dirname(path)), os.path.basename(path)
        first, second = _review(first_dir, host, name), _review(second_dir, host, name)
        if not (first and second):
            continue
        records += 1
        for seen, review in zip(models, (first, second)):
            seen.add(judge_of(review) or "未记")
        for dimension in DIMENSIONS:
            a, b = _score(first, dimension), _score(second, dimension)
            if a is not None and b is not None:
                pairs[dimension].append((a, b))
    dimensions = {}
    for dimension, scores in pairs.items():
        n = len(scores)
        dimensions[dimension] = {
            "n": n,
            "same": sum(1 for a, b in scores if a == b),
            "within_one": sum(1 for a, b in scores if abs(a - b) <= 1),
            "mean_difference": round(sum(b - a for a, b in scores) / float(n), 2) if n else None,
            "low_first": sum(1 for a, _ in scores if a <= 2),
            "low_second": sum(1 for _, b in scores if b <= 2),
        }
    return {"records": records, "first": sorted(models[0]), "second": sorted(models[1]), "dimensions": dimensions}


def agreement_markdown(result):
    lines = ["# 两个评审者的一致程度", "",
             "同一批 %d 条记录。第一评审者：%s；第二评审者：%s。" % (result["records"], "、".join(result["first"]) or "无", "、".join(result["second"]) or "无"), "",
             "| 维度 | 两边都打分 | 相同 | 相差 ≤ 1 | 第二减第一（平均） | 第一 ≤ 2 | 第二 ≤ 2 |", "|---|---|---|---|---|---|---|"]
    for dimension in DIMENSIONS:
        d = result["dimensions"][dimension]
        lines.append("| %s | %d | %d | %d | %s | %d | %d |" % (dimension, d["n"], d["same"], d["within_one"],
                                                           "—" if d["mean_difference"] is None else "%+.2f" % d["mean_difference"],
                                                           d["low_first"], d["low_second"]))
    return "\n".join(lines) + "\n"


def build(records_dir, reviews_dir, calibration_dirs, fixes_path=None, same=None, scripts=None, candidate=None, notes=()):
    fixes = {}
    if fixes_path and os.path.exists(fixes_path):
        with open(fixes_path, encoding="utf-8") as handle:
            fixes = json.load(handle)
    scripts = formal_scripts() if scripts is None else scripts
    candidate = candidate_digest() if candidate is None else candidate
    trusted = calibrated(calibration_dirs, same)
    runs = []
    identities = {}
    for name, rec in _runs(records_dir):
        host = rec["host"]["name"]
        identities.setdefault(host, set()).add((rec["host"].get("version"), host_models(rec), rec.get("date")))
        checks = machine_checks.check(rec)
        # a review by a reviewer that did not pass calibration is no review
        by, review = _counted_review(reviews_dir, host, name, trusted, same)
        skill = (rec.get("installs") or [{}])[-1].get("digest")
        # the verdict is on the candidate's runs of the scripts as they are now: all of them, none picked
        why_not = None if skill == candidate else "Skill 摘要 %s，不是候选版本" % (skill or "未记")
        if why_not is None and not ran_script(rec, scripts.get(rec["script"])):
            why_not = "剧本已经改过" if rec["script"] in scripts else "不是正式剧本"
        empty = made_up(rec, checks) if why_not is None else []
        if empty:
            why_not = "宿主空回复（第 %s 轮），按用户的决定补跑" % "、".join(str(i) for i in empty)
        runs.append({
            "file": name, "host": host, "script": rec["script"], "run": rec["run"], "skill": skill, "counted": why_not is None,
            "why_not_counted": why_not, "made_up": bool(empty),
            "machine_pass": checks["pass"], "findings": checks["findings"], "stats": checks.get("stats") or {},
            "reviewed_by": by, "review": review, "fix": fixes.get(name),
        })
    first = [r for r in runs if r["run"] == 1]
    counted = [r for r in runs if r["counted"]]
    per_dimension = {}
    ceiling = []
    for dimension in DIMENSIONS:
        scores = [_score(r["review"], dimension) for r in counted if r["review"]]
        scores = [s for s in scores if s is not None]
        distribution = {str(k): scores.count(k) for k in range(1, 6)}
        per_dimension[dimension] = {
            "n": len(scores),
            "median": statistics.median(scores) if scores else None,
            "distribution": distribution,
        }
        if scores and scores.count(5) * 2 > len(scores):
            ceiling.append(dimension)
    # ACCEPTANCE 6.3: the spread between runs of one script, run by run (None: n/a or no counted review)
    variance = {}
    for r in sorted(counted, key=lambda r: (r["host"], r["script"], r["run"])):
        scores = variance.setdefault("%s / 剧本 %s" % (r["host"], r["script"]), {d: [] for d in DIMENSIONS})
        for dimension in DIMENSIONS:
            scores[dimension].append(_score(r["review"], dimension))
    critical_low = [
        {"file": r["file"], "dimension": d, "score": _score(r["review"], d)}
        for r in counted if r["review"] for d in CRITICAL if (_score(r["review"], d) or 5) <= 2
    ]
    ordinary = [(r["stats"]["average_calls"], r["stats"]["ordinary_turns"]) for r in counted if r["stats"].get("average_calls") is not None]
    turns = sum(n for _avg, n in ordinary)
    average_calls = round(sum(avg * n for avg, n in ordinary) / turns, 3) if turns else None
    machine_failures = [r["file"] for r in counted if not r["machine_pass"]]
    unreviewed = [r["file"] for r in counted if not r["review"]]
    hosts = sorted({r["host"] for r in counted})
    # ACCEPTANCE 6.1 item 4 and 6.4: every script at least three times on every host that ran anything
    done = {}
    for r in counted:
        done.setdefault(r["host"], {}).setdefault(r["script"], set()).add(r["run"])
    short = ["%s 上剧本 %s %d 次" % (h, s, len(done.get(h, {}).get(s, ()))) for h in sorted(identities) for s in sorted(scripts)
             if len(done.get(h, {}).get(s, ())) < RUNS_PER_SCRIPT]
    low_medians = ["%s %s" % (d, _number(v["median"])) for d, v in per_dimension.items() if v["median"] is None or v["median"] < 4]
    conditions = [
        {"condition": "至少 %d 个宿主" % MIN_HOSTS, "ok": len(hosts) >= MIN_HOSTS, "detail": "%d 个（%s）" % (len(hosts), "、".join(hosts) or "无")},
        {"condition": "每条剧本在每个宿主上至少 %d 次" % RUNS_PER_SCRIPT, "ok": bool(hosts) and not short,
         "detail": "；".join(short) if short else "%d 条剧本都齐" % len(scripts) if hosts else "没有计入的运行"},
        {"condition": "没有机器检查失败", "ok": not machine_failures, "detail": "%d 条失败" % len(machine_failures)},
        {"condition": "每条记录都有已校准评审者的可用评审", "ok": not unreviewed, "detail": "%d 条没有" % len(unreviewed)},
        {"condition": "每个维度的中位数 ≥ 4", "ok": not low_medians, "detail": "、".join(low_medians) or "都 ≥ 4"},
        {"condition": "关键维度（%s）没有 ≤ 2" % "、".join(CRITICAL), "ok": not critical_low, "detail": "%d 处" % len(critical_low)},
        {"condition": "普通回合平均工具调用 ≤ %.1f" % AVERAGE_CALLS_LIMIT, "ok": average_calls is not None and average_calls <= AVERAGE_CALLS_LIMIT,
         "detail": "没有普通回合" if average_calls is None else "%g" % average_calls},
    ]
    passed = all(c["ok"] for c in conditions)
    return {
        "hosts": {h: sorted([list(i) for i in identities[h]]) for h in sorted(identities)},
        "reviewers": _reviewers(runs, trusted),
        "same_model": dict(same or {}),
        "candidate": candidate,
        "runs": len(runs),
        "counted_runs": len(counted),
        "not_counted": [{"file": r["file"], "why": r["why_not_counted"]} for r in runs if not r["counted"]],
        "made_up": [r["file"] for r in runs if r["made_up"]],
        "first_run_machine_pass": "%d/%d" % (sum(1 for r in first if r["machine_pass"]), len(first)),
        "machine_failures": machine_failures,
        "unreviewed": unreviewed,
        "average_calls_per_ordinary_turn": average_calls,
        "dimensions": per_dimension,
        "ceiling": ceiling,
        "critical_low": critical_low,
        "variance": variance,
        "failures_and_fixes": [{"file": r["file"], "counted": r["counted"], "machine": [f["message"] for f in r["findings"]][:5], "fix": r["fix"]}
                               for r in runs if not r["machine_pass"]],
        "conditions": conditions,
        "notes": list(notes),
        "pass": passed,
    }

def to_markdown(report):
    lines = ["# 端到端评测报告", ""]
    for host, ids in report["hosts"].items():
        lines.append("- %s：%s" % (host, "；".join("版本 %s，模型 %s，日期 %s" % tuple(i) for i in ids)))
    lines += [
        "- 评审者：%s%s" % (_reviewers_text(report["reviewers"]), "；" + _same_text(report["same_model"]) if report["same_model"] else ""),
        "",
        "- 候选版本：Skill 摘要 %s；运行 %d 条，计入结论的 %d 条（其余照样列在下面，写明为什么不计入）" % (report["candidate"], report["runs"], report["counted_runs"]),
        "- 首跑机器检查通过：%s（每条剧本在每个宿主上的第 1 次）；计入的运行里没有可用评审的：%d" % (report["first_run_machine_pass"], len(report["unreviewed"])),
        "- 普通回合平均工具调用：%s（门槛 ≤ %.1f）" % (report["average_calls_per_ordinary_turn"], AVERAGE_CALLS_LIMIT),
        "- 结论：%s" % ("通过" if report["pass"] else "未通过"),
        "",
        "| 条件 | 满足 | 实际 |",
        "|---|---|---|",
    ]
    lines += ["| %s | %s | %s |" % (c["condition"], "是" if c["ok"] else "**否**", c["detail"]) for c in report["conditions"]]
    if report["made_up"]:
        lines += ["", "宿主空回复：%d 条运行只因某一轮宿主什么也没给（没有工具调用、也没有正文）而不合格。按用户 2026-09-29 的决定，"
                  "这样的运行不计入结论，同一剧本补跑一次，补跑的不论结果都计入；在别的轮次上还有失败的照常计入。首跑通过率照旧算它们不通过。" % len(report["made_up"])]
    if report["notes"]:
        lines += ["", "说明："] + ["- %s" % note for note in report["notes"]]
    lines += [
        "",
        "| 维度 | 样本 | 中位数 | 1 | 2 | 3 | 4 | 5 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for dimension, v in report["dimensions"].items():
        d = v["distribution"]
        lines.append("| %s | %d | %s | %s | %s | %s | %s | %s |" % (dimension, v["n"], _number(v["median"]), d["1"], d["2"], d["3"], d["4"], d["5"]))
    if report["ceiling"]:
        lines += ["", "**触顶**（超过一半样本满分，下一轮收紧锚点）：%s" % "、".join(report["ceiling"])]
    if report["critical_low"]:
        lines += ["", "关键维度 ≤ 2："] + ["- %s：%s %s 分" % (x["file"], x["dimension"], x["score"]) for x in report["critical_low"]]
    if report["failures_and_fixes"]:
        lines += ["", "失败记录与修复："] + ["- %s%s：%s；修复：%s" % (x["file"], "" if x["counted"] else "（不计入）", "；".join(x["machine"]), x["fix"] or "未修")
                                        for x in report["failures_and_fixes"]]
    if report["not_counted"]:
        lines += ["", "不计入结论的运行："] + ["- %s：%s" % (x["file"], x["why"]) for x in report["not_counted"]]
    if report["variance"]:
        lines += ["", "同一剧本各次运行的分数（按运行次序；— 是 n/a 或没有计入的评审）：", "",
                  "| 宿主 / 剧本 | %s |" % " | ".join(DIMENSIONS), "|---|%s" % ("---|" * len(DIMENSIONS))]
        for key, dims in report["variance"].items():
            lines.append("| %s | %s |" % (key, " | ".join(" ".join("—" if s is None else str(s) for s in dims[d]) for d in DIMENSIONS)))
    return "\n".join(lines) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    pack = sub.add_parser("packet")
    pack.add_argument("--record", required=True)
    pack.add_argument("--out", required=True)
    same_help = "<served name>=<model>: the user says these are one model; repeat for each"
    cal = sub.add_parser("calibrate")
    cal.add_argument("--reviews", required=True)
    cal.add_argument("--same-model", action="append", default=[], help=same_help)
    rep = sub.add_parser("build")
    rep.add_argument("--records", required=True)
    rep.add_argument("--reviews", required=True)
    rep.add_argument("--calibration", action="append", required=True, help="a calibration reviews directory; repeat for each reviewer")
    rep.add_argument("--same-model", action="append", default=[], help=same_help)
    rep.add_argument("--fixes")
    rep.add_argument("--candidate", help="the Skill digest the verdict is on (default: the repository's Skill directory)")
    rep.add_argument("--note", action="append", default=[], help="the operator's word on a condition left unmet; printed, changes no verdict")
    rep.add_argument("--out")
    play = sub.add_parser("playtests")
    play.add_argument("--records", required=True)
    play.add_argument("--reviews", required=True)
    play.add_argument("--calibration", action="append", required=True, help="a calibration reviews directory; repeat for each reviewer")
    play.add_argument("--same-model", action="append", default=[], help=same_help)
    play.add_argument("--out")
    agree = sub.add_parser("agreement")
    agree.add_argument("--first", required=True)
    agree.add_argument("--second", required=True)
    agree.add_argument("--out")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    same = {}
    for pair in getattr(args, "same_model", None) or []:
        served, _, model = pair.partition("=")
        if not (served.strip() and model.strip()):
            parser.error("--same-model 要写成 <应答的模型名>=<它等同的模型名>：%s" % pair)
        same[served.strip()] = model.strip()
    if args.action == "agreement":
        text = agreement_markdown(agreement(args.first, args.second))
        if args.out:
            with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        print(text)
        return 0
    if args.action == "packet":
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(packet(args.record))
        print(args.out)
        return 0
    if args.action == "playtests":
        result = playtests(args.records, args.reviews, args.calibration, same)
        text = playtests_markdown(result)
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            with open(os.path.join(args.out, "playtests.json"), "w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
            with open(os.path.join(args.out, "playtests.md"), "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        print(text)
        return 0
    if args.action == "calibrate":
        result = calibrate(args.reviews, same)
        for row in result["rows"]:
            print("[%s] %s：%s" % ("对" if row["right"] else "错", row["record"], row["why"]))
        if same:
            print(_same_text(same))
        if result["reviewer"] is None:
            print("评审者：%s——校准只能替同一个模型说话，要 12 条都由同一个已知的模型回答" % ("、".join(result["reviewers"]) or "无"))
        else:
            print("评审者：%s" % result["reviewer"])
        verdict = "可以开始正式评审" if result["ready"] else "先改锚点" if result["correct"] < 10 else "评审者不止一个或没有记下，重新校准"
        print("正确 %d/%d：%s" % (result["correct"], result["total"], verdict))
        return 0 if result["ready"] else 1
    report = build(args.records, args.reviews, args.calibration, args.fixes, same, candidate=args.candidate, notes=args.note)
    text = to_markdown(report)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
        with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    print(text)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
