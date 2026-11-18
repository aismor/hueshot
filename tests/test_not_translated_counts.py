"""Every failed shader program is counted by the reason behind its capped "not translated" line."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    at = text.index(marker)
    end = text.index("{", at) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[at:end]


def main():
    shader = (ROOT / "gpu/vk/vk_shader.cpp").read_text(encoding="utf-8")
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    required = (
        "constexpr int64_t kFailNamed = 30;",
        "std::atomic<int64_t> st_failed_left_out, st_not_translated, st_mesh_not_translated, st_stage_failed;",
        "void shader_fail_lines() {",
    )
    for needle in required:
        if needle not in shader:
            raise SystemExit("FAIL: vk_shader.cpp no longer has " + needle)
    counters = ("st_failed_left_out", "st_not_translated", "st_mesh_not_translated", "st_stage_failed")
    for name in counters:
        if shader.count(name + "++ < kFailNamed") != 1:
            raise SystemExit("FAIL: %s is not the one counter behind its capped line" % name)
    if shader.count("st_failed++") != 4:
        raise SystemExit("FAIL: the failed-program sites changed; review their reason counters")
    lines = block(shader, "void shader_fail_lines() {")
    if any((name + ".load()") not in lines for name in counters):
        raise SystemExit("FAIL: shader_fail_lines does not report every failure reason")
    if "st_left_out" in lines:
        raise SystemExit("FAIL: Hueshot's deliberately left-out networks were counted as failures")
    prepared = block(draw, "bool prepare_run(")
    at = prepared.index('logf("vk: prepared %zu shader programs')
    after = prepared[prepared.index(";", prepared.index("std::chrono::steady_clock::now() - t0).count())", at)) + 1:]
    if not after.lstrip().startswith("shader_fail_lines();"):
        raise SystemExit("FAIL: the failure reason counts are not immediately after the prepared line")
    if not re.search(r"%lld failed, %lld networks left out", prepared):
        raise SystemExit("FAIL: Hueshot no longer reports deliberate network exclusions apart from failures")
    print("PASS: every capped not-translated reason keeps a whole count; deliberate LeftOut networks remain separate")


if __name__ == "__main__":
    main()
