"""The staged runner parses logs/frames, orders A/B runs and gates regressions."""
import importlib.util
import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("staged_run", ROOT / "scripts" / "staged_run.py")
staged = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(staged)


def check(value, message):
    if not value:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        before = root / "before.log"
        after = root / "after.log"
        before.write_text("\n".join([
            "vk: 600 presents, 40.0 fps; a frame: 2000 draws",
            "vk: GPU time 12.0 ms a frame",
            "vk: a frame's replay time (ms): submit 15.0, draw 8.0, descriptors 2.0, memory sync 1.0",
            "vk: VRAM: 4000 MB used of 8000 MB allowed",
            "vk: 720 presents, 42.0 fps; a frame: 2100 draws",
        ]), encoding="utf-8")
        after.write_text("\n".join([
            "vk: 600 presents, 44.0 fps; a frame: 2000 draws",
            "vk: GPU time 11.0 ms a frame",
            "vk: a frame's replay time (ms): submit 12.0, draw 6.0, descriptors 1.5, memory sync 0.8",
            "vk: VRAM: 4100 MB used of 8000 MB allowed",
            "vk: 720 presents, 46.0 fps; a frame: 2100 draws",
        ]), encoding="utf-8")
        frames = root / "frames.csv"
        frames.write_text("frame,seconds,ms\n1,0.016,16\n2,0.050,34\n3,0.150,100\n", encoding="utf-8")
        b = staged.parse_log(before) | staged.parse_frame_csv(frames)
        a = staged.parse_log(after)
        check(b["fps"] == 41.0 and b["replay_ms"]["submit"] == 15.0, "log medians")
        check(b["frame_p95_ms"] == 100.0 and b["frames_over_33"] == 2, "frame percentiles")
        summary = root / "summary.json"
        summary.write_text(json.dumps({"first_frame_s": 8, "wall_s": 80, "places": {
            "Field": {"reports": 4, "fps": 50.0, "replay_ms": {"submit": 9.0}, "memory_mb": 1234}
        }}), encoding="utf-8")
        parsed_summary = staged.parse_summary(summary)
        check(parsed_summary["Field.fps"] == 50.0 and parsed_summary["Field.replay_submit"] == 9.0,
              "benchmark summary")
        result = staged.compare_metrics(staged.aggregate([b]), staged.aggregate([a]), {
            "fps": {"min_ratio": 1.05}, "vram_used_mb": {"max_delta": 128}
        })
        check(result["passed"], "passing gates")
        failed = staged.compare_metrics(staged.aggregate([b]), staged.aggregate([a]), {
            "fps": {"min_ratio": 1.20}
        })
        check(not failed["passed"] and not failed["metrics"]["fps"]["passed"], "failing gate")
        out = root / "out"
        staged.compare_files(before, after, out)
        check((out / "comparison.json").is_file() and (out / "report.md").is_file(), "comparison artifacts")
        check(staged.variant_order(["A", "B"], 2, "ABBA") == ["A", "B", "B", "A"], "ABBA order")
        env = staged.sanitized_env({"RX_TEST": "1"})
        check(env["RX_TEST"] == "1" and "HOS_ENV_FILE" not in env, "environment sanitizing")
        plan = root / "plan.json"
        plan.write_text(json.dumps({"schema": 1, "stages": []}), encoding="utf-8")
        check(staged.load_plan(plan)["schema"] == 1, "plan schema")
    print("PASS: staged log/frame metrics, gates, artifacts, ordering and environment")


if __name__ == "__main__":
    main()
