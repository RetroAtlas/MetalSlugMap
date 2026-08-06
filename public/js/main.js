// Metal Slug Map viewer: browse the stages extracted from the PS1 disc.

import "./interaction.js";
import "./sidebar.js";
import { buildDialogs } from "./dialog.js";
import { applyHash, copyLink, selectMission } from "./navigate.js";
import { draw, exportPng, resize } from "./render.js";
import { buildMissionBar, buildToggles } from "./sidebar.js";
import { buildSearch } from "./search.js";
import { $, S } from "./state.js";

addEventListener("resize", resize);

function isMobile() {
  return matchMedia("(max-width: 720px)").matches;
}
function toggleMenu(open) {
  document.body.classList.toggle("menu-open",
    open ?? !document.body.classList.contains("menu-open"));
  resize();
}
$("menuBtn").onclick = () => toggleMenu();
$("scrim").onclick = () => toggleMenu(false);
$("exportBtn").onclick = exportPng;
$("copyLinkBtn").onclick = () => copyLink().then(() => toast("Link copied"));

let toastTimer = null;
function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 1800);
}

fetch("map_data_msx.json", { cache: "no-store" })
  .then((r) => r.json())
  .then((d) => {
    S.data = d;
    $("gameName").textContent = d.game;
    buildMissionBar();
    buildToggles();
    buildSearch(d);
    buildDialogs();
    resize();
    if (!applyHash() && d.missions.length) selectMission(d.missions[0]);
    if (isMobile()) toggleMenu(false);
    draw();
  })
  .catch(() => {
    $("gameName").textContent = "map data failed to load — serve this directory";
  });
