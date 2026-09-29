"""Have an independent model review one record (ACCEPTANCE.md 6.1 item 7).

    python tests/e2e/harness/review.py --record <record.json> --out <review.json>
        --endpoint-file <file>

The reviewer is a fresh model instance: one request that holds the review
packet and nothing else (reviewer.md, rubric.md, NARRATIVE_RULES.md and the
record: report.packet), sent to an OpenAI-compatible chat endpoint, without
tools. It sees no implementation, no script focus, no expectations.

The endpoint file (kept outside the repository) has KEY=VALUE lines:
REVIEW_BASE_URL (".../v1"), REVIEW_API_KEY and REVIEW_MODEL.

The answer must be the JSON object reviewer.md asks for. An answer that is
not (no JSON, a dimension missing, a score out of range) goes back to the
reviewer with what is wrong in its form, asking for the same review in the
required form; at most 3 attempts in all; every raw answer is kept in the
output. Scores are taken as the reviewer gave them.

reviewer.model is the name asked for; each attempt's served_model is the
model the endpoint says answered. Reports go by the latter (report.reviewer_of):
one name can be served by different models. reviewer.rubric_version is the
rubric version in the packet: a calibration counts only for its own version.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import report  # noqa: E402
import run_script  # noqa: E402

ATTEMPTS = 3
FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)


def parse_answer(text):
    """The JSON object in the answer (bare or in a code fence), or None."""
    text = (text or "").strip()
    match = FENCE_RE.search(text)
    candidates = [match.group(1)] if match else []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def json_error(text):
    """Where the answer stops being JSON, for the reviewer to fix."""
    text = text or ""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return "回答里没有 JSON 对象"
    try:
        json.loads(text[start : end + 1])
    except ValueError as err:
        return "JSON 在第 %d 行第 %d 列出错（%s）" % (err.lineno, err.colno, err.msg)
    return None


FORMAT_AGAIN = (
    "上面的回答不能用：%s。请把同一份评审原样改成评审说明要求的 JSON 对象，分数和证据都不要改；"
    "字符串里引用原文时用「」，或者把英文双引号写成 \\\"。只输出这个 JSON 对象。"
)


def problems_of(review):
    """What makes an answer unusable: the shape reviewer.md asks for."""
    if not isinstance(review, dict):
        return ["不是 JSON 对象"]
    out = []
    scores = review.get("scores")
    if not isinstance(scores, dict):
        return ["缺少 scores"]
    for dimension in report.DIMENSIONS:
        entry = scores.get(dimension)
        if not isinstance(entry, dict):
            out.append("缺少维度 %s" % dimension)
            continue
        score = entry.get("score")
        if not (score == "n/a" or (isinstance(score, int) and not isinstance(score, bool) and 1 <= score <= 5)):
            out.append("%s 的分数不是 1–5 的整数或 n/a：%r" % (dimension, score))
        if not isinstance(entry.get("evidence"), list) or not entry["evidence"]:
            out.append("%s 没有证据" % dimension)
    extra = sorted(set(scores) - set(report.DIMENSIONS))
    if extra:
        out.append("多出的维度：%s" % "、".join(extra))
    if not isinstance(review.get("severe", []), list):
        out.append("severe 不是列表")
    return out


def ask(endpoint, messages, timeout=900, max_tokens=16000):
    # room for a thinking model's reasoning and the whole JSON answer
    body = {"model": endpoint["REVIEW_MODEL"], "max_tokens": max_tokens, "messages": messages}
    req = urllib.request.Request(
        endpoint["REVIEW_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + endpoint["REVIEW_API_KEY"], "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choice = (data.get("choices") or [{}])[0]
    return (choice.get("message") or {}).get("content") or "", data.get("model")


def review(record_path, endpoint, send=ask, wait=60):
    text = report.packet(record_path)
    messages = [{"role": "user", "content": text}]
    attempts = []
    result = None
    for _ in range(ATTEMPTS):
        try:
            answer, served = send(endpoint, messages)
        except urllib.error.HTTPError as err:
            # what the endpoint said (a model it does not serve, a quota), never the key
            said = err.read().decode("utf-8", "replace")[:300]
            if endpoint.get("REVIEW_API_KEY"):
                said = said.replace(endpoint["REVIEW_API_KEY"], "<key>")
            attempts.append({"error": "HTTP %d" % err.code, "detail": said, "retry_after": err.headers.get("Retry-After")})
            time.sleep(min(int(err.headers.get("Retry-After") or wait), 600))
            continue
        parsed = parse_answer(answer)
        found = problems_of(parsed)
        attempts.append({"served_model": served, "answer": answer, "problems": found})
        if not found:
            result = parsed
            break
        # only the form goes back: the answer that failed and what is wrong with it
        wrong = [json_error(answer)] if parsed is None else found
        messages = messages[:1] + [{"role": "assistant", "content": answer}, {"role": "user", "content": FORMAT_AGAIN % "；".join(wrong)}]
    out = dict(result or {"scores": None, "severe": None})
    out["reviewer"] = {
        "model": endpoint["REVIEW_MODEL"],
        "date": datetime.date.today().isoformat(),
        "rubric_version": report.rubric_version(),
        "packet_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "attempts": attempts,
        "usable": result is not None,
    }
    return out


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--endpoint-file", required=True)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    endpoint = run_script.read_env_file(args.endpoint_file)
    missing = [k for k in ("REVIEW_BASE_URL", "REVIEW_API_KEY", "REVIEW_MODEL") if not endpoint.get(k)]
    if missing:
        raise SystemExit("评审接口文件缺少：%s" % "、".join(missing))
    out = review(args.record, endpoint)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("%s：%s" % (args.out, outcome(out["reviewer"])))
    return 0 if out["reviewer"]["usable"] else 1


def outcome(reviewer):
    """One line on how the review went: usable, no answer at all, or no answer in the required form."""
    if reviewer["usable"]:
        return "可用"
    errors = [a for a in reviewer["attempts"] if "error" in a]
    if len(errors) == len(reviewer["attempts"]):
        return "%d 次都没有拿到回答：%s %s" % (len(errors), errors[-1]["error"], errors[-1].get("detail") or "")
    return "%d 次都不是要求的格式" % len(reviewer["attempts"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
