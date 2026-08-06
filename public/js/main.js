// Metal Slug Map viewer: browse the stage pieces extracted from the disc.

const $ = (id) => document.getElementById(id);
const cv = $("cv");
const ctx = cv.getContext("2d");

const GAP = 24; // breathing room between stacked pieces
let data = null;
let mission = null;
let section = null;
let layout = [];                    // [{piece, x, y}] in world space
let cam = { x: 0, y: 0, z: 1 };
const images = {};

function image(src) {
  if (!images[src]) {
    const im = new Image();
    im.src = src;
    im.onload = draw;
    images[src] = im;
  }
  return images[src];
}

function resize() {
  cv.width = cv.clientWidth * devicePixelRatio;
  cv.height = cv.clientHeight * devicePixelRatio;
  draw();
}
addEventListener("resize", resize);

function isMobile() { return matchMedia("(max-width: 720px)").matches; }
function toggleMenu(open) {
  document.body.classList.toggle("menu-open", open ?? !document.body.classList.contains("menu-open"));
  resize();
}
$("menuBtn").onclick = () => toggleMenu();

// ---- selection ----------------------------------------------------------
function selectMission(m, btn) {
  mission = m;
  [...$("missionBtns").children].forEach((b) => b.classList.remove("on"));
  btn?.classList.add("on");
  const bar = $("sectionBtns");
  bar.innerHTML = "";
  m.sections.forEach((s) => {
    const b = document.createElement("button");
    b.textContent = s.file.replace(/\.BIN$/, "").replace(/^X\d+_/, "");
    b.title = s.file;
    b.onclick = () => selectSection(s, b);
    bar.appendChild(b);
  });
  if (m.sections.length) selectSection(m.sections[0], bar.children[0]);
}

function selectSection(s, btn) {
  section = s;
  [...$("sectionBtns").children].forEach((b) => b.classList.remove("on"));
  btn?.classList.add("on");

  // strip pieces form the continuous playfield; the rest stack beneath it
  const strip = s.pieces.filter((p) => p.strip);
  const rest = s.pieces.filter((p) => !p.strip);
  layout = strip.map((p) => ({ piece: p, x: p.x, y: 0 }));
  let y = (s.playfield_h || 0) + GAP * 2;
  for (const p of rest) {
    layout.push({ piece: p, x: 0, y });
    y += p.h + GAP;
  }

  const list = $("pieceList");
  list.innerHTML = "";
  layout.forEach((at, i) => {
    const b = document.createElement("button");
    const tag = at.piece.strip ? "" : " · layer";
    b.innerHTML = `${i + 1}. <span class="dim">${at.piece.tiles_w}×${at.piece.tiles_h} tiles · ${at.piece.w}×${at.piece.h}px${tag}</span>`;
    b.onclick = () => {
      [...list.children].forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      focus(at);
    };
    list.appendChild(b);
  });

  fit();
  if (isMobile()) toggleMenu(false);
}

function fit() {
  if (!layout.length) return;
  if (!cv.clientWidth || !cv.clientHeight) { requestAnimationFrame(fit); return; }
  const w = Math.max(...layout.map((a) => a.x + a.piece.w));
  const h = Math.max(...layout.map((a) => a.y + a.piece.h));
  cam.z = Math.min(cv.clientWidth / (w + 60), cv.clientHeight / (h + 60), 2);
  cam.x = -30;
  cam.y = -30;
  draw();
}

function focus(at) {
  cam.z = Math.min(cv.clientWidth / (at.piece.w + 40), cv.clientHeight / (at.piece.h + 40), 3);
  cam.x = at.x + at.piece.w / 2 - cv.clientWidth / (2 * cam.z);
  cam.y = at.y + at.piece.h / 2 - cv.clientHeight / (2 * cam.z);
  draw();
}

// ---- interaction --------------------------------------------------------
let drag = null;
cv.addEventListener("pointerdown", (e) => {
  drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, id: e.pointerId };
  cv.setPointerCapture(e.pointerId);
  cv.classList.add("panning");
});
cv.addEventListener("pointermove", (e) => {
  if (!drag || e.pointerId !== drag.id) return;
  cam.x = drag.cx - (e.clientX - drag.x) / cam.z;
  cam.y = drag.cy - (e.clientY - drag.y) / cam.z;
  draw();
});
const endDrag = () => { drag = null; cv.classList.remove("panning"); };
cv.addEventListener("pointerup", endDrag);
cv.addEventListener("pointercancel", endDrag);
cv.addEventListener("wheel", (e) => {
  e.preventDefault();
  const r = cv.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  const wx = cam.x + mx / cam.z, wy = cam.y + my / cam.z;
  cam.z = Math.min(8, Math.max(0.05, cam.z * Math.exp(-e.deltaY * 0.0015)));
  cam.x = wx - mx / cam.z;
  cam.y = wy - my / cam.z;
  draw();
}, { passive: false });

// ---- drawing ------------------------------------------------------------
function draw() {
  if (!cv.clientWidth) return;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--map-bg") || "#0e0f12";
  ctx.fillRect(0, 0, cv.clientWidth, cv.clientHeight);
  ctx.save();
  ctx.scale(cam.z, cam.z);
  ctx.translate(-cam.x, -cam.y);
  ctx.imageSmoothingEnabled = cam.z < 1;
  for (const at of layout) {
    const im = image(at.piece.png);
    if (im.complete && im.naturalWidth) ctx.drawImage(im, at.x, at.y);
    else {
      ctx.fillStyle = "#1a1d22";
      ctx.fillRect(at.x, at.y, at.piece.w, at.piece.h);
    }
  }
  ctx.restore();
  $("hud").textContent = section
    ? `${mission.name} · ${section.file} · ${layout.length} pieces · zoom ${cam.z.toFixed(2)}`
    : "";
}

// ---- boot ---------------------------------------------------------------
fetch("map_data_msx.json", { cache: "no-store" })
  .then((r) => r.json())
  .then((d) => {
    data = d;
    $("gameName").textContent = d.game;
    const bar = $("missionBtns");
    d.missions.forEach((m) => {
      const b = document.createElement("button");
      b.textContent = m.short;
      b.title = m.name;
      b.onclick = () => selectMission(m, b);
      bar.appendChild(b);
    });
    resize();
    if (d.missions.length) selectMission(d.missions[0], bar.children[0]);
  })
  .catch(() => { $("gameName").textContent = "map data failed to load — serve this directory"; });
