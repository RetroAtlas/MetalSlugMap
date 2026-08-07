// Search across missions, sections, stage pieces and objects.

import { index } from "./model.js";
import { focus, selectMission, selectSection } from "./navigate.js";
import { $, S, on } from "./state.js";

let entries = [];
let scope = "all";
let timer = null;

export function buildSearch(data) {
  entries = index(data);
  const bar = $("scopeBar");
  bar.innerHTML = "";
  for (const [key, label] of [["all", "everything"], ["section", "sections"],
    ["piece", "pieces"], ["object", "objects"]]) {
    const b = document.createElement("button");
    b.textContent = label;
    b.classList.toggle("on", key === scope);
    b.onclick = () => {
      scope = key;
      [...bar.children].forEach((x) => x.classList.toggle("on", x === b));
      run($("searchInput").value);
    };
    bar.appendChild(b);
  }
}

function go(hit) {
  if (hit.m !== S.mission) selectMission(hit.m);
  if (hit.s !== S.section) selectSection(hit.s);
  if (hit.kind === "piece") {
    const at = S.layout.find((a) => a.piece === hit.p);
    if (at) focus(at);
  } else if (hit.kind === "object") {
    const at = S.objects.find((a) => a.piece === hit.o);
    if (at) focus(at);
  }
}

function run(query) {
  const box = $("searchResults");
  box.innerHTML = "";
  const q = query.trim().toLowerCase();
  if (!q) return;
  const terms = q.split(/\s+/);
  const hits = entries.filter((e) => (scope === "all" || e.kind === scope)
    && terms.every((t) => e.hay.toLowerCase().includes(t)));
  for (const hit of hits.slice(0, 60)) {
    const b = document.createElement("button");
    const note = hit.kind === "section"
      ? `${hit.s.pieces.length} pieces · ${hit.s.groups.length} lanes`
      : hit.kind === "object"
        ? `${hit.o.frames.length} frames · ${hit.o.tw}×${hit.o.th}`
        : `${hit.p.tw}×${hit.p.th} tiles · lane ${hit.p.group}`;
    b.innerHTML = `<span class="loc">${hit.m.short}</span> ${hit.label} `
      + `<span class="dim">· ${note}</span>`;
    b.onclick = () => go(hit);
    box.appendChild(b);
  }
  const more = document.createElement("div");
  more.className = "more";
  more.textContent = hits.length
    ? `${hits.length} match${hits.length === 1 ? "" : "es"}${hits.length > 60 ? " — showing 60" : ""}`
    : "no matches";
  box.appendChild(more);
}

$("searchInput").addEventListener("input", (e) => {
  clearTimeout(timer);
  timer = setTimeout(() => run(e.target.value), 140);
});

on("search", (v) => run(v));
