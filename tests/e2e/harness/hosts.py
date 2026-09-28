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

# Where run_script installs the Skill in a test project.
SKILL_REL = os.path.join(".claude", "skills", "adult-tension")


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
            # "<synthetic>": a message the host wrote itself (e.g. an API error), not a model's
            if message.get("model") != "<synthetic>":
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
    """The host sees the project's settings only: the operator's user-level
    settings (their API endpoint, model, hooks, plugins) and their MCP servers
    stay out, so every run starts from the same host. Permissions go on the
    command line, because Claude Code ignores the permission rules in the
    settings file of a workspace nobody has trusted interactively: the Skill
    may run Python and edit files in the project; the web is denied."""

    name = "claude-code"
    ISOLATION = ["--setting-sources", "project,local", "--strict-mcp-config"]
    PERMISSIONS = ["--permission-mode", "acceptEdits", "--allowedTools", "Bash(python:*)", "Bash(python3:*)", "Bash(py:*)", "--disallowedTools", "WebFetch", "WebSearch"]

    def __init__(self, project_dir, env, model=None, timeout=900, exe=None):
        self.exe = exe or _which("claude")
        self.project_dir = project_dir
        self.env = env
        self.model = model
        self.timeout = timeout
        self.sessions = {}

    def version(self):
        proc = subprocess.run([self.exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env, timeout=60)
        return proc.stdout.decode("utf-8", errors="replace").strip()

    def command(self, conversation, text):
        argv = [self.exe, "-p", text, "--output-format", "stream-json", "--verbose"] + self.ISOLATION + self.PERMISSIONS
        if self.model:
            argv += ["--model", self.model]
        if conversation in self.sessions:
            argv += ["--resume", self.sessions[conversation]]
        return argv

    def send(self, conversation, text):
        argv = self.command(conversation, text)
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
    """The host sees the project's configuration only. Its global
    configuration directory, session database and scratch directory are
    inside the project, so the operator's providers, plugins, MCP servers,
    agents, instructions and sessions stay out, and runs side by side share
    nothing; Skills come from the project configuration
    (project_config: skills.paths), not from the user-level .claude and
    .agents directories; ~/.claude/CLAUDE.md is not read. No self-update,
    sharing, default plugins or language-server downloads during a run. The
    model's provider is the operator's: e.g. OPENCODE_CONFIG in the host
    environment file names a provider file kept outside the project."""

    name = "opencode"
    ISOLATION = {
        "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
        "OPENCODE_DISABLE_CLAUDE_CODE_PROMPT": "1",
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
        "OPENCODE_DISABLE_SHARE": "1",
        "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1",
        "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
        "OPENCODE_PURE": "1",
    }

    def __init__(self, project_dir, env, model, timeout=900, exe=None):
        if not model:
            raise HostError("OpenCode 需要用 --model 指定模型（provider/model）")
        self.exe = exe or _which("opencode")
        self.project_dir = project_dir
        self.host_dir = os.path.join(project_dir, ".host")
        self.env = dict(env, **self.ISOLATION)
        self.env["XDG_CONFIG_HOME"] = os.path.join(self.host_dir, "config")
        self.env["OPENCODE_DB"] = os.path.join(self.host_dir, "opencode.db")
        # the host's scratch files (the runtime's input files among them) stay in
        # the project, so runs side by side never share one
        self.env["TEMP"] = self.env["TMP"] = os.path.join(self.host_dir, "tmp")
        self.model = model
        self.timeout = timeout
        self.sessions = {}

    def version(self):
        proc = subprocess.run([self.exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env, timeout=60)
        return proc.stdout.decode("utf-8", errors="replace").strip()

    def command(self, conversation, text):
        argv = [self.exe, "run", "--format", "json", "--dir", self.project_dir, "-m", self.model]
        if conversation in self.sessions:
            argv += ["--session", self.sessions[conversation]]
        return argv + [text]

    def send(self, conversation, text):
        argv = self.command(conversation, text)
        os.makedirs(self.env["TEMP"], exist_ok=True)
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


# -- Pi (pi -p --mode json) ---------------------------------------------------------------------------


def _pi_text(content):
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content or [] if isinstance(part, dict) and part.get("type") == "text")


def parse_pi_stream(events):
    """JSON events -> {session_id, model, text, host_calls, cost, error}. The
    completed messages (message_end) are the record: the assistant's text
    blocks are what the player saw, its tool calls pair with the tool
    results by id. The turn failed when its last assistant message stopped
    on an error, an abort or the output limit, or a retry finally failed; a
    message that ended in an error is not part of the reply (a retry that
    succeeded follows it)."""
    session_id = model = error = None
    texts = []
    calls = {}
    order = []
    cost = 0.0
    for event in events:
        kind = event.get("type")
        if kind == "session":
            session_id = event.get("id") or session_id
        elif kind == "message_end":
            message = event.get("message") or {}
            if message.get("role") == "assistant":
                if message.get("model"):
                    model = "%s/%s" % (message["provider"], message["model"]) if message.get("provider") else message["model"]
                cost += ((message.get("usage") or {}).get("cost") or {}).get("total") or 0
                stop = message.get("stopReason")
                if stop in ("error", "aborted", "length"):
                    error = "宿主报告这一轮出错（%s）：%s" % (stop, (message.get("errorMessage") or "")[:300])
                    continue
                error = None
                for block in message.get("content") or []:
                    if block.get("type") == "text" and block.get("text", "").strip():
                        texts.append(block["text"])
                    elif block.get("type") == "toolCall":
                        calls[block.get("id")] = {"tool": block.get("name"), "input": block.get("arguments"), "output": None}
                        order.append(block.get("id"))
            elif message.get("role") == "toolResult" and message.get("toolCallId") in calls:
                call = calls[message["toolCallId"]]
                call["output"] = _pi_text(message.get("content"))
                call["status"] = "error" if message.get("isError") else "completed"
        elif kind == "auto_retry_end" and not event.get("success"):
            error = "宿主重试后仍失败：%s" % (event.get("finalError") or "")[:300]
    return {"session_id": session_id, "model": model, "text": "\n\n".join(texts), "host_calls": [calls[i] for i in order], "cost": cost or None, "error": error}


def _pi_argv(exe):
    """Pi runs on Node. On Windows its npm command is a .cmd shim, which runs
    through cmd.exe and its quoting (a player's line with % or " in it would
    change on the way), so the package's own CLI script runs under node."""
    if exe.lower().endswith(".js"):
        return [_which("node"), exe]
    if os.path.splitext(exe)[1].lower() in (".cmd", ".bat", ".ps1"):
        package = os.path.join(os.path.dirname(exe), "node_modules", "@earendil-works", "pi-coding-agent")
        try:
            with open(os.path.join(package, "package.json"), encoding="utf-8") as handle:
                script = (json.load(handle).get("bin") or {}).get("pi")
        except (OSError, ValueError, AttributeError):
            script = None
        if not script:
            raise HostError("找不到 pi 的 CLI 脚本：%s（用 --host-exe 指向它的 cli.js）" % package)
        node = os.path.join(os.path.dirname(exe), "node.exe")
        return [node if os.path.exists(node) else _which("node"), os.path.join(package, script)]
    return [exe]


class Pi:
    """The host sees the installed Skill and the project, nothing of the
    operator's: its agent directory (settings, models, credentials, trust
    decisions, user skills, extensions, instructions) and its sessions are
    inside the project, so runs side by side share nothing. Only the
    installed Skill loads (--no-skills with --skill: the user-level
    ~/.agents/skills, which Pi reads whatever its agent directory, stays
    out); no extensions, prompt templates or themes; no startup network
    (update checks, model catalog) and no install telemetry. The model's
    provider is the operator's: AT_PI_MODELS in the host environment file
    names a models.json kept outside the project (its key read from the
    environment), and the agent directory gets a copy."""

    name = "pi"
    ISOLATION = {"PI_OFFLINE": "1", "PI_TELEMETRY": "0"}
    NO_DISCOVERY = ["--no-skills", "--no-extensions", "--no-prompt-templates", "--no-themes"]

    def __init__(self, project_dir, env, model, timeout=900, exe=None):
        if not model:
            raise HostError("pi 需要用 --model 指定模型（provider/model）")
        self.models = env.get("AT_PI_MODELS")
        if not self.models or not os.path.isfile(self.models):
            raise HostError("pi 需要模型配置：在宿主环境文件里用 AT_PI_MODELS 指向一个 models.json（%s）" % self.models)
        self.argv = _pi_argv(exe or _which("pi"))
        self.project_dir = project_dir
        self.host_dir = os.path.join(project_dir, ".host")
        self.agent_dir = os.path.join(self.host_dir, "pi-agent")
        self.sessions_dir = os.path.join(self.host_dir, "sessions")
        self.env = dict(env, **self.ISOLATION)
        self.env["PI_CODING_AGENT_DIR"] = self.agent_dir
        # the host's scratch files (the runtime's input files among them) stay in
        # the project, so runs side by side never share one
        self.env["TEMP"] = self.env["TMP"] = os.path.join(self.host_dir, "tmp")
        self.model = model
        self.timeout = timeout
        self.sessions = {}

    def version(self):
        proc = subprocess.run(self.argv + ["--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env, timeout=60)
        return proc.stdout.decode("utf-8", errors="replace").strip()

    def command(self, conversation, text):
        argv = self.argv + ["-p", "--mode", "json"] + self.NO_DISCOVERY
        argv += ["--skill", os.path.join(self.project_dir, SKILL_REL), "--session-dir", self.sessions_dir, "--model", self.model]
        if conversation in self.sessions:
            argv += ["--session", self.sessions[conversation]]
        # after "--" a line starting with "-" is still the player's words
        return argv + ["--", text]

    def send(self, conversation, text):
        for path in (self.agent_dir, self.sessions_dir, self.env["TEMP"]):
            os.makedirs(path, exist_ok=True)
        shutil.copyfile(self.models, os.path.join(self.agent_dir, "models.json"))
        argv = self.command(conversation, text)
        started = time.perf_counter()
        proc = subprocess.run(argv, cwd=self.project_dir, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=self.timeout)
        events = _events(proc.stdout)
        parsed = parse_pi_stream(events)
        if not parsed["session_id"]:
            raise HostError("宿主没有返回会话：exit %d，%s" % (proc.returncode, proc.stderr.decode("utf-8", errors="replace")[:500]), parsed["host_calls"])
        if proc.returncode and not parsed["error"]:
            parsed["error"] = "宿主退出码 %d：%s" % (proc.returncode, proc.stderr.decode("utf-8", errors="replace")[:300])
        self.sessions[conversation] = parsed["session_id"]
        parsed["model"] = parsed["model"] or self.model
        parsed["seconds"] = round(time.perf_counter() - started, 1)
        parsed["events"] = events
        return parsed


HOSTS = {"claude-code": ClaudeCode, "opencode": OpenCode, "pi": Pi}


def project_config(host_name, project_dir, python_names=("python", "python3", "py")):
    """Project-level settings only (no instructions): the host may run the
    runtime and write its temporary input files inside the project; the
    Skill is found in the project's .claude/skills; sessions are never shared.
    Claude Code and Pi take theirs on the command line instead
    (ClaudeCode.PERMISSIONS, Pi.command)."""
    if host_name != "opencode":
        return None
    settings = {
        "$schema": "https://opencode.ai/config.json",
        "permission": {"bash": {"*": "deny", **{"%s *" % n: "allow" for n in python_names}}, "edit": "allow", "webfetch": "deny"},
        "skills": {"paths": [".claude/skills"]},
        "share": "disabled",
        "autoupdate": False,
    }
    path = os.path.join(project_dir, "opencode.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(settings, ensure_ascii=False, indent=1) + "\n")
    return path
