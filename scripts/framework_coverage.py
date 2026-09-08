"""Report literal coverage of legacy world axes; never changes content."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

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
    data = ROOT / "scripts" / "data"
    pools = yaml.safe_load((data / "pools.yaml").read_text(encoding="utf-8"))
    frames = yaml.safe_load((data / "world_frameworks.yaml").read_text(encoding="utf-8"))
    print(json.dumps(coverage(pools, frames), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

