"""Run one end-to-end script on one host and write its record.

    python tests/e2e/harness/run_script.py --host claude-code|opencode|fake
        --script 01 [--run 1] [--model provider/model]
        [--root D:\\projects\\at-e2e] [--out reports/e2e/records]

Each run gets a fresh test project outside this repository (default
D:\\projects\\at-e2e\\<host>-s<script>-r<run>-<time>\\), with the Skill
installed at project level (.claude/skills/adult-tension/), its own data
directory and the engine trace switched on. The host receives the player's
words and nothing else. After the last step the final state is exported
through the runtime (outside the trace) and kept in the record.

--host fake plays the script without a model (a minimal scripted player of
the engine) to test this harness; its records are never evaluation data.

A script whose setup says "install": "previous" starts from an older Skill
(--previous <git commit>) and is upgraded in place at its upgrade step. A
Skill older than the engine trace has its calls rebuilt from the host's own
tool calls (record.calls_from_host); each turn says where its calls came from.
"data_dir": "default" leaves ADULT_TENSION_HOME unset (the release drill of
SKILL_PACKAGING.md 9: no environment settings by the user; run it on a clean
machine), and "include_drafts": false plays only released worlds.
"{seed:N}" in a player line is the seed the opening of player turn N showed
(the player reads it from the footer), e.g. for "重开 N 号".
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
E2E = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(E2E))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))

import hosts as H  # noqa: E402
import machine_checks  # noqa: E402
import record as R  # noqa: E402

SCRIPTS = os.path.join(E2E, "scripts")
DRILLS = os.path.join(E2E, "drills")
DEFAULT_ROOT = os.path.join("D:" + os.sep, "projects", "at-e2e")
SKILL_REL = os.path.join(".claude", "skills", "adult-tension")


def load_script(name):
    if os.path.isfile(name):
        path = name
    else:
        matches = sorted(glob.glob(os.path.join(SCRIPTS, "%s-*.json" % name)))
        if len(matches) != 1:
            raise SystemExit("找不到剧本 %s" % name)
        path = matches[0]
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _safe_root(root, host_name):
    """Never inside this repository; a real host never under the user's home
    either (it is an unrelated Git repository; ENVIRONMENT.md). The fake host
    may use the system temp directory, as automated tests do."""
    root = os.path.abspath(root)
    home = os.path.abspath(os.path.expanduser("~"))
    if root.startswith(os.path.abspath(REPO)):
        raise SystemExit("测试项目不能放在本仓库里：%s" % root)
    if root.startswith(home) and host_name != "fake":
        raise SystemExit("真实宿主的测试项目不能放在用户主目录里：%s（ENVIRONMENT.md）" % root)
    return root


# ACCEPTANCE 6.1 item 1: no same-name Skill may be left where the host would
# also find it. Only existence is checked; nothing there is opened.
USER_SKILL_DIRS = {
    "claude-code": [os.path.join("~", ".claude", "skills")],
    "opencode": [os.path.join("~", ".config", "opencode", "skills"), os.path.join("~", ".agents", "skills"), os.path.join("~", ".claude", "skills")],
}
SKILL_NAMES = ("adult-tension", "dsh-adult-tension")


def preflight(host_name):
    checked, found = [], []
    for base in USER_SKILL_DIRS.get(host_name, []):
        for name in SKILL_NAMES:
            path = os.path.join(os.path.expanduser(base), name)
            checked.append(path)
            if os.path.exists(path):
                found.append(path)
    return {"checked": checked, "found": found}


def install_skill(project, commit=None, replace=False):
    import install_skill as I

    source = os.path.join(REPO, "skill", "adult-tension")
    temp = None
    try:
        if commit:
            temp = tempfile.mkdtemp(prefix="at-skill-")
            archive = os.path.join(temp, "skill.tar")
            subprocess.run(["git", "-C", REPO, "archive", "-o", archive, commit, "skill/adult-tension"], check=True)
            with tarfile.open(archive) as tar:
                try:
                    tar.extractall(temp, filter="data")
                except TypeError:
                    tar.extractall(temp)
            source = os.path.join(temp, "skill", "adult-tension")
        I.install(source, os.path.join(project, SKILL_REL), replace=replace)
    finally:
        if temp:
            shutil.rmtree(temp)
    return source if not commit else "git:%s" % commit


def skill_files(project):
    """What the installed Skill is, read from its files without running it
    (running doctor here would do the first initialization in the host's place)."""
    package = os.path.join(project, SKILL_REL, "runtime", "adult_tension")
    with open(os.path.join(package, "__init__.py"), encoding="utf-8") as handle:
        init = handle.read()
    with open(os.path.join(package, "adapters", "cli.py"), encoding="utf-8") as handle:
        traced = "ADULT_TENSION_TRACE" in handle.read()
    version = re.search(r"^SKILL_VERSION = \"([^\"]+)\"", init, re.M)
    schema = re.search(r"^DB_SCHEMA_VERSION = (\d+)", init, re.M)
    return {"skill_version": version and version.group(1), "db_schema": schema and int(schema.group(1)), "trace": traced}


def host_env(setup, project, base):
    """The host's environment: the engine trace always; a data directory in the
    project and the draft switch unless the script says otherwise."""
    env = dict(base, ADULT_TENSION_TRACE=os.path.join(project, "trace.jsonl"))
    env.pop("ADULT_TENSION_HOME", None)
    env.pop("ADULT_TENSION_INCLUDE_DRAFTS", None)
    if setup.get("data_dir") != "default":
        env["ADULT_TENSION_HOME"] = os.path.join(project, ".at-data")
    if setup.get("include_drafts", True):
        env["ADULT_TENSION_INCLUDE_DRAFTS"] = "1"
    return env


def runtime(project, env, args, payload=None):
    """Call the installed runtime directly (outside the trace): identity and export only."""
    clean = {k: v for k, v in env.items() if k != "ADULT_TENSION_TRACE"}
    argv = [sys.executable, os.path.join(project, SKILL_REL, "scripts", "adult_tension.py")] + args + ["--json"]
    temp = None
    if payload is not None:
        handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False)
        handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        handle.close()
        temp = handle.name
        argv += ["--input-file", temp]
    try:
        proc = subprocess.run(argv, env=clean, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=120)
    finally:
        if temp:
            os.remove(temp)
    return json.loads(proc.stdout.decode("utf-8"))


