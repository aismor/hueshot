"""A game image past 2 GiB fails the build instead of linking silently broken (nx2/build.py)."""
import ast
import os
from pathlib import Path
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "nx2" / "build.py"


def guard():
    tree = ast.parse(BUILD.read_text(encoding="utf-8"), filename=str(BUILD))
    names = {"image_span", "image_too_big"}
    body = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in names) or
            (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "IMAGE_LIMIT" for t in n.targets))]
    if {n.name for n in body if isinstance(n, ast.FunctionDef)} != names or len(body) != 3:
        raise AssertionError("build.py should define IMAGE_LIMIT, image_span and image_too_big")
    ns = {"os": os}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(BUILD), "exec"), ns)
    return ns


def pe(size):
    b = bytearray(0x200)
    b[:2] = b"MZ"
    struct.pack_into("<I", b, 0x3C, 0x80)
    b[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", b, 0x84, 0x8664, 1)
    struct.pack_into("<H", b, 0x98, 0x20B)
    struct.pack_into("<I", b, 0x98 + 56, size)
    return bytes(b)


def elf(loads):
    phs = [(1, v, n) for v, n in loads] + [(4, 0x7FFF00000000, 0x10)]
    b = bytearray(0x40 + 0x38 * len(phs))
    b[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<Q", b, 0x20, 0x40)
    struct.pack_into("<HH", b, 0x36, 0x38, len(phs))
    for i, (kind, vaddr, memsz) in enumerate(phs):
        at = 0x40 + 0x38 * i
        struct.pack_into("<I", b, at, kind)
        struct.pack_into("<Q", b, at + 0x10, vaddr)
        struct.pack_into("<Q", b, at + 0x28, memsz)
    return bytes(b)


class Guard(unittest.TestCase):
    def setUp(self):
        self.ns = guard()
        self.tmp = tempfile.TemporaryDirectory(prefix="hueshot-image-guard-")
        self.addCleanup(self.tmp.cleanup)

    def file(self, name, data):
        path = Path(self.tmp.name) / name
        path.write_bytes(data)
        return str(path)

    def test_reads_pe_and_elf_spans(self):
        self.assertEqual(self.ns["image_span"](self.file("a.exe", pe(0x7FFFF000))), 0x7FFFF000)
        path = self.file("a", elf([(0x200000, 0x1000), (0x400000, 0x7FFF0000), (0x300000, 0x10)]))
        self.assertEqual(self.ns["image_span"](path), 0x400000 + 0x7FFF0000 - 0x200000)

    def test_rejects_and_deletes_at_the_limit(self):
        for name, data in (("a.exe", pe(2**31)), ("a", elf([(0x400000, 2**31)]))):
            path = self.file(name, data)
            message = self.ns["image_too_big"](path)
            self.assertTrue(message and message.startswith("link FAILED"), message)
            self.assertFalse(os.path.exists(path))

    def test_keeps_small_or_unknown_files(self):
        for name, data in (("a.exe", pe(2**31 - 0x1000)), ("a", elf([(0x400000, 0x100000)])),
                           ("bad", b"not an image"), ("short-elf", b"\x7fELF")):
            path = self.file(name, data)
            self.assertIsNone(self.ns["image_too_big"](path))
            self.assertTrue(os.path.exists(path))

    def test_every_lifted_game_link_is_checked(self):
        import re
        main = BUILD.read_text(encoding="utf-8").split("\ndef main(", 1)[1]
        linked = re.findall(r'"-o", (exe|dll)\b', main)
        self.assertGreaterEqual(len(linked), 3)
        for name in set(linked):
            self.assertEqual(main.count("image_too_big(%s)" % name), linked.count(name))


if __name__ == "__main__":
    unittest.main()
