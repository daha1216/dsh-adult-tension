"""Drive an independent reviewer over recorded playtest transcripts.

Scoring stays separate from generation: this never re-runs a probe and never
touches a transcript. It drives a reviewer through DSH headless (with a pinned
cross-model overlay), then machine-checks every review with the same rules
`playtest_report.py` enforces at the release gate: verbatim per-turn evidence,
lowest-scoring-turn aggregation, threshold and findings disposition.

Subcommands:
  run    score transcripts in a batch directory and write <stem>.review.yaml
  check  re-verify existing review files against their transcripts
  stats  aggregate pass rates, means and deduction points for a batch
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from material_inventory import read_yaml  # noqa: E402
from playtest_report import checked_scores  # noqa: E402

CONFIG = read_yaml(ROOT / "maintenance/baseline.yaml")["playtest"]
AGGREGATION = "lowest_scoring_turn_with_all_turns_required_to_pass"


def review_path(directory: Path, stem: str) -> Path:
    return directory / f"{stem}.review.yaml"


def verify(review, record, transcript: Path, reviewer: str) -> list[str]:
    """Mirror the release gate's review rules; never re-checks probe identity."""
    problems: list[str] = []
    if not isinstance(review, dict):
        return ["review file is not a mapping"]
    for key in ("framework_id", "name", "mode"):
        if review.get(key) != record.get(key):
            problems.append(f"{key} mismatch: {review.get(key)!r}")
    digest = hashlib.sha256(transcript.read_bytes()).hexdigest()
    if review.get("transcript_sha256") != digest:
        problems.append(f"transcript_sha256 mismatch: {review.get('transcript_sha256')!r}")
    if review.get("reviewer") != reviewer:
        problems.append(f"reviewer mismatch: {review.get('reviewer')!r}")
    if review.get("protocol") != record.get("protocol"):
        problems.append(f"protocol mismatch: {review.get('protocol')!r}")
    if review.get("aggregation") != AGGREGATION:
        problems.append("aggregation mismatch")
    if not isinstance(review.get("summary"), str) or not review["summary"].strip():
        problems.append("missing summary")
    turns = record["turns"]
    prose = "\n".join(turn["response"] for turn in turns)
    try:
        scores = checked_scores(review, prose, CONFIG)
    except ValueError as exc:
        return problems + [f"case scores: {exc}"]
    turn_reviews = review.get("turn_reviews")
    if not isinstance(turn_reviews, list) or len(turn_reviews) != len(turns):
        return problems + ["missing individual turn reviews"]
    turn_scores = []
    for index, (turn, turn_review) in enumerate(zip(turns, turn_reviews)):
        if not isinstance(turn_review, dict) or turn_review.get("turn") != index:
            problems.append(f"turn_reviews[{index}] sequence")
            continue
        try:
            value = checked_scores(turn_review, turn["response"], CONFIG)
        except ValueError as exc:
            problems.append(f"turn {index} scores: {exc}")
            continue
        if turn_review.get("total") != sum(value.values()):
            problems.append(f"turn {index} total mismatch")
        turn_scores.append(value)
    if len(turn_scores) != len(turns):
        return problems
    minimum = min(sum(value.values()) for value in turn_scores)
    if not any(scores == value and sum(value.values()) == minimum for value in turn_scores):
        problems.append("case score must use the lowest scoring turn")
    if review.get("total") != sum(scores.values()):
        problems.append("case total mismatch")
    findings = review.get("blocking_findings")
    blocked = bool(findings) or any(item.get("blocking_findings") for item in turn_reviews)
    passed = minimum >= CONFIG["minimum_score"] and 0 not in scores.values() and not blocked
    if review.get("passed") is not passed:
        problems.append(f"passed flag mismatch: {review.get('passed')!r} vs {passed}")
    return problems


def build_prompt(args, record, transcript: Path, out: Path, extra: str) -> str:
    digest = hashlib.sha256(transcript.read_bytes()).hexdigest()
    return args.prompt_template.format(
        reviewer=args.reviewer, root=ROOT, brief=args.brief, transcript=transcript,
        framework=ROOT / "authoring/frameworks" / f"{record['framework_id']}.yaml", out=out,
        fid=record["framework_id"], name=record["name"], mode=record["mode"],
        sha=digest, protocol=record["protocol"], aggregation=AGGREGATION, extra=extra)


