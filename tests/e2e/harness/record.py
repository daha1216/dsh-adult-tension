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
they are the same whatever the host's transcript looks like. An older Skill
without the trace (the version a script starts from before an upgrade) gets
them rebuilt from the host's own tool calls instead (`calls_from_host`,
turn["calls_source"] == "host"). `expect` is the script's annotation for the
machine checks; the tested model never sees it.
"""

import json
import re

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


# -- runtime calls rebuilt from the host's own tool calls ---------------------------------
#
# Each runtime invocation in a shell command is one call. Its input is what
# the host last wrote to the --input-file path (a Write/Edit tool call or a
# heredoc into a file), or a heredoc fed to the runtime's stdin; its envelope
# is the JSON the command printed. Exit code and duration are not known there.

PATH_TOKEN = r"\"[^\"]+\"|'[^']+'|[^\s<>'\";&|]+"
RUNTIME_RE = re.compile(r"adult_tension\.py[\"']?[ \t]+(?P<command>[a-z][a-z0-9-]*)(?P<rest>[^\n;&|<>]*)")
INPUT_FILE_RE = re.compile(r"--input-file(?:=|[ \t]+)(?P<path>%s)" % PATH_TOKEN)
HEREDOC_RE = re.compile(r"<<-?[ \t]*(?P<q>['\"]?)(?P<tag>[A-Za-z_]\w*)(?P=q)")
FILE_TARGET_RE = re.compile(r"(?:>[ \t]*|\btee[ \t]+)(?P<path>%s)" % PATH_TOKEN)
TOKEN_RE = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")


def _unquote(token):
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def _path_key(path):
    path = _unquote(path).replace("\\", "/")
    drive = re.match(r"^/([A-Za-z])/(.*)$", path)  # Git Bash: /d/projects -> d:/projects
    if drive:
        path = "%s:/%s" % drive.groups()
    return re.sub(r"^(\./)+", "", path).lower()


class _Files:
    """What the host wrote so far, in order."""

    def __init__(self):
        self.items = []

    def write(self, path, content):
        self.items.append((_path_key(path), content))

    def read(self, path):
        key = _path_key(path)
        base = key.rsplit("/", 1)[-1]
        tests = (lambda k: k == key, lambda k: k.endswith("/" + key), lambda k: k.rsplit("/", 1)[-1] == base)
        for test in tests:
            for written, content in reversed(self.items):
                if test(written):
                    return content
        return None

    def edit(self, path, old, new, replace_all):
        content = self.read(path)
        if content is not None and old and old in content:
            self.write(path, content.replace(old, new) if replace_all else content.replace(old, new, 1))


def _json_value(text):
    try:
        return json.loads(text) if text is not None else None
    except ValueError:
        return None


def _envelopes(output):
    """The runtime envelopes printed in a tool output, in order."""
    out = []
    decoder = json.JSONDecoder()
    text = output if isinstance(output, str) else ""
    index = 0
    while True:
        start = text.find("{", index)
        if start < 0:
            return out
        try:
            value, end = decoder.raw_decode(text, start)
        except ValueError:
            index = start + 1
            continue
        if isinstance(value, dict) and {"ok", "data", "error"} <= set(value):
            out.append(value)
            index = end
        else:
            index = start + 1


# Bash's own report that it could not parse a command. It runs the complete
# commands on the lines before the reported one and nothing from that line on
# ("-c: line 2: unexpected EOF while looking for matching `\"'").
SHELL_SYNTAX_RE = re.compile(r"(?m)^[^\s:]*sh: -c: line (\d+): (?:unexpected EOF while looking for matching|syntax error)")


# Redirections between two invocations on one line (2>&1, >/dev/null, < in.json): not operators.
REDIRECT_RE = re.compile(r"\d*>&\d+|&>>?\s*\S+|\d*>>?\s*\S+|<\s*\S+")
OPERATOR_RE = re.compile(r"\|\||&&|;|\||&")


def _joiner(gap):
    """How the shell joins two runtime invocations on one line, from the text
    between them: "||" (the second runs only if the first failed) or "&&"
    (only if it succeeded) when that operator is all that stands between
    them; None when the second runs either way (;, a pipe) or other commands
    in between make it unknowable."""
    operators = OPERATOR_RE.findall(REDIRECT_RE.sub(" ", gap))
    return operators[0] if len(operators) == 1 and operators[0] in ("||", "&&") else None


def _shell_invocations(command, files, ran_lines=None):
    """(argv, input, joiner) for each runtime invocation in one shell command
    (joiner: see _joiner; None for the first on a line); with ran_lines, only
    in its first ran_lines lines."""
    lines = command.split("\n")
    if ran_lines is not None:
        lines = lines[:ran_lines]
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        stdin, reader = None, None
        heredoc = HEREDOC_RE.search(line)
        if heredoc:
            body = []
            while i < len(lines) and lines[i].strip() != heredoc.group("tag"):
                body.append(lines[i])
                i += 1
            i += 1
            head = line[: heredoc.start()]
            before = [m.start() for m in RUNTIME_RE.finditer(head)]
            if before:
                stdin, reader = "\n".join(body), before[-1]
            else:
                target = FILE_TARGET_RE.search(head + " " + line[heredoc.end() :].split("&&")[0])
                if target:
                    files.write(target.group("path"), "\n".join(body))
        end = None
        for match in RUNTIME_RE.finditer(line):
            joiner = _joiner(line[end : match.start()]) if end is not None else None
            end = match.end()
            tokens = [_unquote(t) for t in TOKEN_RE.findall(match.group("rest"))]
            while tokens and re.match(r"^\d$", tokens[-1]):  # the 2 of 2>&1
                tokens.pop()
            source = INPUT_FILE_RE.search(match.group("rest"))
            if source:
                payload = _json_value(files.read(source.group("path")))
            else:
                payload = _json_value(stdin) if match.start() == reader else None
            out.append(([match.group("command")] + tokens, payload, joiner))
    return out


def calls_from_host(host_calls):
    """Runtime calls in the trace's shape, rebuilt from a host's tool calls."""
    files = _Files()
    out = []
    for call in host_calls or []:
        data = call.get("input")
        if not isinstance(data, dict):
            continue
        path = data.get("file_path") or data.get("filePath") or data.get("path")
        old = data.get("old_string", data.get("oldString", data.get("oldText")))
        if path and isinstance(data.get("content"), str):
            files.write(path, data["content"])
        elif path and isinstance(old, str):
            files.edit(path, old, data.get("new_string", data.get("newString", data.get("newText"))) or "", bool(data.get("replace_all", data.get("replaceAll"))))
        elif path and isinstance(data.get("edits"), list):  # Pi: several replacements in one call
            for edit in data["edits"]:
                if isinstance(edit, dict) and isinstance(edit.get("oldText"), str):
                    files.edit(path, edit["oldText"], edit.get("newText") or "", False)
        elif isinstance(data.get("command"), str):
            output = call.get("output")
            envelopes = _envelopes(output)
            broken = SHELL_SYNTAX_RE.search(output) if isinstance(output, str) else None
            ran_lines = int(broken.group(1)) - 1 if broken else None
            # each invocation that ran printed one envelope, in order; an alternative after a success
            # (a || b) or a follow-up after a failure (a && b) never ran and printed none
            previous, n = None, 0
            for argv, payload, joiner in _shell_invocations(data["command"], files, ran_lines):
                if previous is not None and joiner and (previous.get("ok") is True) == (joiner == "||"):
                    continue
                envelope = envelopes[n] if n < len(envelopes) else None
                n += 1
                previous = envelope
                out.append({"argv": argv, "input": payload, "exit": None, "envelope": envelope, "ms": None, "source": "host"})
    return out


def _brief_call(call):
    out = {"command": command_of(call), "exit": call.get("exit")}
    if call.get("source"):
        out["source"] = call["source"]
    if call.get("input") is not None:
        out["input"] = call["input"]
    envelope = call.get("envelope") or {}
    if not envelope:
        out["result"] = "宿主的记录里没有可解析的返回"
    elif envelope.get("ok"):
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
