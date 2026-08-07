// Pan, zoom, hover inspect, click to select, and the keyboard.

import { pieceAt, sectionName } from "./model.js";
import { draw, exportPng } from "./render.js";
import { bump, focus, pushHash, stepSection } from "./navigate.js";
import { $, S, emit, toWorld } from "./state.js";

const cv = $("cv");
const tip = $("tip");
const PAGE_ZOOM_MIN = 1.02;   // a pinch settles a hair off 1, so 1 is not "unzoomed"

// The canvas takes touch gestures for itself, which would also swallow the
// pinch that ends a browser page zoom; while one is in effect it hands
// two-finger gestures back instead of zooming the map.
const vv = window.visualViewport;
let pageZoomed = false;
function syncPageZoom() {
  pageZoomed = vv.scale > PAGE_ZOOM_MIN;
  document.body.classList.toggle("page-zoomed", pageZoomed);
}
if (vv) {
  vv.addEventListener("resize", syncPageZoom);
  vv.addEventListener("scroll", syncPageZoom);
  syncPageZoom();
}

const pointers = new Map();   // live pointerId -> {x, y} in canvas space
let pan = null;
let moved = 0;
let pinch = 0;

function at(e) {
  const r = cv.getBoundingClientRect();
  return { x: e.clientX - r.left, y: e.clientY - r.top };
}

cv.addEventListener("pointerdown", (e) => {
  const p = at(e);
  pointers.set(e.pointerId, p);
  try {
    // capture would hold a touch pinch back from the browser, but a mouse drag
    // released off the canvas needs it to end at all
    if (!pageZoomed || e.pointerType !== "touch") cv.setPointerCapture(e.pointerId);
  } catch {
    /* pointer already lifted */
  }
  if (pointers.size === 1) {
    pan = { x: p.x, y: p.y, cx: S.cam.x, cy: S.cam.y };
    moved = 0;
    cv.classList.add("panning");
  } else if (pointers.size === 2) {
    pan = null;
    cv.classList.remove("panning");
    const [a, b] = pointers.values();
    pinch = Math.hypot(a.x - b.x, a.y - b.y);
  }
});

cv.addEventListener("pointermove", (e) => {
  const p = at(e);
  if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p);

  if (pointers.size >= 2) {
    const [a, b] = pointers.values();
    const dist = Math.hypot(a.x - b.x, a.y - b.y);
    if (pageZoomed) {
      pinch = dist;   // resuming from a stale baseline would jump the map
      return;
    }
    if (dist && pinch) zoomAt((a.x + b.x) / 2, (a.y + b.y) / 2, dist / pinch);
    pinch = dist;
    return;
  }

  if (pan) {
    moved += Math.abs(p.x - pan.x) + Math.abs(p.y - pan.y);
    S.cam.x = pan.cx - (p.x - pan.x) / S.cam.z;
    S.cam.y = pan.cy - (p.y - pan.y) / S.cam.z;
    draw();
    if (e.pointerType === "touch") tip.hidden = true;
    return;
  }
  if (e.pointerType === "touch") return;   // a finger has no hover to report

  const w = toWorld(cv, p.x, p.y);
  const hit = pieceAt(w.x, w.y);
  if (hit !== S.hover) {
    S.hover = hit;
    draw();
  }
  showTip(hit, p.x, p.y);
});

function showTip(at, sx, sy) {
  if (!at || S.show.composite) {
    tip.hidden = true;
    return;
  }
  const p = at.piece;
  const rows = at.object
    ? [
      ["kind", "animated object"],
      ["frames", p.frames.length],
      ["size", `${p.tw}×${p.th} tiles · ${p.w}×${p.h}px`],
      ["art", p.art],
    ]
    : [
      ["layer", p.layer === 0 ? "0 — playfield" : `${p.layer} — parallax`],
      ["size", `${p.tw}×${p.th} tiles · ${p.w}×${p.h}px`],
      ["at x", `${p.x}px`],
      ["joins left", p.joins ? "yes" : "no — separate strip"],
      ["art", `${p.art} (fit ${p.fit})`],
    ];
  tip.innerHTML = rows.map(([k, v]) => `<b>${k}</b><span>${v}</span>`).join("");
  tip.hidden = false;
  const box = tip.getBoundingClientRect();
  const r = cv.getBoundingClientRect();
  tip.style.left = `${Math.min(sx + 16, r.width - box.width - 8)}px`;
  tip.style.top = `${Math.min(sy + 16, r.height - box.height - 8)}px`;
}

