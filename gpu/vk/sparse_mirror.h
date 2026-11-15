// (Longshot, hueshot) VRAM mirror block residency helpers (vk_memory.cpp when RX_VK_MIRROR_SPARSE is ported).
#pragma once

#include <algorithm>
#include <cstdint>
#include <iterator>
#include <vector>

namespace sparse_mirror {

template <class It>
void live_blocks(uint64_t lo, uint64_t hi, uint64_t block, It first, It last, std::vector<uint8_t>& live) {
    live.assign(hi > lo && block ? (size_t)((hi - lo + block - 1) / block) : 0, 0);
    if (live.empty()) return;
    const It end = std::upper_bound(first, last, hi - 1, [](uint64_t a, const auto& p) { return a < p.lo; });
    for (It it = first; it != end; ++it) {
        if (it->hi <= lo || it->hi <= it->lo) continue;
        const uint64_t a = std::max(it->lo, lo) - lo, b = std::min(it->hi, hi) - lo;
        for (uint64_t i = a / block; i < (b + block - 1) / block; i++) live[(size_t)i] = 1;
    }
}

template <class It>
std::vector<uint8_t> live_blocks(uint64_t lo, uint64_t hi, uint64_t block, It first, It last) {
    std::vector<uint8_t> live;
    live_blocks(lo, hi, block, first, last, live);
    return live;
}

inline void block_span(uint64_t off, uint64_t size, uint64_t block, size_t nblocks, size_t* first, size_t* end) {
    *first = (size_t)std::min<uint64_t>(off / block, nblocks);
    *end = size ? (size_t)std::min<uint64_t>((off + size + block - 1) / block, nblocks) : *first;
}

template <class Get, class Emit>
void runs(size_t nblocks, Get get, bool want, Emit emit) {
    for (size_t i = 0; i < nblocks;) {
        if ((get(i) != 0) != want) {
            i++;
            continue;
        }
        size_t j = i + 1;
        while (j < nblocks && (get(j) != 0) == want) j++;
        emit(i, j - i);
        i = j;
    }
}

struct Copy { uint64_t src, dst, size; };

template <class SrcHas, class DstHas>
std::vector<Copy> clip(const std::vector<Copy>& in, uint64_t block, SrcHas src_has, DstHas dst_has) {
    std::vector<Copy> out;
    for (const Copy& c : in) {
        uint64_t at = 0;
        while (at < c.size) {
            const uint64_t s = c.src + at, d = c.dst + at;
            const uint64_t step = std::min({c.size - at, block - s % block, block - d % block});
            if (src_has(s) && dst_has(d)) {
                if (!out.empty() && out.back().src + out.back().size == s && out.back().dst + out.back().size == d)
                    out.back().size += step;
                else
                    out.push_back({s, d, step});
            }
            at += step;
        }
    }
    return out;
}

}  // namespace sparse_mirror