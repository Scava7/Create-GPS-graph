# -*- coding: utf-8 -*-
"""Parser strict: restituisce valori, righe originali e mappa chiave->indice riga."""
import re
from typing import Any, Dict, List, Tuple

_KEY_RE = re.compile(r"^([A-Za-z0-9_.\[\]]+)\s*:=\s*(.+?)\s*$")

# rimuove eventuali commenti inline e normalizza spazi Unicode
def _clean_value(raw: str) -> str:
    # taglia tutto ciò che segue // (commento stile PLC/HMI)
    raw = re.split(r"\s*//", raw, maxsplit=1)[0]
    # rimuovi spazi e caratteri invisibili tipici (NBSP, ecc.)
    raw = raw.replace("\u00A0", " ").replace("\u2007", " ").replace("\u202F", " ")
    return raw.strip()

def parse_value(raw: str) -> Any:
    s = _clean_value(raw)
    # Hex tipo 16#FF
    if s.upper().startswith("16#"):
        try:
            return int(s.split("#", 1)[1], 16)
        except Exception:
            pass
    # Bool
    if s.upper() in ("TRUE", "FALSE"):
        return s.upper() == "TRUE"
    # Int
    if re.fullmatch(r"[+-]?\d+", s):
        try:
            return int(s)
        except Exception:
            pass
    # Float (punto decimale)
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", s):
        try:
            return float(s)
        except Exception:
            pass
    # fallback: stringa
    return s

def parse_recipe_indexed(path: str) -> Tuple[Dict[str, Any], List[str], Dict[str, int]]:
    data: Dict[str, Any] = {}
    key_to_line: Dict[str, int] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        m = _KEY_RE.match(line)
        if not m:
            continue
        key, raw_val = m.group(1), m.group(2)
        data[key] = parse_value(raw_val)  # <<— adesso “282 // note” diventa numero 282
        key_to_line[key] = idx
    return data, lines, key_to_line
