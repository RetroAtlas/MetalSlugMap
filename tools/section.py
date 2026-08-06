"""Walk a Metal Slug X section file as a chain of chunks, and stage its video memory.

A section file is a sequence of chunks, each identified by a u32 kind:

    0x322   tile list — u16 record count at +4, then 8-byte records
    0x23    tilemap   — width, height, tile size at +4, then u16 indices

A tilemap belongs to the nearest tile list before it, so one file holds several
pieces of stage. Chunks are halfword-aligned and the chain may be followed by
TIM artwork, which ends the walk.

Video memory is the hard part: sections stream art over each other while a
mission plays, so no single set of files is the state every tile list saw.
`stage_vram` sidesteps that by working backwards from a list's own references —
it takes only the pages and palettes that list addresses, from whichever file
supplies them — so nothing a list does not use can overwrite what it does.
"""
import struct

from vram import Vram, tim_records

TILELIST = 0x322
TILEMAP = 0x23
PAGE_W, PAGE_H = 64, 256


def chunks(data):
    """Yield ('tilelist'|'tilemap', offset, info) until the chain stops."""
    p = 0
    while p + 8 <= len(data):
        kind = struct.unpack_from("<I", data, p)[0]
        if kind == TILELIST:
            count = struct.unpack_from("<H", data, p + 4)[0]
            size = 8 + count * 8
            if not count or p + size > len(data):
                return
            yield "tilelist", p, count
        elif kind == TILEMAP and data[p + 6] == 16 and data[p + 7] == 16:
            w, h = data[p + 4], data[p + 5]
            size = 8 + w * h * 2
            if not (w and h) or p + size > len(data):
                return
            yield "tilemap", p, (w, h)
        elif data[p:p + 2] == b"\x00\x00":
            p += 2
            continue
        else:
            return
        p += size


def tile_list(data, offset, count):
    out = []
    for i in range(count):
        o = offset + 8 + i * 8
        x, y = data[o], data[o + 1]
        clut, _, tpage = struct.unpack_from("<HHH", data, o + 2)
        out.append(dict(x=x, y=y, clut=clut,
                        page_x=(tpage & 0xF) * 64, page_y=((tpage >> 4) & 1) * 256))
    return out


def pieces(data):
    """Return [(tilemap w, h, cells, tile list)] for every tilemap in the file."""
    out = []
    current = None
    for kind, off, info in chunks(data):
        if kind == "tilelist":
            current = tile_list(data, off, info)
        elif current:
            w, h = info
            cells = struct.unpack_from(f"<{w * h}H", data, off + 8)
            out.append(dict(offset=off, w=w, h=h, cells=cells, tiles=current))
    return out


def art_index(disc, names):
    """Map every VRAM block these files upload to the record that supplies it."""
    index = []
    for name in names:
        for r in tim_records(disc.read_file(name)):
            index.append((name, r))
    return index


def stage_vram(index, tiles, prefer=()):
    """Build video memory holding just the pages and palettes `tiles` reference."""
    pages = {(t["page_x"], t["page_y"]) for t in tiles}
    cluts = {((t["clut"] & 0x3F) * 16, t["clut"] >> 6) for t in tiles}
    rank = {name: i for i, name in enumerate(prefer)}

    def best(hits):
        return min(hits, key=lambda h: rank.get(h[0], len(rank)))[1] if hits else None

    vram = Vram()
    for px, py in pages:
        hits = [(n, r) for n, r in index
                if r["x"] <= px and px + PAGE_W <= r["x"] + r["w"]
                and r["y"] <= py and py + PAGE_H <= r["y"] + r["h"]]
        r = best(hits)
        if r:
            vram.blit(r["x"], r["y"], r["w"], r["h"], r["pixels"])
    for cx, cy in cluts:
        hits = []
        for n, r in index:
            c = r["clut"]
            if c and c[0] <= cx and cx + 16 <= c[0] + c[2] and c[1] <= cy < c[1] + c[3]:
                hits.append((n, r))
        r = best(hits)
        if r:
            c = r["clut"]
            vram.blit(c[0], c[1], c[2], c[3], c[4])
    return vram
