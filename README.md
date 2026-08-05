# Metal Slug Map

An in-progress interactive map of the Metal Slug games on PlayStation, extracted straight from the game discs — starting with **Metal Slug X** (NTSC-U). Sister project to [Oddworld Map](https://oddworldmap.com/); same idea, a much harder game to extract.

**Status: early.** The stage artwork extracts cleanly today; the stage *layout* (how tiles assemble into each scrolling mission) and the *spawn tables* (POWs, food, weapon drops, hidden objects and branch triggers) are an ongoing reverse-engineering effort. There is no viewer yet — this repo currently holds the extraction tooling and its findings.

## What works now

Artwork is stored as raw, standard PS1 **TIM records** — no custom compression — each carrying its own video-memory destination. `tools/extract_art.py` lifts them straight to PNG:

```bash
python3 tools/extract_art.py --disc "/path/to/Metal Slug X.bin"          # all missions
python3 tools/extract_art.py --disc "/path/to/Metal Slug X.bin" --file X1.BIN
```

Those pages are 4-bit **atlases** whose tiles each want a different palette, so a raw page looks like scrambled fragments under one palette's colour cast. `tools/render_pages.py` fixes both: it rebuilds the game's video memory from a mission's art, then follows a section file's **tile list** — 8-byte records that repaint a page tile by tile through the correct palette — so pages come out in their true colours:

```bash
python3 tools/render_pages.py --disc "/path/to/Metal Slug X.bin" --section X1_00.BIN
```

`--disc` can be omitted if `$METAL_SLUG_DISC` points at the image. Output lands in `out/` (git-ignored).

## Roadmap

The map is being built as a **hybrid**, so there is something usable at every stage and each reverse-engineering win is an in-place quality upgrade rather than a rewrite:

1. **Art extraction** — done: texture pages come off the disc as PNG.
2. **Palette resolution** — done: tile lists give every tile its true colours.
3. **Stage layout** — open: no tilemap arranging pages into a scrolling level has turned up yet. The leads are catalogued in [CLAUDE.md](CLAUDE.md); note the game also streams MIPS **code overlays** per section, so some layout may be built by code rather than described by data.
4. **Spawn tables** — where POWs, items, hidden objects and branch triggers live, keyed to scroll position. This is the data that makes the map worth having, and the least documented.
5. **Viewer** — a data-driven map (each mission is one very wide scrolling stage) with search, permalinks and annotations, reusing the Oddworld Map architecture.

Unlike Oddworld — where a community decompilation ([alive_reversing](https://github.com/AliveTeam/alive_reversing)) handed us every structure — Metal Slug X has no such reference; the only ground truth is the disc and the game executable.

## Layout

- `tools/disc.py` — game-agnostic ISO9660 raw-sector disc reader.
- `tools/tim.py` — PS1 TIM image decoder.
- `tools/png.py` — dependency-free RGBA PNG writer.
- `tools/extract_art.py` — CLI that lifts mission texture pages to PNG.
- `tools/vram.py` — PS1 video-memory model: replays TIM uploads, reads texels through a CLUT.
- `tools/tilelist.py` — decodes the 8-byte tile-list records that assign each tile its palette.
- `tools/render_pages.py` — CLI that renders pages in their true colours.

## Naming

Every game-specific name carries its game prefix from day one (`msx` for Metal Slug X), leaving room for other Metal Slug titles (`ms1`, `ms2`, …) without renaming. No game owns the unsuffixed default.

## Licensing

Copyright (C) 2026 mariobob, under GPL-2.0 (see [LICENSE](LICENSE)), matching the sibling project. The tooling ships no game code; extracted imagery is © SNK and is intended for research and preservation.
