"""End-to-end records (ACCEPTANCE.md 6.1 item 3).

A record is one run of one script on one host, kept in full:

    {
      "format": "adult-tension-e2e-record", "version": 1,
      "script": "01", "run": 1, "date": "2026-10-01",
      "host": {"name": "claude-code", "version": "...", "model": "..."},
      "skill": {"root": "...", "version": "...", "content_version": "..."},
      "turns": [
        {"index": 1, "conversation": "A", "input": "开一局", "expect": {...},
         "host_calls": [{"tool": "Bash", "input": ..., "output": "..."}],
         "runtime_calls": [{"argv": [...], "input": {...}, "exit": 0, "envelope": {...}, "ms": 80.1}],
         "text": "what the player saw", "seconds": 12.3}
      ],
      "harness_events": [{"after_turn": 30, "event": "upgrade_skill", "detail": "..."}],
      "final_export": {... export-save document ...}
    }

`runtime_calls` come from the engine's own trace (ADULT_TENSION_TRACE), so
they are the same whatever the host's transcript looks like. `expect` is the
script's annotation for the machine checks; the tested model never sees it.
"""

import json

FORMAT = "adult-tension-e2e-record"
VERSION = 1
TURN_KEYS = ("index", "conversation", "input", "expect", "host_calls", "runtime_calls", "text")


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(record, path):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=1) + "\n")


def validate(record):
    """Shape problems (strings); an empty list means the record can be checked."""
    problems = []
    if record.get("format") != FORMAT or record.get("version") != VERSION:
        problems.append("不是 %s v%d" % (FORMAT, VERSION))
    for key in ("script", "run", "host", "turns"):
        if key not in record:
            problems.append("缺少 %s" % key)
    host = record.get("host") or {}
    for key in ("name", "version", "model"):
        if not host.get(key):
            problems.append("宿主身份缺少 %s（ACCEPTANCE §6.1 第 5 条）" % key)
    for i, turn in enumerate(record.get("turns") or []):
        for key in TURN_KEYS:
            if key not in turn:
                problems.append("turns[%d] 缺少 %s" % (i, key))
    return problems


def command_of(call):
    argv = call.get("argv") or []
    return argv[0] if argv else None


def ok_data(call):
    envelope = call.get("envelope") or {}
    return envelope.get("data") if envelope.get("ok") else None


def error_code(call):
    envelope = call.get("envelope") or {}
    return None if envelope.get("ok") else (envelope.get("error") or {}).get("code")


def _brief_call(call):
    out = {"command": command_of(call), "exit": call.get("exit")}
    if call.get("input") is not None:
        out["input"] = call["input"]
    envelope = call.get("envelope") or {}
    if envelope.get("ok"):
        data = envelope.get("data") or {}
        out["result"] = {k: data[k] for k in ("receipt", "turn", "revision", "applied", "resolved_events", "clock") if k in data}
    else:
        error = envelope.get("error") or {}
        out["error"] = {"code": error.get("code"), "message": error.get("message"), "details": (error.get("details") or [])[:5]}
    return out


def to_markdown(record):
    """The record as the reviewer reads it: every turn's player input, every
    tool call with its input and result, and everything the player saw."""
    host = record.get("host") or {}
    lines = [
        "# 记录：剧本 %s · 第 %s 次运行" % (record.get("script"), record.get("run")),
        "",
        "- 宿主：%s %s；模型：%s；日期：%s" % (host.get("name"), host.get("version"), host.get("model"), record.get("date")),
        "",
    ]
    events = {e.get("after_turn"): e for e in record.get("harness_events") or []}
    for turn in record.get("turns") or []:
        lines.append("## 第 %d 轮（对话 %s）" % (turn["index"], turn.get("conversation", "A")))
        lines.append("")
        lines.append("**玩家**：%s" % turn["input"])
        lines.append("")
        for call in turn.get("runtime_calls") or []:
            lines.append("<details><summary>工具调用：%s</summary>" % command_of(call))
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(_brief_call(call), ensure_ascii=False, indent=1))
            lines.append("```")
            lines.append("</details>")
            lines.append("")
        lines.append("**玩家看到的**：")
        lines.append("")
        lines.append(turn.get("text") or "（无）")
        lines.append("")
        if turn["index"] in events:
            event = events[turn["index"]]
            lines.append("> 测试框架：%s（%s）" % (event.get("event"), event.get("detail", "")))
            lines.append("")
    return "\n".join(lines) + "\n"
