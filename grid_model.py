# -*- coding: utf-8 -*-
import re, sys
from typing import Any, Dict, List, Tuple

_GRID_RE = re.compile(r"^GVL\.GPS_Grid_data\[(\d+)\]\[(\d+)\]\.([A-Za-z_]\w*)$")


def require_numeric(data: Dict[str, Any], key_variants: List[str], name_for_error: str) -> float:
    for k in key_variants:
        v = data.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    missing = ", ".join(key_variants)
    sys.exit(f"ERRORE: variabile numerica mancante o non valida per {name_for_error}. Cercati: {missing}")


def require_int(data: Dict[str, Any], key: str, name_for_error: str) -> int:
    v = data.get(key)
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    sys.exit(f"ERRORE: variabile intera mancante o non valida per {name_for_error} ({key}).")


def require_points(data: Dict[str, Any]) -> Tuple[List[float], List[float]]:
    easts, norths, missing = [], [], []
    for i in range(1, 5):
        ke = f"IO.GPS.Cfg.stRef_Points.UTM_East[{i}]"
        kn = f"IO.GPS.Cfg.stRef_Points.UTM_North[{i}]"
        ve, vn = data.get(ke), data.get(kn)
        if not isinstance(ve, (int, float)) or not isinstance(vn, (int, float)):
            missing.append(f"{ke} / {kn}")
        else:
            easts.append(float(ve)); norths.append(float(vn))
    if missing:
        sys.exit("ERRORE: punti 1..4 incompleti o non numerici. Mancano:\n  - " + "\n  - ".join(missing))
    return easts, norths


def collect_grid_data(data: Dict[str, Any]) -> Dict[Tuple[int, int], Dict[str, Any]]:
    cells: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for key, val in data.items():
        m = _GRID_RE.match(key)
        if not m:
            continue
        ix, iy, prop = int(m.group(1)), int(m.group(2)), m.group(3)
        cells.setdefault((ix, iy), {})[prop] = val
    return cells


def validate_included_centers(cells: Dict[Tuple[int, int], Dict[str, Any]]):
    problems = []
    for (ix, iy), props in cells.items():
        if props.get("Included") is True:
            cx, cy = props.get("Center_Relative_East_dm"), props.get("Center_Relative_North_dm")
            if not isinstance(cx, (int, float)) or not isinstance(cy, (int, float)):
                problems.append((ix, iy))
    if problems:
        sample = "\n  - " + "\n  - ".join([f"Grid_data[{x}][{y}]" for x, y in problems[:20]])
        more = "" if len(problems) <= 20 else f"\n  (+ altri {len(problems)-20} casi)"
        sys.exit("ERRORE: celle Included=TRUE senza centri valorizzati (Center_*) :" + sample + more)
