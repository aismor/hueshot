#!/usr/bin/env python3
"""Run and compare staged Hueshot changes without mixing their caches or environments.

The stage plan is JSON. Each stage can run focused/changed/full game-free tests, build
commands, and repeated benchmark variants. Results and commands stay under work/.

    python -I scripts/staged_run.py run plan.json [--stage NAME]
    python -I scripts/staged_run.py compare BEFORE.log AFTER.log --out work/result
    python -I scripts/staged_run.py report work/staged-runs/RUN

Commands in a plan are argv arrays, never shell strings. The substitutions {root},
{artifacts}, {stage}, {variant}, {run}, and {log} are available in arguments and env.
"""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS = ROOT / "work" / "staged-runs"
ENV_PREFIXES = ("HOS_", "RX_", "OOT_")
FATAL = re.compile(r"FATAL:|device lost|VK_ERROR|validation error|segmentation fault|access violation", re.I)
PRESENT = re.compile(r"vk: \d+ presents, ([\d.]+) fps; a frame: (\d+) draws")
GPU = re.compile(r"vk: GPU time ([\d.]+) ms a frame")
VRAM = re.compile(r"vk: VRAM: (\d+) MB used of (\d+) MB allowed")
REPLAY = re.compile(r"([a-z][a-z ]*?) ([\d.]+)")


def percentile(values, pct):
    """Nearest-rank percentile, stable across Python versions."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, (len(ordered) * pct + 99) // 100)
    return ordered[min(len(ordered), rank) - 1]


def median(values):
    return round(statistics.median(values), 3) if values else None


def parse_frame_csv(path):
    values = []
    if not path or not Path(path).is_file():
        return {}
    with open(path, newline="", encoding="utf-8", errors="replace") as src:
        for row in csv.reader(src):
            try:
                value = float(row[-1])
            except (ValueError, IndexError):
                continue
            if value >= 0:
                values.append(value)
    return {
        "frames": len(values), "frame_ms": median(values),
        "frame_p95_ms": percentile(values, 95), "frame_p99_ms": percentile(values, 99),
        "frame_worst_ms": max(values) if values else None,
        "frames_over_33": sum(v > 33.333 for v in values),
        "frames_over_50": sum(v > 50 for v in values),
        "frames_over_100": sum(v > 100 for v in values),
        "frames_over_250": sum(v > 250 for v in values),
    }


def parse_log(path):
    fps, draws, gpu, vram = [], [], [], []
    replay = {}
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if match := PRESENT.search(line):
            fps.append(float(match[1]))
            draws.append(int(match[2]))
        elif match := GPU.search(line):
            gpu.append(float(match[1]))
        elif "replay time (ms):" in line:
            for name, value in REPLAY.findall(line.split("replay time (ms):", 1)[1]):
                replay.setdefault(name.strip().replace(" ", "_"), []).append(float(value))
        elif match := VRAM.search(line):
            vram.append((int(match[1]), int(match[2])))
    return {
        "reports": len(fps), "fps": median(fps), "fps_min": min(fps) if fps else None,
        "draws": median(draws), "gpu_ms": median(gpu),
        "replay_ms": {name: median(values) for name, values in sorted(replay.items())},
        "vram_used_mb": max((used for used, _ in vram), default=None),
        "vram_allowed_mb": vram[-1][1] if vram else None,
        "fatal_lines": [line for line in text.splitlines() if FATAL.search(line)],
    }


def parse_summary(path):
    """Flatten hueshot_bench.py's measurement windows, without startup/title reports."""
    if not path or not Path(path).is_file():
        return {}
    summary = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {"first_frame_s": summary.get("first_frame_s"), "wall_s": summary.get("wall_s")}
    places = summary.get("places", {})
    for place, values in sorted(places.items()):
        prefix = place + "."
        for name, value in values.items():
            if name == "replay_ms":
                for replay_name, replay_value in value.items():
                    out[prefix + "replay_" + replay_name] = replay_value
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                out[prefix + name] = value
    out["reports"] = sum(int(v.get("reports") or 0) for v in places.values())
    out["fatal_lines"] = [line for line in summary.get("lines", []) if FATAL.search(line)]
    return out


