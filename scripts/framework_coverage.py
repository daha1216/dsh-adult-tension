"""Report literal coverage of legacy world axes; never changes content."""
from __future__ import annotations

import json
import argparse
from pathlib import Path

from material_inventory import read_yaml

ROOT = Path(__file__).resolve().parents[1]


def coverage(pools, registry):
    frames = registry["frameworks"]
    result = {"framework_count": len(frames), "axes": {}}
    sources = {
        "eras": pools["时代与地点"]["时代"],
        "aesthetics": pools["美学基调"],
        "places": pools["时代与地点"]["地点"],
    }
    for axis, values in sources.items():
        owners = {value: [name for name, row in frames.items() if value in row[axis]] for value in values}
        result["axes"][axis] = {
            "total": len(values),
            "covered": sum(bool(names) for names in owners.values()),
            "missing": [value for value, names in owners.items() if not names],
            "frameworks_by_material": owners,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    data = ROOT / "scripts" / "data"
    pools = read_yaml(data / "pools.yaml")
    frames = read_yaml(data / "world_frameworks.yaml")
    result = coverage(pools, frames)
    if args.summary:
        for row in result["axes"].values():
            row.pop("frameworks_by_material")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
