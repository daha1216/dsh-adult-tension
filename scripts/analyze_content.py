#!/usr/bin/env python3
"""只读分析素材库与开局抽取分布。

用法：python scripts/analyze_content.py [--samples 1000] [--format text|json]
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scripts" / "data"

def load_yaml(path: Path) -> Any:
    from material_inventory import read_yaml
    return read_yaml(path)

def load_roll():
    spec = importlib.util.spec_from_file_location("roll_opening_analysis", ROOT / "scripts" / "roll_opening.py")
    if not spec or not spec.loader:
        raise RuntimeError("cannot load roll_opening.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def strings(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)
    elif isinstance(value, str) and value.strip():
        yield value.strip()

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--framework", default="auto", help="Default reviewed pool; use legacy for the independent old-pool distribution")
    parser.add_argument("--opening-mode", choices=("daily", "pressure"), default="pressure")
    args = parser.parse_args(argv)
    if args.samples < 0:
        parser.error("--samples must be non-negative")
    roll = load_roll()
    pools = roll.load_pools()
    report: dict[str, Any] = {"files": {}, "duplicate_values": {}, "weights": {}, "simulation": {}}
    for path in sorted(DATA.glob("*.yaml")):
        values = list(strings(load_yaml(path)))
        counts = collections.Counter(values)
        report["files"][path.name] = {"total_strings": len(values), "unique_strings": len(counts), "duplicate_value_count": sum(n > 1 for n in counts.values())}
        report["duplicate_values"][path.name] = [{"value": value, "count": count} for value, count in counts.most_common() if count > 1][:20]
    weights = pools.get("meta", {}).get("identity_weights", {})
    total = sum(weights.values())
    report["weights"] = {name: {"weight": weight, "share": round(weight / total, 4) if total else 0} for name, weight in sorted(weights.items(), key=lambda item: -item[1])}
    report["location_coverage"] = {"families": len(pools["时代与地点"]["地点"]), "variants": len(getattr(roll, "_raw_pools_once")().get("时代与地点", {}).get("地点", []))}
    if args.samples:
        counters = {key: collections.Counter() for key in ("世界框架", "地点", "身份族", "处境", "场景动作")}
        for seed in range(args.samples):
            item = roll.build_roll(pools, seed, recent={}, framework=args.framework, opening_mode=args.opening_mode)
            for key, counter in counters.items():
                counter[item.get(key)] += 1
        report["simulation"] = {key: {value: count for value, count in counter.most_common()} for key, counter in counters.items()}
        report["simulation"]["samples"] = args.samples
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print("素材库分析报告")
    print(f"抽样范围：framework={args.framework}, opening_mode={args.opening_mode}, samples={args.samples}")
    for name, info in report["files"].items():
        print(f"- {name}: {info['total_strings']} 条字符串，{info['unique_strings']} 个唯一值，{info['duplicate_value_count']} 个重复值")
    print("身份族权重：")
    for name, info in report["weights"].items():
        print(f"- {name}: {info['weight']} ({info['share']:.1%})")
    print(f"地点：{report['location_coverage']['variants']} 个具体地点")
    for key, values in report["simulation"].items():
        if key == "samples":
            continue
        print(f"{key} 高频：" + "；".join(f"{name}={count}" for name, count in list(values.items())[:5]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
