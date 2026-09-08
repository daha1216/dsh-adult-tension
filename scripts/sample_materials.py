"""Deterministic in-memory probes; no saves, history writes or prose generation."""
from __future__ import annotations

import argparse
import json

import build_opening as build
import fill_opening as fill
import roll_opening as roll
import validate_state as validate


def sample(seeds=(11, 29)):
    pools, tables = roll.load_pools(), fill.load_tables()
    results, errors = [], []
    for framework in [*pools["世界框架"], "legacy", "auto"]:
        for mode in ("daily", "pressure"):
            for seed in seeds:
                case = {"framework": framework, "mode": mode, "seed": seed}
                try:
                    drawn = roll.build_roll(pools, seed, recent={}, opening_mode=mode, framework=framework)
                    state = fill.fill_opening(build.build_skeleton(drawn), drawn, tables)
                    failures = validate.validate_data(state, "opening")
                    if mode == "daily" and (drawn.get("压力来源") or state.get("events")):
                        failures.append("daily opening unexpectedly creates pressure or events")
                    case.update(selected_framework=drawn.get("世界框架"), era=drawn.get("时代"),
                                place=drawn.get("地点"), activity=drawn.get("场景动作"),
                                pressure=drawn.get("压力来源"), failures=failures)
                    if failures:
                        errors.append(case)
                except Exception as exc:
                    case["failures"] = [f"{type(exc).__name__}: {exc}"]
                    errors.append(case)
                results.append(case)
    return {"seeds": list(seeds), "samples": len(results), "failed": len(errors),
            "errors": errors, "results": results,
            "limitations": "Schema and mode probes, not prose quality or exhaustive combination certification."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = sample()
    if args.summary:
        result.pop("results")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(result["failed"])


if __name__ == "__main__":
    raise SystemExit(main())
