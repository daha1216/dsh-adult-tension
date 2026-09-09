"""Apply explicit duplicate-review scope without deleting or merging material."""
from __future__ import annotations

import json

from build_frameworks import ROOT
from material_inventory import read_yaml
from material_quality import quality


def audit():
    candidates = quality()
    reviews = read_yaml(ROOT / "maintenance/duplicate_reviews.yaml")["reviews"]
    unresolved, decisions = [], []
    for candidate in candidates["same_list_candidates"]:
        unresolved.append({"kind": "exact", "candidate": candidate})
    for candidate in candidates["near_candidates"]:
        review = next((r for r in reviews if r["kind"] == "near" and r.get("file") == candidate["file"]
                       and r.get("path") == candidate["path"] and set(r["values"]) == {candidate["a"], candidate["b"]}), None)
        (decisions if review else unresolved).append({"kind": "near", "candidate": candidate, "review": review})
    for candidate in candidates["cross_file_same_candidates"]:
        review = next((r for r in reviews if r["kind"] == "cross_file" and set(r["files"]) == set(candidate["files"])
                       and all(any(s["path"].startswith(p) for p in r["path_prefixes"]) for s in candidate["occurrences"])), None)
        (decisions if review else unresolved).append({"kind": "cross_file", "candidate": candidate, "review": review})
    return {"reviewed_candidates": len(decisions), "unresolved_candidates": len(unresolved),
            "unresolved": unresolved, "decisions": decisions,
            "scope": "Exact list duplicates, near list candidates and cross-file sentence references; prose quality remains a separate review."}


def main():
    result = audit()
    result.pop("decisions")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(result["unresolved_candidates"])


if __name__ == "__main__":
    raise SystemExit(main())
