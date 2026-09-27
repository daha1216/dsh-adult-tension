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

# name -> P95 threshold in milliseconds
COLD_THRESHOLDS = {
    "doctor_first": 1500,
    "doctor_again": 400,
    "version": 400,
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


def cold_call(args, data_dir, payload_path=None):
    argv = [sys.executable, _runtime.ENTRY_SCRIPT] + args + ["--json", "--data-dir", data_dir]
    if payload_path:
        argv += ["--input-file", payload_path]
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADULT_TENSION") and k not in ("PYTHONPYCACHEPREFIX",)}
    started = time.perf_counter()
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env)
    elapsed = (time.perf_counter() - started) * 1000.0
    envelope = json.loads(proc.stdout.decode("utf-8"))
    if proc.returncode != 0 or not envelope.get("ok"):
        raise RuntimeError("benchmark call failed: %s -> %s" % (args, proc.stdout[:400]))
    return elapsed, envelope


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
    workdir = tempfile.mkdtemp(prefix="at-bench-")
    try:
        report = {"machine": machine_info(), "cold": bench_cold(samples, workdir), "inprocess": {}}
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