def flatten_metrics(metrics):
    out = {k: v for k, v in metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    out.update({"replay_" + k: v for k, v in metrics.get("replay_ms", {}).items() if v is not None})
    return out


def aggregate(runs):
    flat = [flatten_metrics(run) for run in runs]
    names = sorted({name for run in flat for name in run})
    out = {}
    for name in names:
        values = [run[name] for run in flat if run.get(name) is not None]
        if values:
            out[name] = median(values)
    out["valid_runs"] = len(runs)
    out["fatal_runs"] = sum(bool(run.get("fatal_lines")) for run in runs)
    return out


def compare_metrics(before, after, thresholds=None):
    thresholds = thresholds or {}
    result = {"before": before, "after": after, "metrics": {}, "passed": True}
    for name in sorted(set(before) | set(after)):
        a, b = before.get(name), after.get(name)
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or isinstance(a, bool) or isinstance(b, bool):
            continue
        item = {"before": a, "after": b, "delta": round(b - a, 3),
                "ratio": round(b / a, 5) if a else None}
        rule = thresholds.get(name, {})
        if "min_ratio" in rule and (not a or b / a < rule["min_ratio"]):
            item["passed"] = result["passed"] = False
        elif "max_ratio" in rule and (not a or b / a > rule["max_ratio"]):
            item["passed"] = result["passed"] = False
        elif "max_delta" in rule and b - a > rule["max_delta"]:
            item["passed"] = result["passed"] = False
        else:
            item["passed"] = True
        result["metrics"][name] = item
    if after.get("fatal_runs", 0) > before.get("fatal_runs", 0):
        result["passed"] = False
        result["fatal_regression"] = True
    return result


def sanitized_env(extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(ENV_PREFIXES) and k != "HOS_ENV_FILE"}
    env.update({str(k): str(v) for k, v in extra.items()})
    return env


def substitutions(value, context):
    return str(value).format_map(context)


def run_command(argv, cwd, env, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as dst:
        proc = subprocess.run(argv, cwd=cwd, env=env, stdout=dst, stderr=subprocess.STDOUT, text=True)
    return proc.returncode


def variant_order(names, repetitions, order):
    if len(names) != 2 or order == "alternate":
        return [name for _ in range(repetitions) for name in names]
    block = names + list(reversed(names)) if order == "ABBA" else list(reversed(names)) + names
    needed = repetitions * len(names)
    return (block * ((needed + len(block) - 1) // len(block)))[:needed]


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    if plan.get("schema") != 1 or not isinstance(plan.get("stages"), list):
        raise SystemExit("plan must have schema 1 and a stages list")
    return plan


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def markdown_report(result):
    rows = ["# Staged run", "", "Result: **%s**" % ("PASS" if result.get("passed") else "FAIL"), "",
            "| Metric | Baseline | Candidate | Delta | Ratio | Gate |", "|---|---:|---:|---:|---:|---|"]
    for name, item in result.get("metrics", {}).items():
        rows.append("| %s | %s | %s | %s | %s | %s |" %
                    (name, item["before"], item["after"], item["delta"], item["ratio"],
                     "pass" if item["passed"] else "fail"))
    return "\n".join(rows) + "\n"


def compare_files(before, after, out, thresholds=None, before_frames=None, after_frames=None):
    b = parse_log(before) | parse_frame_csv(before_frames)
    a = parse_log(after) | parse_frame_csv(after_frames)
    result = compare_metrics(aggregate([b]), aggregate([a]), thresholds)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "comparison.json", result)
    (out / "report.md").write_text(markdown_report(result), encoding="utf-8")
    return result


def test_commands(stage, base):
    commands = []
    focused = stage.get("focused_tests", [])
    if focused:
        commands.append([sys.executable, "-I", "-B", "tests/run_all.py", *focused])
    if stage.get("changed_tests", True):
        commands.append([sys.executable, "-I", "-B", "tests/run_all.py", "--changed", base])
    if stage.get("full_tests", True):
        commands.append([sys.executable, "-I", "-B", "tests/run_all.py"])
    return commands


def run_stage(stage, root, artifacts, base):
    name = stage["name"]
    stage_dir = artifacts / name
    manifest_path = stage_dir / "manifest.json"
    manifest = {"stage": name, "status": "running", "commands": [], "runs": []}
    write_json(manifest_path, manifest)
    common = {"root": root, "artifacts": stage_dir, "stage": name, "variant": "", "run": "", "log": ""}
    for index, command in enumerate(test_commands(stage, base) + stage.get("build", []), 1):
        argv = [substitutions(arg, common) for arg in command]
        output = stage_dir / "commands" / ("%02d.log" % index)
        code = run_command(argv, root, sanitized_env(stage.get("common_env", {})), output)
        manifest["commands"].append({"argv": argv, "output": str(output), "exit": code})
        write_json(manifest_path, manifest)
        if code:
            manifest["status"] = "failed"
            write_json(manifest_path, manifest)
            return False
    variants = stage.get("variants", [])
    by_name = {v["name"]: v for v in variants}
    sequence = variant_order(list(by_name), int(stage.get("repetitions", 1)), stage.get("order", "ABBA"))
    metrics = {name: [] for name in by_name}
    counts = {name: 0 for name in by_name}
    for variant_name in sequence:
        variant = by_name[variant_name]
        counts[variant_name] += 1
        run_name = "%02d-%s" % (counts[variant_name], variant_name)
        run_dir = stage_dir / "runs" / run_name
        log = run_dir / "log.txt"
        command_log = run_dir / "command.log"
        context = common | {"variant": variant_name, "run": run_dir, "log": log}
        argv = [substitutions(arg, context) for arg in variant["command"]]
        env = stage.get("common_env", {}) | variant.get("env", {})
        env = {k: substitutions(v, context) for k, v in env.items()}
        code = run_command(argv, root, sanitized_env(env), command_log)
        frame_path = run_dir / "frames.csv"
        summary_path = run_dir / "summary.json"
        parsed = (parse_summary(summary_path) if summary_path.is_file() else parse_log(log)) | parse_frame_csv(frame_path)
        parsed["exit"] = code
        write_json(run_dir / "metrics.json", parsed)
        metrics[variant_name].append(parsed)
        manifest["runs"].append({"variant": variant_name, "path": str(run_dir), "exit": code})
        write_json(manifest_path, manifest)
        if code or parsed["fatal_lines"]:
            manifest["status"] = "failed"
            write_json(manifest_path, manifest)
            return False
    if len(variants) == 2:
        before, after = (aggregate(metrics[v["name"]]) for v in variants)
        result = compare_metrics(before, after, stage.get("thresholds"))
        write_json(stage_dir / "comparison.json", result)
        (stage_dir / "report.md").write_text(markdown_report(result), encoding="utf-8")
        manifest["status"] = "passed" if result["passed"] else "failed"
    else:
        write_json(stage_dir / "metrics.json", {name: aggregate(runs) for name, runs in metrics.items()})
        manifest["status"] = "passed"
    write_json(manifest_path, manifest)
    return manifest["status"] == "passed"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("compare", help="compare two existing logs")
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--before-frames")
    p.add_argument("--after-frames")
    p.add_argument("--thresholds", help="JSON file mapping metric names to gates")
    p.add_argument("--out", required=True)
    p = sub.add_parser("run", help="run stages from a JSON plan")
    p.add_argument("plan")
    p.add_argument("--stage", action="append", default=[])
    p.add_argument("--base", default="origin/main")
    p.add_argument("--artifacts")
    p = sub.add_parser("report", help="print an existing Markdown report")
    p.add_argument("artifacts")
    args = parser.parse_args()
    if args.command == "compare":
        thresholds = json.loads(Path(args.thresholds).read_text()) if args.thresholds else None
        result = compare_files(Path(args.before), Path(args.after), Path(args.out), thresholds,
                               args.before_frames, args.after_frames)
        print(markdown_report(result), end="")
        return 0 if result["passed"] else 1
    if args.command == "report":
        report = Path(args.artifacts) / "report.md"
        if not report.is_file():
            raise SystemExit("no report: %s" % report)
        print(report.read_text(encoding="utf-8"), end="")
        return 0
    plan = load_plan(args.plan)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    artifacts = Path(args.artifacts) if args.artifacts else DEFAULT_ARTIFACTS / timestamp
    artifacts.mkdir(parents=True, exist_ok=True)
    write_json(artifacts / "plan.json", plan)
    selected = set(args.stage)
    stages = [stage for stage in plan["stages"] if not selected or stage["name"] in selected]
    if selected - {stage["name"] for stage in stages}:
        raise SystemExit("unknown stage(s): %s" % ", ".join(sorted(selected - {stage["name"] for stage in stages})))
    for stage in stages:
        if not run_stage(stage, ROOT, artifacts, args.base):
            print("stage failed: %s (artifacts: %s)" % (stage["name"], artifacts), file=sys.stderr)
            return 1
    print("all stages passed: %s" % artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
