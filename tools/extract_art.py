#!/usr/bin/env python3
"""Extract the raw TIM texture pages from Metal Slug X mission files to PNG.

This is the proven first capability: stage artwork is stored uncompressed as
standard PS1 TIM pages, so it comes straight off the disc. The tilemap that
assembles these tiles into full scrolling stages, and the spawn tables for
POWs / items / hidden objects, are a separate reverse-engineering task (see
README) — this tool only lifts the art.

Usage:
    python3 tools/extract_art.py --disc "Metal Slug X.bin" [--file X1.BIN] [--out out]

--disc defaults to $METAL_SLUG_DISC. With no --file, every X*.BIN mission file
is scanned. Each texture page is written with palette 0; real per-tile palette
selection comes with tilemap decoding.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disc import Disc
from png import write_png
from tim import find_tims


def mission_files(disc):
    return sorted(n for n in disc.files
                  if n.startswith("X") and n.endswith(".BIN") and n[1:-4].isdigit())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=os.environ.get("METAL_SLUG_DISC"),
                    help="raw PS1 disc image (.bin, 2352-byte sectors); "
                         "defaults to $METAL_SLUG_DISC")
    ap.add_argument("--file", help="a single mission file (e.g. X1.BIN); default: all")
    ap.add_argument("--out", default="out", help="output directory (default: out/)")
    args = ap.parse_args()
    if not args.disc:
        ap.error("no disc image: pass --disc or set $METAL_SLUG_DISC")

    disc = Disc(args.disc)
    names = [args.file.upper()] if args.file else mission_files(disc)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for name in names:
        if name not in disc.files:
            print(f"{name}: not on disc, skipping")
            continue
        data = disc.read_file(name)
        stem = name[:-4].lower()
        pages = list(find_tims(data))
        for i, tim in enumerate(pages):
            path = out / f"{stem}_{i:02d}_{tim['width']}x{tim['height']}.png"
            write_png(path, tim["width"], tim["height"], tim["rgba"], keep_alpha=True)
        print(f"{name}: {len(pages)} texture page(s) -> {stem}_*.png")
        total += len(pages)
    print(f"\n{total} texture pages written to {out}/")


if __name__ == "__main__":
    main()
