#!/usr/bin/env python3
"""Build the Metal Slug X map: render every stage piece and emit the viewer's data.

Replays each mission in load order, renders every tilemap against the video
memory that makes it coherent, works out which pieces join into a strip of
stage, and writes the PNGs plus `map_data_msx.json`.

    python3 tools/build_map.py --disc "Metal Slug X.bin"

--disc defaults to $METAL_SLUG_DISC_X. Output goes to public/ by default, which
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
from extract_art import page as art_page, palette_of
from render import TILE, best_state, draw
from section import load_order, pieces, stream
from vram import tim_records

MISSIONS = [
    ("X1", "Mission 1"),
    ("X21", "Mission 2-1"), ("X22", "Mission 2-2"), ("X23", "Mission 2-3"),
    ("X3", "Mission 3"),
    ("X4", "Mission 4"),
    ("X51", "Mission 5-1"), ("X52", "Mission 5-2"), ("X53", "Mission 5-3"),
    ("X61", "Mission 6-1"), ("X62", "Mission 6-2"), ("X63", "Mission 6-3"),
]

# the sprite banks worth cataloguing: the people and machines the missions run
# on, as opposed to the art gallery, the endings and the Combat School
BANKS = [
    ("Characters", ["STD00", "STD01", "STD02", "STD03", "STD04"]),
    ("Mummified", ["MUM01", "MUM02", "MUM03", "MUM04"]),
    ("Fat", ["FAT01", "FAT02", "FAT03", "FAT04"]),
    ("Vehicles", ["_VHIECLE"]),
]

JOIN = 8.0      # seam cost under which two pieces are one strip of stage
BREAK = 32      # pixels left between strips that do not join
FRAMES = 0.6    # cell agreement above which two pieces are frames of one object
UPRIGHT = 2.0   # how far vertical joins must outweigh horizontal to call a stage upright


def edge(vram, piece, side):
    """The colours along one edge of a piece: 'l', 'r', 't' or 'b'."""
    w, h, tiles, cells = piece["w"], piece["h"], piece["tiles"], piece["cells"]
    out = []

    def texel(cell, tx, ty):
        if cell >= len(tiles):
            return 0
        r = tiles[cell]
        i = vram.texel4(r["page_x"], r["page_y"], r["x"] + tx, r["y"] + ty)
        return vram.clut_colour(r["clut"], i) if i else 0

    if side in "lr":
        cx, tx = (0, 0) if side == "l" else (w - 1, TILE - 1)
        for cy in range(h):
            for ty in range(TILE):
                out.append(texel(cells[cy * w + cx], tx, ty))
    else:
        cy, ty = (0, 0) if side == "t" else (h - 1, TILE - 1)
        for cx in range(w):
            for tx in range(TILE):
                out.append(texel(cells[cy * w + cx], tx, ty))
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


def orientation(shot, live):
    """Which way this section's stage runs, decided by which edges actually meet.

    A street scrolls sideways and its chunks meet left to right; a pyramid
    interior scrolls upward and its chunks meet top to bottom. Counting the
    joins each direction affords tells the two apart — the pyramid offers
    dozens of vertical matches and no horizontal one.

    Sideways is the default and has to be beaten clearly, because a section of
    narrow same-width chunks throws off vertical matches whichever way it runs.
    """
    across = down = 0
    for i in live:
        for j in live:
            if i == j:
                continue
            a, b = shot[i], shot[j]
            if a["h"] == b["h"]:
                c = seam(a["r"], b["l"])
                across += c is not None and c < JOIN
            if a["w"] == b["w"]:
                c = seam(a["b"], b["t"])
                down += c is not None and c < JOIN
    return "v" if down > across * UPRIGHT else "h"


def assemble(shot, live, way):
    """Lay the stage pieces out along the axis the section runs on.

    Pieces that share the cross-axis size are one lane and run in file order,
    butted together where their facing edges meet and pushed apart where they
    do not. Order within a lane stays file order rather than the cheapest seam:
    a section's repeated wall chunks all match each other equally well, so the
    seams say a lane exists without saying how it is sequenced.

    Returns {index: (x, y, lane, joins)}.
    """
    lanes = defaultdict(list)
    for k in live:
        lanes[shot[k]["h"] if way == "h" else shot[k]["w"]].append(k)
    order = sorted(lanes.values(),
                   key=lambda ks: -sum(shot[k]["w" if way == "h" else "h"] for k in ks))

    out = {}
    cross = 0
    for lane, ks in enumerate(order):
        run = 0
        prev = None
        for k in ks:
            s = shot[k]
            cost = None if prev is None else seam(
                *((shot[prev]["r"], s["l"]) if way == "h" else (shot[prev]["b"], s["t"])))
            joins = cost is not None and cost < JOIN
            if prev is not None and not joins:
                run += BREAK
            out[k] = ((run, cross) if way == "h" else (cross, run)) + (lane, joins)
            run += s["w"] if way == "h" else s["h"]
            prev = k
        cross += (max(shot[k]["h"] for k in ks) if way == "h"
                  else max(shot[k]["w"] for k in ks)) + BREAK
    return out


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


def sprites(disc, out):
    """Lift the character, transformation and vehicle banks to PNG.

    These are plain TIM chains like the stage art, so a page comes off whole —
    a sheet of every frame the game animates. Cutting the individual frames out
    would need the assembly data in the `PL\\PAT*` files, which is not decoded.
    """
    (out / "sprites").mkdir(parents=True, exist_ok=True)
    banks = []
    for label, names in BANKS:
        for name in names:
            data = disc.read_file(name + ".BIN")
            pages = []
            palette = None
            for i, record in enumerate(tim_records(data)):
                palette = palette_of(record) or palette
                w, h, pixels = art_page(record, palette)
                rel = f"sprites/msx/{name.lower()}_{i:02d}.png"
                write_png(out / rel, w, h, pixels, keep_alpha=True)
                pages.append({"png": rel, "w": w, "h": h})
            if pages:
                banks.append({"group": label, "file": name + ".BIN", "pages": pages})
                print(f"  {name}: {len(pages)} sprite pages", flush=True)
    return banks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", default=os.environ.get("METAL_SLUG_DISC_X"),
                    help="raw PS1 disc image; defaults to $METAL_SLUG_DISC_X")
    ap.add_argument("--out", default="public", help="output directory")
    ap.add_argument("--missions", default="", help="comma list to limit (e.g. X1,X3)")
    args = ap.parse_args()
    if not args.disc:
        ap.error("no disc image: pass --disc or set $METAL_SLUG_DISC_X")

    disc = Disc(args.disc)
    only = {m.strip().upper() for m in args.missions.split(",") if m.strip()}
    out = Path(args.out)
    (out / "pieces").mkdir(parents=True, exist_ok=True)

    data = {"game": "Metal Slug X (PS1 NTSC-U)", "tile": TILE, "missions": [],
            "sprites": sprites(disc, out) if not only else []}
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
                                 fit=round(fit, 1),
                                 **{s: edge(vram, p, s) for s in "lrtb"}))

            sec = {"file": name, "step": name[len(short) + 1:-4],
                   "groups": [], "pieces": [], "objects": []}
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

            way = orientation(shot, stage_pieces) if stage_pieces else "h"
            placed = assemble(shot, stage_pieces, way)
            sec["runs"] = way
            spans = defaultdict(lambda: [0, 0])
            for k, (x, y, lane, _) in placed.items():
                spans[lane][0] = max(spans[lane][0], x + shot[k]["w"])
                spans[lane][1] = max(spans[lane][1], y + shot[k]["h"])
            for lane in sorted(spans):
                sec["groups"].append({"w": spans[lane][0], "h": spans[lane][1],
                                      "pieces": sum(1 for v in placed.values() if v[2] == lane)})
            for k in sorted(placed, key=lambda k: (placed[k][2], placed[k][1], placed[k][0])):
                x, y, lane, joins = placed[k]
                s = shot[k]
                sec["pieces"].append({"png": s["png"], "w": s["w"], "h": s["h"],
                                      "tw": s["tw"], "th": s["th"], "art": s["art"],
                                      "fit": s["fit"], "group": lane,
                                      "x": x, "y": y, "joins": joins})
            if sec["pieces"] or sec["objects"]:
                entry["sections"].append(sec)
                print(f"  {name}: {len(sec['pieces'])} pieces, "
                      f"{len(sec['objects'])} objects, {len(sec['groups'])} groups", flush=True)
        if entry["sections"]:
            data["missions"].append(entry)
            print(f"{short} ({display}): {len(entry['sections'])} sections", flush=True)

    (out / "map_data_msx.json").write_text(json.dumps(data, indent=1))
    n = sum(len(s["pieces"]) for m in data["missions"] for s in m["sections"])
    o = sum(len(s["objects"]) for m in data["missions"] for s in m["sections"])
    b = sum(len(k["pages"]) for k in data["sprites"])
    print(f"\n{len(data['missions'])} missions, {n} pieces, {o} objects, "
          f"{b} sprite pages -> {out}/map_data_msx.json")


if __name__ == "__main__":
    main()
