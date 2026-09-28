"""Long-run simulation (ACCEPTANCE.md 9.4, 5; DELIVERY_PLAN stage 3).

    python tools/simulate.py [--turns 300] [--cold N] [--json] [--out PATH]

Turn numbers count the opening as turn 1, so "turn 300" is the state after
299 commits. Both routes play 10 turns past the last save/load.

Two runs (pressure and daily, different seeds), played in-process through the
real write path (application.service) with the deterministic fake narrator:

- The straight route plays N turns. Before every 7th turn an invalid commit
  is injected: it must be rejected and leave the state digest unchanged.
  Every 25th turn (at 12 mod 25) the turn is committed, undone and committed
  again: the random results (rolls, due events, propagation) must repeat.
  Every 30th turn (at 17 mod 30) the turn is replaced atomically with
  replaces_turn. Invariants and context sizes are checked after every turn.
- The save/load route plays the same sequence, but saves and loads at turns
  100, 200 and 300 (every load is a new session) and continues.
- Both routes must end with the same state digest.

It also reports the brief context size at turns 10/100/300, the session
snapshot size at turns 10/100/300, and the in-process commit P95 at turn 10
and at turn N: copies of the database taken at those turns are measured
side by side, one sample from each in turn (200 commit+undo cycles each), so
both see the same process, caches and machine load. With --cold N the same
two copies are also timed through the real entry script, one fresh process
per call (N samples each, alternating), like a host calls it.
Exit 1 when any gate fails.
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

_runtime.use_runtime()

import benchmark  # noqa: E402
from adult_tension.application import service  # noqa: E402
from adult_tension.application.context import Context  # noqa: E402
from adult_tension.application.fake_narrator import FakeNarrator  # noqa: E402
from adult_tension.domain import invariants  # noqa: E402
from adult_tension.domain import state as SS  # noqa: E402
from adult_tension.errors import AppError  # noqa: E402
from adult_tension.persistence import repo  # noqa: E402
from adult_tension.projections import context as CX  # noqa: E402

RUNS = (("pressure", 7301), ("daily", 7302))
SAVE_TURNS = (100, 200, 300)
PAST_LAST_LOAD = 10
INVALID_EVERY = 7
UNDO_AT = (25, 12)
REPLACE_AT = (30, 17)
LATENCY_SAMPLES = 200
REJECT_CODES = ("INVALID_INPUT", "INVARIANT_VIOLATION", "NOT_FOUND", "SAFETY_BLOCK")


def _ctx(data_dir):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION")}
    env["ADULT_TENSION_INCLUDE_DRAFTS"] = "1"  # the harbor world is still in review
    return Context(_runtime.SKILL_ROOT, data_dir, env, {}, False)


def _load(ctx, sid):
    info = repo.load_session(ctx.db(), sid)
    return info["state"], info["content"], info


def _randomness(result, state):
    """The random results of one commit, without ids that a redo reallocates."""
    rolls = [a["result"] for a in result["applied"] if a["op"] == "roll"]
    due = [(e["event_id"], e["outcome"]) for e in result["resolved_events"]]
    sim = result.get("simulation") or {}
    spread = [(state["facts"][s["fact_id"]]["key"], sorted(s["to"]), s["hop"]) for s in sim.get("spread", [])]
    moved = [(m["character_id"], m["location_id"]) for m in sim.get("moved", [])]
    return {"rolls": rolls, "due": due, "spread": spread, "moved": moved}


class Route:
    """One route of one run: a data directory, a current session and counters."""

    def __init__(self, name, data_dir, mode, seed):
        self.name = name
        self.ctx = _ctx(data_dir)
        self.narrator = FakeNarrator(seed)
        self.n = 0
        opened = service.new_game(self.ctx, {"request_id": self.rid("new"), "mode": mode, "seed": seed, "include_drafts": True})
        self.sid = opened["session_id"]
        self.stats = {
            "invalid_injected": 0,
            "invalid_rejected": 0,
            "invalid_state_changed": 0,
            "undo_redo_checks": 0,
            "undo_redo_mismatch": [],
            "replace_checks": 0,
            "replace_problems": [],
            "invariant_violations": [],
            "brief_max": 0,
            "full_max": 0,
            "saves": [],
        }
        self.sizes = {}

    def rid(self, tag):
        self.n += 1
        return "sim_%s_%s_%05d" % (self.name, tag, self.n)

    def write(self, func, payload, tag):
        info = repo.load_session(self.ctx.db(), self.sid, with_content=False)
        body = dict(payload, session_id=self.sid, request_id=self.rid(tag), expected_revision=info["revision"])
        return func(self.ctx, body)

    def inject_invalid(self, variant):
        state, content, _info = _load(self.ctx, self.sid)
        before = SS.digest(state), state["revision"]
        bad = self.narrator.invalid_commit(state, content, variant)
        self.stats["invalid_injected"] += 1
        try:
            self.write(service.commit_turn, bad, "bad")
        except AppError as err:
            if err.code in REJECT_CODES:
                self.stats["invalid_rejected"] += 1
        after_state, _c, _i = _load(self.ctx, self.sid)
        if (SS.digest(after_state), after_state["revision"]) != before:
            self.stats["invalid_state_changed"] += 1

    def play_turn(self):
        state, content, _info = _load(self.ctx, self.sid)
        turn = state["turn"] + 1
        if turn % INVALID_EVERY == 0:
            self.inject_invalid(turn // INVALID_EVERY)
            state, content, _info = _load(self.ctx, self.sid)
        commit = self.narrator.commit(state, content)
        first = self.write(service.commit_turn, commit, "turn")
        if turn % UNDO_AT[0] == UNDO_AT[1]:
            after_first = _load(self.ctx, self.sid)[0]
            undone = self.write(service.undo_turn, {}, "undo")
            back = _load(self.ctx, self.sid)[0]
            again = self.write(service.commit_turn, commit, "redo")
            after_again = _load(self.ctx, self.sid)[0]
            self.stats["undo_redo_checks"] += 1
            if undone["turn"] != turn - 1 or back["turn"] != turn - 1 or _randomness(first, after_first) != _randomness(again, after_again):
                self.stats["undo_redo_mismatch"].append(turn)
        elif turn % REPLACE_AT[0] == REPLACE_AT[1]:
            replacement = self.narrator.commit(state, content, force_kind="continue")
            replacement["replaces_turn"] = turn
            replaced = self.write(service.commit_turn, replacement, "replace")
            self.stats["replace_checks"] += 1
            log = repo.recent_turn_log(self.ctx.db(), self.sid, 2)
            if replaced["turn"] != turn or replaced["revision"] != first["revision"] + 1 or not log[1]["undone"]:
                self.stats["replace_problems"].append(turn)
        state, content, info = _load(self.ctx, self.sid)
        problems = invariants.check(state)
        if problems:
            self.stats["invariant_violations"].append({"turn": state["turn"], "problems": [p["reason"] for p in problems[:3]]})
        save = service.save_info(info)
        brief = CX.size_of(CX.brief(state, content, save))
        full = CX.size_of(CX.full(state, content, save))
        self.stats["brief_max"] = max(self.stats["brief_max"], brief)
        self.stats["full_max"] = max(self.stats["full_max"], full)
        if state["turn"] in (10, 100, 300) or state["turn"] == TURNS:
            blob = repo.hot(state)
            conn = self.ctx.db()
            facts, fact_bytes = conn.execute("SELECT COUNT(*), COALESCE(SUM(length(data)), 0) FROM facts WHERE session_id=?", (self.sid,)).fetchone()
            self.sizes[state["turn"]] = {
                "brief_context": brief,
                "full_context": full,
                "turn_blob_json": len(json.dumps(blob, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
                "turn_blob_packed": len(repo.pack(blob)),
                "facts": facts,
                "fact_rows_bytes": fact_bytes,
            }
        return state

    def save_and_load(self, turn):
        name = "sim-%s-%d" % (self.name, turn)
        self.write(service.save_slot, {"name": name}, "save")
        loaded = service.load_slot(self.ctx, {"request_id": self.rid("load"), "name": name})
        self.stats["saves"].append({"turn": turn, "slot": name, "old_session": self.sid, "new_session": loaded["session_id"]})
        self.sid = loaded["session_id"]

    def digest(self):
        return SS.digest(_load(self.ctx, self.sid)[0])


def _snapshot_db(ctx, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    target = sqlite3.connect(os.path.join(target_dir, "adult_tension.db"))
    try:
        ctx.db().backup(target)
    finally:
        target.close()


def _summary(samples):
    return {
        "samples": len(samples),
        "p50_ms": round(benchmark.percentile(samples, 50), 2),
        "p95_ms": round(benchmark.percentile(samples, 95), 2),
        "max_ms": round(max(samples), 2),
    }


class LatencyPoint:
    """A copy of the database at one point of the game, ready to time an
    ordinary turn's commit (commit, then undo, so every sample is the same).

    Every ~20 turns a commit also closes a chapter, and every few chapters
    merges the prologue. Those housekeeping commits are not ordinary turns:
    when one is due at this point, it is timed on its own (reported apart)
    and the copy plays on to the next ordinary turn.
    """

    def __init__(self, source_ctx, sid, workdir, label, seed):
        self.label = label
        self.sid = sid
        data_dir = os.path.join(workdir, "latency-%s" % label)
        _snapshot_db(source_ctx, data_dir)
        self.ctx = _ctx(data_dir)
        self.narrator = FakeNarrator(seed)
        self.n = 0
        state, content, _info = _load(self.ctx, sid)
        self.requested_turn = state["turn"]
        self.housekeeping = None
        while state["requests"].get("chapter_summary") or state["requests"].get("prologue"):
            commit = self.narrator.commit(state, content, force_kind="continue")
            if self.housekeeping is None:
                kind = "prologue" if state["requests"].get("prologue") else "chapter"
                samples = [self.sample(commit) for _ in range(LATENCY_SAMPLES // 4)]
                self.housekeeping = dict(_summary(samples), kind=kind, turn=state["turn"])
            self.write(commit)
            state, content, _info = _load(self.ctx, sid)
        self.turn = state["turn"]
        self.commit = self.narrator.commit(state, content, force_kind="continue")
        self.samples = []

    def write(self, commit):
        self.n += 1
        revision = repo.load_session(self.ctx.db(), self.sid, with_content=False)["revision"]
        payload = dict(commit, session_id=self.sid, request_id="lat_%s_%05d" % (self.label, self.n), expected_revision=revision)
        return service.commit_turn(self.ctx, payload)

    def sample(self, commit=None):
        self.n += 1
        revision = repo.load_session(self.ctx.db(), self.sid, with_content=False)["revision"]
        payload = dict(commit or self.commit, session_id=self.sid, request_id="lat_%s_%05d" % (self.label, self.n), expected_revision=revision)
        started = time.perf_counter()
        done = service.commit_turn(self.ctx, payload)
        elapsed = (time.perf_counter() - started) * 1000.0
        self.n += 1
        service.undo_turn(self.ctx, {"session_id": self.sid, "request_id": "lat_%s_%05d" % (self.label, self.n), "expected_revision": done["revision"]})
        return elapsed

    def cold_sample(self, workdir):
        """One commit through a fresh process (then an in-process undo)."""
        self.n += 1
        revision = repo.load_session(self.ctx.db(), self.sid, with_content=False)["revision"]
        payload = dict(self.commit, session_id=self.sid, request_id="cold_%s_%05d" % (self.label, self.n), expected_revision=revision)
        path = os.path.join(workdir, "cold-%s.json" % self.label)
        with open(path, "wb") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.ctx.close()  # let the child process own the database
        elapsed, envelope = benchmark.cold_call(["commit-turn"], self.ctx.data_dir, path, {"ADULT_TENSION_INCLUDE_DRAFTS": "1"})
        self.n += 1
        service.undo_turn(self.ctx, {"session_id": self.sid, "request_id": "cold_%s_%05d" % (self.label, self.n), "expected_revision": envelope["data"]["revision"]})
        return elapsed

    def report(self):
        out = dict(_summary(self.samples), turn=self.turn, requested_turn=self.requested_turn, operations=[op["op"] for op in self.commit["operations"]])
        if self.housekeeping is not None:
            out["housekeeping_commit"] = self.housekeeping
        return out


def measure_side_by_side(points, cold=0, workdir=None):
    for _ in range(LATENCY_SAMPLES):
        for point in points:
            point.samples.append(point.sample())
    cold_samples = {point.label: [] for point in points}
    for _ in range(cold):
        for point in points:
            cold_samples[point.label].append(point.cold_sample(workdir))
    reports = {}
    for point in points:
        report = point.report()
        if cold:
            report["cold_process"] = _summary(cold_samples[point.label])
        reports["turn_%d" % point.requested_turn] = report
        point.ctx.close()
    return reports


def run_one(mode, seed, turns, workdir, cold=0):
    straight = Route("%s_a" % mode, os.path.join(workdir, "%s-straight" % mode), mode, seed)
    split = Route("%s_b" % mode, os.path.join(workdir, "%s-split" % mode), mode, seed)
    points = []
    started = time.perf_counter()
    last = turns + PAST_LAST_LOAD
    state = _load(straight.ctx, straight.sid)[0]
    while state["turn"] < last:
        state = straight.play_turn()
        if state["turn"] in (10, turns):
            points.append(LatencyPoint(straight.ctx, straight.sid, workdir, "%s-%d" % (mode, state["turn"]), seed))
    state = _load(split.ctx, split.sid)[0]
    while state["turn"] < last:
        state = split.play_turn()
        if state["turn"] in SAVE_TURNS:
            split.save_and_load(state["turn"])
    elapsed = time.perf_counter() - started
    latency = measure_side_by_side(points, cold, workdir)
    final_state = _load(straight.ctx, straight.sid)[0]
    archive_rows = repo.count_rows(straight.ctx.db(), "archive", straight.sid)
    result = {
        "mode": mode,
        "seed": seed,
        "turns": final_state["turn"],
        "seconds": round(elapsed, 1),
        "digest_straight": straight.digest(),
        "digest_save_load": split.digest(),
        "straight": straight.stats,
        "save_load": split.stats,
        "sizes": straight.sizes,
        "chapters": final_state["counters"]["chapter_count"],
        "chapters_in_state": len(final_state["memory"]["chapters"]),
        "prologue": bool(final_state["memory"]["prologue"]),
        "facts": len(final_state["facts"]),
        "events_in_state": len(final_state["events"]),
        "archive_rows": archive_rows,
        "twists_accepted": len(final_state["counters"]["twists"]["accepted"]),
        "latency": latency,
    }
    straight.ctx.close()
    split.ctx.close()
    return result


def gates(run, turns):
    checks = []

    def gate(name, ok, value):
        checks.append({"gate": name, "pass": bool(ok), "value": value})

    for route in ("straight", "save_load"):
        stats = run[route]
        gate("%s: 零不变量违反" % route, not stats["invariant_violations"], stats["invariant_violations"][:3])
        gate("%s: 注入的非法提交全部被拒" % route, stats["invalid_injected"] > 0 and stats["invalid_rejected"] == stats["invalid_injected"], "%d/%d" % (stats["invalid_rejected"], stats["invalid_injected"]))
        gate("%s: 被拒后状态不变" % route, stats["invalid_state_changed"] == 0, stats["invalid_state_changed"])
        gate("%s: 撤销后重做随机结果相同" % route, stats["undo_redo_checks"] > 0 and not stats["undo_redo_mismatch"], {"checks": stats["undo_redo_checks"], "mismatch": stats["undo_redo_mismatch"]})
        gate("%s: 改写原子完成" % route, stats["replace_checks"] > 0 and not stats["replace_problems"], {"checks": stats["replace_checks"], "problems": stats["replace_problems"]})
        gate("%s: 简要上下文 ≤ 6 KB" % route, stats["brief_max"] <= CX.BRIEF_LIMIT, stats["brief_max"])
        gate("%s: 完整上下文 ≤ 20 KB" % route, stats["full_max"] <= CX.FULL_LIMIT, stats["full_max"])
    gate("第 100/200/300 回合存读档后续跑，状态摘要一致", run["digest_straight"] == run["digest_save_load"] and len(run["save_load"]["saves"]) == len([t for t in SAVE_TURNS if t <= turns]), {"straight": run["digest_straight"][:16], "save_load": run["digest_save_load"][:16]})
    sizes = run["sizes"]
    if 10 in sizes and turns in sizes:
        ratio = sizes[turns]["brief_context"] / float(sizes[10]["brief_context"])
        gate("第 %d 回合简要上下文 ≤ 第 10 回合的 1.5 倍" % turns, ratio <= 1.5, round(ratio, 3))
    lat = run["latency"]
    if "turn_10" in lat and "turn_%d" % turns in lat:
        ratio = lat["turn_%d" % turns]["p95_ms"] / lat["turn_10"]["p95_ms"]
        gate("第 %d 回合提交 P95 ≤ 第 10 回合的 1.5 倍（进程内）" % turns, ratio <= 1.5, round(ratio, 3))
        if "cold_process" in lat["turn_10"]:
            ratio = lat["turn_%d" % turns]["cold_process"]["p95_ms"] / lat["turn_10"]["cold_process"]["p95_ms"]
            gate("第 %d 回合提交 P95 ≤ 第 10 回合的 1.5 倍（冷进程）" % turns, ratio <= 1.5, round(ratio, 3))
    return checks


def main(argv):
    global TURNS
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--turns", type=int, default=300)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=None)
    parser.add_argument("--keep", action="store_true", help="keep the temporary data directories")
    parser.add_argument("--cold", type=int, default=0, help="cold-process samples per point (0: skip)")
    args = parser.parse_args(argv)
    TURNS = args.turns
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    workdir = tempfile.mkdtemp(prefix="at-simulate-")
    report = {"machine": benchmark.machine_info(), "turns": args.turns, "cold_samples": args.cold, "runs": []}
    try:
        for mode, seed in RUNS:
            run = run_one(mode, seed, args.turns, workdir, args.cold)
            run["gates"] = gates(run, args.turns)
            report["runs"].append(run)
    finally:
        if args.keep:
            report["workdir"] = workdir
        else:
            shutil.rmtree(workdir, ignore_errors=True)
    report["pass"] = all(g["pass"] for run in report["runs"] for g in run["gates"])
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text + "\n")
    if args.json:
        sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    else:
        for run in report["runs"]:
            print("%s seed %d: %d turns in %.1fs" % (run["mode"], run["seed"], run["turns"], run["seconds"]))
            for g in run["gates"]:
                print("  [%s] %s: %s" % ("OK" if g["pass"] else "FAIL", g["gate"], json.dumps(g["value"], ensure_ascii=False)))
        print("PASS" if report["pass"] else "FAIL")
    return 0 if report["pass"] else 1


TURNS = 300

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
