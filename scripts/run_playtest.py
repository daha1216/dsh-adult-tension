"""Run explicit, resumable non-explicit narrative probes through DSH headless.

This consumes configured model quota. It never loads intimate profiles or asks
the model to edit files. Scoring is a separate review, not generator self-rating.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_frameworks import digest
from material_inventory import read_yaml
import roll_opening as roll
import build_opening as build
import fill_opening as fill

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "non-explicit-runtime-brief-v2"
FOLLOWUPS = [
    "我先询问对方真正想完成的事，再选一件现在能帮忙的小事；不要替我承诺后续。",
    "我对刚才的一项安排提出不同意见，愿意协商，但不接受新增义务。继续已有局面。",
    "我决定今天到此为止，明确告别。写出对方反应和已经发生的具体变化，不强行拦人或另造危机。",
]


def request_for_turn(index):
    return "按以下材料开始新局。" if index == 0 else FOLLOWUPS[index - 1]


def render_prompt(material, turns, request):
    rules = ("这是成年人物的非露骨互动小说验收。不得生成露骨性内容；不要调用工具，不读取或修改文件。"
             "每次只写当前回合，350字以内。首次必须有世界观、人物、正文三个标题，前两项各一两句。"
             "人物使用已提交的姓名、明确成年年龄和身份，不能重抽。不要反复复述限制或列菜单，用场景细节与对白推动。"
             "后续只写正文。不要替玩家说话或替玩家决定，不解释功能。日常模式不能凭空生成外部危机；"
             "压力模式只用给定压力链。人物有自己的需求、资源和边界，必须允许玩家退出。")
    history = [{"user": t["request"], "assistant": t["response"]} for t in turns]
    return (rules + "\n材料：" + json.dumps(material, ensure_ascii=False)
            + "\n已发生：" + json.dumps(history, ensure_ascii=False) + "\n当前请求：" + request)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix="playtest-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def context(pools, name, mode, seed):
    drawn = roll.build_roll(pools, seed, recent={}, opening_mode=mode, framework=name)
    frame = pools["世界框架"][name]
    # Only ordinary setting and opening material is sent to the prose model.
    allowed = ("时代", "地点", "美学基调", "核心规则", "社会规则", "世界框架", "场景动作", "压力来源")
    selection = {k: drawn[k] for k in allowed if k in drawn}
    chosen = drawn["框架选择"]
    pair = frame["pairs"][chosen["pair"]]
    package = {"pair": pair, "place": frame["places"][drawn["地点"]],
               "activity": frame["activities"][chosen["activity"]]}
    if chosen["pressure"]:
        package["pressure"] = frame["pressures"][chosen["pressure"]]
    state = fill.fill_opening(build.build_skeleton(drawn), drawn, fill.load_tables())
    visible = {"player": {k: state["player"][k] for k in ("name", "age", "identity")},
               "npc": {k: state["npcs"][0][k] for k in ("name", "age", "identity")},
               "current_node": state["current_node"]}
    return {"mode": mode, "selection": selection, "world_rule": frame["rule"],
            "customs": frame["customs"], "technology_boundary": frame["technology_boundary"],
            "bridge_explanation": frame.get("bridge_explanation"),
            "package": package, "committed_opening": visible}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", action="append", required=True)
    parser.add_argument("--dsh-entry", type=Path, help="DSH bin.js; uses node directly on Windows")
    parser.add_argument("--output", type=Path, default=ROOT / "maintenance/playtests")
    args = parser.parse_args()
    command = [shutil.which("node") or "node", str(args.dsh_entry)] if args.dsh_entry else [shutil.which("dsh") or "dsh"]
    version = subprocess.run([*command, "--version"], capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
    import yaml
    composed = subprocess.run([*command, "--profile", "headless", "--dump-config"], capture_output=True,
                              text=True, encoding="utf-8", check=True).stdout
    # BaseLoader treats executable YAML tags as inert text; emit only model IDs.
    def model_ids(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ("model", "modelId") and isinstance(child, str):
                    yield child
                else:
                    yield from model_ids(child)
        elif isinstance(value, list):
            for child in value:
                yield from model_ids(child)
    models = sorted(set(model_ids(yaml.load(composed, Loader=yaml.BaseLoader))))
    if not models:
        raise ValueError("Cannot identify the configured model without guessing")
    config = read_yaml(ROOT / "maintenance/baseline.yaml")["playtest"]
    index = read_yaml(ROOT / "authoring/framework_index.yaml")
    ids = {r["name"]: r["id"] for r in index["frameworks"]}
    pools = roll.load_pools()
    for name in args.framework:
        if name not in ids:
            parser.error(f"Unknown framework: {name}")
        for mode in config["modes"]:
            path = args.output / f"{ids[name]}-{mode}.json"
            current_hash = digest(pools["世界框架"][name])
            record = {"framework_id": ids[name], "name": name, "mode": mode, "seed": config["seed"],
                      "host": config["host"], "host_version": version, "generator": "dsh-headless:" + ",".join(models),
                      "protocol": PROTOCOL,
                      "source_hash": current_hash, "scope": config["scope"], "turns": []}
            if path.exists():
                previous = json.loads(path.read_text(encoding="utf-8"))
                if (previous.get("source_hash") != current_hash or previous.get("seed") != config["seed"]
                        or previous.get("protocol") != PROTOCOL or previous.get("generator") != record["generator"]):
                    raise ValueError(f"Stale transcript must be archived before rerun: {path}")
                record = previous
            material = context(pools, name, mode, config["seed"])
            for i, turn in enumerate(record["turns"]):
                if turn.get("request") != request_for_turn(i):
                    raise ValueError(f"Stale continuation protocol must be archived: {path}")
                prompt = render_prompt(material, record["turns"][:i], turn["request"])
                if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != turn.get("prompt_sha256"):
                    raise ValueError(f"Stale input must be archived before resuming: {path}")
            while len(record["turns"]) < config["continuation_turns"] + 1:
                i = len(record["turns"])
                request = request_for_turn(i)
                prompt = render_prompt(material, record["turns"], request)
                completed = subprocess.run([*command, "--profile", "headless", prompt], cwd=ROOT,
                                           capture_output=True, text=True, encoding="utf-8", timeout=180)
                if completed.returncode or not completed.stdout.strip():
                    # Do not persist stderr, which may contain reasoning or credentials.
                    raise RuntimeError(f"DSH call failed: {name}/{mode}/{i}; code={completed.returncode}")
                record["turns"].append({"turn": i, "request": request, "response": completed.stdout.strip(),
                                        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                                        "returncode": 0, "recorded_at": datetime.now(timezone.utc).isoformat()})
                atomic_json(path, record)
                print(f"Recorded {name}/{mode}/{i}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
