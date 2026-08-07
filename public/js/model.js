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

/** A section's pieces at the coordinates the builder solved, plus the shelf. */
export function layoutOf(section) {
  const stage = section.pieces.map((p) => ({ piece: p, x: p.x, y: p.y, layer: p.group }));

  let bottom = 0;
  for (const a of stage) bottom = Math.max(bottom, a.y + a.piece.h);
  const shelf = [];
  let sx = 0;
  const top = bottom + SHELF;
  for (const o of section.objects) {
    shelf.push({ piece: o, x: sx, y: top, object: true });
    sx += o.w + GAP;
  }
  return { stage, shelf };
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
          + `${s.groups.length} lanes ${s.pieces.length} pieces ${s.runs === 'v' ? 'upright' : 'sideways'}`,
      });
      s.pieces.forEach((p, i) => {
        out.push({
          kind: "piece",
          m,
          s,
          p,
          label: `${sectionName(s)} piece ${i + 1}`,
          hay: `${m.short} ${m.name} ${sectionName(s)} piece ${i + 1} `
            + `${p.tw}x${p.th} tiles ${p.w}x${p.h}px lane ${p.group} art ${p.art}`,
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
