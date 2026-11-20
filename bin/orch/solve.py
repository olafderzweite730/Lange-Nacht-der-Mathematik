#!/usr/bin/env python3
"""Multi-Modell-Orchestrierung für die Lange Nacht der Mathematik.

Fan-out pro Aufgabe an alle Modelle aus models.json (unabhängige Einzel-Prompts),
Antwort-Extraktion, gewichtetes Mehrheitsvotum, Merge in data/aufgaben.json.

Beispiel:
  bin/orch/solve.py tasks/runde2.json            # lösen + Ergebnis anzeigen
  bin/orch/solve.py tasks/runde2.json --publish  # lösen + committen/pushen
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONF = Path(__file__).with_name("models.json")

RETRY_OVERLAY = str(Path(__file__).with_name("omp-retry.yml"))
DOWN = {"codex-lb": "No available accounts"}


def provider_down(output: str) -> str | None:
    if re.search(r"no_accounts|No available accounts|degraded mode", output, re.I):
        return "provider_down"
    return None


SYSTEM = (
    "Du bist Mathematiker und löst eine Wettbewerbsaufgabe der Langen Nacht der Mathematik. "
    "Arbeite exakt, prüfe dein Ergebnis auf Plausibilität. "
    "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in genau dieser Form, ohne Codefences, ohne Text davor oder danach:\n"
    '{"antwort": "<Endergebnis, kompakt>", "weg": "<Lösungsweg in 3-8 Schritten, Deutsch, LaTeX mit $...$>", '
    '"konfidenz": <Zahl zwischen 0 und 1>, "idee": "<eine Zeile Kernidee>"}\n'
    "Format des Endergebnisses: N = natürliche Zahl als Ziffern; Q = rationale Zahl als Bruch wie 7/2 oder als exakter Ausdruck; "
    "R(k) = Dezimalzahl mit k Nachkommastellen (Punkt als Dezimaltrenner). Mehrere Werte mit ';' trennen. "
    "Keine Einheiten, keine Erklärungen im Feld antwort."
)


def load_conf() -> dict:
    return json.loads(CONF.read_text())


# ---------------------------------------------------------------- Antwort-Extraktion
def _looks_latex(text: str, i: int) -> bool:
    r"""Backslash an Position i sieht nach LaTeX-Befehl aus (\frac, \sqrt, \n + Text)?"""
    if i + 1 >= len(text):
        return False
    nxt = text[i + 1]
    if nxt in '"\\/':
        return False
    if nxt == "u":
        return not re.match(r"[0-9a-fA-F]{4}", text[i + 2:i + 6])
    if nxt in "bfnrt":
        # \f aus \frac, \n gefolgt von Weitertext: LaTeX, keine Escape-Sequenz
        rest = text[i + 2:i + 3]
        return bool(rest) and (rest.isalpha() or rest in "$\\")
    return True


def repair_strings(text: str) -> str:
    """Verdoppelt Backslashes, die in JSON-Strings LaTeX sind (ungültige/mehrdeutige Escapes)."""
    out, i, in_str = [], 0, False
    while i < len(text):
        ch = text[i]
        if not in_str:
            if ch == '"':
                in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "\\":
            if _looks_latex(text, i):
                out.append("\\\\")
                i += 1
            else:
                out.append(ch)
                out.append(text[i + 1] if i + 1 < len(text) else "")
                i += 2
            continue
        if ch == '"':
            in_str = False
        out.append(ch)
        i += 1
    return "".join(out)


def extract_json(text: str) -> dict | None:
    """Finde das letzte vollständige JSON-Objekt im Text (auch aus Codefences)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) and "antwort" in obj else None
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    best = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        for candidate in (text[i:], repair_strings(text[i:])):
            try:
                obj, _ = dec.raw_decode(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "antwort" in obj:
                best = obj
                break
        if best:
            break
    return best


# ---------------------------------------------------------------- Normalisierung
_UNICODE = str.maketrans({
    "−": "-", "–": "-", "—": "-", "√": "sqrt", "·": "*", "×": "*", "⋅": "*",
    "\u200b": "", "\u00a0": " ", "’": "'", "“": '"', "”": '"',
})


def normalize(raw) -> str:
    if raw is None:
        return ""
    s = str(raw).translate(_UNICODE).strip()
    s = re.sub(r"\\(?:text|mathrm|operatorname)\{([^{}]*)\}", r"\1", s)
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    s = re.sub(r"\s+", " ", s)
    s = s.strip("$ ").strip()
    s = s.replace(",", ".") if re.fullmatch(r"-?\d+,\d+", s) else s
    return s.lower() if not re.search(r"[a-z]", s, re.I) else s


def parse_number(s: str):
    try:
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        pass
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return Fraction(s)
    return None


def latex_to_py(s: str) -> str:
    """Wandelt einfache LaTeX-Ausdrücke in sympy-taugliche Syntax um."""
    def group(text: str, i: int):
        """Liest { ... } ab Position i (dort muss '{' stehen), liefert (inhalt, index_danach)."""
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    return text[i + 1:j], j + 1
            j += 1
        return text[i + 1:], len(text)

    out, i = [], 0
    while i < len(s):
        if s.startswith("\\frac", i):
            j = i + 5
            if j < len(s) and s[j] == "{":
                num, j = group(s, j)
            else:
                num, j = s[j], j + 1
            if j < len(s) and s[j] == "{":
                den, j = group(s, j)
            else:
                den, j = s[j], j + 1
            out.append(f"(({latex_to_py(num)})/({latex_to_py(den)}))")
            i = j
        elif s.startswith("\\sqrt", i):
            j = i + 5
            if j < len(s) and s[j] == "{":
                arg, j = group(s, j)
            else:
                arg, j = s[j], j + 1
            out.append(f"sqrt({latex_to_py(arg)})")
            i = j
        elif s.startswith("\\cdot", i):
            out.append("*"); i += 5
        elif s.startswith("\\times", i):
            out.append("*"); i += 6
        elif s[i] == "^":
            out.append("**"); i += 1
        elif s[i] in "{}":
            i += 1
        else:
            out.append(s[i]); i += 1
    return "".join(out)


def symbolic_equal(a: str, b: str) -> bool:
    try:
        from sympy import simplify, sympify
        from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
        tr = standard_transformations + (implicit_multiplication_application,)
        ea = parse_expr(latex_to_py(a), transformations=tr, evaluate=True)
        eb = parse_expr(latex_to_py(b), transformations=tr, evaluate=True)
        return bool(simplify(ea - eb) == 0)
    except Exception:
        return False


def same_value(a: str, b: str) -> bool:
    a, b = normalize(a), normalize(b)
    if a == b:
        return True
    na, nb = parse_number(a), parse_number(b)
    if na is not None and nb is not None:
        return na == nb
    # einfache LaTeX-Brüche wie \frac{7}{2}
    fa = re.fullmatch(r"\\frac\{(-?\d+)\}\{(-?\d+)\}", a)
    fb = re.fullmatch(r"\\frac\{(-?\d+)\}\{(-?\d+)\}", b)
    if fa and fb:
        return Fraction(int(fa[1]), int(fa[2])) == Fraction(int(fb[1]), int(fb[2]))
    if fa:
        n = parse_number(b)
        return n is not None and Fraction(int(fa[1]), int(fa[2])) == n
    if fb:
        n = parse_number(a)
        return n is not None and Fraction(int(fb[1]), int(fb[2])) == n
    if symbolic_equal(a, b):
        return True
    return re.sub(r"[\s{}()$]", "", a) == re.sub(r"[\s{}()$]", "", b)


# ---------------------------------------------------------------- Ein Modell
def ask_model(model: dict, task: dict, timeout: int) -> dict:
    prompt = (
        f"Aufgabe {task['nummer']}: {task.get('titel', '')}\n"
        f"Lösungstyp: {task.get('typ', 'N')}\n\n"
        f"{task['aufgabe']}\n\n"
        "Antworte jetzt nur mit dem JSON-Objekt."
    )
    cmd = [
        "omp", "-p", "--no-session",
        "--model", model["id"],
        "--thinking", model.get("thinking", "high"),
        "--config", RETRY_OVERLAY,
        "--system-prompt", SYSTEM,
        prompt,
    ]
    started = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=tempfile.gettempdir(), env={**os.environ, "NO_COLOR": "1"},
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        parsed = extract_json(out)
        ok = parsed is not None
        err = None if ok else (out.strip()[-400:] or f"exit {proc.returncode}")
        down = provider_down(out)
    except subprocess.TimeoutExpired:
        parsed, ok, err, down = None, False, f"timeout nach {timeout}s", None
    elapsed = round(time.time() - started, 1)
    return {
        "model": model["id"],
        "label": model.get("label", model["id"]),
        "weight": float(model.get("weight", 1.0)),
        "ok": ok,
        "antwort": (parsed or {}).get("antwort"),
        "weg": (parsed or {}).get("weg"),
        "konfidenz": float((parsed or {}).get("konfidenz") or 0.0),
        "idee": (parsed or {}).get("idee"),
        "error": err,
        "down": down,
        "sekunden": elapsed,
    }


# ---------------------------------------------------------------- Votum
def vote(results: list[dict]) -> dict:
    good = [r for r in results if r["ok"] and normalize(r["antwort"])]
    if not good:
        return {"gewinner": None, "konsens": 0, "einig": {}, "stimmen": []}

    clusters: list[list[dict]] = []
    for r in good:
        for c in clusters:
            if same_value(c[0]["antwort"], r["antwort"]):
                c.append(r)
                break
        else:
            clusters.append([r])

    def score(cluster):
        weight = sum(r["weight"] for r in cluster)
        conf = sum(r["konfidenz"] for r in cluster) / len(cluster)
        return (weight, conf)

    ranked = sorted(clusters, key=score, reverse=True)
    winner = max(ranked[0], key=lambda r: (r["konfidenz"], r["weight"]))
    einig = {r["model"]: same_value(r["antwort"], winner["antwort"]) for r in good}

    tie = len(ranked) > 1 and score(ranked[0])[0] == score(ranked[1])[0]
    if tie:
        # Gleichstand nach Gewicht: höchste Konfidenz entscheidet, sonst unsicher
        top_conf = score(ranked[0])[1]
        tie = abs(top_conf - score(ranked[1])[1]) < 0.05

    return {
        "gewinner": winner,
        "konsens": len(ranked[0]),
        "einig": einig,
        "stimmen": [(c[0]["antwort"], sum(r["weight"] for r in c), len(c)) for c in ranked],
        "unentschieden": bool(tie),
        "gesamt_antworten": len(good),
    }


PROBE_CACHE = Path(__file__).with_name(".probe.json")
PROBE_TTL = 600
MINI = {"nummer": "probe", "typ": "N", "aufgabe": "Berechne 6*7."}


def health_filter(roster: list[dict], timeout: int, parallel: int) -> list[dict]:
    """Kurzer Erreichbarkeitstest (10-min-Cache); entfernt nicht antwortende Modelle."""
    cache = {}
    if PROBE_CACHE.exists():
        try:
            cache = json.loads(PROBE_CACHE.read_text())
        except json.JSONDecodeError:
            cache = {}
    now = time.time()
    todo = [m for m in roster if now - cache.get(m["id"], {}).get("ts", 0) > PROBE_TTL]

    if todo:
        print(f"Health-Probe: {len(todo)} Modell(e) …", flush=True)
        with cf.ThreadPoolExecutor(max_workers=parallel) as pool:
            futs = {pool.submit(ask_model, m, MINI, min(timeout, 150)): m for m in todo}
            for fut in cf.as_completed(futs):
                r = fut.result()
                cache[r["model"]] = {"ok": r["ok"], "ts": time.time(),
                                     "error": (r["error"] or "")[:200] if not r["ok"] else ""}
                print(f"  {'OK  ' if r['ok'] else 'DOWN'} {r['label']}", flush=True)
        try:
            PROBE_CACHE.write_text(json.dumps(cache, indent=1))
        except OSError:
            pass

    usable, dead = [], []
    for m in roster:
        entry = cache.get(m["id"], {})
        if entry.get("ok", True):
            usable.append(m)
        else:
            dead.append((m, entry.get("error", "")))
    for m, err in dead:
        print(f"  übersprungen: {m['label']} — {err[:70]}", flush=True)
    return usable


def provider_of(model_id: str) -> str:
    return model_id.split("/", 1)[0]


def solve_task(task: dict, roster: list[dict], timeout: int, parallel: int, dry: bool,
               down: dict[str, str] | None = None) -> dict:
    if dry:
        return {"task": task, "results": [], "votum": None}
    down = down if down is not None else {}
    active = [m for m in roster if provider_of(m["id"]) not in down]
    skipped = [m for m in roster if provider_of(m["id"]) in down]
    for m in skipped:
        print(f"  {m['label']:<22} übersprungen ({down[provider_of(m['id'])][:60]})", flush=True)
    if not active:
        return {"task": task, "results": [], "votum": None}
    print(f"\n=== Aufgabe {task['nummer']} · {len(active)} Modelle ===", flush=True)
    results = []
    with cf.ThreadPoolExecutor(max_workers=parallel) as pool:
        futs = {pool.submit(ask_model, m, task, timeout): m for m in active}
        for fut in cf.as_completed(futs):
            r = fut.result()
            status = f"{normalize(r['antwort'])}" if r["ok"] else f"FEHLER ({r['error'][:80]})"
            print(f"  {r['label']:<22} {r['sekunden']:>6.1f}s  {status}", flush=True)
            if r.get("down"):
                down[provider_of(r["model"])] = r["error"] or "provider down"
            results.append(r)
    v = vote(results)
    if v["gewinner"]:
        print(f"  --> Lösung: {v['gewinner']['antwort']}  ({v['konsens']}/{v['gesamt_antworten']} einig"
              f"{', UNENTSCHIEDEN' if v['unentschieden'] else ''})", flush=True)
    else:
        print("  --> keine verwertbare Antwort", flush=True)
    return {"task": task, "results": results, "votum": v}


# ---------------------------------------------------------------- Merge in die Website
MPYTHON = Path.home() / "mathenv" / "bin" / "mpython"


def run_verification(task: dict, antwort) -> bool | None:
    """Optionaler unabhängiger Check: task['verifikation'] ist Python-Code, dessen letzte
    Ausgabezeile den Sollwert enthält (Feld `loesung`). None = kein Check vorhanden."""
    code = task.get("verifikation")
    if not code:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(code)
        path = fh.name
    try:
        proc = subprocess.run(
            [str(MPYTHON) if MPYTHON.exists() else sys.executable, path],
            capture_output=True, text=True, timeout=300,
        )
        value = (proc.stdout.strip().splitlines() or [""])[-1]
        if proc.returncode != 0 or not value:
            print(f"  Verifikation fehlgeschlagen (Laufzeit): {proc.stderr.strip()[-200:]}")
            return False
        ok = same_value(str(antwort), value)
        print(f"  Verifikation: Sollwert {value} → {'stimmt' if ok else 'ABWEICHUNG'}")
        return ok
    finally:
        os.unlink(path)


def merge_into_site(task: dict, votum: dict, results: list[dict], dry: bool,
                    verifiziert: bool | None = None) -> None:
    """Schreibt das Votum in data/aufgaben.json und akkumuliert Antworten früherer Läufe."""
    path = REPO / "data" / "aufgaben.json"
    data = json.loads(path.read_text())
    entry = next((a for a in data if str(a.get("nummer")) == str(task["nummer"])), None)
    if entry is None:
        entry = {"nummer": task["nummer"], "titel": task.get("titel", ""), "thema": task.get("thema", ""),
                 "jahr": task.get("jahr", ""), "runde": task.get("runde", ""), "stufe": task.get("stufe", ""),
                 "aufgabe": task["aufgabe"], "kurz": task.get("kurz", "")}
        data.append(entry)

    # Frühere Modellantworten behalten, neue überschreiben gleiche Namen.
    combined: dict[str, dict] = {}
    for m in entry.get("modelle", []):
        if m.get("name"):
            combined[m["name"]] = {"model": m["name"], "label": m["name"], "weight": 1.0, "ok": True,
                                   "antwort": m.get("antwort"), "weg": None, "konfidenz": 0.0, "idee": None}
    for r in results:
        if r["ok"]:
            combined[r["label"]] = {**r, "model": r["label"], "label": r["label"]}
    for r in results:
        if not r["ok"] and r["label"] not in combined:
            combined[r["label"]] = {**r, "model": r["label"], "label": r["label"]}

    alle = list(combined.values())
    v = vote(alle) if alle else votum
    entry["modelle"] = [
        {"name": r["label"], "antwort": str(r["antwort"]) if r["ok"] else "–",
         "einig": bool(v["einig"].get(r["model"])) and r["ok"]}
        for r in sorted(alle, key=lambda r: (not r["ok"], -(r["konfidenz"] or 0), r["label"]))
    ]
    entry["konsens"] = v["konsens"]

    g = v["gewinner"]
    loesung = g["antwort"] if g else None
    if verifiziert is True and loesung is not None:
        entry["status"] = "geloest"
        entry["loesung"] = loesung
        entry["notizen"] = entry.get("notizen", "")
    elif g and not v["unentschieden"]:
        entry["status"] = "geloest"
        entry["loesung"] = loesung
    elif g:
        entry["status"] = "unsicher"
        entry["loesung"] = ""
        entry["notizen"] = "Modelle uneinig: " + " · ".join(
            f"{a} ({n}×)" for a, _, n in v["stimmen"][:4])
    else:
        entry["status"] = "bearbeitet"

    weg = next((r["weg"] for r in results if r["ok"] and r.get("weg")), None)
    if weg and entry.get("status") == "geloest":
        entry["loesungsweg"] = weg
    entry["verifiziert"] = bool(verifiziert) if verifiziert is not None else entry.get("verifiziert", False)
    entry["aktualisiert"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    data.sort(key=lambda a: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", str(a["nummer"]))])
    if dry:
        print(f"[dry-run] Aufgabe {task['nummer']} würde geschrieben: {entry['status']}")
        return
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"  data/aufgaben.json aktualisiert: {task['nummer']} → {entry['status']}"
          f" ({len(entry['modelle'])} Modelle, Konsens {entry['konsens']})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tasks", nargs="?", help="JSON-Datei mit Aufgaben")
    ap.add_argument("--only", help="nur diese Aufgabennummer(n), Komma-getrennt")
    ap.add_argument("--models", help="Modell-IDs filtern (Substring, Komma-getrennt)")
    ap.add_argument("--parallel", type=int, help="gleichzeitige Modellaufrufe")
    ap.add_argument("--timeout", type=int, help="Timeout pro Modellaufruf in Sekunden")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--publish", action="store_true", help="nach dem Merge bin/publish ausführen")
    ap.add_argument("--save", help="Rohdaten zusätzlich als JSON speichern")
    ap.add_argument("--probe", action="store_true", help="nur Modell-Erreichbarkeit testen")
    ap.add_argument("--no-probe", action="store_true", help="Health-Probe vor dem Lauf überspringen")
    args = ap.parse_args()

    conf = load_conf()
    roster = conf["roster"]
    if args.models:
        pats = [p.strip() for p in args.models.split(",") if p.strip()]
        roster = [m for m in roster if any(p in m["id"] or p in m.get("label", "") for p in pats)]
    parallel = args.parallel or conf.get("parallel", 8)
    timeout = args.timeout or conf.get("timeoutSec", 900)

    if args.probe:
        probe = {"nummer": "probe", "typ": "N", "aufgabe": "Berechne 6*7."}
        results = []
        with cf.ThreadPoolExecutor(max_workers=parallel) as pool:
            futs = {pool.submit(ask_model, m, probe, min(timeout, 180)): m for m in roster}
            for fut in cf.as_completed(futs):
                results.append(fut.result())
        for r in sorted(results, key=lambda r: r["label"]):
            state = "OK   " if r["ok"] else ("DOWN " if r.get("down") else "FEHLER")
            print(f"{state} {r['label']:<22} {r['model']:<40} {r['sekunden']:>6.1f}s"
                  + (f"  {r['error'][:70]}" if not r["ok"] else ""))
        return 0

    if not args.tasks:
        ap.error("tasks fehlt")
    tasks = json.loads(Path(args.tasks).read_text())
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        tasks = [t for t in tasks if str(t["nummer"]) in wanted]
    if not tasks:
        print("Keine Aufgaben ausgewählt.", file=sys.stderr)
        return 1

    if not args.no_probe and not args.dry_run:
        roster = health_filter(roster, timeout, parallel)

    print(f"{len(tasks)} Aufgabe(n) × {len(roster)} Modelle (parallel {parallel}, timeout {timeout}s)")
    if not roster:
        print("Kein Modell erreichbar.", file=sys.stderr)
        return 1
    out = []
    down: dict[str, str] = {}
    for task in tasks:
        res = solve_task(task, roster, timeout, parallel, args.dry_run, down)
        out.append(res)
        if not args.dry_run and res["votum"]:
            check = run_verification(task, res["votum"]["gewinner"]["antwort"]) if res["votum"]["gewinner"] else None
            if check is False and res["votum"]["gewinner"]:
                res["votum"]["unentschieden"] = True
            merge_into_site(task, res["votum"], res["results"], args.dry_run, check)

    if args.save:
        Path(args.save).write_text(json.dumps(out, ensure_ascii=False, indent=2))

    if args.publish and not args.dry_run:
        subprocess.run([str(REPO / "bin" / "publish"), "update: Lösungen (Multi-Modell)"], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
