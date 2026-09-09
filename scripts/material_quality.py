"""Read-only maintenance candidates, never semantic approval or deletion decisions."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import json
from pathlib import Path

from material_inventory import DATA, read_yaml, pointer


SIMILARITY_THRESHOLD = 0.83
MIN_FUNCTIONS = 3
GENERIC_FOLLOWUPS = ("不因此生成危机", "约下次继续")


def _source(file, path, **details):
    return {"file": file, "path": pointer(path), **details}


def _candidate(**details):
    return {"candidate_only": True, "semantic_grade": "REVIEW_REQUIRED", **details}


def _reuse_candidates(entries, distinct_key):
    groups = defaultdict(list)
    for text, source in entries:
        if isinstance(text, str) and text.strip():
            groups[text].append(source)
    return [
        _candidate(value=text, count=len(sources), occurrences=sources,
                   reason="Literal reuse only; context must be reviewed")
        for text, sources in groups.items()
        if len({distinct_key(source) for source in sources}) > 1
    ]


def quality(data_dir=DATA):
    repeated, lists, same, near = defaultdict(list), [], [], []

    def walk(file, value, path=()):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(file, child, path + (str(key),))
        elif isinstance(value, list):
            strings = [(i, x) for i, x in enumerate(value) if isinstance(x, str)]
            for text, count in Counter(x for _, x in strings).items():
                if count > 1:
                    same.append(_candidate(
                        **_source(file, path), value=text, count=count,
                        paths=[pointer(path + (str(i),)) for i, x in strings if x == text]))
            lists.append((file, path, strings))
            for index, child in enumerate(value):
                walk(file, child, path + (str(index),))
        elif isinstance(value, str) and len(value) >= 16:
            repeated[(file, value)].append(pointer(path))

    docs = {p.name: read_yaml(p) for p in sorted(Path(data_dir).glob("*.yaml"))}
    for file, doc in docs.items():
        walk(file, doc)
    for file, path, values in lists:
        for offset, (i, a) in enumerate(values):
            matcher = SequenceMatcher(None, a)
            for j, b in values[offset + 1:]:
                if a == b:
                    continue
                matcher.set_seq2(b)
                # Both quick ratios are upper bounds, so pruning loses no candidates.
                if (matcher.real_quick_ratio() < SIMILARITY_THRESHOLD
                        or matcher.quick_ratio() < SIMILARITY_THRESHOLD):
                    continue
                ratio = matcher.ratio()
                if ratio >= SIMILARITY_THRESHOLD:
                    near.append(_candidate(
                        **_source(file, path), a=a, b=b, similarity=round(ratio, 3),
                        a_path=pointer(path + (str(i),)), b_path=pointer(path + (str(j),))))

    # Keep legacy prose clusters file-scoped; cross-file reuse is separate evidence.
    clusters = [_candidate(file=file, text=text, paths=paths, count=len(paths))
                for (file, text), paths in repeated.items() if len(paths) > 1]
    cross_values = defaultdict(list)
    for (file, text), paths in repeated.items():
        cross_values[text].extend({"file": file, "path": path} for path in paths)
    cross_file = [_candidate(value=text, occurrences=sources, count=len(sources),
                             files=sorted({s["file"] for s in sources}))
                  for text, sources in cross_values.items()
                  if len({s["file"] for s in sources}) > 1]

    metadata = docs.get("action_metadata.yaml") or {}
    action_categories = docs.get("action_categories.yaml") or {}
    action_functions, action_evidence = Counter(), []
    for category, actions in action_categories.items():
        if not isinstance(actions, list):
            continue
        function = (metadata.get(category) or {}).get("function")
        label = function if isinstance(function, str) and function.strip() else "UNMAPPED"
        count = sum(isinstance(action, str) for action in actions)
        action_functions[label] += count
        action_evidence.append({
            **_source("action_categories.yaml", (category,)), "category": category,
            "function": function, "count": count,
            "function_source": _source("action_metadata.yaml", (category, "function")),
        })
    avatar = (docs.get("pools.yaml") or {}).get("玩家化身轴", {})
    distributions = {
        "count_unit": "source entries, not sampling probabilities or semantic coverage",
        "action_functions": dict(action_functions), "action_function_evidence": action_evidence,
        "appellations": dict(Counter(avatar.get("称谓", []))),
        "social_positions": dict(Counter(avatar.get("社会位置", []))),
        "appellation_source": _source("pools.yaml", ("玩家化身轴", "称谓")),
        "social_position_source": _source("pools.yaml", ("玩家化身轴", "社会位置")),
    }

    frames, shortfalls, generic = [], [], []
    resources, relationships, consequences = [], [], []
    file = "world_frameworks.yaml"
    registry = (docs.get(file) or {}).get("frameworks", {})
    for name, frame in registry.items():
        base = ("frameworks", name)
        activities = frame.get("activities", {})
        pairs = frame.get("pairs", [])
        pressures = frame.get("pressures", {})
        categories = Counter(a.get("category", "UNMAPPED") for a in activities.values())
        functions, function_sources, unmapped = Counter(), [], []
        common = 0
        for activity_name, activity in activities.items():
            path = base + ("activities", activity_name)
            category = activity.get("category")
            function = (metadata.get(category) or {}).get("function")
            evidence = _source(file, path + ("category",), category=category,
                               function_source=_source("action_metadata.yaml", (category, "function")))
            if isinstance(function, str) and function.strip():
                functions[function] += 1
                function_sources.append({**evidence, "function": function})
            else:
                unmapped.append(evidence)
            near_text = activity.get("beats", {}).get("near", "")
            common += isinstance(near_text, str) and any(p in near_text for p in GENERIC_FOLLOWUPS)

        if len(functions) < MIN_FUNCTIONS or unmapped:
            shortfalls.append(_candidate(
                **_source(file, base + ("activities",)), framework=name,
                minimum=MIN_FUNCTIONS, observed=len(functions), functions=dict(functions),
                evidence=function_sources, unmapped=unmapped,
                reason="Fewer than three declared functions or incomplete metadata; not semantic diagnosis"))

        for section, rows in (("activities", activities), ("pressures", pressures)):
            for label, row in rows.items():
                path = base + (section, label)
                texts = [(path + ("beats", key), row.get("beats", {}).get(key))
                         for key in ("immediate", "near")]
                if section == "pressures":
                    texts.append((path + ("far_consequence",), row.get("far_consequence")))
                for text_path, text in texts:
                    if not isinstance(text, str) or not text.strip():
                        continue
                    source = _source(file, text_path, framework=name)
                    consequences.append((text, source))
                    markers = [p for p in GENERIC_FOLLOWUPS if p in text]
                    if markers:
                        generic.append(_candidate(**source, value=text, markers=markers,
                                                  reason="Generic followup phrase match"))

        appellations, positions, pair_distribution = Counter(), Counter(), defaultdict(Counter)
        for index, pair in enumerate(pairs):
            path = base + ("pairs", str(index))
            position = pair.get("position", "UNMAPPED")
            positions[position] += 1
            for appellation in pair.get("appellations", []):
                appellations[appellation] += 1
                pair_distribution[appellation][position] += 1
            fields = [(path + ("npc", "resource"), pair.get("npc", {}).get("resource"))]
            fields.extend((path + ("player", "resources", str(i)), text)
                          for i, text in enumerate(pair.get("player", {}).get("resources", [])))
            for text_path, text in fields:
                resources.append((text, _source(file, text_path, framework=name, pair_index=index)))
            relationships.append((pair.get("relationship_reason"),
                                  _source(file, path + ("relationship_reason",),
                                          framework=name, pair_index=index)))

        frames.append({
            "name": name, "structural_grade": "C" if common > len(activities) / 2 else "B",
            "semantic_grade": "REVIEW_REQUIRED", "places": len(frame.get("places", {})),
            "pairs": len(pairs), "activities": len(activities), "categories": dict(categories),
            "generic_followups": common,
            "pressure_combinations": sum(len(p.get("bindings", [])) for p in pressures.values()),
            "reason": "Structural triage only; A requires recorded semantic review",
            "action_function_distribution": dict(functions), "function_evidence": function_sources,
            "unmapped_functions": unmapped, "appellation_distribution": dict(appellations),
            "social_position_distribution": dict(positions),
            "appellation_social_position_distribution": {k: dict(v) for k, v in pair_distribution.items()},
            "pair_distribution_source": _source(file, base + ("pairs",)),
        })

    pair_key = lambda source: (source["framework"], source["pair_index"])
    resource_reuse = _reuse_candidates(resources, pair_key)
    reason_reuse = _reuse_candidates(relationships, pair_key)
    consequence_reuse = _reuse_candidates(consequences, lambda source: source["path"])
    for row in frames:
        name = row["name"]
        row["three_function_shortfall_candidates"] = [c for c in shortfalls if c["framework"] == name]
        row["generic_consequence_candidates"] = [c for c in generic if c["framework"] == name]
        for key, candidates in (("pair_resource_reuse_candidates", resource_reuse),
                                ("pair_relationship_reason_reuse_candidates", reason_reuse),
                                ("consequence_reuse_candidates", consequence_reuse)):
            row[key] = [c for c in candidates if any(s["framework"] == name for s in c["occurrences"])]

    return {
        "summary": {
            "frameworks": len(frames), "exact_same_list_candidates": len(same),
            "near_candidates": len(near), "repeated_prose_clusters": len(clusters),
            "cross_file_same_candidates": len(cross_file), "lists_scanned": len(lists),
            "large_lists_scanned": sum(len(values) > 150 for _, _, values in lists),
            "three_function_shortfall_candidates": len(shortfalls),
            "generic_consequence_candidates": len(generic),
            "consequence_reuse_candidates": len(consequence_reuse),
            "pair_resource_reuse_candidates": len(resource_reuse),
            "pair_relationship_reason_reuse_candidates": len(reason_reuse),
        },
        "frameworks": frames, "same_list_candidates": same, "near_candidates": near,
        "prose_clusters": clusters, "cross_file_same_candidates": cross_file,
        "distributions": distributions, "three_function_shortfall_candidates": shortfalls,
        "generic_consequence_candidates": generic, "consequence_reuse_candidates": consequence_reuse,
        "pair_resource_reuse_candidates": resource_reuse,
        "pair_relationship_reason_reuse_candidates": reason_reuse,
        "review_policy": {"candidate_only": True, "semantic_grade": "REVIEW_REQUIRED",
                          "automatic_deletion": False, "similarity_threshold": SIMILARITY_THRESHOLD,
                          "prose_min_length": 16, "minimum_declared_functions": MIN_FUNCTIONS},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = quality()
    print(json.dumps(result["summary"] if args.summary else result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
