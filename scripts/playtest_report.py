"""Audit actual non-explicit model transcripts and separate reviewer evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_frameworks import digest
from material_inventory import read_yaml

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "maintenance/playtests"


def checked_scores(review, prose, config):
    scores = review.get("scores", {})
    excerpts = review.get("evidence", {})
    if set(scores) != set(config["dimensions"]):
        raise ValueError("incomplete dimensions")
    for dimension, value in scores.items():
        if type(value) is not int or value not in (0, 1, 2):
            raise ValueError("invalid dimension score")
        if not isinstance(excerpts.get(dimension), str) or not excerpts[dimension] or excerpts[dimension] not in prose:
            raise ValueError("untraceable scoring evidence")
    if not isinstance(review.get("blocking_findings"), list):
        raise ValueError("missing findings disposition")
    return scores


def audit(root=ROOT):
    from run_playtest import context, render_prompt, request_for_turn, roll

    config = read_yaml(root / "maintenance/baseline.yaml")["playtest"]
    index = read_yaml(root / "authoring/framework_index.yaml")
    errors, responses, current_responses, passed_cases = [], 0, 0, 0
    pools = roll.load_pools()
    for row in index["frameworks"]:
        material = read_yaml(root / "authoring/frameworks" / f"{row['id']}.yaml")["material"]
        for mode in config["modes"]:
            stem = f"{row['id']}-{mode}"
            path = root / "maintenance/playtests" / f"{stem}.json"
            review_path = path.with_name(stem + ".review.yaml")
            if not path.exists():
                errors.append(f"PLAYTEST_MISSING: {stem}")
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                turns = record["turns"]
                if (record.get("framework_id") != row["id"] or record.get("name") != row["name"] or record.get("mode") != mode
                        or record.get("seed") != config["seed"] or record.get("source_hash") != digest(material)
                        or record.get("scope") != "non_explicit_narrative"
                        or record.get("protocol") != "non-explicit-runtime-brief-v2"
                        or record.get("host") != config["host"]
                        or not record.get("host_version") or not record.get("generator")):
                    raise ValueError("identity, seed, scope or source mismatch")
                if len(turns) != config["continuation_turns"] + 1:
                    raise ValueError("incomplete continuation sequence")
                for i, turn in enumerate(turns):
                    if (turn.get("turn") != i or turn.get("returncode") != 0 or not turn.get("request")
                            or not isinstance(turn.get("response"), str) or not turn["response"].strip()
                            or not turn.get("recorded_at")):
                        raise ValueError("missing actual successful response")
                    if not isinstance(turn.get("prompt_sha256"), str) or len(turn["prompt_sha256"]) != 64:
                        raise ValueError("missing prompt fingerprint")
                    if turn["request"] != request_for_turn(i):
                        raise ValueError("stale continuation request protocol")
                responses += len(turns)
                prompt_material = context(pools, row["name"], mode, config["seed"])
                for i, turn in enumerate(turns):
                    prompt = render_prompt(prompt_material, turns[:i], turn["request"])
                    if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != turn["prompt_sha256"]:
                        raise ValueError("stale runtime input or prompt; archive before rerun")
                current_responses += len(turns)
                if not review_path.exists():
                    errors.append(f"PLAYTEST_UNSCORED: {stem}")
                    continue
                review = read_yaml(review_path)
                if (review.get("transcript_sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
                        or not review.get("reviewer") or review["reviewer"] == record["generator"]):
                    raise ValueError("stale or non-independent review")
                prose = "\n".join(t["response"] for t in turns)
                scores = checked_scores(review, prose, config)
                turn_reviews = review.get("turn_reviews")
                if not isinstance(turn_reviews, list) or len(turn_reviews) != len(turns):
                    raise ValueError("missing individual turn reviews")
                turn_scores = []
                for i, (turn, turn_review) in enumerate(zip(turns, turn_reviews)):
                    if not isinstance(turn_review, dict) or turn_review.get("turn") != i:
                        raise ValueError("invalid turn review sequence")
                    value = checked_scores(turn_review, turn["response"], config)
                    turn_scores.append(value)
                minimum = min(sum(value.values()) for value in turn_scores)
                if not any(scores == value and sum(value.values()) == minimum for value in turn_scores):
                    raise ValueError("case score must use the lowest scoring turn")
                if 0 in scores.values() or any(0 in value.values() for value in turn_scores):
                    raise ValueError("zero-scored turn blocks acceptance")
                if (minimum < config["minimum_score"] or review["blocking_findings"]
                        or any(item["blocking_findings"] for item in turn_reviews)):
                    raise ValueError("score below gate or unresolved findings")
                passed_cases += 1
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"PLAYTEST_INVALID: {stem}: {exc}")
    required = len(index["frameworks"]) * len(config["modes"]) * (1 + config["continuation_turns"])
    if config["minimum_model_responses"] != required:
        errors.append("PLAYTEST_BASELINE_COUNT_MISMATCH")
    return {"responses": responses, "required_responses": required,
            "current_responses": current_responses,
            "passed_cases": passed_cases, "required_cases": len(index["frameworks"]) * len(config["modes"]), "errors": errors,
            "passed": not errors, "scope": "non_explicit_narrative"}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(result["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