def trace_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class FakeHost:
    """Plays the engine without a model, to test the harness plumbing.

    It opens a game at the first message of a conversation (or loads one for
    "读档 <名>"), saves for "存档 <名>" and commits a plain turn for anything
    else. It reports its tool calls the way a real host does (Write the input
    file, then Bash), so the fallback for a Skill without the engine trace is
    tested too."""

    name = "fake"
    SAVE_RE = re.compile(r"^存档\s*(\S+)$")
    LOAD_RE = re.compile(r"^读档\s*(\S+)$")

    def __init__(self, project, env):
        self.project = project
        self.env = env
        self.model = "none"
        self.sessions = {}

    def version(self):
        return "fake-1"

    def _call(self, log, args, payload=None):
        argv = [sys.executable, os.path.join(self.project, SKILL_REL, "scripts", "adult_tension.py")] + args + ["--json"]
        path = None
        if payload is not None:
            text = json.dumps(payload, ensure_ascii=False)
            handle = tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False, dir=self.project)
            handle.write(text.encode("utf-8"))
            handle.close()
            path = handle.name
            argv += ["--input-file", path]
            log.append({"tool": "Write", "input": {"file_path": path, "content": text}, "output": "File created successfully"})
        try:
            proc = subprocess.run(argv, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=120)
        finally:
            if path:
                os.remove(path)
        stdout = proc.stdout.decode("utf-8")
        command = " ".join('"%s"' % a if re.search(r"[\s\\]", a) else a for a in argv)
        log.append({"tool": "Bash", "input": {"command": command}, "output": stdout})
        out = json.loads(stdout)
        if not out["ok"]:
            raise H.HostError("fake host: %s refused: %s" % (args[0], out["error"]["message"]), log)
        return out["data"]

    def _reply(self, started, state, log, text):
        return {"session_id": state["sid"], "model": self.model, "text": text, "host_calls": log, "cost": None, "seconds": round(time.perf_counter() - started, 1), "events": []}

    @staticmethod
    def _footer(data):
        ctx = data["context"]
        return "【时间】%s｜【地点】%s｜回合：%d" % (ctx["clock"]["label"], ctx["scene"]["location"], data["turn"])

    def send(self, conversation, text):
        started = time.perf_counter()
        log = []
        state = self.sessions.get(conversation)
        load = self.LOAD_RE.match(text.strip())
        save = self.SAVE_RE.match(text.strip())
        if state is None:
            self._call(log, ["doctor"])
            if load:
                data = self._call(log, ["load-slot"], {"request_id": "fake_load_%s" % conversation, "name": load.group(1)})
                body = "%s\n\n%s" % (data["receipt"], self._footer(data))
            else:
                data = self._call(log, ["new-game"], {"request_id": "fake_new_%s" % conversation, "mode": "daily", "seed": 7})
                opening = data["opening"]
                body = "世界观：%s\n人物：%s\n\n%s\n\n%s" % (opening["world"]["premise"], opening["player"]["name"], opening["hook"]["text"], opening["footer"])
            state = {"sid": data["session_id"], "revision": data["revision"], "next": data["next_request_id"], "context": data["context"]}
            self.sessions[conversation] = state
            return self._reply(started, state, log, body)
        if save:
            data = self._call(log, ["save-slot"], {"request_id": state["next"], "session_id": state["sid"], "expected_revision": state["revision"], "name": save.group(1)})
            state.update(revision=data["revision"], next=data["next_request_id"])
            return self._reply(started, state, log, data["receipt"])
        present = [n["id"] for n in state["context"].get("present_npcs") or []]
        ops = [{"op": "npc_action", "npc_id": present[0], "action": "看了一眼门口"}] if present else []
        commit = {
            "request_id": state["next"], "session_id": state["sid"], "expected_revision": state["revision"],
            "action_mode": "continue", "player_input": text, "operations": ops, "content_tags": [],
            "summary": "场面往前走了一点", "open_action": "场面停住",
        }
        data = self._call(log, ["commit-turn"], commit)
        state.update(revision=data["revision"], next=data["next_request_id"], context=data["context"])
        return self._reply(started, state, log, "门口有人影晃了一下。\n\n" + self._footer(data))


