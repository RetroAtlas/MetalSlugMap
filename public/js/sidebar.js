// The sidebar: mission and section pickers, display toggles, piece and object lists.

import { sectionName } from "./model.js";
import { focus, selectMission, selectSection } from "./navigate.js";
import { draw } from "./render.js";
import { $, S, emit, on } from "./state.js";

const LABELS = {
  grid: "Piece outlines", labels: "Size labels (zoomed)",
  objects: "Animated objects",
  seams: "Mark broken joins", dim: "Dim secondary lanes",
  checker: "Transparency checkerboard",
};
const KEYS = { grid: "g", labels: "l", objects: "o", seams: "s", dim: "d", checker: "t" };

export function buildMissionBar() {
  const bar = $("missionBtns");
  bar.innerHTML = "";
  for (const m of S.data.missions) {
    const b = document.createElement("button");
    b.textContent = m.short;
    b.title = m.name;
    b.onclick = () => selectMission(m);
    bar.appendChild(b);
  }
}

export function buildToggles() {
  const box = $("toggles");
  box.innerHTML = "";
  for (const key of Object.keys(LABELS)) {
    const label = document.createElement("label");
    label.className = "checkrow";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.autocomplete = "off";
    input.checked = S.show[key];
    input.onchange = () => {
      S.show[key] = input.checked;
      draw();
    };
    label.append(input, ` ${LABELS[key]} `);
    const kbd = document.createElement("kbd");
    kbd.textContent = KEYS[key];
    label.append(kbd);
    box.appendChild(label);
  }
}

function syncToggles() {
  [...$("toggles").querySelectorAll("input")].forEach((input, i) => {
    input.checked = S.show[Object.keys(LABELS)[i]];
  });
}

function mark(bar, want) {
  [...bar.children].forEach((b) => b.classList.toggle("on", b.dataset.key === want));
}

on("mission-changed", (m) => {
  [...$("missionBtns").children].forEach((b) => b.classList.toggle("on", b.textContent === m.short));
  const bar = $("sectionBtns");
  bar.innerHTML = "";
  for (const s of m.sections) {
    const b = document.createElement("button");
    b.textContent = s.step;
    b.title = `${s.file} — ${s.pieces.length} pieces, ${s.groups.length} lanes`;
    b.dataset.key = s.file;
    b.onclick = () => selectSection(s);
    bar.appendChild(b);
  }
});

on("section-changed", (s) => {
  mark($("sectionBtns"), s.file);
  const list = $("pieceList");
  list.innerHTML = "";
  S.layout.forEach((at, i) => {
    const b = document.createElement("button");
    const tag = at.piece.group === 0 ? "main lane" : `lane ${at.piece.group}`;
    const join = at.piece.joins || !at.piece.x ? "" : " · break";
    b.innerHTML = `${i + 1}. <span class="dim">${at.piece.tw}×${at.piece.th} tiles · ${tag}${join}</span>`;
    b.dataset.key = at.piece.png;
    b.onclick = () => focus(at);
    list.appendChild(b);
  });

  const objects = $("objectList");
  objects.innerHTML = "";
  $("objectHead").hidden = !S.objects.length;
  S.objects.forEach((at, i) => {
    const b = document.createElement("button");
    b.innerHTML = `${i + 1}. <span class="dim">${at.piece.frames.length} frames · `
      + `${at.piece.tw}×${at.piece.th} tiles</span>`;
    b.dataset.key = at.piece.id;
    b.onclick = () => focus(at);
    objects.appendChild(b);
  });
});

on("selection-changed", (at) => {
  const key = at ? (at.object ? at.piece.id : at.piece.png) : null;
  for (const id of ["pieceList", "objectList"]) {
    [...$(id).children].forEach((b) => b.classList.toggle("on", b.dataset.key === key));
  }
  const panel = $("placePanel");
  if (!at) {
    panel.hidden = true;
    return;
  }
  const p = at.piece;
  const rows = at.object
    ? [["Kind", "Animated object"], ["Frames", p.frames.length],
      ["Tiles", `${p.tw}×${p.th}`], ["Pixels", `${p.w}×${p.h}`], ["Art state", p.art]]
    : [["Lane", p.group === 0 ? "0 — main" : `${p.group}`],
      ["Tiles", `${p.tw}×${p.th}`], ["Pixels", `${p.w}×${p.h}`],
      ["Position", `${p.x}, ${p.y}`], ["Joins", p.joins ? "yes" : "no"],
      ["Art state", `${p.art} · fit ${p.fit}`]];
  panel.innerHTML = `<h3>${sectionName(S.section)}</h3>`
    + rows.map(([k, v]) => `<div class="pp-row"><span>${k}</span><b>${v}</b></div>`).join("");
  panel.hidden = false;
});

on("toggles-changed", syncToggles);
