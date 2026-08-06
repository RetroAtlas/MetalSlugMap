#!/usr/bin/env python3
"""Render a Metal Slug X stage section to PNG.

Rebuilds the game's video memory from a mission's artwork, reads the section's
tile list (which tile comes from where, under which palette) and its tilemap
(which tile goes where), and draws the result.

    python3 tools/render_map.py --disc "Metal Slug X.bin" --section X1_00.BIN

--disc defaults to $METAL_SLUG_DISC. Video memory is time-dependent during
play: a section's tiles can need pages or palettes uploaded by a sibling
section, and loading every file at once overwrites pages the section still
needs, so --art takes the exact set to replay.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disc import Disc
from png import write_png
from tilelist import TILE, records
from tilemap import cells, find
from vram import Vram


def render(vram, recs, grid, w, h):
    W, H = w * TILE, h * TILE
    img = bytearray(W * H * 4)
    blank = 0
    for cy in range(h):
        for cx in range(w):
            t = grid[cy * w + cx]
            if t >= len(recs):
                continue
            r = recs[t]
            drew = False
            for ty in range(TILE):
                for tx in range(TILE):
                    idx = vram.texel4(r["page_x"], r["page_y"], r["x"] + tx, r["y"] + ty)
                    if not idx:
                        continue
                    col = vram.clut_colour(r["clut"], idx)
                    if not col:
                        continue
                    drew = True
                    red = (col & 0x1F) << 3
                    grn = ((col >> 5) & 0x1F) << 3
                    blu = ((col >> 10) & 0x1F) << 3
                    o = ((cy * TILE + ty) * W + cx * TILE + tx) * 4
                    img[o:o + 4] = bytes((red | red >> 5, grn | grn >> 5, blu | blu >> 5, 255))
            if not drew:
                blank += 1
    return img, W, H, blank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=os.environ.get("METAL_SLUG_DISC"),
                    help="raw PS1 disc image; defaults to $METAL_SLUG_DISC")
    ap.add_argument("--section", default="X1_00.BIN", help="section holding the tile list and tilemap")
    ap.add_argument("--art", nargs="*", default=None,
                    help="art files to replay into VRAM (default: the mission's X<n>.BIN)")
    ap.add_argument("--out", default="out", help="output directory")
    args = ap.parse_args()
    if not args.disc:
        ap.error("no disc image: pass --disc or set $METAL_SLUG_DISC")

    disc = Disc(args.disc)
    section = args.section.upper()
    if section not in disc.files:
        ap.error(f"{section} is not on the disc")
    data = disc.read_file(section)

    mission = re.match(r"^(X\d+)_", section)
    art = args.art or ([f"{mission.group(1)}.BIN"] if mission else [])
    vram = Vram()
    for name in art:
        loaded = vram.load(disc.read_file(name.upper()))
        print(f"VRAM <- {name.upper()}: {len(loaded)} TIM records")

    recs = list(records(data))
    if not recs:
        print(f"{section}: no tile list")
        return
    tm = find(data, 8 + len(recs) * 8)
    if not tm:
        print(f"{section}: tile list of {len(recs)} tiles, but no tilemap follows it")
        return
    grid = cells(data, tm)
    print(f"{section}: {len(recs)} tiles, tilemap {tm['w']}x{tm['h']} "
          f"({tm['w'] * TILE}x{tm['h'] * TILE}px)")

    img, W, H, blank = render(vram, recs, grid, tm["w"], tm["h"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{section[:-4].lower()}.png"
    write_png(path, W, H, bytes(img), keep_alpha=True)
    print(f"  {path} ({blank} of {tm['w'] * tm['h']} cells empty)")


if __name__ == "__main__":
    main()
