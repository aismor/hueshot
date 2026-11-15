# Changelog

## [0.0.2](https://github.com/aismor/hueshot/releases/tag/v0.0.2) (2026-11-15)

### Performance Improvements

* **vk:** threaded rendering ported from Longshot: optional render thread (`RX_VK_ASYNC`), recorder thread (`RX_VK_RECORDER=thread`), frame gate and present sequencing in `vk_replay.cpp`; **Insert** menu row **Threaded rendering** (`threaded_rendering=` in `hueshot_options.ini`), Auto when the host has 12+ logical CPUs (`gpu/vk/threaded_rendering.h`).
* **vk:** recorder thread uses a futex/`WaitOnAddress` idle wait by default (`RX_VK_RECORDER_IDLE=wait`); `shadow follows sync` for write-back diff so mirror sync seeds the VRAM shadow (`RX_VK_SHADOW_FOLLOWS_SYNC`, on by default).
* **vk:** readback rules for threaded replay (`readback_late.h`, default `newest` when threaded rendering is on); mirror sync and parallel replay segment scheduling improvements in `vk_replay.cpp` and `vk_memory.cpp`.
* **vk:** late-page write-back fix path (`shaders/late_fix.comp`, hooks in `vk_memory.cpp`); opt-in with `RX_VK_LATE_FIX=1` (off by default and incompatible with `RX_VK_PARALLEL>1`). Write-back diff shader carries page stamps (`shaders/wb_diff.comp`).
* **vk:** spawn and scheduling tweaks for open-field play (`host/nvn_native.c`, `vk_texture.cpp`, `vk_vma.cpp`).

### Features

* **vk:** helpers for sparse VRAM mirrors (`gpu/vk/sparse_mirror.h`; `RX_VK_MIRROR_SPARSE` is not wired as a default yet).

### Bug Fixes

* **vk:** shader load / pipeline warm-up adjustments after threaded replay changes (`vk_replay.cpp`).

### Tests

* **vk:** threaded-rendering configuration checks (`tests/test_threaded_rendering.py`).

### BREAKING CHANGES

* **vk:** `MKWVK_API_VERSION` is **23** (`gpu/vk/vk_api.h`). Rebuild **`hueshot` and `hueshot_vk.so` / `hueshot_vk.dll` together** from the same commit; mixing an older executable with this renderer (or the reverse) makes `mkwvk_init` fail and the window stays black.