def fill_placeholders(text, turns):
    """{seed:N}: the seed of the opening made in player turn N."""

    def seed(match):
        index = int(match.group(1))
        for turn in turns:
            if turn["index"] == index:
                for call in turn["runtime_calls"]:
                    data = R.ok_data(call) or {}
                    if R.command_of(call) == "new-game" and "seed" in data:
                        return str(data["seed"])
        return "?"

    return re.sub(r"\{seed:(\d+)\}", seed, text)


def make_host(name, project, env, model):
    if name == "fake":
        return FakeHost(project, env)
    return H.HOSTS[name](project, env, model) if name == "opencode" else H.HOSTS[name](project, env, model=model)


def run(script, host_name, run_index, model, root, out_dir, keep_events=False, previous=None):
    root = _safe_root(root, host_name)
    checks = preflight(host_name)
    if checks["found"]:
        raise SystemExit("宿主的用户级 Skill 目录里有同名 Skill，评测会混进旧版：%s。请先处理（不要让我打开或删除它们）。" % "、".join(checks["found"]))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    project = os.path.join(root, "%s-s%s-r%d-%s" % (host_name, script["id"], run_index, stamp))
    os.makedirs(project)
    subprocess.run(["git", "init", "-q", project], check=True)
    setup = script.get("setup") or {}
    if setup.get("install") == "previous" and not previous:
        raise SystemExit("剧本 %s 从旧版 Skill 开始：请用 --previous <git commit> 指定旧版" % script["id"])
    installed = install_skill(project, previous if setup.get("install") == "previous" else None)
    installs = [dict(skill_files(project), after_turn=0, source=installed)]
    if host_name != "fake":
        H.project_config(host_name, project)
    env = host_env(setup, project, os.environ)
    trace = env["ADULT_TENSION_TRACE"]
    host = make_host(host_name, project, env, model)
    rec = {
        "format": R.FORMAT,
        "version": R.VERSION,
        "script": script["id"],
        "run": run_index,
        "date": datetime.date.today().isoformat(),
        "host": {"name": host_name, "version": host.version(), "model": model or getattr(host, "model", None)},
        "project": project,
        "installed_from": installed,
        "installs": installs,
        "preflight": checks,
        "setup": {"data_dir": env.get("ADULT_TENSION_HOME", "default"), "include_drafts": "ADULT_TENSION_INCLUDE_DRAFTS" in env},
        "turns": [],
        "harness_events": [],
    }
    index = 0
    for step in script["steps"]:
        if "harness" in step:
            if step["harness"] == "upgrade_skill":
                source = install_skill(project, None, replace=True)
                installs.append(dict(skill_files(project), after_turn=index, source=source))
                rec["harness_events"].append({"after_turn": index, "event": "upgrade_skill", "detail": "替换为当前版本的 Skill 目录"})
            continue
        index += 1
        before = len(trace_lines(trace))
        conversation = step.get("conversation", "A")
        say = fill_placeholders(step["say"], rec["turns"])
        try:
            reply = host.send(conversation, say)
            error = reply.get("error")
        except (H.HostError, subprocess.TimeoutExpired) as err:
            reply, error = {"text": "", "host_calls": getattr(err, "host_calls", []), "seconds": None, "model": None}, str(err)
        if installs[-1]["trace"]:
            calls, source = trace_lines(trace)[before:], "trace"
        else:
            calls, source = R.calls_from_host(reply["host_calls"]), "host"
        turn = {
            "index": index,
            "conversation": conversation,
            "input": say,
            "expect": step.get("expect") or {},
            "host_calls": reply["host_calls"],
            "runtime_calls": calls,
            "calls_source": source,
            "text": reply["text"],
            "seconds": reply.get("seconds"),
        }
        if error:
            turn["host_error"] = error
        if keep_events:
            turn["events"] = reply.get("events")
        if reply.get("model") and not rec["host"].get("model"):
            rec["host"]["model"] = reply["model"]
        rec["turns"].append(turn)
    # The Skill the host ran last: its own doctor after the last install, else ask the runtime.
    last = installs[-1]["after_turn"]
    doctor = next((c for t in rec["turns"] if t["index"] > last for c in t["runtime_calls"] if R.command_of(c) == "doctor" and R.ok_data(c)), None)
    identity = R.ok_data(doctor) if doctor else (runtime(project, env, ["doctor"]).get("data") or {})
    rec["skill"] = {k: identity.get(k) for k in ("skill_root", "skill_version", "content_version")}
    sessions = (runtime(project, env, ["list-sessions"]).get("data") or {}).get("sessions") or []
    if sessions:
        exported = runtime(project, env, ["export-save"], {"session_id": sessions[0]["session_id"]})
        if exported.get("ok"):
            with open(exported["data"]["path"], encoding="utf-8") as handle:
                rec["final_export"] = json.load(handle)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s-s%s-r%d.json" % (host_name, script["id"], run_index))
    R.save(rec, path)
    return path, rec


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", required=True, choices=("claude-code", "opencode", "fake"))
    parser.add_argument("--script", required=True)
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("--model")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--out", default=os.path.join(REPO, "reports", "e2e", "records"))
    parser.add_argument("--keep-events", action="store_true")
    parser.add_argument("--previous", help="旧版 Skill 的 git 提交（剧本 16）")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    script = load_script(args.script)
    path, rec = run(script, args.host, args.run, args.model, args.root, os.path.join(args.out, args.host), args.keep_events, args.previous)
    result = machine_checks.check(rec)
    print("record: %s" % path)
    for line in machine_checks.summary_lines(result):
        print(line)
    print("machine checks: %s" % ("PASS" if result["pass"] else "FAIL"))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
