"""Run end-to-end scripts in a few lanes until each has a counted run of the
candidate, making up the runs the endpoint broke.

    python tests/e2e/harness/batch.py --host pi --model <provider/model> --host-env-file <env>
        --scripts 16 01 02 ... [--lanes 2] [--previous 2aa58c8] [--host-exe <path>]
        [--root D:\\projects\\at-e2e] [--out reports/e2e/records] [--candidate <digest>] [--log <file>]

A script is done when a run of the candidate (report.candidate_digest(), or
--candidate) of the script as it is now has a record that counts: one not
made up (report.made_up). Done scripts are skipped, so a batch that stopped
can be started again. Each script runs in one lane at a time, in the order
given (the long one first), with the next free run number; a run made up by
the user's decision (PROGRESS P10: a failed run with a turn where the
endpoint gave no whole reply) is followed at once by another run of the same
script, whatever that one ends in.

A counted run that failed its machine checks means the candidate cannot pass
(ACCEPTANCE 6.4): no new run starts after it, and the ones under way finish
(the user's word, 2026-09-29: stop a batch once its candidate cannot pass;
fix everything at once). So does a run that left no record, and a file STOP
in the records directory. Each run is run_script.py in a process of its own;
what it prints goes to the log (a temporary file unless --log names one).
Exit 0 when every script has a counted run and all of them passed.
"""

import argparse
import datetime
import glob
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import machine_checks  # noqa: E402
import record as R  # noqa: E402
import report  # noqa: E402
import run_script  # noqa: E402

RUN_SCRIPT = os.path.join(HERE, "run_script.py")


def runs_of(out_dir, host, script):
    """{run number: record path} of SCRIPT on HOST."""
    prefix = run_script.run_tag(script, host, 1)[:-1]
    found = {}
    for path in glob.glob(os.path.join(out_dir, host, prefix + "*.json")):
        match = re.match(re.escape(prefix) + r"(\d+)\.json$", os.path.basename(path))
        if match:
            found[int(match.group(1))] = path
    return found


def standing(out_dir, host, script, candidate):
    """Where SCRIPT stands: its counted runs of the candidate ({run, pass}),
    the ones made up, and the next free run number."""
    runs = runs_of(out_dir, host, script)
    counted, made_up = [], []
    for n in sorted(runs):
        rec = R.load(runs[n])
        if (rec.get("installs") or [{}])[-1].get("digest") != candidate or not report.ran_script(rec, script):
            continue
        checks = machine_checks.check(rec)
        if report.made_up(rec, checks):
            made_up.append(n)
        else:
            counted.append({"run": n, "pass": checks["pass"]})
    return {"counted": counted, "made_up": made_up, "next_run": max(runs, default=0) + 1}


class Batch:
    def __init__(self, args, passthrough):
        self.args = args
        self.passthrough = passthrough
        self.candidate = args.candidate or report.candidate_digest()
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.todo = []
        self.results = {}  # script name -> (what happened, whether it has a counted run and all its counted runs passed)
        self.log_path = args.log or os.path.join(tempfile.gettempdir(), "at-batch-%s.log" % time.strftime("%Y%m%d-%H%M%S"))

    def say(self, text):
        line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), text)
        with self.lock:
            print(line, flush=True)
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def halt(self, why):
        if not self.stop.is_set():
            self.stop.set()
            self.say("停止新开：%s" % why)

    def stopped(self):
        if os.path.exists(os.path.join(self.args.out, "STOP")):
            self.halt("记录目录里有 STOP 文件")
        return self.stop.is_set()

    def run_one(self, name, script, run, lane):
        argv = [sys.executable, RUN_SCRIPT, "--host", self.args.host, "--script", name, "--run", str(run), "--out", self.args.out] + self.passthrough
        self.say("第 %d 路：开始 %s" % (lane, run_script.run_tag(script, self.args.host, run)))
        started = time.perf_counter()
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        output = proc.stdout.decode("utf-8", errors="replace")
        with self.lock:
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write("---- %s（exit %d）\n%s\n" % (" ".join(argv[1:]), proc.returncode, output))
        return proc.returncode, round((time.perf_counter() - started) / 60, 1)

    def lane(self, lane):
        while not self.stopped():
            with self.lock:
                if not self.todo:
                    return
                name, script = self.todo.pop(0)
            # one script stays in its lane until it has a counted run
            while not self.stopped():
                run = standing(self.args.out, self.args.host, script, self.candidate)["next_run"]
                code, minutes = self.run_one(name, script, run, lane)
                tag = run_script.run_tag(script, self.args.host, run)
                if run not in runs_of(self.args.out, self.args.host, script):
                    self.results[name] = ("%s 没有留下记录（exit %d）" % (tag, code), False)
                    self.halt("%s 没有留下记录（exit %d），见日志" % (tag, code))
                    return
                now = standing(self.args.out, self.args.host, script, self.candidate)
                if run in now["made_up"]:
                    self.say("第 %d 路：%s 不合格，有一轮接口没有给出完整的回复，按用户的决定补跑（%.1f 分钟）" % (lane, tag, minutes))
                    continue
                counted = [c for c in now["counted"] if c["run"] == run]
                if not counted:
                    self.results[name] = ("%s 不是这个候选版本或现在的剧本" % tag, False)
                    self.halt(self.results[name][0])
                    return
                passed = counted[0]["pass"]
                self.results[name] = ("%s %s" % (tag, "通过" if passed else "失败"), passed)
                self.say("第 %d 路：%s 机器检查%s（%.1f 分钟）" % (lane, tag, "通过" if passed else "失败，计入", minutes))
                if not passed:
                    self.halt("%s 是计入的失败，候选版本过不了" % tag)
                break

    def run(self, names):
        self.say("候选版本 %s；日志 %s" % (self.candidate, self.log_path))
        for name in names:
            script = run_script.load_script(name)
            now = standing(self.args.out, self.args.host, script, self.candidate)
            if now["counted"]:
                passed = all(c["pass"] for c in now["counted"])
                self.results[name] = ("已有计入的运行：%s" % "、".join("r%d%s" % (c["run"], "" if c["pass"] else " 失败") for c in now["counted"]), passed)
                self.say("跳过 %s：%s" % (name, self.results[name][0]))
                if not passed:
                    self.halt("剧本 %s 已有计入的失败" % name)
            else:
                self.todo.append((name, script))
        lanes = [threading.Thread(target=self.lane, args=(n,)) for n in range(1, self.args.lanes + 1)]
        for thread in lanes:
            thread.start()
        for thread in lanes:
            thread.join()
        for name in names:
            self.say("%s：%s" % (name, self.results.get(name, ("没有跑", False))[0]))
        return 0 if all(self.results.get(name, ("", False))[1] for name in names) else 1


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", required=True, choices=("claude-code", "opencode", "pi", "fake"))
    parser.add_argument("--scripts", nargs="+", required=True)
    parser.add_argument("--lanes", type=int, default=2)
    parser.add_argument("--out", default=os.path.join(run_script.REPO, "reports", "e2e", "records"))
    parser.add_argument("--candidate")
    parser.add_argument("--log")
    args, passthrough = parser.parse_known_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    return Batch(args, passthrough).run(args.scripts)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
