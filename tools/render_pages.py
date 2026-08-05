#!/usr/bin/env python3
"""Render Metal Slug X texture pages in their true colours.

Loads a mission's artwork into VRAM, then follows a section file's tile list so
every 16x16 tile is drawn through the palette the game assigns it.

    python3 tools/render_pages.py --disc "Metal Slug X.bin" --section X1_00.BIN

--disc defaults to $METAL_SLUG_DISC. VRAM is time-dependent during play: extra
files can be layered with --art, but loading everything at once overwrites
pages the section still needs.
"""
import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disc import Disc
from png import write_png
from tilelist import BLOCK, records, render
from vram import Vram


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=os.environ.get("METAL_SLUG_DISC"),
                    help="raw PS1 disc image; defaults to $METAL_SLUG_DISC")
    ap.add_argument("--section", default="X1_00.BIN", help="section file holding a tile list")
    ap.add_argument("--art", nargs="*", default=None,
                    help="art files to load into VRAM (default: the mission's X<n>.BIN)")
    ap.add_argument("--out", default="out", help="output directory")
    args = ap.parse_args()
    if not args.disc:
        ap.error("no disc image: pass --disc or set $METAL_SLUG_DISC")

    disc = Disc(args.disc)
    section = args.section.upper()
    if section not in disc.files:
        ap.error(f"{section} is not on the disc")

    mission = re.match(r"^(X\d+)_", section)
    art = args.art or ([f"{mission.group(1)}.BIN"] if mission else [])
    vram = Vram()
    for name in art:
        loaded = vram.load(disc.read_file(name.upper()))
        print(f"VRAM <- {name.upper()}: {len(loaded)} TIM records")

    recs = list(records(disc.read_file(section)))
    if not recs:
        print(f"{section}: no tile list found")
        return
    blocks = defaultdict(list)
    for r in recs:
        blocks[r["index"] // BLOCK].append(r)
    print(f"{section}: {len(recs)} tile records in {len(blocks)} page block(s)")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = section[:-4].lower()
    for b, rs in sorted(blocks.items()):
        write_png(out / f"{stem}_page{b:02d}.png", BLOCK, BLOCK,
                  bytes(render(vram, rs)), keep_alpha=True)
        cluts = len({r["clut"] for r in rs})
        print(f"  page {b}: {len(rs)} tiles, {cluts} palettes, VRAM x={rs[0]['page_x']}")


if __name__ == "__main__":
    main()
