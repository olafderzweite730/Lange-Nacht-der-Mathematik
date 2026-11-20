# Lange Nacht der Mathematik – Live-Lösungsseite

Statische GitHub-Pages-Seite: Aufgaben der **Langen Nacht der Mathematik** mit Ergebnis,
Lösungsweg und Modell-Konsens. **Live**: beide Seiten pollen `data/aufgaben.json` (20 s bzw. 15 s),
neue/geänderte Lösungen erscheinen ohne Reload.

Seite: <https://olafderzweite730.github.io/Lange-Nacht-der-Mathematik/>

## Struktur

```
index.html              – Übersicht: Fortschritt, Suche, Filter, Ergebnis-Chips
aufgabe.html            – Detail: Ergebnis oben, Lösungsweg, Modelle, Aufgabentext
data/aufgaben.json      – ALLE Aufgaben & Lösungen (einzige Datei, die du bearbeitest!)
assets/css/style.css    – Design (dunkles Theme)
assets/js/common.js     – Helfer (esc, KaTeX, Status, Absätze)
assets/js/main.js       – Übersichtslogik + Live-Polling
assets/js/aufgabe.js    – Detailansicht + Live-Polling
```

## Felder in `aufgaben.json`

| Feld | Bedeutung |
|---|---|
| `nummer` | Aufgabennummer (URL: `aufgabe.html?nr=3`) |
| `titel` | Kurzer Titel |
| `thema` | z. B. *Geometrie*, *Zahlentheorie* (Filter) |
| `jahr`, `runde`, `stufe` | Wettbewerb, z. B. `2026` / `2` / `11–13` |
| `aufgabe` | Aufgabenstellung (LaTeX erlaubt) |
| `kurz` | Ein Satz für die Übersichtskarte |
| `loesung` | Endergebnis – steht auf der Detailseite ganz oben |
| `loesungsweg` | Schritt-für-Schritt, Absätze durch Leerzeile |
| `status` | `offen` · `bearbeitet` · `geloest` · `unsicher` |
| `modelle` | `[{"name": "...", "antwort": "...", "einig": true}]` |
| `konsens` | Anzahl übereinstimmender Modelle |
| `verifiziert` | `true`, wenn symbolisch (sympy) nachgerechnet |
| `notizen` | Sonstiges |
| `aktualisiert` | ISO-Zeitstempel des letzten Updates |

`geloest: true/false` wird weiterhin als Alt-Feld akzeptiert (Status wird daraus abgeleitet).

## Formeln

KaTeX mit `$…$` (inline) und `$$…$$` (abgesetzt). In JSON Backslashes verdoppeln:
`"\\frac{a}{b}"`.

## Lösen: Multi-Modell-Orchestrierung

```
bin/orch/extract.py "<pdf>" --jahr 2026 --runde 1 -o tasks/r1.json   # Blatt → Aufgaben-JSON
bin/orch/solve.py --probe                                           # Modell-Erreichbarkeit
bin/orch/solve.py tasks/r1.json --publish                           # lösen, mergen, veröffentlichen
bin/orch/solve.py tasks/r1.json --only 2.3 --models "glm,gpt-5.6"   # gezielt einzelne Aufgabe/Modelle
```

- Roster: `bin/orch/models.json` (`mistral/*`, `codex-lb/*`) mit Gewichten und Thinking-Level.
- Jede Aufgabe läuft unabhängig über alle Modelle (`omp -p`, isolierte Prompts), Antworten müssen
  striktes JSON liefern; kaputte LaTeX-Escapes werden repariert.
- Votum: Antworten werden normalisiert (Bruch/Dezimal/LaTeX, sympy-Vergleich), gewichtete Mehrheit
  entscheidet; Gleichstand → Konfidenz, sonst `status: "unsicher"`.
- `verifikation`: optionales Python-Snippet pro Aufgabe, das den Wert unabhängig berechnet
  (`mpython` mit sympy) — stimmt es überein, wird `verifiziert: true` gesetzt.
- Antworten früherer Läufe bleiben in `modelle` erhalten; neue Läufe ergänzen/überschreiben sie.
- Verteilung: `--task-parallel N` löst mehrere Aufgaben gleichzeitig; pro Provider gilt eine
  Obergrenze aus `providerConcurrency` in `models.json` (Mistral 4, codex-lb 8).
- Health-Probe vor jedem Lauf (10-min-Cache) entfernt nicht erreichbare Modelle automatisch.

## Live-Ablauf am Wettbewerbsabend

1. Aufgaben aus dem PDF in `data/aufgaben.json` eintragen, `status: "bearbeitet"`, committen, pushen.
2. Aufgaben lösen (siehe Skill `mathe-nacht` → Abschnitt *Live-Modus*), Ergebnis/Lösungsweg
   eintragen, `status: "geloest"`, `modelle`/`konsens`/`verifiziert` füllen.
3. `bin/publish` (JSON validieren, committen, pushen). Seite aktualisiert sich nach ~1 Minute,
   offene Tabs ziehen die Änderung automatisch.