def review_one(args, command, transcript: Path, out: Path) -> tuple[str, str]:
    record = json.loads(transcript.read_text(encoding="utf-8"))
    extra = ""
    for attempt in range(1, args.retries + 2):
        try:
            completed = subprocess.run([*command, build_prompt(args, record, transcript, out, extra)],
                                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                                       timeout=args.timeout)
        except subprocess.TimeoutExpired:
            extra = " 上一轮超时，请缩短说明后重写该文件。"
            continue
        if completed.returncode:
            return transcript.name, f"reviewer call failed: code={completed.returncode}"
        if not out.exists():
            extra = f" 上一轮没有写出 {out}，请直接用写文件工具创建该文件。"
            continue
        try:
            review = read_yaml(out)
        except Exception as exc:  # noqa: BLE001 - any parse failure is a failed attempt
            extra = f" 上一轮产物无法解析（{exc}），请重写为合法 YAML。"
            continue
        problems = verify(review, record, transcript, args.reviewer)
        if not problems:
            return transcript.name, ""
        extra = " 上一轮产物机器复核失败（" + "；".join(problems[:4]) + "），请修正后重写该文件。"
    return transcript.name, "unresolved: " + extra.strip()


def resolve_batch(args) -> list[tuple[Path, Path]]:
    batch = Path(args.batch)
    out_dir = Path(args.out_dir) if args.out_dir else batch
    pairs = []
    for transcript in sorted(batch.glob("*.json")):
        record = json.loads(transcript.read_text(encoding="utf-8"))
        if len(record.get("turns", [])) < CONFIG["continuation_turns"] + 1:
            # In-flight transcripts are never scored: a review must cover all four turns.
            continue
        out = review_path(out_dir, transcript.stem)
        if args.only and transcript.stem not in set(args.only):
            continue
        if out.exists() and not args.force:
            if args.check_existing or args.action != "run":
                pairs.append((transcript, out))
            continue
        pairs.append((transcript, out))
        if args.limit and len(pairs) >= args.limit:
            break
    return pairs


def cmd_run(args) -> int:
    command = [shutil.which("node") or "node", str(args.dsh_entry)] if args.dsh_entry else [shutil.which("dsh") or "dsh"]
    command = [*command, "--profile", "headless", "--patch", str(ROOT / "maintenance/playtest_headless_patch.yml"),
               "--patch", str(ROOT / args.model_patch), *args.dsh_extra]
    Path(args.out_dir or args.batch).mkdir(parents=True, exist_ok=True)
    pairs = resolve_batch(args)
    if not pairs:
        print("nothing to review")
        return 0
    failures = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for name, problem in pool.map(lambda item: review_one(args, command, *item), pairs):
            print(f"{name}: {'ok' if not problem else problem}", flush=True)
            if problem:
                failures.append((name, problem))
    print(json.dumps({"reviewed": len(pairs) - len(failures), "failed": len(failures)}, ensure_ascii=False))
    return 1 if failures else 0


def cmd_check(args) -> int:
    pairs = resolve_batch(args)
    failures = 0
    for transcript, out in pairs:
        record = json.loads(transcript.read_text(encoding="utf-8"))
        if not out.exists():
            print(f"{transcript.name}: missing review {out}")
            failures += 1
            continue
        try:
            review = read_yaml(out)
        except Exception as exc:  # noqa: BLE001 - report unparseable products instead of dying
            print(f"{transcript.name}: unparseable review ({exc})")
            failures += 1
            continue
        problems = verify(review, record, transcript, args.reviewer)
        if problems:
            print(f"{transcript.name}: " + "；".join(problems))
            failures += 1
    print(json.dumps({"checked": len(pairs), "failed": failures}, ensure_ascii=False))
    return 1 if failures else 0


