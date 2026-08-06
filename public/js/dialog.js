// The overlays: keyboard shortcuts and what this map is.

import { stats } from "./model.js";
import { $, S, on } from "./state.js";

const SHORTCUTS = [
  [["←", "→", "↑", "↓"], "pan (hold shift to go further)"],
  [["+", "−"], "zoom"],
  [["[", "]"], "previous / next section"],
  [["/"], "search"],
  [["g"], "piece outlines"],
  [["l"], "size labels"],
  [["p"], "composite the parallax layers"],
  [["o"], "animated objects"],
  [["s"], "mark broken joins"],
  [["d"], "dim parallax layers"],
  [["t"], "transparency checkerboard"],
  [["e"], "export the view as PNG"],
  [["?"], "this list"],
];

function open(id) {
  $(id).classList.add("open");
}
function close(id) {
  $(id).classList.remove("open");
}

export function buildDialogs() {
  $("shortcutsBody").innerHTML = SHORTCUTS.map(([keys, what]) =>
    `<div class="sc-row"><span class="sc-keys">${keys.map((k) => `<kbd>${k}</kbd>`).join("")}</span>${what}</div>`).join("");

  const s = stats(S.data);
  $("aboutBody").innerHTML = `
    <p>Every stage piece here was read straight off a PlayStation disc of
    <b>Metal Slug X</b> (NTSC-U, SLUS-012.12) — no emulator, no screenshots.
    The tooling walks the disc's ISO9660 sectors, decodes the PS1 TIM artwork,
    replays those uploads into a model of the console's video memory, and reads
    each stage's tile list and tilemap back out of it.</p>
    <p>It currently holds <b>${s.pieces} stage pieces</b> and
    <b>${s.objects} animated objects</b> (${s.frames} frames) across
    ${s.sections} sections of ${s.missions} missions.</p>
    <p>Video memory is the hard part: sections stream art over each other while
    a mission plays, so a tilemap only means something against the memory that
    was resident when it was on screen — and nothing records that. Each piece is
    rendered at the point in the mission's load order where its tiles join most
    smoothly, which is the state it was drawn under. The <i>art state</i> shown
    for a piece is the one that won.</p>
    <p>What is <b>not</b> here yet: where the game places these pieces relative
    to one another, and the spawn tables for POWs, weapons and enemies. The
    stage files hold artwork, tile lists and tilemaps and almost nothing else,
    so that data lives somewhere still unidentified. Pieces are laid out in the
    order their file holds them, butted together where their edges actually
    match and separated where they do not — a broken join is drawn, not hidden.</p>
    <p>Sister project to <a href="https://oddworldmap.com/" target="_blank"
    rel="noopener">Oddworld Map</a>.</p>`;

  for (const [btn, id] of [["shortcutsClose", "shortcutsOverlay"], ["aboutClose", "aboutOverlay"]]) {
    $(btn).onclick = () => close(id);
  }
  for (const id of ["shortcutsOverlay", "aboutOverlay"]) {
    $(id).onclick = (e) => {
      if (e.target.id === id) close(id);
    };
  }
  $("aboutBtn").onclick = () => open("aboutOverlay");
  $("helpBtn").onclick = () => open("shortcutsOverlay");
  addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      close("shortcutsOverlay");
      close("aboutOverlay");
    }
  });
}

on("dialog", (which) => {
  if (which === "shortcuts") open("shortcutsOverlay");
  if (which === "place") $("placePanel").hidden = !$("placePanel").hidden;
});
