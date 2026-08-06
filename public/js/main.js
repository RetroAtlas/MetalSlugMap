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

  // each band is a layer laid left to right; bands stack tallest first
  const bandY = [];
  let y = 0;
  for (const b of s.bands || []) {
    bandY.push(y);
    y += b.h + GAP * 2;
  }
  layout = s.pieces.map((p) => ({ piece: p, x: p.x, y: bandY[p.band] || 0 }));

  const list = $("pieceList");
  list.innerHTML = "";
  layout.forEach((at, i) => {
    const b = document.createElement("button");
    const tag = at.piece.band === 0 ? "" : ` · layer ${at.piece.band}`;
    b.innerHTML = `${i + 1}. <span class="dim">${at.piece.tiles_w}×${at.piece.tiles_h} tiles · ${at.piece.w}×${at.piece.h}px${tag}</span>`;
    b.onclick = () => {
      [...list.children].forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      focus(at);
    };
    list.appendChild(b);
  });

  fit();
  scheduleHash(true);
  if (isMobile()) toggleMenu(false);
}

// ---- permalinks: #MISSION/section/x/y/zoom ------------------------------
let applyingHash = false;
let hashTimer = null;

function hashFor() {
  return `#${mission.short}/${section.file.replace(/\.BIN$/, "")}/${Math.round(cam.x)}/${Math.round(cam.y)}/${cam.z.toFixed(2)}`;
}

function scheduleHash(push) {
  if (applyingHash || !section) return;
  clearTimeout(hashTimer);
  hashTimer = setTimeout(() => {
    const h = hashFor();
    if (h === location.hash) return;
    if (push) location.hash = h;
    else history.replaceState(null, "", h);
  }, push ? 0 : 300);
}

function applyHash() {
  const m = location.hash.replace(/^#/, "").split("/");
  if (m.length < 2 || !data) return false;
  const mi = data.missions.find((x) => x.short === m[0].toUpperCase());
  if (!mi) return false;
  const sec = mi.sections.find((s) => s.file.replace(/\.BIN$/, "") === m[1]);
  if (!sec) return false;
  applyingHash = true;
  const mb = [...$("missionBtns").children].find((b) => b.textContent === mi.short);
  selectMission(mi, mb);
  const sb = [...$("sectionBtns").children].find((b) => b.title === sec.file);
  selectSection(sec, sb);
  if (m.length >= 5) {
    cam.x = +m[2];
    cam.y = +m[3];
    cam.z = Math.max(0.05, Math.min(8, +m[4]));
    camToken++;
  }
  applyingHash = false;
  draw();
  return true;
}

addEventListener("hashchange", () => { if (!applyingHash) applyHash(); });

let camToken = 0;   // bumped on explicit positioning so a deferred fit cannot stomp it

function fit() {
  if (!layout.length) return;
  const token = ++camToken;
  const attempt = () => {
    if (token !== camToken) return;
    if (!cv.clientWidth || !cv.clientHeight) { requestAnimationFrame(attempt); return; }
    const w = Math.max(...layout.map((a) => a.x + a.piece.w));
    const h = Math.max(...layout.map((a) => a.y + a.piece.h));
    cam.z = Math.min(cv.clientWidth / (w + 60), cv.clientHeight / (h + 60), 2);
    cam.x = -30;
    cam.y = -30;
    draw();
  };
  attempt();
}

function focus(at) {
  cam.z = Math.min(cv.clientWidth / (at.piece.w + 40), cv.clientHeight / (at.piece.h + 40), 3);
  cam.x = at.x + at.piece.w / 2 - cv.clientWidth / (2 * cam.z);
  cam.y = at.y + at.piece.h / 2 - cv.clientHeight / (2 * cam.z);
  camToken++;
  draw();
  scheduleHash(true);
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
const endDrag = () => { if (drag) scheduleHash(false); drag = null; cv.classList.remove("panning"); };
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
  camToken++;
  draw();
  scheduleHash(false);
}, { passive: false });

// ---- drawing ------------------------------------------------------------
function draw() {
  // a zero-width canvas has no layout yet; retry rather than skip the frame,
  // since an explicit camera (a permalink) cancels the pending fit that would
  // otherwise have redrawn
  if (!cv.clientWidth) { requestAnimationFrame(draw); return; }
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

// ---- search -------------------------------------------------------------
const searchInput = $("searchInput");
const searchResults = $("searchResults");
let searchTimer = null;

function runSearch(q) {
  searchResults.innerHTML = "";
  q = q.trim().toLowerCase();
  if (q.length < 1) return;
  const hits = [];
  for (const m of data.missions) {
    for (const s of m.sections) {
      const bands = (s.bands || []).length;
      const hay = `${m.short} ${m.name} ${s.file} ${bands} layers`.toLowerCase();
      if (hay.includes(q)) hits.push({ m, s });
    }
  }
  for (const h of hits.slice(0, 40)) {
    const b = document.createElement("button");
    const w = Math.max(...h.s.pieces.map((p) => p.x + p.w), 0);
    b.innerHTML = `<span class="loc">${h.m.short}</span> ${h.s.file.replace(/\.BIN$/, "")} <span class="dim">· ${h.s.pieces.length} pieces · ${w}px</span>`;
    b.onclick = () => {
      const mb = [...$("missionBtns").children].find((x) => x.textContent === h.m.short);
      selectMission(h.m, mb);
      const sb = [...$("sectionBtns").children].find((x) => x.title === h.s.file);
      selectSection(h.s, sb);
    };
    searchResults.appendChild(b);
  }
  const more = document.createElement("div");
  more.className = "more";
  more.textContent = hits.length ? `${hits.length} section${hits.length === 1 ? "" : "s"}` : "no matches";
  searchResults.appendChild(more);
}

searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => runSearch(searchInput.value), 150);
});
addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== searchInput) {
    e.preventDefault();
    searchInput.focus();
    searchInput.select();
  } else if (e.key === "Escape" && document.activeElement === searchInput) {
    searchInput.value = "";
    runSearch("");
    searchInput.blur();
  }
});

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
    if (!applyHash() && d.missions.length) selectMission(d.missions[0], bar.children[0]);
  })
  .catch(() => { $("gameName").textContent = "map data failed to load — serve this directory"; });