def cmd_stats(args) -> int:
    pairs = resolve_batch(args)
    cases = passed_cases = turns = turns_passed = turns_passed_by_score = 0
    zero_dims = 0
    deductions = {dimension: 0 for dimension in CONFIG["dimensions"]}
    distribution: dict[int, int] = {}
    modes: dict[str, list[int]] = {}
    opening_totals: list[int] = []
    continuation_totals: list[int] = []
    blocking: list[str] = []
    reviewers, protocols = set(), set()
    for transcript, out in pairs:
        record = json.loads(transcript.read_text(encoding="utf-8"))
        if not out.exists():
            continue
        review = read_yaml(out)
        cases += 1
        reviewers.add(review.get("reviewer"))
        protocols.add(review.get("protocol"))
        row = modes.setdefault(record["mode"], [0, 0])
        row[1] += 1
        row[0] += bool(review.get("passed"))
        passed_cases += bool(review.get("passed"))
        minimum = min(sum(turn["scores"].values()) for turn in review["turn_reviews"])
        distribution[minimum] = distribution.get(minimum, 0) + 1
        if review.get("blocking_findings"):
            blocking.append(transcript.stem)
        for index, turn_review in enumerate(review["turn_reviews"]):
            turns += 1
            total = sum(turn_review["scores"].values())
            turns_passed += bool(turn_review.get("passed"))
            turns_passed_by_score += total >= CONFIG["minimum_score"] and 0 not in turn_review["scores"].values() \
                and not turn_review.get("blocking_findings")
            (opening_totals if index == 0 else continuation_totals).append(total)
            for dimension, value in turn_review["scores"].items():
                deductions[dimension] += 2 - value
                zero_dims += value == 0
    mean = lambda values: round(sum(values) / len(values), 2) if values else None  # noqa: E731
    below = sum(1 for value in continuation_totals if value < CONFIG["minimum_score"])
    result = {
        "cases": cases, "cases_passed": passed_cases,
        "turns": turns, "turns_passed_flag": turns_passed, "turns_passed_by_score": turns_passed_by_score,
        "modes": {mode: {"passed": row[0], "total": row[1]} for mode, row in sorted(modes.items())},
        "case_total_distribution": {str(key): distribution[key] for key in sorted(distribution, reverse=True)},
        "opening_mean": mean(opening_totals), "continuation_mean": mean(continuation_totals),
        "continuation_below_minimum": below,
        "continuation_below_minimum_share": round(below / len(continuation_totals), 3) if continuation_totals else None,
        "zero_dimensions": zero_dims,
        "deduction_points": {**deductions, "total": sum(deductions.values())},
        "blocking_cases": blocking, "reviewers": sorted(x for x in reviewers if x), "protocols": sorted(x for x in protocols if x),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["run", "check", "stats"])
    parser.add_argument("--batch", required=True, help="directory holding <stem>.json transcripts")
    parser.add_argument("--out-dir", help="review output directory (default: batch directory)")
    parser.add_argument("--brief", default=ROOT / "maintenance/attribution_review_protocol.md", type=Path)
    parser.add_argument("--reviewer", default="glm-independent-review-v3")
    parser.add_argument("--model-patch", default="maintenance/playtest_reviewer_glm.yml")
    parser.add_argument("--dsh-entry", type=Path)
    parser.add_argument("--dsh-extra", action="append", default=[])
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--force", action="store_true", help="re-review cases that already have a review file")
    parser.add_argument("--check-existing", action="store_true", help="include already reviewed cases in this run")
    parser.add_argument("--prompt-template", default=(
        "你是独立于生成器的评分者，reviewer={reviewer}，工作目录 {root}。"
        "第一步：读评分简报 {brief}（含八条校准与批次适用说明，先确认本批该用哪几条）。"
        "第二步：读实玩转写 {transcript}（4 回合，每回合含 request 与 response，首回合正文以「世界观 / 人物 / 正文」标题开头）。"
        "第三步：可选参考框架文件 {framework}，只用于姓名、年龄、称呼核对；该文件现值为修复后版本，不得因素材后改而扣分。"
        "第四步：用写文件工具把评分写到 {out}，只写这一个文件。必须照抄：framework_id={fid}、name={name}、mode={mode}、"
        "transcript_sha256={sha}、reviewer={reviewer}、protocol={protocol}、aggregation={aggregation}。"
        "其余字段按简报的输出契约：scores 与 evidence（五维，evidence 必须是该回合正文的逐字子串）、total、passed、"
        "turn_reviews（4 条，每条含 turn/scores/evidence/reason/blocking_findings/total/passed）、blocking_findings、summary。"
        "硬约束：案例级 scores 取最低回合那一套；不修改转写、不重跑生成、不改门槛、不碰其他文件，"
        "不得创建脚本、诊断或临时文件，除 {out} 外不得在工作区写入任何文件。{extra}"))
    args = parser.parse_args()
    args.brief = Path(args.brief)
    return {"run": cmd_run, "check": cmd_check, "stats": cmd_stats}[args.action](args)


if __name__ == "__main__":
    raise SystemExit(main())
