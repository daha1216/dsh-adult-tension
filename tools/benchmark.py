"""Performance measurement (ACCEPTANCE.md section 4).

    python tools/benchmark.py --json [--samples N] [--quick]

Cold-process numbers spawn a fresh interpreter per call, exactly like a host.
Every case reports sample count, P50, P95 and max; the run fails (exit 1)
when any P95 exceeds its threshold. Reports machine, OS and Python.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _runtime  # noqa: E402

COLD_SAMPLES = 50
INPROC_SAMPLES = 200

# name -> P95 threshold in milliseconds (ACCEPTANCE.md section 4)
COLD_THRESHOLDS = {
    "doctor_first": 1500,
    "doctor_again": 400,
    "version": 400,
    "new_game": 800,
    "commit_turn": 500,
    "get_context": 400,
}
INPROC_THRESHOLDS = {
    "opening": 300,
    "commit_turn": 80,
    "get_context": 30,
    "save_slot": 100,
    "load_slot": 100,
}


def percentile(values, pct):
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, int(-(-pct * len(ordered) // 100)))  # nearest-rank
    return ordered[rank - 1]


def summarize(samples_ms, threshold):
    p95 = percentile(samples_ms, 95)
    return {
        "samples": len(samples_ms),
        "p50_ms": round(percentile(samples_ms, 50), 2),
        "p95_ms": round(p95, 2),
        "max_ms": round(max(samples_ms), 2),
        "threshold_ms": threshold,
        "pass": threshold is None or p95 < threshold,
    }


def _winreg_value(path, name):
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            return str(winreg.QueryValueEx(key, name)[0]).strip()
    except OSError:
        return None


def _read_first(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return None


def machine_info():
    info = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "cpu_count": os.cpu_count(),
    }
    if sys.platform.startswith("win"):
        info["cpu"] = _winreg_value(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
        info["machine"] = " ".join(
            filter(None, [_winreg_value(r"HARDWARE\DESCRIPTION\System\BIOS", "SystemManufacturer"), _winreg_value(r"HARDWARE\DESCRIPTION\System\BIOS", "SystemProductName")])
        )
    else:
        cpu = None
        text = _read_first("/proc/cpuinfo") or ""
        for line in text.splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
        info["cpu"] = cpu or platform.processor()
        info["machine"] = _read_first("/sys/class/dmi/id/product_name")
    import sqlite3

    info["sqlite"] = sqlite3.sqlite_version
    return info


def cold_call(args, data_dir, payload_path=None, extra_env=None):
    argv = [sys.executable, _runtime.ENTRY_SCRIPT] + args + ["--json", "--data-dir", data_dir]
    if payload_path:
        argv += ["--input-file", payload_path]
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION") and k not in ("PYTHONPYCACHEPREFIX",)}
    env.update(extra_env or {})
    started = time.perf_counter()
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env)
    elapsed = (time.perf_counter() - started) * 1000.0
    envelope = json.loads(proc.stdout.decode("utf-8"))
    if proc.returncode != 0 or not envelope.get("ok"):
        raise RuntimeError("benchmark call failed: %s -> %s" % (args, proc.stdout[:400]))
    return elapsed, envelope


def _app(workdir, name):
    _runtime.use_runtime()
    from adult_tension.application.context import Context

    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION")}
    return Context(_runtime.SKILL_ROOT, os.path.join(workdir, name), env, {}, False)


def _timed(func, *args):
    started = time.perf_counter()
    result = func(*args)
    return (time.perf_counter() - started) * 1000.0, result


def bench_inprocess(samples, workdir):
    from adult_tension.application import service
    from adult_tension.application.fake_narrator import FakeNarrator
    from adult_tension.persistence import repo

    ctx = _app(workdir, "inproc")
    results = {}
    opening_times = []
    session_ids = []
    for index in range(samples):
        mode = "daily" if index % 2 else "pressure"
        elapsed, opened = _timed(service.new_game, ctx, {"request_id": "bench_new_%06d" % index, "mode": mode, "seed": index + 1, "include_drafts": True})
        opening_times.append(elapsed)
        session_ids.append(opened["session_id"])
    results["opening"] = summarize(opening_times, INPROC_THRESHOLDS["opening"])

    commit_times = []
    sid = session_ids[0]
    narrator = FakeNarrator(7)
    for index in range(samples):
        info = repo.load_session(ctx.db(), sid)
        commit = narrator.commit(info["state"], info["content"])
        payload = dict(commit, session_id=sid, request_id="bench_turn_%06d" % index, expected_revision=info["revision"])
        elapsed, _ = _timed(service.commit_turn, ctx, payload)
        commit_times.append(elapsed)
    results["commit_turn"] = summarize(commit_times, INPROC_THRESHOLDS["commit_turn"])

    context_times = [_timed(service.get_context, ctx, {"session_id": sid})[0] for _ in range(samples)]
    results["get_context"] = summarize(context_times, INPROC_THRESHOLDS["get_context"])

    save_times = []
    load_times = []
    for index in range(samples):
        info = repo.load_session(ctx.db(), sid)
        elapsed, _ = _timed(service.save_slot, ctx, {"session_id": sid, "request_id": "bench_save_%06d" % index, "expected_revision": info["revision"], "name": "bench-%d" % (index % 5), "overwrite": True})
        save_times.append(elapsed)
        elapsed, _ = _timed(service.load_slot, ctx, {"request_id": "bench_load_%06d" % index, "name": "bench-%d" % (index % 5)})
        load_times.append(elapsed)
    results["save_slot"] = summarize(save_times, INPROC_THRESHOLDS["save_slot"])
    results["load_slot"] = summarize(load_times, INPROC_THRESHOLDS["load_slot"])
    results["_state"] = {"turns_played": samples, "state_bytes_turn_%d" % (samples + 1): len(repo.pack(repo.load_session(ctx.db(), sid)["state"]))}
    ctx.close()
    return results


def _payload_file(workdir, payload):
    path = os.path.join(workdir, "payload-%d.json" % os.getpid())
    with open(path, "wb") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return path


def bench_cold_game(samples, workdir):
    _runtime.use_runtime()
    from adult_tension.application.fake_narrator import FakeNarrator
    from adult_tension.persistence import repo

    data_dir = os.path.join(workdir, "cold-game")
    cold_call(["doctor"], data_dir)
    extra_env = {"ADULT_TENSION_INCLUDE_DRAFTS": "1"}
    new_game = []
    session_id = None
    for index in range(samples):
        path = _payload_file(workdir, {"request_id": "cold_new_%06d" % index, "mode": "pressure" if index % 2 else "daily", "seed": 1000 + index})
        elapsed, envelope = cold_call(["new-game"], data_dir, path, extra_env)
        new_game.append(elapsed)
        session_id = session_id or envelope["data"]["session_id"]
    results = {"new_game": summarize(new_game, COLD_THRESHOLDS["new_game"])}
    ctx = _app(workdir, "cold-game")
    narrator = FakeNarrator(11)
    commits = []
    for index in range(samples):
        info = repo.load_session(ctx.db(), session_id)
        commit = narrator.commit(info["state"], info["content"])
        path = _payload_file(workdir, dict(commit, session_id=session_id, request_id="cold_turn_%06d" % index, expected_revision=info["revision"]))
        ctx.close()
        elapsed, _ = cold_call(["commit-turn"], data_dir, path, extra_env)
        commits.append(elapsed)
    results["commit_turn"] = summarize(commits, COLD_THRESHOLDS["commit_turn"])
    path = _payload_file(workdir, {"session_id": session_id})
    contexts = [cold_call(["get-context"], data_dir, path, extra_env)[0] for _ in range(samples)]
    results["get_context"] = summarize(contexts, COLD_THRESHOLDS["get_context"])
    ctx.close()
    return results


def bench_cold(samples, workdir):
    results = {}
    first = []
    for index in range(samples):
        data_dir = os.path.join(workdir, "first-%d" % index)
        elapsed, _env = cold_call(["doctor"], data_dir)
        first.append(elapsed)
        shutil.rmtree(data_dir, ignore_errors=True)
    results["doctor_first"] = summarize(first, COLD_THRESHOLDS["doctor_first"])

    shared = os.path.join(workdir, "shared")
    cold_call(["doctor"], shared)
    again = [cold_call(["doctor"], shared)[0] for _ in range(samples)]
    results["doctor_again"] = summarize(again, COLD_THRESHOLDS["doctor_again"])
    version = [cold_call(["version"], shared)[0] for _ in range(samples)]
    results["version"] = summarize(version, COLD_THRESHOLDS["version"])
    return results


def main(argv):
    samples = COLD_SAMPLES
    if "--samples" in argv:
        samples = int(argv[argv.index("--samples") + 1])
    if "--quick" in argv:
        samples = 10
    inproc_samples = INPROC_SAMPLES if "--quick" not in argv else 20
    workdir = tempfile.mkdtemp(prefix="at-bench-")
    try:
        cold = bench_cold(samples, workdir)
        cold.update(bench_cold_game(samples, workdir))
        inprocess = bench_inprocess(inproc_samples, workdir)
        extra = inprocess.pop("_state")
        report = {"machine": machine_info(), "cold": cold, "inprocess": inprocess, "notes": extra}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    failures = [
        "%s.%s" % (group, name)
        for group in ("cold", "inprocess")
        for name, item in report[group].items()
        if isinstance(item, dict) and item.get("pass") is False
    ]
    report["ok"] = not failures
    report["failures"] = failures
    if "--json" in argv:
        sys.stdout.buffer.write(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    else:
        for group in ("cold", "inprocess"):
            for name, item in report[group].items():
                print("%-9s %-24s n=%-4s p50=%8.1fms p95=%8.1fms max=%8.1fms limit=%s %s" % (group, name, item["samples"], item["p50_ms"], item["p95_ms"], item["max_ms"], item["threshold_ms"], "ok" if item["pass"] else "FAIL"))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
