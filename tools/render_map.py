#!/usr/bin/env python3
"""Render the stage pieces of one Metal Slug X section to PNG.

Replays the mission in load order, then draws each of the section's tilemaps
against the video memory that makes its tiles join — the state the game held
when that piece was on screen.

    python3 tools/render_map.py --disc "Metal Slug X.bin" --section X1_00.BIN

--disc defaults to $METAL_SLUG_DISC_X.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disc import Disc
from png import write_png
from render import TILE, best_state, draw
from section import load_order, pieces, stream


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=os.environ.get("METAL_SLUG_DISC_X"),
                    help="raw PS1 disc image; defaults to $METAL_SLUG_DISC_X")
    ap.add_argument("--section", default="X1_00.BIN", help="section holding the tilemaps")
    ap.add_argument("--out", default="out", help="output directory")
    args = ap.parse_args()
    if not args.disc:
        ap.error("no disc image: pass --disc or set $METAL_SLUG_DISC_X")

    disc = Disc(args.disc)
    name = args.section.upper()
    if name not in disc.files:
        ap.error(f"{name} is not on the disc")
    mission = re.match(r"^(X\d+)_", name)
    if not mission:
        ap.error(f"{name} is not a mission section file")

    ps = pieces(disc.read_file(name))
    if not ps:
        print(f"{name}: no tilemap paired with a tile list")
        return
    states = [(n, v.copy(), later) for n, v, later in stream(disc, load_order(disc, mission.group(1)))]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(ps):
        vram, art, fit = best_state(states, p)
        img, W, H, drawn = draw(vram, p)
        path = out / f"{name[:-4].lower()}_{i:02d}.png"
        write_png(path, W, H, img, keep_alpha=True)
        print(f"{path}  {p['w']}x{p['h']} tiles ({W}x{H}px)  art {art}  fit {fit:.1f}  "
              f"{drawn}/{p['w'] * p['h']} cells drawn")


if __name__ == "__main__":
    main()
