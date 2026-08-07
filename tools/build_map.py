#!/usr/bin/env python3
"""Build the Metal Slug X map: render every stage piece and emit the viewer's data.

Replays each mission in load order, renders every tilemap against the video
memory that makes it coherent, works out which pieces join into a strip of
stage, and writes the PNGs plus `map_data_msx.json`.

    python3 tools/build_map.py --disc "Metal Slug X.bin"

--disc defaults to $METAL_SLUG_DISC. Output goes to public/ by default, which
is what the viewer serves.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disc import Disc
from png import write_png
from render import TILE, best_state, draw
from section import load_order, pieces, stream

MISSIONS = [
    ("X1", "Mission 1"),
    ("X21", "Mission 2-1"), ("X22", "Mission 2-2"), ("X23", "Mission 2-3"),
    ("X3", "Mission 3"),
    ("X4", "Mission 4"),
    ("X51", "Mission 5-1"), ("X52", "Mission 5-2"), ("X53", "Mission 5-3"),
    ("X61", "Mission 6-1"), ("X62", "Mission 6-2"), ("X63", "Mission 6-3"),
]

JOIN = 8.0      # seam cost under which two pieces are one strip of stage
BREAK = 32      # pixels left between strips that do not join
FRAMES = 0.6    # cell agreement above which two pieces are frames of one object


def edge(vram, piece, side):
    """The colours down one vertical edge of a piece; side 0 left, 1 right."""
    w, h, tiles, cells = piece["w"], piece["h"], piece["tiles"], piece["cells"]
    cx = 0 if side == 0 else w - 1
    tx = 0 if side == 0 else TILE - 1
    out = []
    for cy in range(h):
        t = cells[cy * w + cx]
        if t >= len(tiles):
            out += [0] * TILE
            continue
        r = tiles[t]
        for ty in range(TILE):
            i = vram.texel4(r["page_x"], r["page_y"], r["x"] + tx, r["y"] + ty)
            out.append(vram.clut_colour(r["clut"], i) if i else 0)
    return out


def seam(a, b):
    """How badly two edges disagree; None when too little of either is solid.

    An edge that is opaque where its neighbour is clear is a hard mismatch, so
    those count separately from the colour distance between solid pixels.
    """
    total = solid = ragged = 0
    for p, q in zip(a, b):
        if bool(p) != bool(q):
            ragged += 1
        elif p:
            total += (abs((p & 31) - (q & 31)) + abs(((p >> 5) & 31) - ((q >> 5) & 31))
                      + abs(((p >> 10) & 31) - ((q >> 10) & 31)))
            solid += 1
    if solid < len(a) * 0.2:
        return None
    return total / solid + 20.0 * ragged / len(a)


def frames_of(a, b):
    """Share of cells two same-shaped pieces agree on."""
    if (a["w"], a["h"]) != (b["w"], b["h"]):
        return 0.0
    same = sum(1 for x, y in zip(a["cells"], b["cells"]) if x == y)
    return same / len(a["cells"])


def group(ps):
    """Split a file's pieces into animated objects and stage pieces.

    A prop is stored as its frames back to back — same shape, nearly the same
    cells — so a run of three or more that agree that closely is one object,
    not three pieces of stage.
    """
    runs = []
    i = 0
    while i < len(ps):
        j = i + 1
        while j < len(ps) and frames_of(ps[j - 1], ps[j]) >= FRAMES:
            j += 1
        runs.append((i, j, j - i >= 3))
        i = j
    return runs


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

    data = {"game": "Metal Slug X (PS1 NTSC-U)", "tile": TILE, "missions": []}
    for short, display in MISSIONS:
        if only and short not in only:
            continue
        names = load_order(disc, short)
        if len(names) < 2:
            continue
        states = [(n, v.copy(), later) for n, v, later in stream(disc, names)]
        entry = {"short": short, "name": display, "sections": []}
        for name in names:
            ps = pieces(disc.read_file(name))
            if not ps:
                continue
            stem = name[:-4].lower()
            shot = []
            for i, p in enumerate(ps):
                vram, art, fit = best_state(states, p)
                img, W, H, drawn = draw(vram, p)
                if not drawn:
                    shot.append(None)
                    continue
                rel = f"pieces/msx/{stem}_{i:02d}.png"
                write_png(out / rel, W, H, img, keep_alpha=True)
                shot.append(dict(png=rel, w=W, h=H, tw=p["w"], th=p["h"], art=art,
                                 fit=round(fit, 1), left=edge(vram, p, 0),
                                 right=edge(vram, p, 1)))

            sec = {"file": name, "step": name[len(short) + 1:-4],
                   "layers": [], "pieces": [], "objects": []}
            stage_pieces = []
            for a, b, animated in group(ps):
                live = [k for k in range(a, b) if shot[k]]
                if not live:
                    continue
                if animated:
                    sec["objects"].append({
                        "id": f"{stem}-{a:02d}",
                        "frames": [shot[k]["png"] for k in live],
                        "w": shot[live[0]]["w"], "h": shot[live[0]]["h"],
                        "tw": ps[a]["w"], "th": ps[a]["h"], "art": shot[live[0]]["art"]})
                else:
                    stage_pieces += live

            by_height = defaultdict(list)
            for k in stage_pieces:
                by_height[ps[k]["h"]].append(k)
            # a layer is every stage piece of one height, in the order the file
            # holds them; layers run widest first, the widest being the ground
            # the player walks and the narrower ones the parallax behind it
            layers = sorted(by_height.values(),
                            key=lambda ks: -sum(shot[k]["w"] for k in ks))
            for depth, ks in enumerate(layers):
                x = 0
                width = 0
                prev = None
                for k in ks:
                    s = shot[k]
                    cost = seam(prev["right"], s["left"]) if prev is not None else None
                    joins = cost is not None and cost < JOIN
                    if prev is not None and not joins:
                        x += BREAK
                    sec["pieces"].append({"png": s["png"], "w": s["w"], "h": s["h"],
                                          "tw": s["tw"], "th": s["th"], "art": s["art"],
                                          "fit": s["fit"], "layer": depth,
                                          "x": x, "joins": joins})
                    x += s["w"]
                    width = x
                    prev = s
                sec["layers"].append({"h": shot[ks[0]]["h"], "w": width})
            if sec["pieces"] or sec["objects"]:
                entry["sections"].append(sec)
                print(f"  {name}: {len(sec['pieces'])} pieces, "
                      f"{len(sec['objects'])} objects, {len(sec['layers'])} layers", flush=True)
        if entry["sections"]:
            data["missions"].append(entry)
            print(f"{short} ({display}): {len(entry['sections'])} sections", flush=True)

    (out / "map_data_msx.json").write_text(json.dumps(data, indent=1))
    n = sum(len(s["pieces"]) for m in data["missions"] for s in m["sections"])
    o = sum(len(s["objects"]) for m in data["missions"] for s in m["sections"])
    print(f"\n{len(data['missions'])} missions, {n} pieces, {o} objects "
          f"-> {out}/map_data_msx.json")


if __name__ == "__main__":
    main()
