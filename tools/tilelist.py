"""Decode the tile lists found in Metal Slug X section files (X<mission>_<nn>.BIN).

A tile list opens with an 8-byte header and continues as 8-byte records, each a
compact PS1 sprite primitive drawing one 16x16 tile:

    byte 0   destination X, a multiple of 16
    byte 1   destination Y, a multiple of 16
    u16 @2   CLUT id — VRAM ((id & 0x3F) * 16, id >> 6)
    u16 @4   zero in every record seen so far
    u16 @6   texture page in the low nibble (VRAM X = nibble * 64), bit 4 the
             Y half; the top two bits index the 256-record block

Records run in raster order and their destination equals their source, so a
block of 256 records repaints one 256x256 texture page in place. The point is
the CLUT: a page is a 4-bit atlas whose tiles each want a different palette, so
the list is what assigns them. Following it is the only way to get a page's
true colours — reading the raw TIM gives shapes with one palette's cast.

This is not a stage layout: it composes pages, not levels.
"""
import struct

RECORD = 8
HEADER = 8
TILE = 16
BLOCK = 256


def records(data):
    """Yield tile records, stopping where the run stops looking like one."""
    for i in range((len(data) - HEADER) // RECORD):
        o = HEADER + i * RECORD
        x, y = data[o], data[o + 1]
        clut, unused, tpage = struct.unpack_from("<HHH", data, o + 2)
        if x % TILE or y % TILE or unused:
            return
        yield dict(index=i, x=x, y=y, clut=clut, tpage=tpage,
                   page_x=(tpage & 0xF) * 64, page_y=((tpage >> 4) & 1) * 256,
                   block=tpage >> 14)


def render(vram, recs, size=BLOCK):
    """Draw records into an RGBA buffer, each tile through its own CLUT."""
    img = bytearray(size * size * 4)
    for r in recs:
        for ty in range(TILE):
            py = r["y"] + ty
            if py >= size:
                continue
            for tx in range(TILE):
                px = r["x"] + tx
                if px >= size:
                    continue
                idx = vram.texel4(r["page_x"], r["page_y"], px, py)
                if not idx:
                    continue
                col = vram.clut_colour(r["clut"], idx)
                if not col:
                    continue
                red = (col & 0x1F) << 3
                grn = ((col >> 5) & 0x1F) << 3
                blu = ((col >> 10) & 0x1F) << 3
                o = (py * size + px) * 4
                img[o:o + 4] = bytes((red | red >> 5, grn | grn >> 5, blu | blu >> 5, 255))
    return img
