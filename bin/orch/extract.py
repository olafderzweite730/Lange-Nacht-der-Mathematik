#!/usr/bin/env python3
"""PDF eines LNM-Aufgabenblatts → tasks.json für bin/orch/solve.py.

Nutzt pymupdf aus ~/mathenv (Wrapper ~/mathenv/bin/mpython), Fallback pdftotext.
Aufgaben werden an Überschriften "Aufgabe 2.3: Titel" getrennt; "Lösungstyp:" wird übernommen.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HEAD = re.compile(r"^\s*Aufgabe\s+(\d+\.\d+)\s*:\s*(.+?)\s*$", re.M)
TYP = re.compile(r"Lösungstyp\s*:\s*([NQR0-9();]+)")
SPLIT = re.compile(r"Lösungstyp\s*:\s*[NQR0-9();]+")


def pdf_text(path: Path) -> str:
    mpython = Path.home() / "mathenv" / "bin" / "mpython"
    if mpython.exists():
        code = (
            "import pymupdf,sys\n"
            "d=pymupdf.open(sys.argv[1])\n"
            "print('\\n'.join(p.get_text() for p in d))\n"
        )
        out = subprocess.run([str(mpython), "-c", code, str(path)], capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout
        print(f"mpython fehlgeschlagen: {out.stderr[-300:]}", file=sys.stderr)
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True)
        if out.returncode == 0:
            return out.stdout
    raise SystemExit("Kein PDF-Text-Extraktor verfügbar (mpython/pdftotext)")


BOILER = re.compile(
    r"^\s*(Wir suchen Helfer|Wenn jede teilnehmende|Da wir den Wettbewerb|Kosten entstehen|"
    r"Stichwort Mathenacht|Kontoinhaber|Kreditinstitut|IBAN|Lange Nacht der Mathematik \(\d+\)|"
    r"\d{2}\.\s*-\s*\d{2}\.\s*\w+|Aufgaben \d+ Runde|Alle Rechte|"
    r"Mathe-Nacht|www\.|https?://).*$", re.M)


def clean(text: str) -> str:
    text = re.sub(r"-\n(?=\w)", "", text)          # Silbentrennung
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(ln for ln in text.splitlines() if not BOILER.match(ln))
    text = re.sub(r"Lange Nacht\s+der\s+Mathematik\s*\(?\d+\)?\s*\d*\s*written by[^\n]*", "", text)
    text = re.sub(r"Für mehr Informationen.*?(?=\n|$)", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default="-", help="Zieldatei (default stdout)")
    ap.add_argument("--jahr", default="")
    ap.add_argument("--runde", default="")
    ap.add_argument("--stufe", default="")
    args = ap.parse_args()

    text = clean(pdf_text(Path(args.pdf)))
    heads = list(HEAD.finditer(text))
    if not heads:
        raise SystemExit("Keine 'Aufgabe X.Y:'-Überschriften gefunden")

    tasks = []
    for i, m in enumerate(heads):
        start = m.start()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        typ_m = TYP.search(body)
        typ = re.sub(r"\s+", "", typ_m.group(1)) if typ_m else "N"
        body = SPLIT.sub("", body, count=1).strip()
        title = m.group(2).strip()
        body = body[len(m.group(0)):].strip() if body.startswith(m.group(0)) else body
        tasks.append({
            "nummer": m.group(1),
            "titel": title,
            "thema": "",
            "jahr": args.jahr,
            "runde": args.runde,
            "stufe": args.stufe,
            "typ": typ,
            "kurz": "",
            "aufgabe": body,
        })

    payload = json.dumps(tasks, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(payload)
    else:
        Path(args.out).write_text(payload + "\n")
        print(f"{len(tasks)} Aufgaben → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
