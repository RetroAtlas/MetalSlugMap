# CLAUDE.md

Guidance for AI agents working in this repo. Read [README.md](README.md) first for what the project is and where it stands; this file covers what is not obvious from the code and the traps found during reverse engineering. The sibling project [OddworldMap](https://github.com/MagogCartel/OddworldMap) is the model for where this is headed — its viewer is data-driven and most of it will be reusable once Metal Slug data is extracted.

## Where the data lives (Metal Slug X, NTSC-U, SLUS-012.12)

- Standard ISO9660 disc, raw 2352-byte Mode 2 sectors; `tools/disc.py` reads it with no game-specific logic.
- `X<n>.BIN` is a mission's **base artwork**, nothing else: a chain of TIM records covering 99% of the file. `X1`, `X3`, `X4` are missions; `X21/X22/X23`, `X51/X52/X53`, `X61/X62/X63` are sub-stages of multi-part missions.
- `X<n>_<nn>.BIN` are the per-mission section files, 150 of them. Most (124) are more TIM artwork; 26 carry data. Their first bytes identify the kind: `22 03 00 00` a tile list, `23 00 00 00` and `00 00 55 00` unidentified tables, `70 51 45 53` (`pQES`) sequence data, and `27 bd ff d8`-style MIPS prologues mark **code overlays** (`X3_0801`, `X61_000`) — the game streams executable code per section, so behaviour is not all in the main executable.
- `X09.BIN` and `X801.BIN` are **streamed media, not art** — both start with an audio sync header, entropy alternating ~0.5 and ~7.9 bits/byte (interleaved XA-ADPCM and/or MDEC video). Do not mistake them for sprite banks.
- `SLUS_012.12` is the game executable (622 KB MIPS) — the only structural ground truth, since no decompilation of this port exists (unlike Oddworld's alive_reversing).

## Format gotchas (established so far)

- Artwork is **raw PS1 TIM**, no custom compression, and each record carries its own VRAM destination — a mission's art is reconstructed by replaying those uploads into a 1024x512 halfword VRAM (`tools/vram.py`), which is the state everything else addresses.
- **The TIM magic word is optional.** Only the first record in a file tends to carry `10 00 00 00`; the rest begin at the flag word. A scanner that requires the magic silently stops after one record — this hid 13 of X1.BIN's 17 pages at first. Validate records by their block lengths (`12 + w*h*2 == bnum`) instead.
- Pages are 256x256 4-bit **atlases**, not finished pictures: a page rendered straight from its TIM looks like scrambled fragments, and that is correct.
- A page's tiles each want a different palette, so a page carries a bank of 6-16 CLUTs and the assignment lives in a **tile list** (`tools/tilelist.py`, rendered by `tools/render_pages.py`): 8-byte records, 256 per page, that repaint the page tile by tile through the right CLUT. Destination equals source in raster order — verified 1024/1024 records — so a tile list composes *pages*, not levels. It is the only way to get true colours; a raw TIM read gives shapes under one palette's cast.
- **VRAM is time-dependent.** Section files upload over each other during play, so loading a mission's whole file set at once corrupts pages. A section's tile list can reference palettes uploaded by a *sibling* section (`X1_00`'s first page needs `X1_081`'s CLUTs at VRAM y 496), and which files are resident together is not yet known — pass art files explicitly with `--art` until it is.
- The **stage layout is still unfound**: no tilemap that arranges pages into a scrolling level has turned up yet. The candidates are the unidentified `23 00 00 00` / `00 00 55 00` tables, the region of a tile-list file past its records (X1_00's records stop at 1024 of 9378, and the remainder starts with a `23 00 00 00` header), and the code overlays. That is the next milestone.
- Multi-part missions share structure across their sub-stage files (`X51/X52/X53`) — diffing sub-stages of one mission is the fastest way into an unknown table.

## Conventions (inherited from the sibling project)

- One concern per commit; split bundled diffs before committing.
- A user-facing or behaviour change ships its docs in the same commit — update README.md / this file as part of the same concern, not a follow-up.
- Prose files (README, docs, this file) are never manually line-wrapped — let lines run long.
- Code comments — default to none. A comment earns its place only by recording a durable *why* the code can't show: an invariant, a constraint, a non-obvious trade-off. Keep them generic enough that a routine change doesn't force a comment edit — put a per-item note *inline on the item*, never in a doc-comment that re-describes a set's members (that rots the moment you add one). Don't name consumers or other modules ("used by X", "the way the sibling project does"); don't narrate history ("was previously…"); don't restate a constant's value or units. Comment footprint matches code footprint. An absent comment never goes stale.
- No game owns unsuffixed defaults: everything game-specific carries its prefix (`msx`, later `ms1`/`ms2`) in files, identifiers and paths. Do not reintroduce unsuffixed names for Metal Slug X just because it came first.
- Tooling is dependency-free Python 3 (standard library only); `tools/png.py` is a minimal writer rather than a Pillow dependency.
