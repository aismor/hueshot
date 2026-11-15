"""Hueshot's HUESHOT_MINGW, as the vendored a64-kit toolchain asks for it.

third_party/a64-kit/tools/toolchain.py is an unmodified upstream copy (its PROVENANCE.md), and it reads
HOOKSHOT_MINGW for llvm-mingw's folder. sync() gives it Hueshot's value under that name before a build asks which
compiler to use, so HUESHOT_MINGW is the name the builder, the docs and CI use. A value already set as
HOOKSHOT_MINGW stays as it is."""
import os


def sync():
    value = os.environ.get("HUESHOT_MINGW", "")
    if value:
        os.environ["HOOKSHOT_MINGW"] = value
