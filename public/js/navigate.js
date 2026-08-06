// Selecting a mission, a section and a place in it — and putting that in the URL.

import { extent, layoutOf, sectionName } from "./model.js";
import { draw } from "./render.js";
import { $, S, emit } from "./state.js";

const cv = $("cv");
let camToken = 0;   // bumped on explicit positioning so a deferred fit cannot stomp it
let applying = false;
let timer = null;

export function selectMission(m) {
  S.mission = m;
  emit("mission-changed", m);
  if (m.sections.length) selectSection(m.sections[0]);
}

export function selectSection(s) {
  S.section = s;
  S.hover = null;
  S.selected = null;
  const { stage, shelf } = layoutOf(s);
  S.layout = stage;
  S.objects = shelf;
  emit("section-changed", s);
  fit();
  pushHash(true);
}

export function fit() {
  if (!S.layout.length && !S.objects.length) return;
  const token = ++camToken;
  const attempt = () => {
    if (token !== camToken) return;
    if (!cv.clientWidth || !cv.clientHeight) {
      requestAnimationFrame(attempt);
      return;
    }
    let w = 0;
    let h = 0;
    for (const a of S.layout.concat(S.objects)) {
      w = Math.max(w, a.x + a.piece.w);
      h = Math.max(h, a.y + a.piece.h);
    }
    S.cam.z = Math.min(cv.clientWidth / (w + 80), cv.clientHeight / (h + 80), 2);
    S.cam.x = -40;
    S.cam.y = -40;
    draw();
  };
  attempt();
}

export function focus(at, zoom) {
  const z = zoom
    ?? Math.min(cv.clientWidth / (at.piece.w + 60), cv.clientHeight / (at.piece.h + 60), 3);
  S.cam.z = Math.max(0.05, Math.min(8, z));
  S.cam.x = at.x + at.piece.w / 2 - cv.clientWidth / (2 * S.cam.z);
  S.cam.y = at.y + at.piece.h / 2 - cv.clientHeight / (2 * S.cam.z);
  S.selected = at;
  camToken += 1;
  draw();
  pushHash(true);
  emit("selection-changed", at);
}

export function stepSection(delta) {
  const list = S.mission.sections;
  const i = list.indexOf(S.section);
  const next = list[(i + delta + list.length) % list.length];
  if (next) selectSection(next);
}

// ---- permalinks: #MISSION/section/x/y/zoom ------------------------------
function hashFor() {
  return `#${S.mission.short}/${sectionName(S.section)}/${Math.round(S.cam.x)}`
    + `/${Math.round(S.cam.y)}/${S.cam.z.toFixed(2)}`;
}

export function pushHash(now) {
  if (applying || !S.section) return;
  clearTimeout(timer);
  timer = setTimeout(() => {
    const h = hashFor();
    if (h === location.hash) return;
    if (now) location.hash = h;
    else history.replaceState(null, "", h);
  }, now ? 0 : 300);
}

export function applyHash() {
  const parts = location.hash.replace(/^#/, "").split("/");
  if (parts.length < 2 || !S.data) return false;
  const m = S.data.missions.find((x) => x.short === parts[0].toUpperCase());
  if (!m) return false;
  const s = m.sections.find((x) => sectionName(x) === parts[1]);
  if (!s) return false;
  applying = true;
  selectMission(m);
  selectSection(s);
  if (parts.length >= 5) {
    S.cam.x = +parts[2];
    S.cam.y = +parts[3];
    S.cam.z = Math.max(0.05, Math.min(8, +parts[4]));
    camToken += 1;
  }
  applying = false;
  draw();
  return true;
}

export function copyLink() {
  const url = `${location.origin}${location.pathname}${hashFor()}`;
  return navigator.clipboard.writeText(url).then(() => url);
}

export function bump() {
  camToken += 1;
}

export function widthOf(section) {
  return extent(section);
}

addEventListener("hashchange", () => {
  if (!applying) applyHash();
});
