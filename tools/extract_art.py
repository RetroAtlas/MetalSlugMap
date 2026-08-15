#!/usr/bin/env python3
"""Extract the TIM texture pages from any Metal Slug X file to PNG.

Artwork is stored uncompressed as standard PS1 TIM pages, so it comes straight
off the disc — not only the mission files but the character and vehicle banks
under `\\PL` and `\\STD` too.

Usage:
    python3 tools/extract_art.py --disc "Metal Slug X.bin" [--file X1.BIN] [--out out]

--disc defaults to $METAL_SLUG_DISC_X. With no --file, every X*.BIN mission file
is scanned. Each page is written under the first palette its record carries;
tiles pick their own palette out of that bank, which is what the tilemap tools
resolve.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disc import Disc
from png import write_png
from vram import rgba, tim_records


def mission_files(disc):
    return sorted(n for n in disc.files
                  if n.startswith("X") and n.endswith(".BIN") and n[1:-4].isdigit())


def palette_of(record):
    clut = record["clut"]
    if not clut:
        return None
    return [clut[4][i * 2] | (clut[4][i * 2 + 1] << 8) for i in range(clut[2])]


def page(record, palette=None):
    """Unpack one record to (width, height, RGBA).

    Only some records carry a palette; the rest are uploaded against one a
    previous record left in memory, so the caller passes the last one seen.
    """
    blob, w, h = record["pixels"], record["w"], record["h"]
    per = {0: 4, 1: 2, 2: 1}[record["mode"]]
    palette = palette_of(record) or palette or []
    out = bytearray(w * per * h * 4)
    for y in range(h):
        for x in range(w):
            word = blob[(y * w + x) * 2] | (blob[(y * w + x) * 2 + 1] << 8)
            for s in range(per):
                if record["mode"] == 2:
                    colour = word
                else:
                    bits = 4 if per == 4 else 8
                    index = (word >> (s * bits)) & ((1 << bits) - 1)
                    colour = palette[index] if index < len(palette) else 0
                o = (y * w * per + x * per + s) * 4
                out[o:o + 4] = bytes(rgba(colour))
    return w * per, h, bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=os.environ.get("METAL_SLUG_DISC_X"),
                    help="raw PS1 disc image (.bin, 2352-byte sectors); "
                         "defaults to $METAL_SLUG_DISC_X")
    ap.add_argument("--file", help="a single mission file (e.g. X1.BIN); default: all")
    ap.add_argument("--out", default="out", help="output directory (default: out/)")
    args = ap.parse_args()
    if not args.disc:
        ap.error("no disc image: pass --disc or set $METAL_SLUG_DISC_X")

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
        pages = tim_records(data)
        palette = None
        for i, record in enumerate(pages):
            palette = palette_of(record) or palette
            w, h, pixels = page(record, palette)
            path = out / f"{stem}_{i:02d}_{w}x{h}.png"
            write_png(path, w, h, pixels, keep_alpha=True)
        print(f"{name}: {len(pages)} texture page(s) -> {stem}_*.png")
        total += len(pages)
    print(f"\n{total} texture pages written to {out}/")


if __name__ == "__main__":
    main()
