/* (Longshot rule, hueshot) How much VRAM the game's memory pools may be mirrored in (vk_memory.cpp mirror_budget), by the card.
   No Vulkan here. */
#pragma once

#include <algorithm>
#include <cstdint>

namespace mkwvk::mirror_rule {

/// What a card counts as small: 4.5 GB or less, where the mirrors get at most 256 MB
inline bool small_card(uint64_t vram) { return vram && vram <= (4ull << 30) + (512ull << 20); }

/// The mirrors: a quarter of the card, at most 2 GB under 15 GB and 3 GB from there, and on a small card an eighth, at most 256 MB
inline uint64_t auto_bytes(uint64_t vram) {
    if (!vram) return 3072ull << 20;
    if (small_card(vram)) return std::min<uint64_t>(vram / 8, 256ull << 20);
    return std::min<uint64_t>(vram / 4, vram < (15ull << 30) ? 2048ull << 20 : 3072ull << 20);
}

}  // namespace mkwvk::mirror_rule