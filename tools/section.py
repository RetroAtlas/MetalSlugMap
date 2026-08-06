"""Walk a Metal Slug X section file as a chain of chunks, and stage its video memory.

A section file is a sequence of chunks, each identified by a u32 kind:

    0x322   tile list — u16 record count at +4, then 8-byte records
    0x23    tilemap   — width, height, tile size at +4, then u16 indices

A tilemap belongs to the nearest tile list before it, so one file holds several
pieces of stage. Chunks are halfword-aligned and the chain may be followed by
TIM artwork, which ends the walk.

Video memory is the hard part: sections stream art over each other while a
mission plays, so no single set of files is the state every tile list saw.
`stream` replays a mission in load order and hands each file the memory it
actually finds, which is the only state its tile list means anything against.
"""
import re
import struct

from vram import Vram, tim_records

TILELIST = 0x322
TILEMAP = 0x23
PAGE_W, PAGE_H = 64, 256
CLUT_W = 16


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


def load_order(disc, mission):
    """A mission's files in the order the game streams them.

    A section's number is a path through the stage — `04` opens the step that
    `040`..`043` scroll through — so ordering the numbers as text is the order
    the player reaches them. The mission's own file is the art they start on.
    """
    base = f"{mission}.BIN"
    sections = sorted(n for n in disc.files if re.fullmatch(rf"{mission}_\d+\.BIN", n))
    return ([base] if base in disc.files else []) + sections


def stream(disc, names):
    """Yield (name, vram, later) with memory as each file in turn finds it.

    `later` is every upload still ahead in the order, which `stage` draws on
    for a page the mission has not written by this point.
    """
    records = {n: tim_records(disc.read_file(n)) for n in names}
    vram = Vram()
    for i, name in enumerate(names):
        for r in records[name]:
            vram.upload(r)
        yield name, vram, [r for n in names[i + 1:] for r in records[n]]


def _crop(blob, stride, ox, oy, w, h):
    out = bytearray()
    for row in range(h):
        off = ((oy + row) * stride + ox) * 2
        out += blob[off:off + w * 2]
    return bytes(out)


def _page_fill(records, x, y):
    for r in records:
        if (r["x"] <= x and x + PAGE_W <= r["x"] + r["w"]
                and r["y"] <= y and y + PAGE_H <= r["y"] + r["h"]):
            return x, y, PAGE_W, PAGE_H, _crop(r["pixels"], r["w"], x - r["x"], y - r["y"],
                                               PAGE_W, PAGE_H)
    return None


def _clut_fill(records, x, y):
    for r in records:
        c = r["clut"]
        if c and c[0] <= x and x + CLUT_W <= c[0] + c[2] and c[1] <= y < c[1] + c[3]:
            return x, y, CLUT_W, 1, _crop(c[4], c[2], x - c[0], y - c[1], CLUT_W, 1)
    return None


def stage(vram, tiles, later):
    """Memory as this tile list needs it, filling only what is still unwritten.

    A list can address art the mission streams in after it, so anything no
    upload has reached yet is taken from the next file that supplies it. Blocks
    already written stand: they are what this point in the mission really holds.
    """
    fills = []
    for x, y in {(t["page_x"], t["page_y"]) for t in tiles}:
        if vram.blank(x, y, PAGE_W, PAGE_H):
            fills.append(_page_fill(later, x, y))
    for x, y in {((t["clut"] & 0x3F) * CLUT_W, t["clut"] >> 6) for t in tiles}:
        if vram.blank(x, y, CLUT_W, 1):
            fills.append(_clut_fill(later, x, y))
    fills = [f for f in fills if f]
    if not fills:
        return vram
    patched = vram.copy()
    for f in fills:
        patched.blit(*f)
    return patched
