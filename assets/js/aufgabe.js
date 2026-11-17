"use strict";

const DATA_URL = "data/aufgaben.json";

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
}

function renderMath(el) {
  if (window.renderMathInElement) {
    renderMathInElement(el, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\[", right: "\\]", display: true },
        { left: "\\(", right: "\\)", display: false }
      ]
    });
  }
}

function nrFromQuery() {
  const p = new URLSearchParams(location.search).get("nr");
  return p ? decodeURIComponent(p) : null;
}

(async function init() {
  const content = document.getElementById("content");
  const nr = nrFromQuery();

  let aufgaben;
  try {
    aufgaben = await (await fetch(DATA_URL, { cache: "no-cache" })).json();
  } catch (e) {
    content.innerHTML = `<p class="subtitle">Fehler beim Laden: ${esc(e.message)}</p>`;
    return;
  }

  if (!nr) {
    content.innerHTML = `<p class="subtitle">Keine Aufgabennummer angegeben. <a href="index.html">Zur Übersicht</a></p>`;
    return;
  }

  const idx = aufgaben.findIndex(a => String(a.nummer) === String(nr));
  if (idx === -1) {
    content.innerHTML = `<p class="subtitle">Aufgabe ${esc(nr)} existiert nicht (noch nicht). <a href="index.html">Zur Übersicht</a></p>`;
    return;
  }

  const a = aufgaben[idx];
  document.title = `Aufgabe ${a.nummer} – Lange Nacht der Mathematik`;

  content.innerHTML = `
    <div class="kopf">
      <h1 class="card-nr">Aufgabe ${esc(a.nummer)}</h1>
      <span class="badge${a.geloest ? " geloest" : ""}">${a.geloest ? "✓ gelöst" : "offen"}</span>
    </div>
    <p class="meta">${esc(a.thema || "")}${a.jahr ? " · Jahr " + esc(a.jahr) : ""}</p>

    ${a.titel ? `<div class="block"><h2>Titel</h2><p>${esc(a.titel)}</p></div>` : ""}

    <div class="block">
      <h2>Aufgabenstellung</h2>
      <p>${a.aufgabe}</p>
    </div>

    ${a.geloest === true || a.loesung || a.loesungsweg ? `
    <div class="block loesungsweg">
      <h2>Lösung</h2>
      <details class="loesung" open>
        <summary>Lösung anzeigen</summary>
        ${a.loesungsweg ? `<p>${a.loesungsweg}</p>` : ""}
        ${a.loesung ? `<p><strong>Ergebnis:</strong> ${a.loesung}</p>` : ""}
      </details>
    </div>` : `
    <div class="block">
      <h2>Lösung</h2>
      <p class="subtitle">Noch nicht gelöst.</p>
    </div>`}

    ${a.notizen ? `<div class="block"><h2>Notizen</h2><p>${a.notizen}</p></div>` : ""}
  `;

  const prev = aufgaben[idx - 1];
  const next = aufgaben[idx + 1];
  document.getElementById("prev-link").href = prev ? `aufgabe.html?nr=${encodeURIComponent(prev.nummer)}` : "#";
  document.getElementById("next-link").href = next ? `aufgabe.html?nr=${encodeURIComponent(next.nummer)}` : "#";
  document.getElementById("prev-link").style.visibility = prev ? "visible" : "hidden";
  document.getElementById("next-link").style.visibility = next ? "visible" : "hidden";

  renderMath(content);
})();
