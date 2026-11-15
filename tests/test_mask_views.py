"""The mask blend's cached storage views go with the image they were made for.

A view is made once a texture image and level, and the texture's own deferred free (destroy_later, or the VRAM
compaction's move) takes it: a stale view on a destroyed image is a use-after-free when the driver reuses the handle.

python -I -B tests/test_mask_views.py [--cxx g++]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    draw = (a.source / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    tex = (a.source / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")

    stabilize = block(draw, "void mask_stabilize(")
    if "std::lock_guard lk(mask_views_mu);" not in stabilize:
        raise SystemExit("mask_stabilize makes or reads a view without the lock")
    if "destroy_image(retired[i].image, retired[i].mem)" not in stabilize:
        raise SystemExit("a resized history image is not destroyed")
    if "vkDestroyImageView(dev.device, retired[i].view, nullptr)" not in stabilize:
        raise SystemExit("a resized history view is not destroyed")
    if "mask_views_take(tex.image)" not in block(tex, "void destroy_later(Texture& tex)"):
        raise SystemExit("destroy_later leaves the mask's views on a destroyed image")
    if "mask_views_take(t->image)" not in block(tex, "void compact_step(uint64_t completed)"):
        raise SystemExit("the VRAM compaction leaves the mask's views on the image it moves away")

    actual = "\n".join([
        block(draw, "std::map<std::tuple<VkImage, uint32_t, uint32_t>, VkImageView>& mask_views()"),
        "std::mutex mask_views_mu;",
        block(draw, "std::vector<VkImageView> mask_views_take(VkImage image)"),
    ])
    fixture = r'''
#include <cassert>
#include <cstdint>
#include <map>
#include <mutex>
#include <tuple>
#include <vector>
using VkImage = uint64_t;
using VkImageView = uint64_t;
@@ACTUAL@@
int main() {
    mask_views()[{1, 0, 0}] = 10;
    mask_views()[{1, 1, 0}] = 11;
    mask_views()[{2, 0, 0}] = 20;
    mask_views()[{3, 0, 0}] = 0;
    std::vector<VkImageView> a = mask_views_take(1);
    assert((a == std::vector<VkImageView>{10, 11}));
    assert(mask_views().size() == 2);
    assert(mask_views().count({2, 0, 0}) && mask_views().count({3, 0, 0}));
    std::vector<VkImageView> b = mask_views_take(1);
    assert(b.empty());
    std::vector<VkImageView> c = mask_views_take(2);
    assert((c == std::vector<VkImageView>{20}));
    std::vector<VkImageView> d = mask_views_take(3);
    assert(d.empty());
    assert(mask_views().empty());
}
'''
    with tempfile.TemporaryDirectory(prefix="mask-views-") as temp:
        cpp, exe = Path(temp) / "fixture.cpp", Path(temp) / "fixture"
        cpp.write_text(fixture.replace("@@ACTUAL@@", actual), encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror",
                        str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("mask views are taken with the image they were made for: PASS")


if __name__ == "__main__":
    main()
