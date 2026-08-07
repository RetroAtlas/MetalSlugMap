// Shared viewer state, and the world <-> screen transforms everything draws with.

export const S = {
  data: null,
  mission: null,
  section: null,
  layout: [],        // [{piece, x, y, layer}] in world space
  objects: [],       // [{object, x, y}] laid out on the shelf below the stage
  cam: { x: 0, y: 0, z: 1 },
  hover: null,
  selected: null,
  show: {
    grid: true,
    labels: true,
    composite: false,
    objects: true,
    seams: true,
    dim: false,
    checker: false,
  },
};

export const GAP = 28;        // between stacked layers
export const SHELF = 56;      // between the stage and the object shelf

export const $ = (id) => document.getElementById(id);

export function toWorld(cv, sx, sy) {
  return { x: S.cam.x + sx / S.cam.z, y: S.cam.y + sy / S.cam.z };
}

export function bounds() {
  let w = 0;
  let h = 0;
  for (const a of S.layout.concat(S.objects)) {
    w = Math.max(w, a.x + a.piece.w);
    h = Math.max(h, a.y + a.piece.h);
  }
  return { w, h };
}

const listeners = {};
export function on(name, fn) {
  (listeners[name] ||= []).push(fn);
}
export function emit(name, detail) {
  for (const fn of listeners[name] || []) fn(detail);
}
