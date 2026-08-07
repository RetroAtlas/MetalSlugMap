# Metal Slug Map

An in-progress interactive map of the Metal Slug games on PlayStation, extracted straight from the game discs — starting with **Metal Slug X** (NTSC-U). Sister project to [Oddworld Map](https://oddworldmap.com/); same idea, a much harder game to extract.

**Status: usable.** Every stage piece in the game comes off the disc in its true colours, assembled along the axis its stage runs on, and browsable in the viewer. The two things the disc does not record — how far apart chunks sit, and where objects spawn — are answered as far as they can be: spacing is recovered by matching edges, and object placement turns out to be compiled into per-sub-stage code rather than stored, so there is nothing to extract.

## What works now

Artwork is stored as raw, standard PS1 **TIM records** — no custom compression — each carrying its own video-memory destination. `tools/extract_art.py` lifts them straight to PNG:

```bash
python3 tools/extract_art.py --disc "/path/to/Metal Slug X.bin"          # all missions
python3 tools/extract_art.py --disc "/path/to/Metal Slug X.bin" --file X1.BIN
```

Those pages are 4-bit **atlases** whose tiles each want a different palette, so a raw page looks like scrambled fragments under one palette's colour cast. Two more structures put them back together: a **tile list** defining each tile (its page, position and palette) and a **tilemap** placing those tiles into a piece of stage. `tools/render_map.py` follows both and draws the result:

```bash
python3 tools/render_map.py --disc "/path/to/Metal Slug X.bin" --section X1_00.BIN
python3 tools/render_map.py --disc "/path/to/Metal Slug X.bin" --section X23_00.BIN
```

Which artwork a tilemap means is the hard part, because sections stream art over each other as a mission plays and nothing on the disc records what was resident when. The tools replay each mission in its load order and pick, for every piece, the point where its tiles join most smoothly — tiles cut from one picture have no seams, so the state that renders a piece cleanly is the state it was drawn under. Every piece reports the file it settled on.

`tools/render_pages.py` renders the underlying pages themselves, in true colour, when you want the raw material rather than the assembled stage. `tools/extract_art.py` works on any file, not just the missions — the character and vehicle banks under `\PL` and `\STD` come off the same way.

## Browsing the map

`tools/build_map.py` renders every stage piece in the game and writes the viewer's data into `public/`:

```bash
python3 tools/build_map.py --disc "/path/to/Metal Slug X.bin"
python3 -m http.server 8479 -d public      # then open http://localhost:8479
```

That currently yields **219 stage pieces and 16 animated objects across all 12 missions**. Pick a mission, then a section: the builder works out whether the stage runs sideways or upright, lays its pieces along that axis in lanes, and butts them together where their edges actually match, leaving a marked break where they do not. Hover any piece to inspect it, click to pin its details, and press `?` for the shortcuts. On a touch screen, drag to pan, pinch to zoom and tap a piece for its details. Search covers sections, pieces and objects; the URL hash carries the current view, so a link reopens exactly what you were looking at.

The build also lifts the **sprite banks** — the four playable characters, their mummified and fat forms, and the vehicles — which browse under `SPR` alongside the missions. These are whole sheets of every animation frame, not individual cut-outs: the assembly data that would separate the frames lives in `\PL\PAT*.BIN` and is not decoded.

`--disc` can be omitted if `$METAL_SLUG_DISC` points at the image. `tools/render_map.py` writes single sections to `out/` (git-ignored) when you want the PNGs on their own.

## Roadmap

The map is being built as a **hybrid**, so there is something usable at every stage and each reverse-engineering win is an in-place quality upgrade rather than a rewrite:

1. **Art extraction** — done: texture pages come off the disc as PNG.
2. **Palette resolution** — done: tile lists give every tile its true colours.
3. **Stage layout** — done: tilemaps place tiles into stage sections, and each section renders end to end.
4. **Viewer** — browse by mission and section, pan and zoom, hover to inspect, click for details, toggle layers and overlays, export a view, search across sections, pieces and objects, and share any view by URL.
5. **Streaming order** — done: a section's number is a path through the stage, so sorting those numbers gives the order the game loads them, and each piece is rendered against the memory state where its tiles join. This is what took the artwork from plausible-looking mosaics to the real stages.
6. **Piece placement** — done as far as the disc allows. The arrangement is not stored anywhere, so it is measured: chunks cut from one picture still meet cleanly, and counting which way they meet tells a street that scrolls sideways from a pyramid interior that climbs. Pieces run along that axis, butted together where their edges match and separated by a marked break where they do not.
7. **Spawn tables** — answered, and the answer is that there are none. The last unidentified files on the disc, the per-sub-stage `ST*` family, turned out to be MIPS code: every one of them is an overlay of object behaviour, confirmed by disassembling it at the load address the executable's own asset manifest gives. Metal Slug X places its objects in compiled code, not in a table, so POWs, items and enemies cannot be lifted the way Oddworld's TLVs were. See [CLAUDE.md](CLAUDE.md) for the test that settles it.

Unlike Oddworld — where a community decompilation ([alive_reversing](https://github.com/AliveTeam/alive_reversing)) handed us every structure — Metal Slug X has no such reference; the only ground truth is the disc and the game executable.

## Layout

- `tools/disc.py` — game-agnostic ISO9660 raw-sector disc reader.
- `tools/tim.py` — PS1 TIM image decoder.
- `tools/png.py` — dependency-free RGBA PNG writer.
- `tools/extract_art.py` — CLI that lifts mission texture pages to PNG.
- `tools/vram.py` — PS1 video-memory model: replays TIM uploads, reads texels through a CLUT.
- `tools/tilelist.py` — decodes the tile list: each tile's source page, position and palette.
- `tools/tilemap.py` — decodes the stage tilemap: a grid of tile indices.
- `tools/render_pages.py` — CLI that renders pages in their true colours.
- `tools/section.py` — finds a file's tile lists and tilemaps, and replays a mission's video memory in load order.
- `tools/render.py` — draws a piece, and scores how well it came out so the right memory state can be chosen.
- `tools/render_map.py` — CLI that renders one section's pieces.
- `tools/mips.py` — MIPS disassembler for the executable and the code overlays.
- `tools/manifest.py` — dumps the executable's asset manifest: every file's load address, and whether it is code.
- `tools/build_map.py` — CLI that renders every piece in the game and emits the viewer's data.
- `public/` — the viewer: `index.html`, `css/main.css`, the ES modules under `js/`, plus the generated `map_data_msx.json` and `pieces/msx/`.

## Naming

Every game-specific name carries its game prefix from day one (`msx` for Metal Slug X), leaving room for other Metal Slug titles (`ms1`, `ms2`, …) without renaming. No game owns the unsuffixed default.

## Licensing

Copyright (C) 2026 mariobob, under GPL-2.0 (see [LICENSE](LICENSE)), matching the sibling project. The tooling ships no game code; extracted imagery is © SNK and is intended for research and preservation.
