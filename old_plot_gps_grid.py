#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Strict + colori configurabili:
- Usa SOLO i dati del file, nessun fallback.
- Se manca qualcosa, esce con errore.
- Griglia, celle Included=TRUE, perimetro e punti.
- Sezione CONFIG per colori, spessori, dimensioni marker.

Dipendenze: matplotlib
"""

import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# ============================= CONFIG =================================
FIG_BG            = "white"
AX_BG             = "white"

GRID_COLOR        = "gray"
GRID_ALPHA        = 0.6
GRID_LINEWIDTH    = 1.5
Z_GRID            = 5         # zorder griglia

INCLUDED_FACE     = "lightblue"
INCLUDED_ALPHA    = 0.35
INCLUDED_EDGE     = None
INCLUDED_EDGEWIDTH= 0.0       # 0 elimina il bordo, aiuta contro i “gap”
Z_INCLUDED        = 1

PERIMETER_COLOR   = "tab:brown"
PERIMETER_WIDTH   = 2.0
Z_PERIMETER       = 7

POINT_COLOR       = "green"
POINT_SIZE        = 90
Z_POINTS          = 8
LABEL_COLOR       = "black"

TOOLTIP_BOX_FC   = "white"  # sfondo tooltip
TOOLTIP_BOX_EC   = "0.5"    # bordo tooltip
TOOLTIP_FONTSIZE = 9

FIG_SIZE     = (10, 10)   # dimensione finestra in pollici
AX_PAD_FRAC  = 0.08       # 8% di margine su destra e alto

# =========================== FINE CONFIG ==============================


# ---------------------------- parsing ---------------------------------

def parse_value(raw: str) -> Any:
    s = raw.strip()
    if s.upper().startswith("16#"):
        try:
            return int(s.split("#", 1)[1], 16)
        except Exception:
            pass
    if s.upper() in ("TRUE", "FALSE"):
        return s.upper() == "TRUE"
    if re.fullmatch(r"[+-]?\d+", s):
        try:
            return int(s)
        except Exception:
            pass
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", s):
        try:
            return float(s)
        except Exception:
            pass
    return s

def parse_recipe_indexed(path: str):
    """
    Ritorna:
      data: dict chiave -> valore già parsato
      lines: lista di righe originali del file
      key_to_line: dict chiave -> indice riga in 'lines'
    """
    import re
    data = {}
    key_to_line = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\[\]]+)\s*:=\s*(.+?)\s*$", line)
        if not m:
            continue
        key, raw_val = m.group(1), m.group(2)
        data[key] = parse_value(raw_val)
        key_to_line[key] = idx
    return data, lines, key_to_line


# ------------------------ grid_data extraction ------------------------

GRID_RE = re.compile(
    r"^IO\.GPS\.Sts\.Grid_data\[(\d+)\]\[(\d+)\]\.([A-Za-z_][A-Za-z0-9_]*)$"
)

def collect_grid_data(data: Dict[str, Any]) -> Dict[Tuple[int, int], Dict[str, Any]]:
    cells: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for key, val in data.items():
        m = GRID_RE.match(key)
        if not m:
            continue
        ix = int(m.group(1))
        iy = int(m.group(2))
        prop = m.group(3)
        cells.setdefault((ix, iy), {})[prop] = val
    return cells

# ----------------------------- helpers --------------------------------

def require_numeric(data: Dict[str, Any], key_variants: List[str], name_for_error: str) -> float:
    for k in key_variants:
        v = data.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    missing = ", ".join(key_variants)
    sys.exit(f"ERRORE: variabile numerica mancante o non valida per {name_for_error}. "
             f"Cercati: {missing}")

def require_int(data: Dict[str, Any], key: str, name_for_error: str) -> int:
    v = data.get(key)
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    sys.exit(f"ERRORE: variabile intera mancante o non valida per {name_for_error} ({key}).")

def require_points(data: Dict[str, Any]) -> Tuple[List[float], List[float]]:
    easts, norths = [], []
    missing = []
    for i in range(1, 5):
        ke = f"IO.GPS.Cfg.Relative_UTM_East[{i}]"
        kn = f"IO.GPS.Cfg.Relative_UTM_North[{i}]"
        ve = data.get(ke)
        vn = data.get(kn)
        if not isinstance(ve, (int, float)) or not isinstance(vn, (int, float)):
            missing.append(f"{ke} / {kn}")
        else:
            easts.append(float(ve))
            norths.append(float(vn))
    if missing:
        sys.exit("ERRORE: punti 1..4 incompleti o non numerici. Mancano:\n  - " + "\n  - ".join(missing))
    return easts, norths

def validate_included_centers(cells: Dict[Tuple[int, int], Dict[str, Any]]):
    problems = []
    for (ix, iy), props in cells.items():
        included = props.get("Included")
        if included is True:
            cx = props.get("Center_Relative_East_dm")
            cy = props.get("Center_Relative_North_dm")
            if not isinstance(cx, (int, float)) or not isinstance(cy, (int, float)):
                problems.append((ix, iy))
    if problems:
        sample = "\n  - " + "\n  - ".join([f"Grid_data[{x}][{y}]" for x, y in problems[:20]])
        more = "" if len(problems) <= 20 else f"\n  (+ altri {len(problems)-20} casi)"
        sys.exit("ERRORE: celle Included=TRUE senza centri valorizzati "
                 "(Center_Relative_East_dm / Center_Relative_North_dm):"
                 f"{sample}{more}")

# ----------------------------- plotting --------------------------------

def auto_pick_file(preferred_name: str = "GPS_Grid.txtrecipe") -> Path:
    here = Path.cwd()

    # 1) preferito esatto
    cand = here / preferred_name
    if cand.exists():
        print(f"[auto_pick_file] Uso: {cand}")
        return cand

    # 2) prima prova *.txtrecipe, poi anche *.txrtrecipe (typo comune)
    for pattern in ("*.txtrecipe", "*.txrtrecipe"):
        found = sorted(here.glob(pattern))
        if found:
            print(f"[auto_pick_file] Nessun {preferred_name}. Uso il primo {pattern}: {found[0]}")
            return found[0]

    # 3) dialog
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        path = filedialog.askopenfilename(
            title="Seleziona il file ricetta",
            filetypes=[("Recipe file", "*.txtrecipe;*.txrtrecipe"), ("Tutti i file", "*.*")]
        )
        root.destroy()
        if path:
            print(f"[auto_pick_file] Scelto: {path}")
            return Path(path)
    except Exception:
        pass

    raise FileNotFoundError("Nessun file .txtrecipe/.txrtrecipe trovato o selezionato.")


def plot_from_recipe(data: Dict[str, Any],
                     lines: List[str],
                     key_to_line: Dict[str, int],
                     source_path: str):
    
    # lato del quadrato (dm), obbligatorio
    extent_dm = require_numeric(
        data,
        ["IO.GPS.Vis.Square_Width_Scale_dm"],
        "dimensione quadrato (dm)",
    )

    N = require_int(data, "IO.GPS.Cfg.Num_Grid_Rows_Cols", "numero righe/colonne griglia")
    step = require_numeric(data, ["IO.GPS.Cfg.Grid_Cell_Size_dm"], "passo griglia (dm)")
    if N <= 0 or step <= 0:
        sys.exit("ERRORE: Num_Grid_Rows_Cols e Grid_Cell_Size_dm devono essere > 0.")
    easts, norths = require_points(data)

    cells = collect_grid_data(data)
    validate_included_centers(cells)  # controlla solo le celle Included=TRUE

    # --- Setup figura/assi ---
    fig = plt.figure(figsize=globals().get("FIG_SIZE", (8, 8)), facecolor=FIG_BG)
    ax = plt.gca()
    ax.set_facecolor(AX_BG)

    # --- 1) Hitbox trasparenti per TUTTE le celle ---
    rects_info: List[Dict[str, Any]] = []
    for ix in range(N):
        for iy in range(N):
            llx = ix * step
            lly = iy * step
            rect = Rectangle(
                (llx, lly),
                step, step,
                facecolor="none",
                edgecolor="none",
                linewidth=0.0,
                zorder=9,
            )
            ax.add_patch(rect)
            props = cells.get((ix, iy), {})  # solo ciò che esiste nel file
            rects_info.append({"rect": rect, "ix": ix, "iy": iy, "props": props})

    # --- 2) Celle Included=TRUE (riempimento verde con centri del file) ---
    edge_w = globals().get("INCLUDED_EDGEWIDTH", 0.0)
    for (ix, iy), props in cells.items():
        if props.get("Included") is True:
            cx = float(props["Center_Relative_East_dm"])
            cy = float(props["Center_Relative_North_dm"])
            llx = cx - step / 2.0
            lly = cy - step / 2.0
            rect = Rectangle(
                (llx, lly),
                step, step,
                facecolor=INCLUDED_FACE,
                alpha=INCLUDED_ALPHA,
                edgecolor=INCLUDED_EDGE,
                linewidth=edge_w,
                zorder=10,
                joinstyle="miter",
            )
            ax.add_patch(rect)

    # --- 3) Perimetro e punti ---
    xs_line = easts[:] + [easts[0]]
    ys_line = norths[:] + [norths[0]]
    plt.plot(xs_line, ys_line, linewidth=PERIMETER_WIDTH, color=PERIMETER_COLOR, zorder=20)

    plt.scatter(easts, norths, s=POINT_SIZE, color=POINT_COLOR, zorder=25)
    for i, (x0, y0) in enumerate(zip(easts, norths), start=1):
        plt.annotate(str(i), (x0, y0), xytext=(4, 4), textcoords="offset points",
                     color=LABEL_COLOR, zorder=26)

    # --- 4) Griglia per ultima, sopra tutto ---
    for k in range(N + 1):
        x = k * step
        y = k * step
        plt.axvline(x=x, linewidth=GRID_LINEWIDTH, alpha=GRID_ALPHA, color=GRID_COLOR, zorder=100)
        plt.axhline(y=y, linewidth=GRID_LINEWIDTH, alpha=GRID_ALPHA, color=GRID_COLOR, zorder=100)

    # --- Limiti esatti ---
    plt.xlim(0, extent_dm)
    plt.ylim(0, extent_dm)

    # --- Tooltip a quadranti (anche su celle bianche) ---
    tooltip = ax.annotate(
        "",
        xy=(0, 0),
        xytext=(12, 12),
        textcoords="offset points",
        bbox=dict(boxstyle="round", fc=TOOLTIP_BOX_FC, ec=TOOLTIP_BOX_EC, alpha=0.95),
        arrowprops=dict(arrowstyle="->", lw=0.6),
        fontsize=TOOLTIP_FONTSIZE,
        zorder=1000,
    )
    tooltip.set_visible(False)

    ORDERED_KEYS = [
        "Included",
        "First_Depth_Read_cm",
        "Last_Depth_Read_cm",
        "Target_Depth_cm",
        "Center_Relative_East_dm",
        "Center_Relative_North_dm",
        "Edges_Crossed",
        "Error",
    ]
    TOOLTIP_OFFSET = globals().get("TOOLTIP_OFFSET", 12)

    def build_text(info: Dict[str, Any]) -> str:
        p = info["props"]
        lines = [f"Grid_data[{info['ix']}][{info['iy']}]"]
        for k in ORDERED_KEYS:
            if k in p:
                lines.append(f"{k}: {p[k]}")
        return "\n".join(lines)

    def quad_offsets(x: float, y: float) -> tuple:
        # Offset e allineamenti in base al quadrante rispetto al centro del quadro
        cx_mid = extent_dm * 0.5
        cy_mid = extent_dm * 0.5
        o = TOOLTIP_OFFSET
        if x < cx_mid and y < cy_mid:      # basso-sx -> tooltip alto-dx
            return (+o, +o, "left",  "bottom")
        if x < cx_mid and y >= cy_mid:     # alto-sx  -> tooltip basso-dx
            return (+o, -o, "left",  "top")
        if x >= cx_mid and y >= cy_mid:    # alto-dx  -> tooltip basso-sx
            return (-o, -o, "right", "top")
        # basso-dx -> tooltip alto-sx
        return (-o, +o, "right", "bottom")

    def on_move(event):
        if not event.inaxes or event.xdata is None or event.ydata is None:
            if tooltip.get_visible():
                tooltip.set_visible(False)
                fig.canvas.draw_idle()
            return
        for info in rects_info:
            contains, _ = info["rect"].contains(event)
            if contains:
                x, y = event.xdata, event.ydata
                dx, dy, ha, va = quad_offsets(x, y)
                tooltip.xy = (x, y)
                tooltip.set_text(build_text(info))
                tooltip.set_position((dx, dy))
                tooltip.set_ha(ha)
                tooltip.set_va(va)
                tooltip.set_visible(True)
                fig.canvas.draw_idle()
                return
        if tooltip.get_visible():
            tooltip.set_visible(False)
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", on_move)

    # --- Click per editare Target_Depth_cm (solo se la chiave esiste nel file) ---
    def on_click(event):
        if not event.inaxes or event.xdata is None or event.ydata is None:
            return
        for info in rects_info:
            contains, _ = info["rect"].contains(event)
            if not contains:
                continue
            ix, iy = info["ix"], info["iy"]
            key = f"IO.GPS.Sts.Grid_data[{ix}][{iy}].Target_Depth_cm"
            line_idx = key_to_line.get(key)
            if line_idx is None:
                print(f"Questa cella non ha '{key}' nel file. Non modificabile in modalità strict.")
                return
            current = info["props"].get("Target_Depth_cm", data.get(key, ""))
            # Dialog
            try:
                import tkinter as tk
                from tkinter import simpledialog, messagebox
                root = tk.Tk(); root.withdraw()
                s = simpledialog.askstring(
                    "Edit Target_Depth_cm",
                    f"{key}\nValore attuale: {current}\nNuovo valore (numero):"
                )
                root.destroy()
            except Exception:
                s = input(f"Nuovo valore per {key} (numero): ")
            if s is None:
                return
            try:
                v = float(s)
            except ValueError:
                print("Valore non numerico, modifica annullata.")
                return
            # formatting: int se intero, altrimenti float
            v_out = str(int(v)) if v.is_integer() else f"{v}"
            # Aggiorna riga e dizionari
            lines[line_idx] = f"{key}:={v_out}\n"
            data[key] = int(v) if v.is_integer() else v
            info["props"]["Target_Depth_cm"] = data[key]
            # Salva copia
            from pathlib import Path
            p = Path(source_path)
            out_path = str(p.with_name(p.stem + "_edited" + p.suffix))
            with open(out_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"Modificato {key} = {v_out}  ->  salvato in: {out_path}")
            fig.canvas.draw_idle()
            return

    fig.canvas.mpl_connect("button_press_event", on_click)

    # --- Assi/label/layout ---
    ax.set_aspect("equal", adjustable="box")
    plt.xlabel("East (dm)")
    plt.ylabel("North (dm)")
    plt.title("Grid, Included Cells and Perimeter (dm)")
    plt.tight_layout()


def main():
    path = auto_pick_file()
    print(f"Carico: {path}")
    data, lines, key_to_line = parse_recipe_indexed(str(path))
    plot_from_recipe(data, lines, key_to_line, str(path))
    plt.show()


if __name__ == "__main__":
    main()

