# -*- coding: utf-8 -*-
"""Viewer interattivo strict: tooltip a quadranti, click-to-edit Target_Depth_cm."""
from typing import Any, Dict, List
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from config import (
    FIG_SIZE, FIG_BG, AX_BG,
    GRID_COLOR, GRID_ALPHA, GRID_LINEWIDTH, Z_GRID,
    INCLUDED_FACE, INCLUDED_ALPHA, INCLUDED_EDGE, INCLUDED_EDGEWIDTH, Z_INCLUDED,
    PERIMETER_COLOR, PERIMETER_WIDTH, Z_PERIMETER,
    POINT_COLOR, POINT_SIZE, Z_POINTS, LABEL_COLOR,
    TOOLTIP_BOX_FC, TOOLTIP_BOX_EC, TOOLTIP_FONTSIZE, TOOLTIP_OFFSET, HIDE_MPL_TOOLBAR
)
from grid_model import (
    require_numeric, require_int, require_points,
    collect_grid_data, validate_included_centers,
)

# Nasconde la toolbar globalmente
if HIDE_MPL_TOOLBAR:
    plt.rcParams["toolbar"] = "None"


def _build_tooltip_text(ix: int, iy: int, props: Dict[str, Any]) -> str:
    ordered = [
        "Included",
        "First_Depth_Read_cm",
        "Last_Depth_Read_cm",
        "Target_Depth_cm",
        "Center_Relative_East_dm",
        "Center_Relative_North_dm",
        "Edges_Crossed",
        "Error",
    ]
    lines = [f"Grid_data[{ix}][{iy}]"]
    for k in ordered:
        if k in props:
            lines.append(f"{k}: {props[k]}")
    return "\n".join(lines)


def _quad_offsets(x: float, y: float, extent_dm: float):
    """Offset e allineamento tooltip in base al quadrante rispetto al centro del quadro dati."""
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


def _ask_number_near_figure(fig, title: str, message: str, default: str | None = None) -> str | None:
    """
    Mostra un input ancorato alla finestra della figura (stesso monitor).
    - TkAgg: usa la finestra Tk della figura come parent.
    - QtAgg: prova QInputDialog con la finestra Qt come parent.
    - Fallback: piccolo root Tk posizionato vicino alla figura.
    """
    # 1) TkAgg (o canvas Tk disponibile)
    try:
        parent = fig.canvas.get_tk_widget().winfo_toplevel()  # type: ignore[attr-defined]
        if parent is not None:
            from tkinter import simpledialog
            full_msg = message if default is None else f"{message}\n(Predefinito: {default})"
            s = simpledialog.askstring(title, full_msg, parent=parent, initialvalue=default)
            return s
    except Exception:
        pass

    # 2) QtAgg: usa QInputDialog e aggancia al window manager della figura
    try:
        mgr = plt.get_current_fig_manager()
        win = getattr(mgr, "window", None)  # QMainWindow / QWidget
        if win is not None:
            try:
                from PyQt5.QtWidgets import QInputDialog
                text, ok = QInputDialog.getText(win, title, message)
                return str(text) if ok else None
            except Exception:
                try:
                    from PySide6.QtWidgets import QInputDialog
                    text, ok = QInputDialog.getText(win, title, message)
                    return str(text) if ok else None
                except Exception:
                    pass
    except Exception:
        pass

    # 3) Fallback: mini-root Tk vicino alla figura
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        try:
            mgr = plt.get_current_fig_manager()
            w = getattr(mgr, "window", None)
            x = y = None
            if hasattr(w, "winfo_rootx"):          # Tk
                x, y = w.winfo_rootx(), w.winfo_rooty()
            elif hasattr(w, "x") and hasattr(w, "y"):  # Qt
                x, y = int(w.x()), int(w.y())
            if x is not None and y is not None:
                root.geometry(f"+{x+60}+{y+60}")
        except Exception:
            pass
        full_msg = message if default is None else f"{message}\n(Predefinito: {default})"
        s = simpledialog.askstring(title, full_msg, parent=root, initialvalue=default)
        try:
            root.destroy()
        except Exception:
            pass
        return s
    except Exception:
        pass

    return None


