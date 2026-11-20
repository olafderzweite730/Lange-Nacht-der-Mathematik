"use strict";

const POLL_MS = 15000;

function nrFromQuery() {
  const p = new URLSearchParams(location.search).get("nr");
  return p ? decodeURIComponent(p) : null;
}

function signatur(a) {
  return JSON.stringify([a.status, a.geloest, a.loesung, a.loesungsweg, a.modelle, a.notizen, a.aktualisiert]);
}

function modelleBlock(a) {
  if (!Array.isArray(a.modelle) || a.modelle.length === 0) return "";
  const zeilen = a.modelle.map(m => {
    const einig = m.einig !== false;
    return `<tr>
      <td class="modell">${LNM.esc(m.name || "Modell")}</td>
      <td class="antwort">${LNM.esc(m.antwort ?? "–")}</td>
      <td class="einig ${einig ? "ja" : "nein"}">${einig ? "✓ stimmt überein" : "✗ abweichend"}</td>
    </tr>`;
  }).join("");
  const konsens = a.konsens != null ? Number(a.konsens) : null;
  return `
  <section class="block">
    <h2>Modelle &amp; Konsens</h2>
    <table class="modelle">
      <thead><tr><th>Modell</th><th>Antwort</th><th>Übereinstimmung</th></tr></thead>
      <tbody>${zeilen}</tbody>
    </table>
    ${konsens != null ? `<p class="konsens">Konsens: <strong>${konsens} / ${a.modelle.length}</strong> Modelle${a.verifiziert ? " · symbolisch verifiziert ✓" : ""}</p>` : ""}
  </section>`;
}

function baueAnsicht(a, aufgaben) {
  const st = LNM.statusOf(a);
  const idx = aufgaben.findIndex(x => String(x.nummer) === String(a.nummer));
  const geloest = Boolean(a.loesung);

  document.title = `Aufgabe ${a.nummer}${a.titel ? " – " + a.titel : ""} – Lange Nacht der Mathematik`;

  return `
  <div class="kopf">
    <div class="kopf-oben">
      <h1><span class="kopf-nr">Aufgabe ${LNM.esc(a.nummer)}</span>${a.titel ? `<span class="kopf-titel">${LNM.esc(a.titel)}</span>` : ""}</h1>
      ${LNM.badge(a)}
    </div>
    <p class="meta">${[
      a.thema, a.runde ? "Runde " + a.runde : "", a.jahr, a.stufe ? "Stufe " + a.stufe : ""
    ].filter(Boolean).map(LNM.esc).join(" · ")}</p>
  </div>

  <section class="ergebnis ${geloest ? "da" : ""}">
    <div class="ergebnis-kopf">
      <h2>Ergebnis</h2>
      ${geloest ? `<button class="copy" data-copy="${LNM.esc(a.loesung)}" type="button">kopieren</button>` : ""}
    </div>
    ${geloest
      ? `<div class="ergebnis-text">${a.loesung}</div>`
      : `<div class="ergebnis-text leer">${
          st === "bearbeitet" ? "Wird gerade gelöst …"
          : st === "unsicher" ? "Kein belastbares Ergebnis — Modelle uneinig, siehe Tabelle unten."
          : "Noch kein Ergebnis."
        }</div>`}
    ${a.aktualisiert ? `<p class="stand">Stand ${LNM.formatTime(a.aktualisiert)}</p>` : ""}
  </section>

  ${a.loesungsweg ? `
  <section class="block loesungsweg">
    <h2>Lösungsweg</h2>
    ${LNM.paragraphs(a.loesungsweg)}
  </section>` : ""}

  ${modelleBlock(a)}

  <section class="block">
    <h2>Aufgabenstellung</h2>
    <div class="aufgabe-text">${a.aufgabe || ""}</div>
  </section>

  ${a.notizen ? `<section class="block"><h2>Notizen</h2>${LNM.paragraphs(a.notizen)}</section>` : ""}

  <nav class="pager">
    <a href="${idx > 0 ? `aufgabe.html?nr=${encodeURIComponent(aufgaben[idx - 1].nummer)}` : "#"}" id="prev-link" class="${idx > 0 ? "" : "aus"}">← Aufgabe ${idx > 0 ? LNM.esc(aufgaben[idx - 1].nummer) : ""}</a>
    <a href="${idx >= 0 && idx < aufgaben.length - 1 ? `aufgabe.html?nr=${encodeURIComponent(aufgaben[idx + 1].nummer)}` : "#"}" id="next-link" class="${idx >= 0 && idx < aufgaben.length - 1 ? "" : "aus"}">Aufgabe ${idx >= 0 && idx < aufgaben.length - 1 ? LNM.esc(aufgaben[idx + 1].nummer) : ""} →</a>
  </nav>`;
}

(async function init() {
  const content = document.getElementById("content");
  const navTitel = document.getElementById("nav-titel");
  const nr = nrFromQuery();

  let aufgaben, aktuell, letzteSignatur = null;

  function zeichne() {
    content.innerHTML = baueAnsicht(aktuell, aufgaben);
    LNM.renderMath(content);
    navTitel.textContent = `aufgabe ${aktuell.nummer}`;
    document.querySelectorAll(".copy").forEach(btn => {
      btn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(btn.dataset.copy);
          btn.textContent = "kopiert ✓";
          setTimeout(() => (btn.textContent = "kopieren"), 1500);
        } catch { /* Clipboard evtl. gesperrt */ }
      });
    });
  }

  if (!nr) {
    content.innerHTML = `<p class="empfaenger">Keine Aufgabennummer angegeben. <a href="index.html">Zur Übersicht</a></p>`;
    return;
  }

  try {
    aufgaben = LNM.sortiert(await LNM.ladeAufgaben());
  } catch (e) {
    content.innerHTML = `<p class="empfaenger">Fehler beim Laden: ${LNM.esc(e.message)}</p>`;
    return;
  }

  aktuell = aufgaben.find(a => String(a.nummer) === String(nr));
  if (!aktuell) {
    content.innerHTML = `<p class="empfaenger">Aufgabe ${LNM.esc(nr)} existiert nicht (noch nicht). <a href="index.html">Zur Übersicht</a></p>`;
    return;
  }

  letzteSignatur = signatur(aktuell);
  zeichne();

  async function aktualisiere() {
    try {
      aufgaben = LNM.sortiert(await LNM.ladeAufgaben());
      const neu = aufgaben.find(a => String(a.nummer) === String(nr));
      if (neu && signatur(neu) !== letzteSignatur) {
        const y = window.scrollY;
        aufgaben = LNM.sortiert(aufgaben);
        aktuell = neu;
        letzteSignatur = signatur(neu);
        zeichne();
        window.scrollTo(0, y);
        content.classList.add("frisch");
        setTimeout(() => content.classList.remove("frisch"), 6000);
      }
      document.getElementById("live-zeit").textContent = "aktualisiert " + new Date().toLocaleTimeString("de-DE");
    } catch { /* still weiterpolen */ }
  }

  setInterval(() => { if (!document.hidden) aktualisiere(); }, POLL_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) aktualisiere(); });
})();
