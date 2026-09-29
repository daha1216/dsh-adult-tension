"""The end-to-end report (ACCEPTANCE.md 6) and the reviewer calibration.

    python tests/e2e/harness/report.py packet --record <record.json> --out <file.md>
    python tests/e2e/harness/report.py calibrate --reviews <dir> [--same-model <served>=<model> ...]
    python tests/e2e/harness/report.py build --records <dir> --reviews <dir> --calibration <dir> [--calibration <dir> ...]
                                        [--same-model <served>=<model> ...] [--fixes <fixes.json>] [--out <dir>]
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
print every such statement.

calibrate: the reviewer's scores on the calibration set against key.json.
A good record is judged right when no dimension is <= 2; a record with a
planted defect when every planted dimension is <= 2. Below 10 of 12, fix the
anchors before the formal review (ACCEPTANCE 6.3). A calibration speaks for
one reviewer: all twelve answered by the same model.

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
"""

import argparse
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E2E = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import machine_checks  # noqa: E402
import record as R  # noqa: E402

DIMENSIONS = ("玩家主权", "NPC 意志", "知识边界", "关系节奏", "同意与安全", "世界具体性", "连续性", "表达")
CRITICAL = ("玩家主权", "同意与安全", "知识边界")
AVERAGE_CALLS_LIMIT = 1.2


REPO = os.path.dirname(os.path.dirname(E2E))


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
        reviewers.add(reviewer_of(review, same))
        low = [d for d in DIMENSIONS if (_score(review, d) or 5) <= 2]
        if expected["low"]:
            right = all(d in low for d in expected["low"])
            why = "植入的缺陷维度 %s；评审判为 ≤ 2 的：%s" % ("、".join(expected["low"]), "、".join(low) or "无")
        else:
            right = not low
            why = "好的记录；评审判为 ≤ 2 的：%s" % ("、".join(low) or "无")
        rows.append({"record": name, "right": right, "why": why})
    correct = sum(1 for r in rows if r["right"])
    # the result speaks for one reviewer only: the same known model answered every record
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


def _same_text(same):
    """The served names taken as one model, as the reports print them."""
    return "；".join("%s 与 %s 视为同一个模型（用户确认）" % (served, model) for served, model in sorted((same or {}).items()))


def _reviewers_text(reviewers):
    return "、".join("%s %d 条（%s）" % (name, v["reviews"], "校准 %s" % v["calibration"] if v["calibration"] else "未通过校准，不计入")
                    for name, v in sorted(reviewers.items())) or "无"


def host_models(rec):
    """Every model the host reported answering in the run, joined with + (a
    proxy can switch models between turns); else the one the record names."""
    models = sorted({m for t in rec["turns"] if t.get("model") for m in t["model"].split("+")})
    return "+".join(models) if models else rec["host"].get("model")


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
    by = reviewer_of(review, same) or "未记"
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
                                                           " | ".join("—" if s["medians"][d] is None else str(s["medians"][d]) for d in DIMENSIONS)))
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
            seen.add(reviewer_of(review) or "未记")
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