function endPointer(e) {
  const p = pointers.get(e.pointerId);
  if (!pointers.delete(e.pointerId)) return;
  const tap = pointers.size === 0 && pan && moved < (e.pointerType === "mouse" ? 5 : 12);
  if (tap && p) {
    const w = toWorld(cv, p.x, p.y);
    const hit = pieceAt(w.x, w.y);
    S.selected = hit;
    emit("selection-changed", hit);
    draw();
  }
  if (pointers.size === 1) {
    // a pinch that lost a finger carries on as a pan from where the other is
    const [rest] = pointers.values();
    pan = { x: rest.x, y: rest.y, cx: S.cam.x, cy: S.cam.y };
    moved = 99;
    cv.classList.add("panning");
  } else if (!pointers.size) {
    if (pan && moved) pushHash(false);
    pan = null;
    cv.classList.remove("panning");
  }
}
cv.addEventListener("pointerup", endPointer);
cv.addEventListener("pointercancel", endPointer);
cv.addEventListener("pointerleave", () => {
  if (pointers.size) return;   // a captured drag only leaves after release
  tip.hidden = true;
  if (S.hover) {
    S.hover = null;
    draw();
  }
});

cv.addEventListener("wheel", (e) => {
  e.preventDefault();
  const r = cv.getBoundingClientRect();
  zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * 0.0015));
}, { passive: false });

function zoomAt(sx, sy, factor) {
  const w = toWorld(cv, sx, sy);
  S.cam.z = Math.min(8, Math.max(0.05, S.cam.z * factor));
  S.cam.x = w.x - sx / S.cam.z;
  S.cam.y = w.y - sy / S.cam.z;
  bump();
  draw();
  pushHash(false);
}

const TOGGLES = {
  g: "grid", l: "labels", p: "composite", o: "objects",
  s: "seams", d: "dim", t: "checker",
};

addEventListener("keydown", (e) => {
  const input = $("searchInput");
  if (document.activeElement === input) {
    if (e.key === "Escape") {
      input.value = "";
      input.blur();
      emit("search", "");
    }
    return;
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const pan = e.shiftKey ? 240 : 80;
  const moves = {
    ArrowLeft: [-pan, 0], ArrowRight: [pan, 0], ArrowUp: [0, -pan], ArrowDown: [0, pan],
  };
  if (moves[e.key]) {
    e.preventDefault();
    S.cam.x += moves[e.key][0] / S.cam.z;
    S.cam.y += moves[e.key][1] / S.cam.z;
    bump();
    draw();
    pushHash(false);
    return;
  }
  if (e.key === "/") {
    e.preventDefault();
    input.focus();
    input.select();
    return;
  }
  if (e.key === "+" || e.key === "=") {
    zoomAt(cv.clientWidth / 2, cv.clientHeight / 2, 1.25);
    return;
  }
  if (e.key === "-" || e.key === "_") {
    zoomAt(cv.clientWidth / 2, cv.clientHeight / 2, 0.8);
    return;
  }
  if (e.key === "[") { stepSection(-1); return; }
  if (e.key === "]") { stepSection(1); return; }
  if (e.key === "?") { emit("dialog", "shortcuts"); return; }
  if (e.key === "i") { emit("dialog", "place"); return; }
  if (e.key === "e") { exportPng(); return; }
  const t = TOGGLES[e.key.toLowerCase()];
  if (t) {
    S.show[t] = !S.show[t];
    emit("toggles-changed", t);
    draw();
  }
});

export function selectionLabel(at) {
  if (!at) return "";
  if (at.object) return `${sectionName(S.section)} object`;
  return `${sectionName(S.section)} · layer ${at.piece.layer}`;
}
