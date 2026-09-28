"""Host drivers: send one player message to a real host, headless, and return
what happened (ACCEPTANCE.md 6.1: through the real Skill, from a new
conversation, full records).

Each conversation keeps its host session id, so a script's turns are one
conversation (and a script can open a second one, e.g. "another dialogue
changed the same save"). Nothing but the player's words is sent: no rubric,
no hints, no instructions beyond the installed Skill.

The event parsers are separate functions so they can be tested on saved
streams without running a host.
"""

import json
import os
import shutil
import subprocess
import time


class HostError(Exception):
    """The host did not finish a turn. `host_calls`: the tool calls it had
    made before that, when they are known."""

    def __init__(self, message, host_calls=None):
        Exception.__init__(self, message)
        self.host_calls = host_calls or []


def _which(name):
    path = shutil.which(name)
    if not path:
        raise HostError("找不到宿主命令：%s" % name)
    return path


def _events(stdout_bytes):
    out = []
    for raw in stdout_bytes.decode("utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw.startswith("{"):
            continue
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


# -- Claude Code (claude -p --output-format stream-json) ------------------------------------------


def parse_claude_stream(events):
    """stream-json events -> {session_id, model, text, host_calls, cost, error}.
    `error`: the host's own result says the turn failed (is_error, or a
    subtype other than success, such as error_max_turns)."""
    session_id = model = error = None
    texts = []
    calls = {}
    order = []
    result_text = None
    cost = None
    for event in events:
        kind = event.get("type")
        session_id = event.get("session_id") or session_id
        if kind == "system" and event.get("subtype") == "init":
            model = event.get("model") or model
        elif kind == "assistant":
            message = event.get("message") or {}
            model = message.get("model") or model
            for block in message.get("content") or []:
                if block.get("type") == "text" and block.get("text", "").strip():
                    texts.append(block["text"])
                elif block.get("type") == "tool_use":
                    calls[block.get("id")] = {"tool": block.get("name"), "input": block.get("input"), "output": None}
                    order.append(block.get("id"))
        elif kind == "user":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                    content = block.get("content")
                    if isinstance(content, list):
                        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
                    calls[block["tool_use_id"]]["output"] = content
        elif kind == "result":
            result_text = event.get("result")
            cost = event.get("total_cost_usd")
            if event.get("is_error") or event.get("subtype", "success") != "success":
                error = "宿主报告这一轮出错（%s）：%s" % (event.get("subtype"), (result_text or "")[:300])
    text = "\n\n".join(texts) if texts else (result_text or "")
    return {"session_id": session_id, "model": model, "text": text, "host_calls": [calls[i] for i in order], "cost": cost, "error": error}


class ClaudeCode:
    name = "claude-code"

    def __init__(self, project_dir, env, model=None, timeout=900):
        self.exe = _which("claude")
        self.project_dir = project_dir
        self.env = env
        self.model = model
        self.timeout = timeout
        self.sessions = {}

    def version(self):
        proc = subprocess.run([self.exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env, timeout=60)
        return proc.stdout.decode("utf-8", errors="replace").strip()

    def send(self, conversation, text):
        argv = [self.exe, "-p", text, "--output-format", "stream-json", "--verbose"]
        if self.model:
            argv += ["--model", self.model]
        if conversation in self.sessions:
            argv += ["--resume", self.sessions[conversation]]
        started = time.perf_counter()
        proc = subprocess.run(argv, cwd=self.project_dir, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=self.timeout)
        events = _events(proc.stdout)
        parsed = parse_claude_stream(events)
        if not parsed["session_id"]:
            raise HostError("宿主没有返回会话：exit %d，%s" % (proc.returncode, proc.stderr.decode("utf-8", errors="replace")[:500]), parsed["host_calls"])
        if proc.returncode and not parsed["error"]:
            parsed["error"] = "宿主退出码 %d：%s" % (proc.returncode, proc.stderr.decode("utf-8", errors="replace")[:300])
        self.sessions[conversation] = parsed["session_id"]
        parsed["seconds"] = round(time.perf_counter() - started, 1)
        parsed["events"] = events
        return parsed


# -- OpenCode (opencode run --format json) ------------------------------------------------------------


def parse_opencode_stream(events):
    """JSON events -> {session_id, text, host_calls, error}. The stage 0
    transcript has no error event to copy; any event of type "error" counts,
    and the caller checks the exit code as well."""
    session_id = error = None
    texts = []
    calls = []
    for event in events:
        session_id = event.get("sessionID") or session_id
        part = event.get("part") or {}
        if event.get("type") == "text" and part.get("text", "").strip():
            texts.append(part["text"])
        elif event.get("type") == "tool_use":
            state = part.get("state") or {}
            calls.append({"tool": part.get("tool"), "input": state.get("input"), "output": state.get("output"), "status": state.get("status")})
        elif event.get("type") == "error":
            error = "宿主报告这一轮出错：%s" % json.dumps(event.get("error", event), ensure_ascii=False)[:300]
    return {"session_id": session_id, "model": None, "text": "\n\n".join(texts), "host_calls": calls, "cost": None, "error": error}


class OpenCode:
    name = "opencode"

    def __init__(self, project_dir, env, model, timeout=900):
        if not model:
            raise HostError("OpenCode 需要用 --model 指定模型（provider/model）")
        self.exe = _which("opencode")
        self.project_dir = project_dir
        self.env = env
        self.model = model
        self.timeout = timeout
        self.sessions = {}

    def version(self):
        proc = subprocess.run([self.exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env, timeout=60)
        return proc.stdout.decode("utf-8", errors="replace").strip()

    def send(self, conversation, text):
        argv = [self.exe, "run", "--format", "json", "--dir", self.project_dir, "-m", self.model]
        if conversation in self.sessions:
            argv += ["--session", self.sessions[conversation]]
        argv.append(text)
        started = time.perf_counter()
        proc = subprocess.run(argv, cwd=self.project_dir, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=self.timeout)
        events = _events(proc.stdout)
        parsed = parse_opencode_stream(events)
        if not parsed["session_id"]:
            raise HostError("宿主没有返回会话：exit %d，%s" % (proc.returncode, proc.stderr.decode("utf-8", errors="replace")[:500]), parsed["host_calls"])
        if proc.returncode and not parsed["error"]:
            parsed["error"] = "宿主退出码 %d：%s" % (proc.returncode, proc.stderr.decode("utf-8", errors="replace")[:300])
        self.sessions[conversation] = parsed["session_id"]
        parsed["model"] = self.model
        parsed["seconds"] = round(time.perf_counter() - started, 1)
        parsed["events"] = events
        return parsed


HOSTS = {"claude-code": ClaudeCode, "opencode": OpenCode}


def project_config(host_name, project_dir, python_names=("python", "python3", "py")):
    """Project-level permissions only (no instructions): the host may run the
    runtime and write its temporary input files inside the project."""
    if host_name == "claude-code":
        os.makedirs(os.path.join(project_dir, ".claude"), exist_ok=True)
        allow = ["Bash(%s:*)" % name for name in python_names] + ["Write(./**)", "Read(./**)"]
        settings = {"permissions": {"allow": allow, "deny": ["WebFetch", "WebSearch"]}}
        path = os.path.join(project_dir, ".claude", "settings.json")
    else:
        settings = {"$schema": "https://opencode.ai/config.json", "permission": {"bash": {"*": "deny", **{"%s *" % n: "allow" for n in python_names}}, "edit": "allow", "webfetch": "deny"}}
        path = os.path.join(project_dir, "opencode.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(settings, ensure_ascii=False, indent=1) + "\n")
    return path
