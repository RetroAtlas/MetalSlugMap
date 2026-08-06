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


def _valid_tilelist(data, p, count):
    """Records place 16x16 tiles, so both destinations are multiples of 16."""
    if not count or p + 8 + count * 8 > len(data):
        return False
    for i in range(0, min(count, 8)):
        o = p + 8 + i * 8
        if data[o] % 16 or data[o + 1] % 16 or struct.unpack_from("<H", data, o + 4)[0]:
            return False
    return True


def _valid_tilemap(data, p):
    if data[p + 6] != 16 or data[p + 7] != 16:
        return False
    w, h = data[p + 4], data[p + 5]
    if not (w and h) or p + 8 + w * h * 2 > len(data):
        return False
    cells = struct.unpack_from(f"<{w * h}H", data, p + 8)
    return max(cells) < 4096


def chunks(data):
    """Yield ('tilelist'|'tilemap', offset, info) for every chunk in the file.

    Chunks also sit after a file's leading TIM artwork, so the whole file is
    scanned rather than walked from the start; accepting a chunk skips its
    payload, which is what stops tile data from matching as a chunk itself.
    """
    p = 0
    while p + 8 <= len(data):
        kind = struct.unpack_from("<I", data, p)[0] & 0xFFFFFF  # top byte carries flags
        if kind == TILELIST:
            count = struct.unpack_from("<H", data, p + 4)[0]
            if _valid_tilelist(data, p, count):
                yield "tilelist", p, count
                p += 8 + count * 8
                continue
        elif kind == TILEMAP and _valid_tilemap(data, p):
            w, h = data[p + 4], data[p + 5]
            yield "tilemap", p, (w, h)
            p += 8 + w * h * 2
            continue
        p += 2


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
    """Return a piece per tilemap, paired with the tile list its indices mean.

    A tilemap usually follows its list, but some files put every tilemap first
    and the list after them, so a map with no list before it takes the next one.
    A file with no list at all yields nothing — its indices belong to a list
    that lives somewhere else.
    """
    found = list(chunks(data))
    lists = {}
    for kind, off, info in found:
        if kind == "tilelist":
            lists[off] = tile_list(data, off, info)
    if not lists:
        return []
    offsets = sorted(lists)

    out = []
    for kind, off, info in found:
        if kind != "tilemap":
            continue
        before = [o for o in offsets if o < off]
        tiles = lists[before[-1] if before else offsets[0]]
        w, h = info
        cells = struct.unpack_from(f"<{w * h}H", data, off + 8)
        out.append(dict(offset=off, w=w, h=h, cells=cells, tiles=tiles))
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