def view_from_file(data: Dict[str, Any], lines: List[str], key_to_line: Dict[str, int], source_path: str):
    # --- Parametri base strict ---
    extent_dm = require_numeric(
        data,
        ["IO.GPS.Vis.Square_Width_Scale_dm"],   # chiave unica, corretta ortograficamente
        "dimensione quadrato (dm)",
    )
    N = require_int(data, "IO.GPS.Cfg.Num_Grid_Rows_Cols", "numero righe/colonne griglia")
    step = require_numeric(
        data,
        ["IO.GPS.Cfg.Grid_Cell_Size_dm", "IO.GPS. Cfg.Grid_Cell_Size_dm"],  # accetta anche la variante con spazio
        "passo griglia (dm)",
    )
    if N <= 0 or step <= 0:
        raise SystemExit("ERRORE: Num_Grid_Rows_Cols e Grid_Cell_Size_dm devono essere > 0.")
    easts, norths = require_points(data)

    cells = collect_grid_data(data)
    validate_included_centers(cells)  # controlla solo Included=TRUE

    # --- Setup figura ---
    fig = plt.figure(figsize=FIG_SIZE, facecolor=FIG_BG)
    ax = plt.gca()
    ax.set_facecolor(AX_BG)

    # Fallback extra: prova a nascondere una toolbar già creata dal backend
    if HIDE_MPL_TOOLBAR:
        try:
            manager = plt.get_current_fig_manager()
            tb = getattr(manager, "toolbar", None)
            if tb is not None:
                try:
                    tb.pack_forget()  # TkAgg
                except Exception:
                    try:
                        tb.hide()      # altri backend
                    except Exception:
                        pass
        except Exception:
            pass

    # 1) Hitbox invisibili per TUTTE le celle (tooltip anche sulle bianche)
    rects_info: List[Dict[str, Any]] = []
    for ix in range(N):
        for iy in range(N):
            llx = ix * step
            lly = iy * step
            r = Rectangle((llx, lly), step, step, facecolor="none", edgecolor="none", linewidth=0.0, zorder=9)
            ax.add_patch(r)
            rects_info.append({"rect": r, "ix": ix, "iy": iy, "props": cells.get((ix, iy), {})})

    # 2) Celle verdi Included=TRUE (usando SOLO i centri del file)
    for (ix, iy), props in cells.items():
        if props.get("Included") is True:
            cx = float(props["Center_Relative_East_dm"])
            cy = float(props["Center_Relative_North_dm"])
            llx = cx - step / 2.0
            lly = cy - step / 2.0
            rect = Rectangle(
                (llx, lly), step, step,
                facecolor=INCLUDED_FACE, alpha=INCLUDED_ALPHA,
                edgecolor=INCLUDED_EDGE, linewidth=INCLUDED_EDGEWIDTH,
                zorder=Z_INCLUDED, joinstyle="miter",
            )
            ax.add_patch(rect)

    # 3) Perimetro e punti
    xs_line = easts[:] + [easts[0]]
    ys_line = norths[:] + [norths[0]]
    plt.plot(xs_line, ys_line, linewidth=PERIMETER_WIDTH, color=PERIMETER_COLOR, zorder=Z_PERIMETER)
    plt.scatter(easts, norths, s=POINT_SIZE, color=POINT_COLOR, zorder=Z_POINTS)
    for i, (x0, y0) in enumerate(zip(easts, norths), start=1):
        plt.annotate(str(i), (x0, y0), xytext=(4, 4), textcoords="offset points",
                     color=LABEL_COLOR, zorder=Z_POINTS+1)

    # 4) Griglia per ultima, sopra tutto
    for k in range(N + 1):
        x = k * step; y = k * step
        plt.axvline(x=x, linewidth=GRID_LINEWIDTH, alpha=GRID_ALPHA, color=GRID_COLOR, zorder=Z_GRID)
        plt.axhline(y=y, linewidth=GRID_LINEWIDTH, alpha=GRID_ALPHA, color=GRID_COLOR, zorder=Z_GRID)

    # Limiti esatti
    plt.xlim(0, extent_dm)
    plt.ylim(0, extent_dm)

    # Tooltip a quadranti
    tooltip = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
        bbox=dict(boxstyle="round", fc=TOOLTIP_BOX_FC, ec=TOOLTIP_BOX_EC, alpha=0.95),
        arrowprops=dict(arrowstyle="->", lw=0.6), fontsize=TOOLTIP_FONTSIZE, zorder=1000,
    )
    tooltip.set_visible(False)

    def on_move(event):
        if not event.inaxes or event.xdata is None or event.ydata is None:
            if tooltip.get_visible():
                tooltip.set_visible(False); fig.canvas.draw_idle()
            return
        for info in rects_info:
            ok, _ = info["rect"].contains(event)
            if ok:
                x, y = event.xdata, event.ydata
                dx, dy, ha, va = _quad_offsets(x, y, extent_dm)
                tooltip.xy = (x, y)
                tooltip.set_text(_build_tooltip_text(info["ix"], info["iy"], info["props"]))
                tooltip.set_position((dx, dy))
                tooltip.set_ha(ha); tooltip.set_va(va)
                tooltip.set_visible(True); fig.canvas.draw_idle()
                return
        if tooltip.get_visible():
            tooltip.set_visible(False); fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", on_move)

    # Click per editare Target_Depth_cm solo se la chiave esiste nel file
    def on_click(event):
        if not event.inaxes or event.xdata is None or event.ydata is None:
            return
        for info in rects_info:
            ok, _ = info["rect"].contains(event)
            if not ok:
                continue
            ix, iy = info["ix"], info["iy"]
            key = f"IO.GPS.Sts.Grid_data[{ix}][{iy}].Target_Depth_cm"
            line_idx = key_to_line.get(key)
            if line_idx is None:
                print(f"Cella [{ix}][{iy}] senza '{key}' nel file: non modificabile.")
                return

            current = info["props"].get("Target_Depth_cm")
            msg = f"{key}\nValore attuale: {current}\nNuovo valore (numero):"
            s = _ask_number_near_figure(
                fig, "Edit Target_Depth_cm", msg,
                default=str(current) if current is not None else None
            )
            if s is None:
                return
            try:
                v = float(s)
            except ValueError:
                print("Valore non numerico, modifica annullata.")
                return

            v_out = str(int(v)) if v.is_integer() else f"{v}"
            # Patch riga e dizionari, salva copia _edited
            lines[line_idx] = f"{key}:={v_out}\n"
            info["props"]["Target_Depth_cm"] = int(v) if v.is_integer() else v

            from pathlib import Path
            p = Path(source_path)
            out_path = str(p.with_name(p.stem + "_edited" + p.suffix))
            with open(out_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"Modificato {key} = {v_out}  ->  salvato in: {out_path}")
            fig.canvas.draw_idle()
            return

    fig.canvas.mpl_connect("button_press_event", on_click)

    # Assi/label/layout
    ax.set_aspect("equal", adjustable="box")
    plt.xlabel("East (dm)")
    plt.ylabel("North (dm)")
    plt.title("Grid, Included Cells and Perimeter (dm)")
    plt.tight_layout()
