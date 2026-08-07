#!/usr/bin/env python3
"""Dump the asset manifest the Metal Slug X executable carries.

    python3 tools/manifest.py
    python3 tools/manifest.py --code

135 entries of `{path, load address, lba, size}`; the last two are filled in at
runtime once the file is found on the disc, so they read zero here. The load
address is the useful column: it says where a file ends up, which is what makes
an overlay disassemblable (`tools/mips.py --base`) and what groups files that
share a slot. --disc defaults to $METAL_SLUG_DISC.
"""
import argparse
import os
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disc import Disc

EXE = "SLUS_012.12"
BASE = 0x80010000 - 0x800
TABLE = 0x800841c4
COUNT = 135
PROLOGUE = 0x27BD0000   # addiu $sp, $sp, -N opens all but the leaf functions


def entries(exe):
    def cstr(addr):
        p = addr - BASE
        return exe[p:exe.find(b"\x00", p)].decode("ascii", "replace")

    out = []
    for i in range(COUNT):
        path, dest, lba, size = struct.unpack_from("<4I", exe, TABLE + i * 16 - BASE)
        out.append((i, cstr(path), dest, lba, size))
    return out


def code_score(blob, base):
    """Prologues found, and how many of the file's own calls land on one.

    Data scores near zero on both; a code overlay loaded at the right address
    scores high on the second, which is what confirms an address is right.
    """
    pro = {p for p in range(0, len(blob) - 4, 4)
           if (struct.unpack_from("<I", blob, p)[0] & 0xFFFF0000) == PROLOGUE
           and struct.unpack_from("<I", blob, p)[0] & 0x8000}
    hit = total = 0
    for p in range(0, len(blob) - 4, 4):
        word = struct.unpack_from("<I", blob, p)[0]
        if word >> 26 != 3:
            continue
        target = ((base + p) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
        if base <= target < base + len(blob):
            total += 1
            hit += (target - base) in pro
    return len(pro), hit, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=os.environ.get("METAL_SLUG_DISC"),
                    help="raw PS1 disc image; defaults to $METAL_SLUG_DISC")
    ap.add_argument("--code", action="store_true",
                    help="also test each file for MIPS code at its load address")
    args = ap.parse_args()
    if not args.disc:
        ap.error("no disc image: pass --disc or set $METAL_SLUG_DISC")

    disc = Disc(args.disc)
    exe = disc.read_file(EXE)
    print(f"{'#':>3s}  {'path':34s} {'loads at':>10s} {'size':>9s}"
          + ("   prologues  calls on one" if args.code else ""))
    for i, path, dest, _, _ in entries(exe):
        name = path.split("\\")[-1].split(";")[0]
        size = disc.files.get(name, (0, 0))[1]
        line = f"{i:3d}  {path:34s} 0x{dest:08x} {size:9d}"
        if args.code and size:
            pro, hit, total = code_score(disc.read_file(name), dest)
            share = f"{100 * hit // total}%" if total else "  -"
            line += f"   {pro:9d}  {hit:4d}/{total:<4d} {share:>4s}"
        print(line)


if __name__ == "__main__":
    main()
