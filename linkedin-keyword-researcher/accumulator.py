"""
LinkedIn Lead Accumulator
==========================
Recibe el output de la extensión de Claude (tabla Markdown o JSON)
y lo agrega al CSV de leads sin duplicados.

Uso:
  python accumulator.py           → modo interactivo (pega y presiona Ctrl+D)
  python accumulator.py --report  → ver estadísticas del CSV
  python accumulator.py --open    → abrir el CSV en el editor por defecto
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from typing import List, Optional

OUTPUT_DIR  = "results"
LEADS_FILE  = os.path.join(OUTPUT_DIR, "leads.csv")
FIELDS = [
    "fecha_sesion", "nombre", "cargo", "empresa", "ubicacion",
    "url_perfil", "tipo", "contenido_post", "fecha_post",
    "relevancia", "razon_relevancia", "mensaje_apertura", "estado",
]


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_markdown_table(text: str) -> List[dict]:
    """
    Parsea una tabla Markdown generada por Claude.
    Acepta encabezados en inglés o español (fuzzy match).
    """
    lines = [l.strip() for l in text.strip().splitlines()]
    table_lines = [l for l in lines if l.startswith("|")]
    if len(table_lines) < 3:
        return []

    # Extraer encabezados
    raw_headers = [h.strip().lower() for h in table_lines[0].split("|") if h.strip()]

    # Mapa de nombres alternativos → nombre canónico
    HEADER_MAP = {
        "nombre": "nombre", "name": "nombre",
        "cargo": "cargo", "title": "cargo", "título": "cargo", "position": "cargo",
        "empresa": "empresa", "company": "empresa",
        "ubicacion": "ubicacion", "ubicación": "ubicacion", "location": "ubicacion",
        "url_perfil": "url_perfil", "url": "url_perfil", "perfil": "url_perfil", "profile": "url_perfil",
        "tipo": "tipo", "type": "tipo",
        "contenido_post": "contenido_post", "contenido": "contenido_post", "post": "contenido_post", "content": "contenido_post",
        "fecha_post": "fecha_post", "fecha": "fecha_post", "date": "fecha_post",
        "relevancia": "relevancia", "score": "relevancia",
        "razon_relevancia": "razon_relevancia", "razón": "razon_relevancia", "reason": "razon_relevancia",
        "mensaje_apertura": "mensaje_apertura", "mensaje": "mensaje_apertura", "message": "mensaje_apertura",
    }
    headers = [HEADER_MAP.get(h, h) for h in raw_headers]

    rows = []
    for line in table_lines[2:]:   # skip header and separator
        cells = [c.strip() for c in line.split("|") if c.strip() != ""]
        if not cells:
            continue
        row = dict(zip(headers, cells))
        row.setdefault("fecha_sesion", datetime.now().strftime("%Y-%m-%d"))
        row.setdefault("estado", "nuevo")
        rows.append(row)

    return rows


def parse_json_block(text: str) -> List[dict]:
    """Intenta parsear un bloque JSON del output de Claude."""
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if not match:
        match = re.search(r"(\[.*?\])", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
        for row in data:
            row.setdefault("fecha_sesion", datetime.now().strftime("%Y-%m-%d"))
            row.setdefault("estado", "nuevo")
        return data
    except json.JSONDecodeError:
        return []


def parse_input(text: str) -> List[dict]:
    """Detecta automáticamente el formato y parsea."""
    rows = parse_json_block(text)
    if rows:
        return rows
    rows = parse_markdown_table(text)
    return rows


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _load_seen_urls() -> set:
    if not os.path.exists(LEADS_FILE):
        return set()
    seen = set()
    with open(LEADS_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = row.get("url_perfil", "").strip()
            if url:
                seen.add(url)
    return seen


def _ensure_header():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(LEADS_FILE):
        with open(LEADS_FILE, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def save_leads(leads: List[dict]) -> int:
    seen_urls = _load_seen_urls()
    new_leads = []
    for lead in leads:
        url = lead.get("url_perfil", "").strip()
        if url and url in seen_urls:
            continue
        new_leads.append(lead)
        if url:
            seen_urls.add(url)

    if not new_leads:
        return 0

    _ensure_header()
    with open(LEADS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        for lead in new_leads:
            writer.writerow(lead)

    return len(new_leads)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report():
    if not os.path.exists(LEADS_FILE):
        print("No hay leads guardados aún.")
        return

    from collections import Counter
    leads = []
    with open(LEADS_FILE, "r", encoding="utf-8") as f:
        leads = list(csv.DictReader(f))

    if not leads:
        print("El archivo CSV está vacío.")
        return

    by_date    = Counter(l.get("fecha_sesion", "?") for l in leads)
    by_tipo    = Counter(l.get("tipo", "?") for l in leads)
    by_rel     = Counter(l.get("relevancia", "?") for l in leads)
    by_estado  = Counter(l.get("estado", "nuevo") for l in leads)

    print(f"\n{'='*55}")
    print(f"  LEADS ACUMULADOS: {len(leads)}")
    print(f"{'='*55}")
    print(f"\n📅 Por fecha:")
    for d, c in sorted(by_date.items(), reverse=True)[:10]:
        print(f"  {d}: {c}")
    print(f"\n🔎 Por tipo:")
    for t, c in by_tipo.most_common():
        print(f"  {t}: {c}")
    print(f"\n⭐ Por relevancia:")
    for r, c in sorted(by_rel.items(), reverse=True):
        print(f"  {r}: {c}")
    print(f"\n📌 Por estado:")
    for s, c in by_estado.most_common():
        print(f"  {s}: {c}")
    print(f"\n📁 Archivo: {os.path.abspath(LEADS_FILE)}")
    print(f"{'='*55}\n")

    # Mostrar top leads relevancia 5
    top = [l for l in leads if l.get("relevancia", "") in ("5", "4") and l.get("estado") == "nuevo"]
    if top:
        print(f"\n🔥 TOP LEADS sin contactar (score 4-5): {len(top)}")
        for lead in top[:10]:
            print(f"  • {lead.get('nombre','?')} | {lead.get('cargo','?')} @ {lead.get('empresa','?')}")
            print(f"    {lead.get('url_perfil','')}")
            if lead.get("mensaje_apertura"):
                print(f"    💬 {lead.get('mensaje_apertura','')[:100]}...")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Acumula leads desde el output de la extensión de Claude"
    )
    parser.add_argument("--report", action="store_true", help="Ver estadísticas")
    parser.add_argument("--open",   action="store_true", help="Abrir CSV")
    args = parser.parse_args()

    if args.report:
        print_report()
        return

    if args.open:
        path = os.path.abspath(LEADS_FILE)
        os.system(f"xdg-open '{path}' 2>/dev/null || open '{path}' 2>/dev/null || start '{path}'")
        return

    print("=" * 55)
    print("  LinkedIn Lead Accumulator")
    print("  Pega el output de la extensión de Claude.")
    print("  Cuando termines, presiona Ctrl+D (Linux/Mac)")
    print("  o Ctrl+Z + Enter (Windows).")
    print("=" * 55)
    print()

    try:
        raw = sys.stdin.read()
    except KeyboardInterrupt:
        print("\nCancelado.")
        return

    if not raw.strip():
        print("No se recibió contenido.")
        return

    leads = parse_input(raw)

    if not leads:
        print("\n⚠️  No se encontraron leads en el texto pegado.")
        print("   Asegúrate de pegar una tabla Markdown o JSON del output de Claude.")
        return

    saved = save_leads(leads)
    skipped = len(leads) - saved

    print(f"\n✅ Guardados:   {saved} leads nuevos")
    if skipped:
        print(f"⏭️  Duplicados:  {skipped} ya existían")
    print(f"📁 Archivo:    {os.path.abspath(LEADS_FILE)}\n")

    if saved > 0:
        print_report()


if __name__ == "__main__":
    main()
