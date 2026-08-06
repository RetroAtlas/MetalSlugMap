#!/usr/bin/env python3
"""Build the Metal Slug X map: render every stage piece and emit the viewer's data.

Walks each mission's section files, renders every tilemap through its tile list
and staged video memory, and writes the PNGs plus `map_data_msx.json`.

    python3 tools/build_map.py --disc "Metal Slug X.bin"

--disc defaults to $METAL_SLUG_DISC. Output goes to public/ by default, which
is what the viewer serves.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disc import Disc
from png import write_png
from section import art_index, pieces, stage_vram

TILE = 16

MISSIONS = [
    ("X1", "Mission 1"),
    ("X21", "Mission 2-1"), ("X22", "Mission 2-2"), ("X23", "Mission 2-3"),
    ("X3", "Mission 3"),
    ("X4", "Mission 4"),
    ("X51", "Mission 5-1"), ("X52", "Mission 5-2"), ("X53", "Mission 5-3"),
    ("X61", "Mission 6-1"), ("X62", "Mission 6-2"), ("X63", "Mission 6-3"),
]


def render(vram, piece):
    w, h, tiles, cells = piece["w"], piece["h"], piece["tiles"], piece["cells"]
    W, H = w * TILE, h * TILE
    img = bytearray(W * H * 4)
    drawn = 0
    for cy in range(h):
        for cx in range(w):
            t = cells[cy * w + cx]
            if t >= len(tiles):
                continue
            r = tiles[t]
            hit = False
            for ty in range(TILE):
                for tx in range(TILE):
                    idx = vram.texel4(r["page_x"], r["page_y"], r["x"] + tx, r["y"] + ty)
                    if not idx:
                        continue
                    col = vram.clut_colour(r["clut"], idx)
                    if not col:
                        continue
                    hit = True
                    red = (col & 0x1F) << 3
                    grn = ((col >> 5) & 0x1F) << 3
                    blu = ((col >> 10) & 0x1F) << 3
                    o = ((cy * TILE + ty) * W + cx * TILE + tx) * 4
                    img[o:o + 4] = bytes((red | red >> 5, grn | grn >> 5, blu | blu >> 5, 255))
            drawn += hit
    return img, W, H, drawn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=os.environ.get("METAL_SLUG_DISC"),
                    help="raw PS1 disc image; defaults to $METAL_SLUG_DISC")
    ap.add_argument("--out", default="public", help="output directory")
    ap.add_argument("--missions", default="", help="comma list to limit (e.g. X1,X3)")
    args = ap.parse_args()
    if not args.disc:
        ap.error("no disc image: pass --disc or set $METAL_SLUG_DISC")

    disc = Disc(args.disc)
    only = {m.strip().upper() for m in args.missions.split(",") if m.strip()}
    out = Path(args.out)
    (out / "pieces").mkdir(parents=True, exist_ok=True)

    by_mission = defaultdict(list)
    for name in disc.files:
        m = re.match(r"^(X\d+)_\d+\.BIN$", name)
        if m:
            by_mission[m.group(1)].append(name)

    data = {"game": "Metal Slug X (PS1 NTSC-U)", "tile": TILE, "missions": []}
    for short, display in MISSIONS:
        if only and short not in only:
            continue
        sections = sorted(by_mission.get(short, []))
        if not sections:
            continue
        base = f"{short}.BIN"
        art_files = ([base] if base in disc.files else []) + sections
        index = art_index(disc, art_files)
        entry = {"short": short, "name": display, "sections": []}
        for sec in sections:
            raw = disc.read_file(sec)
            ps = pieces(raw)
            if not ps:
                continue
            # pieces of one height are one layer of the stage and run left to
            # right in file order; the tallest layer is the playfield, shorter
            # ones are parallax and set dressing
            heights = sorted({p["h"] for p in ps}, reverse=True)
            band_of = {h: i for i, h in enumerate(heights)}
            sec_entry = {"file": sec,
                         "bands": [{"h": h * TILE} for h in heights],
                         "pieces": []}
            band_x = defaultdict(int)
            for i, p in enumerate(ps):
                vram = stage_vram(index, p["tiles"], prefer=[sec, base] + sections)
                img, W, H, drawn = render(vram, p)
                if not drawn:
                    continue
                rel = f"pieces/msx/{sec[:-4].lower()}_{i:02d}.png"
                write_png(out / rel, W, H, bytes(img), keep_alpha=True)
                b = band_of[p["h"]]
                sec_entry["pieces"].append({"png": rel, "w": W, "h": H,
                                            "tiles_w": p["w"], "tiles_h": p["h"],
                                            "band": b, "x": band_x[b]})
                band_x[b] += W
            if sec_entry["pieces"]:
                entry["sections"].append(sec_entry)
                print(f"  {sec}: {len(sec_entry['pieces'])} pieces")
        if entry["sections"]:
            data["missions"].append(entry)
            print(f"{short} ({display}): {len(entry['sections'])} sections")

    (out / "map_data_msx.json").write_text(json.dumps(data, indent=1))
    n = sum(len(s["pieces"]) for m in data["missions"] for s in m["sections"])
    print(f"\n{len(data['missions'])} missions, {n} pieces -> {out}/map_data_msx.json")


if __name__ == "__main__":
    main()
