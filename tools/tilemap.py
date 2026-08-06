"""Decode the stage tilemaps in Metal Slug X section files.

A tilemap section is an 8-byte header followed by a row-major grid of u16
tile indices:

    u32 @0   0x23, the section kind
    byte 4   width in tiles
    byte 5   height in tiles
    byte 6   tile width, 16 in every section seen so far
    byte 7   tile height, likewise

Each index selects a record of the tile list (`tools/tilelist.py`), which
carries the tile's source page, position in it, and palette — so the two
sections together describe a finished piece of stage. Index 0 is an empty
cell. A tilemap usually follows the tile list in the same file, but the kind
also appears standalone.
"""
import struct

KIND = 0x23
HEADER = 8


def find(data, start=0):
    """Locate a tilemap section at or after `start`; returns None if absent."""
    p = start
    while p + HEADER <= len(data) - 2:
        if (struct.unpack_from("<I", data, p)[0] == KIND
                and data[p + 6] == 16 and data[p + 7] == 16
                and data[p + 4] and data[p + 5]):
            w, h = data[p + 4], data[p + 5]
            if p + HEADER + w * h * 2 <= len(data):
                return dict(offset=p, w=w, h=h, tile_w=data[p + 6], tile_h=data[p + 7])
        p += 2
    return None


def cells(data, section):
    w, h = section["w"], section["h"]
    return struct.unpack_from(f"<{w * h}H", data, section["offset"] + HEADER)
