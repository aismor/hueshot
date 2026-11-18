# Changelog

## [0.0.3](https://github.com/aismor/hueshot/releases/tag/v0.0.3) (2026-11-17)

### Features

* **vk:** selectable CRT monitor and TV filters, ported from Longshot: **CRT filter** (Off, Lottes aperture grille, Lottes consumer TV, Hyllian Fast, zfast CRT) and **CRT lines** (240, 480 or 720 virtual lines), both live and preset-exempt (`crt_filter=`, `crt_lines=`); **CRT lines** is shown only while a filter is chosen, and its saved value returns with the row. The finished SDR picture, HUD included, is box-downsampled to the virtual raster and filtered after window scaling; Hueshot's menu and overlays stay clean, Native HDR (PQ) bypasses it, and Off allocates nothing. Shader sources and licences are in `third_party/crt_shaders/`.

### Performance Improvements

* **vk:** ASTC opacity checks now scan the cached guest/source bytes while copying to the staging buffer instead of rereading uncached host-visible VRAM. On Hyrule Field this removed the 17–30 ms ASTC upload scans: slow uploads fell from 13 to 2 and frames over 20 ms from 0.2% to 0% in the controlled 30-second comparison.

* **host:** character shadow maps reserve stepped storage (`HOS_SHADOW_BUCKET`, 384 by default), reducing transient render-target address churn.
* **vk:** finalized ASTC textures can supply identical textures made at new addresses by image copy instead of another decode (`RX_VK_ASTC_REUSE=1`; off by default while its in-game test is investigated).
* **vk:** dead transient render targets are swept between the ten-present eviction passes, and unused pooled target images expire after eight presents (`RX_VK_DEAD_EVERY`, `RX_VK_DEAD_MIN_UNUSED`, `RX_VK_POOL_IDLE`).

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
