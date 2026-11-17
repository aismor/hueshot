"""Timeline waits returning VK_ERROR_DEVICE_LOST are logged as device loss, never as timeouts."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "gpu" / "vk" / "vk_replay.cpp"


def block(text, marker, start=0):
    at = text.index(marker, start)
    end = text.index("{", at) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[at:end]


def main():
    source = REPLAY.read_text(encoding="utf-8")
    helper = block(source, "void wait_lost(")
    timeline = block(source, "void vk_timeline_wait(uint64_t v) {")
    recording = block(source, "static void wait_rec_seq(uint64_t seq, uint64_t timeout_ns, int* ok) {")
    if 'came back VK_ERROR_DEVICE_LOST: the GPU device is lost' not in helper or "logged++ >= 8" not in helper:
        raise SystemExit("FAIL: a lost timeline wait is not logged, with the line capped")
    rec_lost = "if (wait_rec_result == VK_ERROR_DEVICE_LOST) return;"
    if rec_lost not in timeline or timeline.index(rec_lost) > timeline.index("if (!ok)"):
        raise SystemExit("FAIL: a lost recording wait can still be reported as a capture timeout")
    for needle in ('const VkResult res = vkWaitSemaphores', "if (res == VK_TIMEOUT)",
                   'if (res == VK_ERROR_DEVICE_LOST) wait_lost("a capture\'s wait for write-back", v);'):
        if needle not in timeline:
            raise SystemExit("FAIL: vk_timeline_wait no longer distinguishes: " + needle)
    for needle in ("res = vkWaitSemaphores", "*ok = res == VK_SUCCESS;", "wait_rec_result = res;",
                   'if (res == VK_ERROR_DEVICE_LOST) wait_lost("a wait for recording", seq);'):
        if needle not in recording:
            raise SystemExit("FAIL: wait_rec_seq no longer distinguishes: " + needle)
    if recording.index("wait_rec_result = res;") > recording.index("wait_lost("):
        raise SystemExit("FAIL: the recording wait reports loss before publishing its result")
    for name, piece in (("vk_timeline_wait", timeline), ("wait_rec_seq", recording)):
        if "device_lost(" in piece:
            raise SystemExit("FAIL: %s ends the process; this port changes the diagnostic only" % name)
    print("PASS: device-lost timeline waits are said as device loss; true timeouts keep their timeout line")


if __name__ == "__main__":
    main()