def build(records_dir, reviews_dir, calibration_dirs, fixes_path=None, same=None):
    fixes = {}
    if fixes_path and os.path.exists(fixes_path):
        with open(fixes_path, encoding="utf-8") as handle:
            fixes = json.load(handle)
    trusted = calibrated(calibration_dirs, same)
    runs = []
    identities = {}
    ordinary_calls = []
    for name, rec in _runs(records_dir):
        host = rec["host"]["name"]
        identities.setdefault(host, set()).add((rec["host"].get("version"), host_models(rec), rec.get("date")))
        checks = machine_checks.check(rec)
        # a review by a reviewer that did not pass calibration is no review
        by, review = _counted_review(reviews_dir, host, name, trusted, same)
        stats = checks.get("stats") or {}
        if stats.get("average_calls") is not None:
            ordinary_calls.append((stats["average_calls"], stats["ordinary_turns"]))
        runs.append({
            "file": name, "host": host, "script": rec["script"], "run": rec["run"],
            "machine_pass": checks["pass"], "findings": checks["findings"], "reviewed_by": by, "review": review,
            "fix": fixes.get(name),
        })
    first = [r for r in runs if r["run"] == 1]
    per_dimension = {}
    ceiling = []
    for dimension in DIMENSIONS:
        scores = [_score(r["review"], dimension) for r in runs if r["review"]]
        scores = [s for s in scores if s is not None]
        distribution = {str(k): scores.count(k) for k in range(1, 6)}
        per_dimension[dimension] = {
            "n": len(scores),
            "median": statistics.median(scores) if scores else None,
            "distribution": distribution,
        }
        if scores and scores.count(5) * 2 > len(scores):
            ceiling.append(dimension)
    variance = {}
    for r in runs:
        if not r["review"]:
            continue
        key = "%s / 剧本 %s" % (r["host"], r["script"])
        for dimension in DIMENSIONS:
            score = _score(r["review"], dimension)
            if score is not None:
                variance.setdefault(key, {}).setdefault(dimension, []).append(score)
    critical_low = [
        {"file": r["file"], "dimension": d, "score": _score(r["review"], d)}
        for r in runs if r["review"] for d in CRITICAL if (_score(r["review"], d) or 5) <= 2
    ]
    turns = sum(n for _avg, n in ordinary_calls)
    average_calls = round(sum(avg * n for avg, n in ordinary_calls) / turns, 3) if turns else None
    machine_failures = [r["file"] for r in runs if not r["machine_pass"]]
    unreviewed = [r["file"] for r in runs if not r["review"]]
    hosts = sorted(identities)
    passed = (
        len(hosts) >= 2
        and not machine_failures
        and not unreviewed
        and all(v["median"] is not None and v["median"] >= 4 for v in per_dimension.values())
        and not critical_low
        and average_calls is not None and average_calls <= AVERAGE_CALLS_LIMIT
    )
    return {
        "hosts": {h: sorted([list(i) for i in identities[h]]) for h in hosts},
        "reviewers": _reviewers(runs, trusted),
        "same_model": dict(same or {}),
        "runs": len(runs),
        "first_run_machine_pass": "%d/%d" % (sum(1 for r in first if r["machine_pass"]), len(first)),
        "machine_failures": machine_failures,
        "unreviewed": unreviewed,
        "average_calls_per_ordinary_turn": average_calls,
        "dimensions": per_dimension,
        "ceiling": ceiling,
        "critical_low": critical_low,
        "variance": {k: {d: [min(v), max(v)] for d, v in dims.items()} for k, dims in variance.items()},
        "failures_and_fixes": [{"file": r["file"], "machine": [f["message"] for f in r["findings"]][:5], "fix": r["fix"]} for r in runs if not r["machine_pass"]],
        "pass": passed,
    }


def to_markdown(report):
    lines = ["# 端到端评测报告", ""]
    for host, ids in report["hosts"].items():
        lines.append("- %s：%s" % (host, "；".join("版本 %s，模型 %s，日期 %s" % tuple(i) for i in ids)))
    lines += [
        "- 评审者：%s%s" % (_reviewers_text(report["reviewers"]), "；" + _same_text(report["same_model"]) if report["same_model"] else ""),
        "",
        "- 运行数：%d；首跑机器检查通过：%s；没有可用评审的记录：%d" % (report["runs"], report["first_run_machine_pass"], len(report["unreviewed"])),
        "- 普通回合平均工具调用：%s（门槛 ≤ %.1f）" % (report["average_calls_per_ordinary_turn"], AVERAGE_CALLS_LIMIT),
        "- 结论：%s" % ("通过" if report["pass"] else "未通过"),
        "",
        "| 维度 | 样本 | 中位数 | 1 | 2 | 3 | 4 | 5 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for dimension, v in report["dimensions"].items():
        d = v["distribution"]
        lines.append("| %s | %d | %s | %s | %s | %s | %s | %s |" % (dimension, v["n"], v["median"], d["1"], d["2"], d["3"], d["4"], d["5"]))
    if report["ceiling"]:
        lines += ["", "**触顶**（超过一半样本满分，下一轮收紧锚点）：%s" % "、".join(report["ceiling"])]
    if report["critical_low"]:
        lines += ["", "关键维度 ≤ 2："] + ["- %s：%s %s 分" % (x["file"], x["dimension"], x["score"]) for x in report["critical_low"]]
    if report["failures_and_fixes"]:
        lines += ["", "失败记录与修复："] + ["- %s：%s；修复：%s" % (x["file"], "；".join(x["machine"]), x["fix"] or "未修") for x in report["failures_and_fixes"]]
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
    report = build(args.records, args.reviews, args.calibration, args.fixes, same)
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
