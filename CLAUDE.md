# CLAUDE.md

Guidance for AI agents working in this repo. Read [README.md](README.md) first for what the project is and where it stands; this file covers what is not obvious from the code and the traps found during reverse engineering. The sibling project [OddworldMap](https://github.com/MagogCartel/OddworldMap) is the model for where this is headed — its viewer is data-driven and most of it will be reusable once Metal Slug data is extracted.

## Where the data lives (Metal Slug X, NTSC-U, SLUS-012.12)

- Standard ISO9660 disc, raw 2352-byte Mode 2 sectors; `tools/disc.py` reads it with no game-specific logic.
- Missions are `X<n>.BIN` at the disc root: `X1`, `X3`, `X4` are missions; `X21/X22/X23`, `X51/X52/X53`, `X61/X62/X63` are the sub-stages of multi-part missions. `X09.BIN` yields no TIMs (different/compressed — unexamined). Each mission file is `[TIM texture pages][large structured tail]`.
- `X801.BIN` (30 MB) is **streamed media, not art** — starts with an audio sync header, entropy alternates ~0.5 and ~7.9 bits/byte across it (interleaved XA-ADPCM and/or MDEC video). Do not mistake it for a sprite bank.
- `SLUS_012.12` is the game executable (622 KB MIPS) — the only structural ground truth, since no decompilation of this port exists (unlike Oddworld's alive_reversing).

## Format gotchas (established so far)

- Stage art is **raw PS1 TIM** at the head of each mission file — 256x256 4-bit pages, each carrying a bank of 6-16 CLUTs (palettes) chosen per tile at draw time. No custom compression. `tools/tim.py` decodes 4/8/16-bit TIMs (RGB5551, `0x0000` = transparent).
- Because palette is per-tile (selected by the tilemap, not stored with the page), rendering a whole page with a single CLUT gives correct shapes but wrong colours for most tiles — expect a colour cast until the tilemap is decoded. This is not a bug.
- The mission-file tail (270-410 KB, entropy ~4.0 bits/byte) is structured binary: the tilemap that lays tiles into the scrolling stage, plus object/spawn tables. Not encrypted, not high-entropy-packed — decodable with effort. Its format is **not yet reversed**; that is the next milestone.
- Multi-part missions share a tail structure across their sub-stage files (`X51/X52/X53`) — diffing sub-stages of one mission is the fastest way into the layout format.

## Conventions (inherited from the sibling project)

- One concern per commit; split bundled diffs before committing.
- A user-facing or behaviour change ships its docs in the same commit — update README.md / this file as part of the same concern, not a follow-up.
- Prose files (README, docs, this file) are never manually line-wrapped — let lines run long.
- Code comments — default to none. A comment earns its place only by recording a durable *why* the code can't show: an invariant, a constraint, a non-obvious trade-off. Keep them generic enough that a routine change doesn't force a comment edit — put a per-item note *inline on the item*, never in a doc-comment that re-describes a set's members (that rots the moment you add one). Don't name consumers or other modules ("used by X", "the way the sibling project does"); don't narrate history ("was previously…"); don't restate a constant's value or units. Comment footprint matches code footprint. An absent comment never goes stale.
- No game owns unsuffixed defaults: everything game-specific carries its prefix (`msx`, later `ms1`/`ms2`) in files, identifiers and paths. Do not reintroduce unsuffixed names for Metal Slug X just because it came first.
- Tooling is dependency-free Python 3 (standard library only); `tools/png.py` is a minimal writer rather than a Pillow dependency.
