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

async function ladeAufgaben() {
  const res = await fetch(DATA_URL, { cache: "no-cache" });
  if (!res.ok) throw new Error("aufgaben.json konnte nicht geladen werden");
  return res.json();
}

function initIndex() {
  const liste = document.getElementById("aufgaben-liste");
  const stats = document.getElementById("stats");
  const search = document.getElementById("search");
  const themaSel = document.getElementById("filter-thema");
  const geloestChk = document.getElementById("filter-geloest");
  document.getElementById("jahr").textContent = new Date().getFullYear();

  ladeAufgaben().then(aufgaben => {
    const themen = [...new Set(aufgaben.map(a => a.thema).filter(Boolean))].sort();
    themen.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t; opt.textContent = t;
      themaSel.appendChild(opt);
    });

    const geloestCount = aufgaben.filter(a => a.geloest).length;

    function aktualisiere() {
      const q = search.value.trim().toLowerCase();
      const thema = themaSel.value;
      const nurGeloest = geloestChk.checked;
      const sichtbar = aufgaben.filter(a => {
        if (thema && a.thema !== thema) return false;
        if (nurGeloest && !a.geloest) return false;
        if (!q) return true;
        const heu = `${a.nummer} ${a.titel} ${a.thema} ${a.jahr} ${a.kurz}`.toLowerCase();
        return heu.includes(q);
      });

      liste.innerHTML = sichtbar.length === 0
        ? `<p class="subtitle">Keine Aufgaben gefunden.</p>`
        : sichtbar.map(a => `
          <a class="card${a.geloest ? " geloest" : ""}" href="aufgabe.html?nr=${encodeURIComponent(a.nummer)}">
            <div class="card-top">
              <span class="card-nr">Aufgabe ${esc(a.nummer)}</span>
              <span class="badge${a.geloest ? " geloest" : ""}">${a.geloest ? "✓ gelöst" : "offen"}</span>
            </div>
            <p class="card-titel">${esc(a.titel || "(noch ohne Titel)")}</p>
            <span class="card-thema">${esc(a.thema || "")}${a.jahr ? " · " + esc(a.jahr) : ""}</span>
            <p class="card-kurz">${esc(a.kurz || "")}</p>
          </a>`).join("");
      renderMath(liste);

      stats.innerHTML = `
        <div class="stat-box"><div class="zahl">${aufgaben.length}</div><div class="label">Aufgaben</div></div>
        <div class="stat-box"><div class="zahl">${geloestCount}</div><div class="label">gelöst</div></div>
        <div class="stat-box"><div class="zahl">${aufgaben.length - geloestCount}</div><div class="label">offen</div></div>`;
    }

    [search, themaSel, geloestChk].forEach(el => el.addEventListener("input", aktualisiere));
    aktualisiere();
  }).catch(err => {
    liste.innerHTML = `<p class="subtitle">Fehler: ${esc(err.message)}</p>`;
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("aufgaben-liste")) initIndex();
  window.__renderMath = renderMath;
});
