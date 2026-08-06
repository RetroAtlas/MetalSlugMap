// Turns the builder's data into laid-out world space, and indexes it for search.

import { GAP, S, SHELF } from "./state.js";

const images = {};

export function image(src, onload) {
  let im = images[src];
  if (!im) {
    im = new Image();
    im.src = src;
    im.onload = onload;
    images[src] = im;
  }
  return im;
}

export function sectionName(section) {
  return section.file.replace(/\.BIN$/, "");
}

/** Every layer of a section, its pieces already placed left to right. */
export function layoutOf(section) {
  const stage = [];
  let y = 0;
  section.layers.forEach((layer, depth) => {
    for (const p of section.pieces) {
      if (p.layer === depth) stage.push({ piece: p, x: p.x, y, layer: depth });
    }
    y += layer.h + GAP;
  });

  const shelf = [];
  let sx = 0;
  const top = y + SHELF;
  for (const o of section.objects) {
    shelf.push({ piece: o, x: sx, y: top, object: true });
    sx += o.w + 24;
  }
  return { stage, shelf };
}

/**
 * Where a background layer sits when layers are composited rather than stacked.
 *
 * A shorter layer covers the same stage in fewer pixels because it scrolls
 * slower, so stretching it back over the widest layer puts each of its pixels
 * at the place in the stage you actually see it, and the layers line up on the
 * ground rather than floating at their own tops.
 */
export function composite(section, depth) {
  const wide = Math.max(...section.layers.map((l) => l.w), 1);
  const tall = Math.max(...section.layers.map((l) => l.h), 1);
  const layer = section.layers[depth];
  return { scale: wide / (layer.w || 1), dy: tall - layer.h };
}

export function index(data) {
  const out = [];
  for (const m of data.missions) {
    for (const s of m.sections) {
      out.push({
        kind: "section",
        m,
        s,
        label: sectionName(s),
        hay: `${m.short} ${m.name} ${sectionName(s)} section ${s.step} `
          + `${s.layers.length} layers ${s.pieces.length} pieces`,
      });
      s.pieces.forEach((p, i) => {
        out.push({
          kind: "piece",
          m,
          s,
          p,
          label: `${sectionName(s)} piece ${i + 1}`,
          hay: `${m.short} ${m.name} ${sectionName(s)} piece ${i + 1} `
            + `${p.tw}x${p.th} tiles ${p.w}x${p.h}px layer ${p.layer} art ${p.art}`,
        });
      });
      s.objects.forEach((o, i) => {
        out.push({
          kind: "object",
          m,
          s,
          o,
          label: `${sectionName(s)} object ${i + 1}`,
          hay: `${m.short} ${m.name} ${sectionName(s)} object prop animated `
            + `${o.frames.length} frames ${o.tw}x${o.th} tiles ${o.w}x${o.h}px art ${o.art}`,
        });
      });
    }
  }
  return out;
}

export function stats(data) {
  let pieces = 0;
  let objects = 0;
  let frames = 0;
  let sections = 0;
  for (const m of data.missions) {
    for (const s of m.sections) {
      sections += 1;
      pieces += s.pieces.length;
      objects += s.objects.length;
      for (const o of s.objects) frames += o.frames.length;
    }
  }
  return { missions: data.missions.length, sections, pieces, objects, frames };
}

export function extent(section) {
  return Math.max(...section.layers.map((l) => l.w), 0);
}

export function pieceAt(wx, wy) {
  for (let i = S.layout.length - 1; i >= 0; i -= 1) {
    const a = S.layout[i];
    if (wx >= a.x && wx < a.x + a.piece.w && wy >= a.y && wy < a.y + a.piece.h) return a;
  }
  for (let i = S.objects.length - 1; i >= 0; i -= 1) {
    const a = S.objects[i];
    if (wx >= a.x && wx < a.x + a.piece.w && wy >= a.y && wy < a.y + a.piece.h) return a;
  }
  return null;
}
