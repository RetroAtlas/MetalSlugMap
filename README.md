# Metal Slug Map

An in-progress interactive map of the Metal Slug games on PlayStation, extracted straight from the game discs — starting with **Metal Slug X** (NTSC-U). Sister project to [Oddworld Map](https://oddworldmap.com/); same idea, a much harder game to extract.

**Status: early.** The stage artwork extracts cleanly today; the stage *layout* (how tiles assemble into each scrolling mission) and the *spawn tables* (POWs, food, weapon drops, hidden objects and branch triggers) are an ongoing reverse-engineering effort. There is no viewer yet — this repo currently holds the extraction tooling and its findings.

## What works now

Every mission file (`X1.BIN`, `X3.BIN`, `X51.BIN`, …) stores its stage art as raw, standard PS1 **TIM texture pages** — no custom compression. `tools/extract_art.py` lifts them to PNG:

```bash
python3 tools/extract_art.py --disc "/path/to/Metal Slug X.bin"          # all missions
python3 tools/extract_art.py --disc "/path/to/Metal Slug X.bin" --file X1.BIN
```

`--disc` can be omitted if `$METAL_SLUG_DISC` points at the image. Output lands in `out/` (git-ignored). Pages are written with palette 0 for now; true per-tile palette selection arrives with tilemap decoding.

## Roadmap

The map is being built as a **hybrid**, so there is something usable at every stage and each reverse-engineering win is an in-place quality upgrade rather than a rewrite:

1. **Art extraction** — done: texture pages come off the disc as PNG.
2. **Tilemap decoding** — reverse the per-mission layout (the large structured tail after the texture pages in each `X*.BIN`) to assemble full-stage panoramas, pixel-exact.
3. **Spawn tables** — reverse where POWs, items, hidden objects and branch triggers live, keyed to scroll position. This is the data that makes the map worth having, and the least documented.
4. **Viewer** — a data-driven map (each mission is one very wide scrolling stage) with search, permalinks and annotations, reusing the Oddworld Map architecture.

Unlike Oddworld — where a community decompilation ([alive_reversing](https://github.com/AliveTeam/alive_reversing)) handed us every structure — Metal Slug X has no such reference; the only ground truth is the disc and the game executable.

## Layout

- `tools/disc.py` — game-agnostic ISO9660 raw-sector disc reader.
- `tools/tim.py` — PS1 TIM image decoder.
- `tools/png.py` — dependency-free RGBA PNG writer.
- `tools/extract_art.py` — CLI that lifts mission texture pages to PNG.

## Naming

Every game-specific name carries its game prefix from day one (`msx` for Metal Slug X), leaving room for other Metal Slug titles (`ms1`, `ms2`, …) without renaming. No game owns the unsuffixed default.

## Licensing

Copyright (C) 2026 mariobob, under GPL-2.0 (see [LICENSE](LICENSE)), matching the sibling project. The tooling ships no game code; extracted imagery is © SNK and is intended for research and preservation.
