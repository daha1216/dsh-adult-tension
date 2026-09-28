"""The end-to-end report (ACCEPTANCE.md 6) and the reviewer calibration.

    python tests/e2e/harness/report.py packet --record <record.json> --out <file.md>
    python tests/e2e/harness/report.py calibrate --reviews <dir>
    python tests/e2e/harness/report.py build --records <dir> --reviews <dir>
                                        [--fixes <fixes.json>] [--out <dir>]

packet: what an independent reviewer gets, as one document: the reviewer
instructions, the rubric, NARRATIVE_RULES.md and the record. Nothing else:
no script focus, no expectations, no implementation (ACCEPTANCE 6.1 item 7).

calibrate: the reviewer's scores on the calibration set against key.json.
A good record is judged right when no dimension is <= 2; a record with a
planted defect when every planted dimension is <= 2. Below 10 of 12, fix the
anchors before the formal review (ACCEPTANCE 6.3).

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


def calibrate(reviews_dir):
    with open(os.path.join(E2E, "calibration", "key.json"), encoding="utf-8") as handle:
        key = json.load(handle)
    rows = []
    for name, expected in sorted(key.items()):
        path = os.path.join(reviews_dir, name + ".json")
        if not os.path.exists(path):
            rows.append({"record": name, "right": False, "why": "没有评审结果"})
            continue
        with open(path, encoding="utf-8") as handle:
            review = json.load(handle)
        low = [d for d in DIMENSIONS if (_score(review, d) or 5) <= 2]
        if expected["low"]:
            right = all(d in low for d in expected["low"])
            why = "植入的缺陷维度 %s；评审判为 ≤ 2 的：%s" % ("、".join(expected["low"]), "、".join(low) or "无")
        else:
            right = not low
            why = "好的记录；评审判为 ≤ 2 的：%s" % ("、".join(low) or "无")
        rows.append({"record": name, "right": right, "why": why})
    correct = sum(1 for r in rows if r["right"])
    return {"correct": correct, "total": len(rows), "ready": correct >= 10, "rows": rows}


def _runs(records_dir):
    out = []
    for path in sorted(glob.glob(os.path.join(records_dir, "*", "*.json"))):
        rec = R.load(path)
        out.append((os.path.basename(path), rec))
    return out


def build(records_dir, reviews_dir, fixes_path=None):
    fixes = {}
    if fixes_path and os.path.exists(fixes_path):
        with open(fixes_path, encoding="utf-8") as handle:
            fixes = json.load(handle)
    runs = []
    identities = {}
    ordinary_calls = []
    for name, rec in _runs(records_dir):
        host = rec["host"]["name"]
        identities.setdefault(host, set()).add((rec["host"].get("version"), rec["host"].get("model"), rec.get("date")))
        checks = machine_checks.check(rec)
        review_path = os.path.join(reviews_dir, host, name)
        review = None
        if os.path.exists(review_path):
            with open(review_path, encoding="utf-8") as handle:
                review = json.load(handle)
        stats = checks.get("stats") or {}
        if stats.get("average_calls") is not None:
            ordinary_calls.append((stats["average_calls"], stats["ordinary_turns"]))
        runs.append({
            "file": name, "host": host, "script": rec["script"], "run": rec["run"],
            "machine_pass": checks["pass"], "findings": checks["findings"], "review": review,
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
    hosts = sorted(identities)
    passed = (
        len(hosts) >= 2
        and not machine_failures
        and all(v["median"] is not None and v["median"] >= 4 for v in per_dimension.values())
        and not critical_low
        and average_calls is not None and average_calls <= AVERAGE_CALLS_LIMIT
    )
    return {
        "hosts": {h: sorted([list(i) for i in identities[h]]) for h in hosts},
        "runs": len(runs),
        "first_run_machine_pass": "%d/%d" % (sum(1 for r in first if r["machine_pass"]), len(first)),
        "machine_failures": machine_failures,
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
        "",
        "- 运行数：%d；首跑机器检查通过：%s" % (report["runs"], report["first_run_machine_pass"]),
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
    cal = sub.add_parser("calibrate")
    cal.add_argument("--reviews", required=True)
    rep = sub.add_parser("build")
    rep.add_argument("--records", required=True)
    rep.add_argument("--reviews", required=True)
    rep.add_argument("--fixes")
    rep.add_argument("--out")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.action == "packet":
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(packet(args.record))
        print(args.out)
        return 0
    if args.action == "calibrate":
        result = calibrate(args.reviews)
        for row in result["rows"]:
            print("[%s] %s：%s" % ("对" if row["right"] else "错", row["record"], row["why"]))
        print("正确 %d/%d：%s" % (result["correct"], result["total"], "可以开始正式评审" if result["ready"] else "先改锚点"))
        return 0 if result["ready"] else 1
    report = build(args.records, args.reviews, args.fixes)
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
