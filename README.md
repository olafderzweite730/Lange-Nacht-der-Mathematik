# Lange Nacht der Mathematik

Website mit Aufgaben, Lösungen und kurzen Lösungswegen für die **Lange Nacht der Mathematik**.
Als statische GitHub-Pages-Seite veröffentlicht – kein Build-Step nötig.

## Seite aktivieren (GitHub Pages)

1. Auf GitHub: **Settings → Pages**
2. *Source*: **Deploy from a branch**, Branch **main**, Ordner **/(root)**
3. Speichern – nach ~1 Minute ist die Seite unter `https://olafderzweite730.github.io/Lange-Nacht-der-Mathematik/` erreichbar

## Struktur

```
index.html                  – Übersicht: alle Aufgaben, Suche, Filter, Statistik
aufgabe.html                – Detailansicht einer Aufgabe (?nr=1 …)
data/aufgaben.json          – ALLE Aufgaben & Lösungen (einzige Datei, die du bearbeitest!)
assets/css/style.css        – Design (dunkles Theme)
assets/js/main.js           – Logik der Übersichtsseite
assets/js/aufgabe.js        – Logik der Detailseite
```

## Aufgabe hinzufügen

Öffne `data/aufgaben.json` und füge einen Eintrag hinzu (oder kopiere einen bestehenden):

```json
{
  "nummer": 3,
  "titel": "Turm und Schatten",
  "thema": "Geometrie",
  "jahr": "2025",
  "aufgabe": "Ein Turm wirft bei Sonnenstand $45°$ einen $12$ m langen Schatten. Wie hoch ist der Turm?",
  "kurz": "Turmhöhe über Schattenlänge bei 45° Sonneneinstrahlung",
  "loesungsweg": "Bei $45°$ ist das Schattendreieck gleichschenklig, also $h = s$. Genauer via Tangens: $\\tan(45°) = \\frac{h}{12} \\Rightarrow h = 12 \\cdot \\tan(45°) = 12$.",
  "loesung": "$h = 12$ m",
  "notizen": "",
  "geloest": true
}
```

**Felder:**

| Feld | Bedeutung |
|---|---|
| `nummer` | Aufgabennummer (wird in der URL benutzt, z. B. `aufgabe.html?nr=3`) |
| `titel` | Kurzer Titel (optional) |
| `thema` | z. B. *Geometrie*, *Algebra*, *Zahlentheorie* (optional, erzeugt Filter) |
| `jahr` | Jahr der Mathe-Nacht (optional) |
| `aufgabe` | Aufgabenstellung – kann LaTeX enthalten |
| `kurz` | Ein Satz für die Übersichtskarte (optional) |
| `loesungsweg` | Kurzer Lösungsweg, Schritt für Schritt |
| `loesung` | Endergebnis |
| `notizen` | Sonstiges (optional) |
| `geloest` | `true`/`false` – steuert den Status-Badge und Filter |

## Formeln schreiben (LaTeX)

Die Website rendert LaTeX automatisch mit **KaTeX**.

| Syntax | Anzeige |
|---|---|
| `$x^2 + 1$` | Inline-Formel |
| `$$\int_0^1 x^2\,dx$$` | Abgesetzte (große) Formel |
| `\frac{a}{b}` | Bruch |
| `\sqrt{2}` | Wurzel |

Wichtig: In JSON muss der Backslash verdoppelt werden: `\\frac{a}{b}` statt `\frac{a}{b}`.

## Neue Aufgabe nach dem Publishen

Direkt auf GitHub editieren: `data/aufgaben.json` → Stift-Symbol → Eintrag ergänzen → *Commit changes*.
Die Seite aktualisiert sich nach ~1 Minute automatisch.
