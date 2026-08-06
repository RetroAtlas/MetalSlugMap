// Pan, zoom, hover inspect, click to select, and the keyboard.

import { pieceAt, sectionName } from "./model.js";
import { draw, exportPng } from "./render.js";
import { bump, focus, pushHash, stepSection } from "./navigate.js";
import { $, S, emit, toWorld } from "./state.js";

const cv = $("cv");
const tip = $("tip");

let drag = null;
let moved = 0;

cv.addEventListener("pointerdown", (e) => {
  drag = { x: e.clientX, y: e.clientY, cx: S.cam.x, cy: S.cam.y, id: e.pointerId };
  moved = 0;
  cv.setPointerCapture(e.pointerId);
  cv.classList.add("panning");
});

cv.addEventListener("pointermove", (e) => {
  if (drag && e.pointerId === drag.id) {
    moved += Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y);
    S.cam.x = drag.cx - (e.clientX - drag.x) / S.cam.z;
    S.cam.y = drag.cy - (e.clientY - drag.y) / S.cam.z;
    draw();
    return;
  }
  const r = cv.getBoundingClientRect();
  const w = toWorld(cv, e.clientX - r.left, e.clientY - r.top);
  const at = pieceAt(w.x, w.y);
  if (at !== S.hover) {
    S.hover = at;
    draw();
  }
  showTip(at, e.clientX - r.left, e.clientY - r.top);
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

const endDrag = () => {
  if (drag) pushHash(false);
  drag = null;
  cv.classList.remove("panning");
};
cv.addEventListener("pointerup", (e) => {
  if (drag && moved < 5) {
    const r = cv.getBoundingClientRect();
    const w = toWorld(cv, e.clientX - r.left, e.clientY - r.top);
    const at = pieceAt(w.x, w.y);
    S.selected = at;
    emit("selection-changed", at);
    draw();
  }
  endDrag();
});
cv.addEventListener("pointercancel", endDrag);
cv.addEventListener("pointerleave", () => {
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
