"use strict";

const POLL_MS = 20000;

function signatur(a) {
  return JSON.stringify([a.status, a.geloest, a.loesung, a.loesungsweg, a.aktualisiert]);
}

function initIndex() {
  const liste = document.getElementById("aufgaben-liste");
  const stats = document.getElementById("stats");
  const progressFill = document.getElementById("progress-fill");
  const live = document.getElementById("live");
  const liveZeit = document.getElementById("live-zeit");
  const search = document.getElementById("search");
  const themaSel = document.getElementById("filter-thema");
  const statusSel = document.getElementById("filter-status");
  document.getElementById("jahr").textContent = new Date().getFullYear();

  let aufgaben = [];
  const bekannt = new Map();      // nummer -> Signatur
  const frisch = new Set();       // nummern, die sich gerade geändert haben

  function baueThemen() {
    const themen = [...new Set(aufgaben.map(a => a.thema).filter(Boolean))].sort();
    const aktuell = themaSel.value;
    themaSel.innerHTML = `<option value="">Alle Themen</option>` +
      themen.map(t => `<option value="${LNM.esc(t)}">${LNM.esc(t)}</option>`).join("");
    themaSel.value = themen.includes(aktuell) ? aktuell : "";
  }

  function zeichne() {
    const q = search.value.trim().toLowerCase();
    const thema = themaSel.value;
    const status = statusSel.value;

    const sichtbar = aufgaben.filter(a => {
      if (thema && a.thema !== thema) return false;
      if (status && LNM.statusOf(a) !== status) return false;
      if (!q) return true;
      const hay = `${a.nummer} ${a.titel} ${a.thema} ${a.jahr} ${a.runde} ${a.kurz}`.toLowerCase();
      return hay.includes(q);
    });

    liste.innerHTML = aufgaben.length === 0
      ? `<p class="empfaenger">Noch keine Aufgaben hinterlegt – sobald die Blätter eintreffen, erscheinen sie hier automatisch.</p>`
      : sichtbar.length === 0
      ? `<p class="empfaenger">Keine Aufgaben passen zu Filter/Suche.</p>`
      : sichtbar.map(a => {
          const st = LNM.statusOf(a);
          const neu = frisch.has(String(a.nummer));
          return `
          <a class="card ${st}${neu ? " frisch" : ""}" href="aufgabe.html?nr=${encodeURIComponent(a.nummer)}">
            <div class="card-top">
              <span class="card-nr">Aufgabe ${LNM.esc(a.nummer)}</span>
              ${LNM.badge(a)}
            </div>
            <p class="card-titel">${LNM.esc(a.titel || "(noch ohne Titel)")}</p>
            <span class="card-thema">${LNM.esc(a.thema || "")}${a.runde ? " · Runde " + LNM.esc(a.runde) : ""}</span>
            ${a.loesung ? `<p class="card-ergebnis">${a.loesung}</p>` : ""}
            <p class="card-kurz">${LNM.esc(a.kurz || "")}</p>
            ${neu ? `<span class="neu-tag">✦ aktualisiert</span>` : ""}
          </a>`;
        }).join("");
    LNM.renderMath(liste);
  }

  function zeichneStats() {
    const n = aufgaben.length;
    const geloest = aufgaben.filter(a => LNM.statusOf(a) === "geloest").length;
    const arbeit = aufgaben.filter(a => LNM.statusOf(a) === "bearbeitet").length;
    stats.innerHTML = `
      <div class="stat-box"><div class="zahl">${n}</div><div class="label">aufgaben</div></div>
      <div class="stat-box"><div class="zahl ok">${geloest}</div><div class="label">gelöst</div></div>
      <div class="stat-box"><div class="zahl warn">${arbeit}</div><div class="label">in arbeit</div></div>
      <div class="stat-box"><div class="zahl">${n - geloest - arbeit}</div><div class="label">offen</div></div>`;
    progressFill.style.width = n ? `${(geloest / n) * 100}%` : "0%";
  }

  function uebernehme(neu) {
    const listeNeu = LNM.sortiert(neu);
    frisch.clear();
    for (const a of listeNeu) {
      const id = String(a.nummer);
      const vorher = bekannt.get(id);
      if (vorher !== undefined && vorher !== signatur(a)) frisch.add(id);
      bekannt.set(id, signatur(a));
    }
    aufgaben = listeNeu;
    baueThemen();
    zeichneStats();
    zeichne();
    if (frisch.size) setTimeout(() => { frisch.clear(); zeichne(); }, 8000);
  }

  async function aktualisiere() {
    try {
      const neu = await LNM.ladeAufgaben();
      live.hidden = false;
      liveZeit.textContent = "aktualisiert " + new Date().toLocaleTimeString("de-DE");
      uebernehme(neu);
    } catch (err) {
      liste.innerHTML = `<p class="empfaenger">Fehler: ${LNM.esc(err.message)}</p>`;
    }
  }

  [search, themaSel, statusSel].forEach(el => el.addEventListener("input", zeichne));
  aktualisiere();
  setInterval(() => { if (!document.hidden) aktualisiere(); }, POLL_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) aktualisiere(); });
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("aufgaben-liste")) initIndex();
});
