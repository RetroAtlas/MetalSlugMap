"""Draw a piece of Metal Slug X stage, and judge whether it came out right.

A tilemap only means something against the video memory the game held when it
was on screen, and that state is not recorded anywhere — sections stream art
over each other as a mission plays. `roughness` supplies the missing evidence:
tiles cut from one picture join seamlessly, so the state that makes a piece
smooth is the state it was drawn under.
"""
from section import stage

TILE = 16


def _tile(vram, r, cache):
    key = (r["page_x"], r["page_y"], r["x"], r["y"], r["clut"])
    got = cache.get(key)
    if got is None:
        px = []
        for ty in range(TILE):
            for tx in range(TILE):
                i = vram.texel4(r["page_x"], r["page_y"], r["x"] + tx, r["y"] + ty)
                px.append(vram.clut_colour(r["clut"], i) if i else 0)
        cache[key] = got = px
    return got


def _gap(a, b):
    return (abs((a & 31) - (b & 31)) + abs(((a >> 5) & 31) - ((b >> 5) & 31))
            + abs(((a >> 10) & 31) - ((b >> 10) & 31)))


def roughness(vram, piece):
    """Mean colour break across the seams inside a piece, and how many it found.

    Returns (break, seams). A piece rendered from the art it was cut from has a
    small break; one rendered from whatever else the page happens to hold is a
    mosaic of unrelated fragments, and breaks badly. The seam count guards the
    comparison: a page nothing has written to joins perfectly with nothing.
    """
    w, h, tiles, cells = piece["w"], piece["h"], piece["tiles"], piece["cells"]
    cache = {}
    total = pairs = 0
    for cy in range(h):
        for cx in range(w):
            t = cells[cy * w + cx]
            if t >= len(tiles):
                continue
            here = _tile(vram, tiles[t], cache)
            for dx, dy in ((1, 0), (0, 1)):
                if cx + dx >= w or cy + dy >= h:
                    continue
                u = cells[(cy + dy) * w + cx + dx]
                if u >= len(tiles):
                    continue
                there = _tile(vram, tiles[u], cache)
                for k in range(TILE):
                    a = here[k * TILE + TILE - 1] if dx else here[(TILE - 1) * TILE + k]
                    b = there[k * TILE] if dx else there[k]
                    if a and b:
                        total += _gap(a, b)
                        pairs += 1
    if not pairs:
        return 999.0, 0
    return total / pairs, pairs


def draw(vram, piece):
    """Render a piece to RGBA bytes; returns (pixels, width, height, tiles drawn)."""
    w, h, tiles, cells = piece["w"], piece["h"], piece["tiles"], piece["cells"]
    W, H = w * TILE, h * TILE
    img = bytearray(W * H * 4)
    cache = {}
    drawn = 0
    for cy in range(h):
        for cx in range(w):
            t = cells[cy * w + cx]
            if t >= len(tiles):
                continue
            px = _tile(vram, tiles[t], cache)
            hit = False
            for ty in range(TILE):
                o = ((cy * TILE + ty) * W + cx * TILE) * 4
                for tx in range(TILE):
                    c = px[ty * TILE + tx]
                    if not c:
                        continue
                    hit = True
                    r = (c & 31) << 3
                    g = ((c >> 5) & 31) << 3
                    b = ((c >> 10) & 31) << 3
                    img[o + tx * 4:o + tx * 4 + 4] = bytes(
                        (r | r >> 5, g | g >> 5, b | b >> 5, 255))
            drawn += hit
    return bytes(img), W, H, drawn


def _visible(vram, tiles):
    """Fingerprint the memory a tile list reads, so equal states collapse."""
    out = []
    for x, y in {(t["page_x"], t["page_y"]) for t in tiles}:
        rows = [vram.buf[((y + r) * 1024 + x) * 2:((y + r) * 1024 + x + 64) * 2]
                for r in range(0, 256, 16)]
        out.append(hash(b"".join(rows)))
    for x, y in {((t["clut"] & 0x3F) * 16, t["clut"] >> 6) for t in tiles}:
        out.append(hash(bytes(vram.buf[(y * 1024 + x) * 2:(y * 1024 + x + 16) * 2])))
    return out


def best_state(states, piece, tolerance=1.05):
    """Pick the point in a mission's load order that renders `piece` cleanest.

    Ties go to the earliest state, which is where the player meets the piece
    first; a state that finds far fewer seams than the best one is rejected, so
    a mostly-unwritten page cannot win by having nothing to break.

    Most of a mission's uploads land nowhere near any one piece, so states are
    collapsed by what the piece can actually see before any of them is scored.
    """
    scored = []
    seen = set()
    for name, vram, later in states:
        v = stage(vram, piece["tiles"], later)
        look = hash(tuple(sorted(_visible(v, piece["tiles"]))))
        if look in seen:
            continue
        seen.add(look)
        rough, seams = roughness(v, piece)
        scored.append((rough, seams, name, v))
    top = max(s for _, s, _, _ in scored)
    usable = [s for s in scored if s[1] >= top * 0.75] or scored
    floor = min(r for r, _, _, _ in usable)
    for rough, seams, name, v in usable:
        if rough <= floor * tolerance:
            return v, name, rough
    return usable[0][3], usable[0][2], usable[0][0]
