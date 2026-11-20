---
name: lnm-live
description: Load this skill for "Lange Nacht der Mathematik" competition night live operation — user drops an Aufgabenblatt PDF (usually ~/Downloads), wants it solved by many models and published live to the LNM website (~/lnm, GitHub Pages). Covers the one-command pipeline, model roster, consensus/voting, verification, and live troubleshooting.
---

# LNM Live — Aufgabenblatt → Multi-Modell-Lösung → Website

Kompletter Betriebsablauf für den Wettbewerbsabend. Wenn der Nutzer ein Blatt schickt
(„hier ist Runde 1“, „Blätter liegen in Downloads“, „löse das und stell's online“),
läuft alles über **einen** Befehl. Ziel: er liest um 21:40 die Ergebnisse auf dem Handy.

## 0. In 30 Sekunden loslegen

```bash
cd ~/lnm
bin/live "<PFAD ZUR PDF>" --jahr 2026 --runde 1 --stufe "11-13"
```

Das macht: PDF → `tasks/*.json` → alle Aufgaben als **„wird gelöst“** online → Multi-Modell-Lösung
→ Votum → Verifikation → Merge → Publish. Dauer: ~2–4 min pro Aufgabe (8 Modelle parallel).

Varianten:

```bash
bin/live "<pdf>" --dry-run                      # nur extrahieren, nichts schreiben
bin/live "<pdf>" --only 1.3,1.4                 # erst einzelne Aufgaben
bin/live "<pdf>" --models "glm,gpt-5.6"         # Teil-Roster
bin/live "<pdf>" --no-publish                   # Probe-Lauf ohne Commit
bin/orch/solve.py --probe                       # wer ist gerade erreichbar?
```

## 1. Was der Nutzer schreiben wird (und was du dann tust)

| Nutzer sagt | Deine Reaktion |
|---|---|
| „Blatt liegt in Downloads“ / „hier die Aufgaben“ | `ls -t ~/Downloads/*.pdf \| head -3` → `bin/live …` |
| „Runde 2 ist da“ | Blatt identifizieren, `--runde 2`, gleiche Pipeline |
| „nur Aufgabe 3 und 4“ | `--only 3,4` (Nummern wie im Blatt, z. B. `2.3`) |
| „warum steht da unsicher?“ | Modelltabelle prüfen, ggf. 4. Modell als Tie-Break, Verifikation nachziehen |
| „Design/Website angepasst“ | Skill `lnm-live` Abschnitt 4 + Repo direkt editieren |

Nie Rückfragen zu Format/Modellen — Roster und Defaults stehen hier. Nur bei fehlendem PDF fragen.

## 2. Repo & Website

- Repo: `~/lnm` (SSH, Branch `main`), Remote `git@github.com:olafderzweite730/Lange-Nacht-der-Mathematik.git`
- Live: <https://olafderzweite730.github.io/Lange-Nacht-der-Mathematik/>
- Deploy: GitHub Pages aus `main` / root, ~1 min nach Push. Kein Build-Step.
- Publish-Helfer: `bin/publish "Nachricht"` (validiert JSON, committet, pusht).
- Dateien: `index.html`, `aufgabe.html`, `data/aufgaben.json`, `assets/{css,js}`.
  `assets/js/common.js` (Helfer), `main.js` (Übersicht + Polling 20 s), `aufgabe.js` (Detail + Polling 15 s).

### Design-Regeln (nicht verwässern)

- Tokens: `#0a0d13` Canvas, Panels `#0e131b`, 1px-Kanten `#1c2635`, Radius 6px, **keine** Schatten,
  **keine** Gradient-Blobs, **keine** Puls-Glows. Akzent `#4db6f7`, Status `#46c48a` / `#d9a441` / `#e5645f`.
- Monospace (`ui-monospace`) für Zahlen, Labels, Meta, Badges; System-Sans für Text.
- Badges als `[ gelöst ]` (Klammern per CSS-Pseudo), Status zusätzlich als 2px linke Kartenkante.
- Detailseite-Reihenfolge ist Pflicht: **Kopf → Ergebnis → Lösungsweg → Modelle/Konsens → Aufgabentext**.
- Vorbild: GitHub-Primer/Linear, nicht „AI-Landingpage“.

## 3. Datenmodell `data/aufgaben.json`

```json
{
  "nummer": "2.3", "titel": "Doppelfakultät", "thema": "Zahlentheorie",
  "jahr": "2023", "runde": "2", "stufe": "11–13",
  "aufgabe": "… LaTeX …", "kurz": "Ein Satz",
  "loesung": "15",
  "loesungsweg": "1. …\n\n2. …",
  "status": "bearbeitet | geloest | unsicher | offen",
  "modelle": [{"name": "GLM-5.3", "antwort": "15", "einig": true}],
  "konsens": 5, "verifiziert": true,
  "notizen": "", "aktualisiert": "2026-11-20T21:14:00+01:00"
}
```

LaTeX mit `$…$` / `$$…$$` (KaTeX). Im JSON Backslashes verdoppeln — beim Schreiben von Hand
immer über Python `json.dump`, nie per Texteditor.

## 4. Roster, Health, Verteilung

`bin/orch/models.json` — 8 Modelle, 2 Provider, Gewichte:

| Modell | ID | Thinking | Gewicht |
|---|---|---|---|
| Mistral Large 4 | `mistral/mistral-large-4-0` | xhigh | 1.2 |
| Magistral Medium | `mistral/magistral-medium-latest` | xhigh | 1.0 |
| Mistral Medium 3.5 | `mistral/mistral-medium-2604` | xhigh | 1.0 |
| GLM-5.3 | `mistral/zai-glm-5-3` | max | 1.0 |
| DeepSeek V4.1 Flash | `mistral/deepseek-v4-1-flash-1017` | max | 1.0 |
| GPT-5.6 Sol | `codex-lb/gpt-5.6-sol` | xhigh | 1.0 |
| GPT-5.6 Terra | `codex-lb/gpt-5.6-terra` | xhigh | 1.0 |
| GPT-6 Luna | `codex-lb/gpt-6-luna` | xhigh | 1.0 |

- Health-Probe läuft automatisch vor jedem Solve (10-min-Cache, `.probe.json`, gitignored).
  `codex-lb` fällt sporadisch mit `503 No available accounts` aus → Provider wird übersprungen,
  Mistral rechnet weiter. Nach Ablauf des Caches kommt codex-lb automatisch zurück.
- Verteilung: `--task-parallel N` (Default 2) löst mehrere Aufgaben gleichzeitig;
  `providerConcurrency` = mistral 4, codex-lb 8 gleichzeitige Calls.

## 5. Lösungs-Pipeline im Detail (`bin/orch/solve.py`)

1. Prompt pro Aufgabe + Modell, isoliert (`omp -p --no-session --model … --thinking …`).
2. Modelle müssen strikt liefern: `{"antwort", "weg", "konfidenz", "idee"}`.
3. JSON-Reparatur: LaTeX-Backslashes (`\frac`) sind ungültige JSON-Escapes → werden verdoppelt;
   Codefences/Prosa drumherum werden toleriert.
4. Normalisierung: Brüche (`7/2` ≡ `3.5`), Dezimalkomma, `\frac{a}{b}`, `\sqrt`, `^` → sympy-Vergleich.
5. Gewichtetes Mehrheitsvotum; Gleichstand → höhere Konfidenz, sonst `status: "unsicher"` + alle Stimmen.
6. Optional `verifikation` im Task-JSON (Python, läuft mit `~/mathenv/bin/mpython`, letzte Zeile = Sollwert):
   stimmt überein → `verifiziert: true`, sonst `unsicher`.
7. Merge akkumuliert: frühere Modellantworten bleiben, neue überschreiben gleiche Namen;
   ausgefallene Modelle erscheinen als `–` (transparent).
8. `--publish` am Ende → live in ~1 min.

**Qualitätsregeln:** `verifiziert: true` nur nach *unabhängiger* Rechnung (sympy exakt, Burnside/Zyklus/
Brute-Force für kleine Fälle) — nie das Modell-Votum als Beweis verkaufen. Bei Figurenaufgaben
(PDF-Bilder) zusätzlich `~/.omp/agent/skills/mathe-nacht/bin/pdfpages` rendern und den Text ergänzen.

## 6. Publish & Live-Verhalten

- `bin/publish "update: …"` → Commit + Push; Seite aktualisiert nach ~1 min.
- Offene Tabs pollen selbst: Index 20 s, Detail 15 s; Karte flippt Status, `⟹ Ergebnis`-Chip erscheint.
- Nach dem Push kurz prüfen: `curl -s https://olafderzweite730.github.io/…/data/aufgaben.json | head`.
- Nie unveröffentlicht liegen lassen: nach jeder Aufgabe oder jedem Block publizieren.

## 7. Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| `FEHLER (Working... Retry budget exhausted … 503)` | codex-lb ohne Accounts → abwarten/überspringen; Mistral liefert weiter |
| Antwort `–` in Tabelle | Modell down oder JSON unparsebar; `--probe` zeigt's |
| `unsicher` obwohl Modelle ähnlich | Vergleich scheitert an Format (Einheiten, `%`) → Antwort normalisieren lassen oder Verifikation ergänzen |
| Lauf hängt > 10 min | `--timeout 300`, `--task-parallel 1`; `codex-lb` ist der übliche Langsam-Macher |
| Extraction liefert leere `aufgabe` | PDF ist Bild-Scan → `pdfpages` + Sichtprüfung, Text manuell ergänzen |
| `data/aufgaben.json` kaputt | `python3 -m json.tool data/aufgaben.json`, Fix, `bin/publish` |

## 8. Checkliste vor dem „fertig“

- [ ] Alle Blatt-Aufgaben stehen in `data/aufgaben.json` (Nummern wie im PDF).
- [ ] Jede gelöste Aufgabe hat `loesung`, `loesungsweg`, `modelle`, `konsens`, `aktualisiert`.
- [ ] `verifiziert: true` nur mit bestandener unabhängiger Rechnung.
- [ ] `bin/publish` gelaufen; Live-JSON geprüft; Seite zeigt Ergebnis oben.
- [ ] Ausfälle (codex-lb) stehen als `–` in der Tabelle, nicht stillschweigend versteckt.
