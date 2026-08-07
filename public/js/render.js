// Draws the map: stage layers, the object shelf, and the overlays on top.

import { composite, image, sectionName } from "./model.js";
import { $, S, bounds } from "./state.js";

const cv = $("cv");
const ctx = cv.getContext("2d");
let frame = 0;
let pending = false;

export function draw() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(paint);
}

export function resize() {
  cv.width = cv.clientWidth * devicePixelRatio;
  cv.height = cv.clientHeight * devicePixelRatio;
  draw();
}

function css(name, fallback) {
  return getComputedStyle(document.body).getPropertyValue(name).trim() || fallback;
}

function checkerboard() {
  const c = document.createElement("canvas");
  c.width = 16;
  c.height = 16;
  const g = c.getContext("2d");
  g.fillStyle = "#191c22";
  g.fillRect(0, 0, 16, 16);
  g.fillStyle = "#1f232b";
  g.fillRect(0, 0, 8, 8);
  g.fillRect(8, 8, 8, 8);
  return ctx.createPattern(c, "repeat");
}
let checker = null;

function paint() {
  pending = false;
  // a canvas with no layout yet has nothing to scale to; retry rather than
  // skip, since an explicit camera cancels the fit that would have redrawn
  if (!cv.clientWidth || !cv.clientHeight) {
    requestAnimationFrame(paint);
    return;
  }
  const { cam, layout, objects, show } = S;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  ctx.fillStyle = css("--map-bg", "#0e0f12");
  ctx.fillRect(0, 0, cv.clientWidth, cv.clientHeight);

  if (show.checker) {
    checker ||= checkerboard();
    ctx.save();
    ctx.fillStyle = checker;
    ctx.fillRect(0, 0, cv.clientWidth, cv.clientHeight);
    ctx.restore();
  }

  ctx.save();
  ctx.scale(cam.z, cam.z);
  ctx.translate(-cam.x, -cam.y);
  ctx.imageSmoothingEnabled = cam.z < 1;

  const deepest = S.section ? S.section.layers.length - 1 : 0;
  const order = show.composite
    ? [...layout].sort((a, b) => b.layer - a.layer)
    : layout;

  for (const at of order) {
    const im = image(at.piece.png, draw);
    ctx.save();
    if (show.composite) {
      const { scale, dy } = composite(S.section, at.layer);
      ctx.translate(0, dy);
      ctx.scale(scale, 1);
    }
    if (show.dim && at.layer !== 0) ctx.globalAlpha = 0.45;
    const x = show.composite ? at.piece.x : at.x;
    const y = show.composite ? 0 : at.y;
    if (im.complete && im.naturalWidth) ctx.drawImage(im, x, y);
    else {
      ctx.fillStyle = "#1a1d22";
      ctx.fillRect(x, y, at.piece.w, at.piece.h);
    }
    ctx.restore();
  }

  if (show.objects && objects.length) {
    frame = Math.floor(performance.now() / 180);
    const px = 1 / cam.z;
    for (const at of objects) {
      ctx.fillStyle = "rgba(255,255,255,.045)";
      ctx.fillRect(at.x - 6, at.y - 6, at.piece.w + 12, at.piece.h + 12);
      const f = at.piece.frames[frame % at.piece.frames.length];
      const im = image(f, draw);
      if (im.complete && im.naturalWidth) ctx.drawImage(im, at.x, at.y);
      ctx.strokeStyle = "rgba(143,208,255,.35)";
      ctx.lineWidth = px;
      ctx.strokeRect(at.x - 6, at.y - 6, at.piece.w + 12, at.piece.h + 12);
    }
  }

  if (show.grid && !show.composite) outlines(deepest);
  if (show.objects) shelfLabels();
  marker(S.selected, css("--accent", "#e8a33d"), 2);
  marker(S.hover, "#8fd0ff", 1.5);
  ctx.restore();

  hud();
  // the object shelf animates, so it drives its own frames; a hidden tab has
  // nobody watching them
  if (show.objects && objects.length && !document.hidden && !animating) {
    animating = setTimeout(() => {
      animating = null;
      draw();
    }, 180);
  }
}
let animating = null;
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) draw();
});

function outlines() {
  const px = 1 / S.cam.z;
  ctx.lineWidth = px;
  for (const at of S.layout) {
    ctx.strokeStyle = at.layer === 0 ? "rgba(232,163,61,.45)" : "rgba(140,150,170,.30)";
    ctx.strokeRect(at.x + px / 2, at.y + px / 2, at.piece.w - px, at.piece.h - px);
    if (S.show.seams && !at.piece.joins && at.piece.x > 0) {
      ctx.strokeStyle = "rgba(255,120,120,.55)";
      ctx.setLineDash([6 * px, 4 * px]);
      ctx.beginPath();
      ctx.moveTo(at.x - 8, at.y);
      ctx.lineTo(at.x - 8, at.y + at.piece.h);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
  if (S.show.labels && S.cam.z > 0.45) {
    ctx.font = `${11 / S.cam.z}px -apple-system, "Segoe UI", sans-serif`;
    ctx.textBaseline = "top";
    for (const at of S.layout) {
      const t = `${at.piece.tw}×${at.piece.th}`;
      ctx.fillStyle = "rgba(10,11,14,.7)";
      const w = ctx.measureText(t).width + 6 / S.cam.z;
      ctx.fillRect(at.x + 2 / S.cam.z, at.y + 2 / S.cam.z, w, 14 / S.cam.z);
      ctx.fillStyle = "rgba(220,225,235,.9)";
      ctx.fillText(t, at.x + 5 / S.cam.z, at.y + 4 / S.cam.z);
    }
  }
}

function shelfLabels() {
  if (!S.objects.length || S.cam.z < 0.3) return;
  ctx.font = `${11 / S.cam.z}px -apple-system, "Segoe UI", sans-serif`;
  ctx.textBaseline = "bottom";
  ctx.fillStyle = "rgba(160,170,190,.85)";
  for (const at of S.objects) {
    ctx.fillText(`${at.piece.frames.length}f`, at.x, at.y - 4 / S.cam.z);
  }
}

function marker(at, colour, width) {
  if (!at) return;
  ctx.strokeStyle = colour;
  ctx.lineWidth = width / S.cam.z;
  ctx.strokeRect(at.x, at.y, at.piece.w, at.piece.h);
}

function hud() {
  if (!S.section) {
    $("hud").textContent = "";
    return;
  }
  const b = bounds();
  const parts = [
    S.mission.name,
    sectionName(S.section),
    `${S.section.pieces.length} pieces`,
  ];
  if (S.section.objects.length) parts.push(`${S.section.objects.length} objects`);
  parts.push(`${b.w}×${b.h}px`, `zoom ${S.cam.z.toFixed(2)}`);
  $("hud").textContent = parts.join(" · ");
}

export function exportPng() {
  const link = document.createElement("a");
  link.download = `${sectionName(S.section)}.png`;
  link.href = cv.toDataURL("image/png");
  link.click();
}
