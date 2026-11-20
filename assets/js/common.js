"use strict";

// Gemeinsame Helfer für Übersicht und Detailansicht.
const LNM = (() => {
  const DELIMS = [
    { left: "$$", right: "$$", display: true },
    { left: "$", right: "$", display: false },
    { left: "\\[", right: "\\]", display: true },
    { left: "\\(", right: "\\)", display: false }
  ];

  const STATUS = {
    offen:      { label: "offen",          cls: "offen" },
    bearbeitet: { label: "wird gelöst …",  cls: "bearbeitet" },
    geloest:    { label: "gelöst",         cls: "geloest" },
    unsicher:   { label: "unsicher",       cls: "unsicher" }
  };

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  function renderMath(el) {
    if (window.renderMathInElement) {
      renderMathInElement(el, { delimiters: DELIMS, throwOnError: false });
    }
  }

  // Status aus Feld oder Alt-Feld `geloest` ableiten.
  function statusOf(a) {
    const key = a.status || (a.geloest ? "geloest" : "offen");
    return STATUS[key] ? key : "offen";
  }

  function badge(a) {
    const key = statusOf(a);
    return `<span class="badge ${key}">${STATUS[key].label}</span>`;
  }

  // Absätze aus einem mehrzeiligen Lösungsweg bauen (Leerzeile = neuer Absatz).
  function paragraphs(text) {
    return String(text || "")
      .split(/\n{2,}/)
      .map(p => p.trim())
      .filter(Boolean)
      .map(p => `<p>${p.replace(/\n/g, "<br>")}</p>`)
      .join("");
  }

  function formatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) +
      " " + d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  }

  async function ladeAufgaben() {
    const res = await fetch("data/aufgaben.json", { cache: "no-cache" });
    if (!res.ok) throw new Error("aufgaben.json konnte nicht geladen werden");
    return res.json();
  }

  function sortiert(liste) {
    return [...liste].sort((x, y) => Number(x.nummer) - Number(y.nummer));
  }

  window.__renderMath = renderMath;
  return { esc, renderMath, statusOf, badge, paragraphs, formatTime, ladeAufgaben, sortiert, STATUS };
})();
