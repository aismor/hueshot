/* (Longshot rule, hueshot) How much VRAM the texture cache may hold (vk_texture.cpp texture_frame), by the card. No Vulkan here. */
#pragma once

#include <algorithm>
#include <cstdint>

#include "mirror_budget.h"

namespace mkwvk::texture_rule {

constexpr uint64_t kMB = 1ull << 20;

inline uint64_t dedicated_bytes(uint64_t allowed, uint64_t vram, uint64_t ram) {
    if (ram && ram < 12288 * kMB && vram > 6912 * kMB)
        return allowed ? std::min<uint64_t>(allowed / 100 * (allowed <= 8704 * kMB ? 45 : 70), 6144 * kMB) : 4096 * kMB;
    if (!vram) return 4096 * kMB;
    uint64_t b = std::max<uint64_t>(vram / 12 * 7, vram > 5120 * kMB ? vram - 5120 * kMB : 0);
    b = std::min<uint64_t>(b, 11000 * kMB);
    if (mirror_rule::small_card(vram)) b = std::min<uint64_t>(b, 2200 * kMB);
    if (allowed) b = std::min<uint64_t>(b, allowed / 4 * 3);
    return b;
}

inline uint64_t integrated_bytes(uint64_t allowed, uint64_t vram) {
    if (!allowed) return 4096 * kMB;
    uint64_t b = std::min<uint64_t>(allowed / 100 * (allowed <= 8704 * kMB ? 45 : 70), 6144 * kMB);
    if (mirror_rule::small_card(vram)) b = std::min<uint64_t>(b, 2200 * kMB);
    return b;
}

}  // namespace mkwvk::texture_rule