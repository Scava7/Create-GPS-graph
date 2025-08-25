# -*- coding: utf-8 -*-
"""Viewer interattivo strict: tooltip a quadranti, overlay centrati, edit Target_Depth_cm, UI Tk e FTP pull."""
from typing import Any, Dict, List, Tuple
import os, time
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from ftplib import FTP

import config as CFG
from config import (
    FIG_SIZE, FIG_BG, AX_BG,
    GRID_COLOR, GRID_ALPHA, GRID_LINEWIDTH, Z_GRID,
    INCLUDED_FACE, INCLUDED_ALPHA, INCLUDED_EDGE, INCLUDED_EDGEWIDTH, Z_INCLUDED,
    PERIMETER_COLOR, PERIMETER_WIDTH, Z_PERIMETER,
    POINT_COLOR, POINT_SIZE, Z_POINTS, LABEL_COLOR, POINTS_LABEL_COLOR,
    TOOLTIP_BOX_FC, TOOLTIP_BOX_EC, TOOLTIP_FONTSIZE, TOOLTIP_OFFSET, HIDE_MPL_TOOLBAR,
)
from grid_model import (
    require_numeric, require_int, require_points,
    collect_grid_data, validate_included_centers,
)

# --- Flag overlay (fallback se non definiti in config) ---
SHOW_PATH_INDEX    = getattr(CFG, "SHOW_PATH_INDEX", True)
SHOW_LAST_DEPTH    = getattr(CFG, "SHOW_LAST_DEPTH", False)
SHOW_TARGET_DEPTH  = getattr(CFG, "SHOW_TARGET_DEPTH", False)
PATH_TEXT_FONTSIZE = getattr(CFG, "PATH_TEXT_FONTSIZE", max(TOOLTIP_FONTSIZE, 10))

# --- UI Tk (dimensioni, stile) ---
LAYER_UI_GEOMETRY    = getattr(CFG, "LAYER_UI_GEOMETRY", "280x180+60+60")
LAYER_UI_FONT_SIZE   = getattr(CFG, "LAYER_UI_FONT_SIZE", 13)
LAYER_UI_ALWAYSONTOP = getattr(CFG, "LAYER_UI_ALWAYSONTOP", True)

# --- Toolbar Matplotlib ---
if HIDE_MPL_TOOLBAR:
    plt.rcParams["toolbar"] = "None"


# ============================ Tooltip helpers =================================
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
        "Path_Index",
    ]
    lines = [f"Grid_data[{ix}][{iy}]"]
    for k in ordered:
        if k in props:
            lines.append(f"{k}: {props[k]}")
    return "\n".join(lines)


def _quad_offsets(x: float, y: float, extent_dm: float) -> Tuple[float, float, str, str]:
    cx_mid = extent_dm * 0.5
    cy_mid = extent_dm * 0.5
    o = TOOLTIP_OFFSET
    if x < cx_mid and y < cy_mid:      # basso-sx -> tooltip alto-dx
        return (+o, +o, "left",  "bottom")
    if x < cx_mid and y >= cy_mid:     # alto-sx  -> tooltip basso-dx
        return (+o, -o, "left",  "top")
    if x >= cx_mid and y >= cy_mid:    # alto-dx  -> tooltip basso-sx
        return (-o, -o, "right", "top")
    return (-o, +o, "right", "bottom") # basso-dx -> tooltip alto-sx


def _ask_number_near_figure(fig, title: str, message: str, default: str | None = None) -> str | None:
    """Dialog di input numero (Tk-only)."""
    # 1) TkAgg (o canvas Tk disponibile)
    try:
        parent = fig.canvas.get_tk_widget().winfo_toplevel()  # type: ignore[attr-defined]
        if parent is not None:
            from tkinter import simpledialog
            full = message if default is None else f"{message}\n(Predefinito: {default})"
            return simpledialog.askstring(title, full, parent=parent, initialvalue=default)
    except Exception:
        pass
    # 2) Fallback mini-root
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk(); root.withdraw()
        full = message if default is None else f"{message}\n(Predefinito: {default})"
        s = simpledialog.askstring(title, full, parent=root, initialvalue=default)
        try: root.destroy()
        except Exception: pass
        return s
    except Exception:
        pass
    return None


# ================================ FTP PULL ====================================
def _ts() -> str:
    fmt = getattr(CFG, "BACKUP_STAMP_FMT", "%Y%m%d-%H%M%S")
    return time.strftime(fmt)

def _script_dir() -> Path:
    return Path(__file__).resolve().parent

def _local_recipe_path() -> Path:
    name = getattr(CFG, "LOCAL_RECIPE_FILENAME", "GPS_Grid.txtrecipe")
    return _script_dir() / name

def _ftp_connect() -> FTP:
    ftp = FTP()
    ftp.connect(getattr(CFG, "FTP_HOST", "127.0.0.1"), 21, timeout=getattr(CFG, "FTP_TIMEOUT", 8))
    ftp.login(getattr(CFG, "FTP_USER", ""), getattr(CFG, "FTP_PASS", ""))
    try: ftp.set_pasv(getattr(CFG, "FTP_PASSIVE", True))
    except Exception: pass
    return ftp

def _popup(title: str, message: str, kind: str = "info", parent=None):
    """Messagebox Tk; fallback: print."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = None
        if parent is None:
            root = tk.Tk(); root.withdraw()
        if kind == "warning":
            messagebox.showwarning(title, message, parent=parent or root)
        elif kind == "error":
            messagebox.showerror(title, message, parent=parent or root)
        else:
            messagebox.showinfo(title, message, parent=parent or root)
        if root is not None:
            try: root.destroy()
            except Exception: pass
    except Exception:
        print(f"[{title}] {message}")

def ftp_pull_recipe_to_script_dir(verbose: bool = True) -> Path | None:
    """
    Scarica FTP_REMOTE_PATH nella cartella dello script come LOCAL_RECIPE_FILENAME.
    Sicuro: scarica su .tmp, fa backup del locale (se presente), rename atomico.
    Ritorna Path se ok, altrimenti None (file locale invariato).
    """
    if not getattr(CFG, "FTP_ENABLED", True):
        if verbose: print("[FTP] Disabilitato da config.")
        return None

    remote_path = getattr(CFG, "FTP_REMOTE_PATH", "")
    if not remote_path:
        if verbose: print("[FTP pull] FTP_REMOTE_PATH non impostato.")
        return None

    dst = _local_recipe_path()
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        ftp = _ftp_connect()
        rdir, rname = os.path.split(remote_path)
        if rdir: ftp.cwd(rdir)
        with open(tmp, "wb") as f:
            ftp.retrbinary("RETR " + rname, f.write)
        try: ftp.quit()
        except Exception: pass

        if dst.exists():
            bak = dst.with_name(f"{dst.stem}_{_ts()}{dst.suffix}")
            dst.rename(bak)
            if verbose: print(f"[FTP pull] Backup locale: {bak.name}")

        tmp.rename(dst)
        if verbose: print(f"[FTP pull] Scaricato → {dst}")
        return dst

    except Exception as e:
        try:
            if tmp.exists(): tmp.unlink()
        except Exception:
            pass
        if verbose: print(f"[FTP pull] Errore: {e}. Uso il file locale (se presente): {dst}")
        return None

def ensure_local_recipe_pulled(silent: bool = False, popup: bool = True, parent_tk=None) -> Path:
    """
    Se FTP_PULL_ON_START=True prova il pull. Mostra popup secondo config.
    Ritorna SEMPRE il path locale atteso (esista o meno).
    NOTA: chiamala PRIMA di leggere/parlare il file per la sessione corrente.
    """
    dst = _local_recipe_path()
    do_pull = getattr(CFG, "FTP_PULL_ON_START", True)
    do_popups = popup and getattr(CFG, "FTP_POPUPS", True)
    title = getattr(CFG, "FTP_POPUP_TITLE", "FTP")

    had_old = dst.exists()
    ok = False
    err = None
    try:
        if do_pull:
            ok = ftp_pull_recipe_to_script_dir(verbose=not silent) is not None
    except Exception as e:
        err = str(e)

    if do_popups:
        if ok:
            if getattr(CFG, "FTP_POPUPS_ON_SUCCESS", True):
                msg = f"File scaricato da FTP in:\n{dst}"
                if had_old:
                    msg += "\n\nIl precedente file locale è stato salvato come backup con timestamp."
                _popup(title, msg, "info", parent=parent_tk)
        else:
            if not err and not do_pull:
                msg = "FTP non eseguito (disattivato in config). Si userà il file locale (se presente):\n" + str(dst)
            elif not err:
                msg = "Connessione FTP fallita o file remoto non disponibile.\n" \
                      "Si userà il file locale (se presente):\n" + str(dst)
            else:
                msg = f"Errore FTP: {err}\nSi userà il file locale (se presente):\n{dst}"
            _popup(title, msg, "warning", parent=parent_tk)

    return dst


# ================================ VIEWER ======================================
def view_from_file(data: Dict[str, Any], lines: List[str], key_to_line: Dict[str, int], source_path: str):
    # Parametri base
    extent_dm = require_numeric(data, ["IO.GPS.Vis.Square_Width_Scale_dm"], "dimensione quadrato (dm)")
    N = require_int(data, "IO.GPS.Cfg.Num_Grid_Rows_Cols", "numero righe/colonne griglia")
    step = require_numeric(data, ["IO.GPS.Cfg.Grid_Cell_Size_dm", "IO.GPS. Cfg.Grid_Cell_Size_dm"], "passo griglia (dm)")
    if N <= 0 or step <= 0:
        raise SystemExit("ERRORE: Num_Grid_Rows_Cols e Grid_Cell_Size_dm devono essere > 0.")
    easts, norths = require_points(data)

    cells = collect_grid_data(data)
    validate_included_centers(cells)  # controlla solo Included=TRUE

    # Figura/assi
    fig = plt.figure(figsize=FIG_SIZE, facecolor=FIG_BG)
    ax = plt.gca()
    ax.set_facecolor(AX_BG)

    if HIDE_MPL_TOOLBAR:
        try:
            manager = plt.get_current_fig_manager()
            tb = getattr(manager, "toolbar", None)
            if tb is not None:
                try: tb.pack_forget()  # TkAgg
                except Exception:
                    try: tb.hide()      # altri backend
                    except Exception: pass
        except Exception:
            pass

    # Hitbox invisibili (tooltip anche su celle vuote)
    rects_info: List[Dict[str, Any]] = []
    for ix in range(N):
        for iy in range(N):
            llx = ix * step; lly = iy * step
            r = Rectangle((llx, lly), step, step, facecolor="none", edgecolor="none", linewidth=0.0, zorder=9)
            ax.add_patch(r)
            rects_info.append({"rect": r, "ix": ix, "iy": iy, "props": cells.get((ix, iy), {})})

    # Celle Included (posizione dai Center_*)
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

    # Overlay centrati (un unico Text per cella, multilinea)
    def _fmt_num(v: Any) -> str:
        if isinstance(v, (int, float)):
            try:
                return f"{int(v)}" if float(v).is_integer() else f"{v}"
            except Exception:
                return f"{v}"
        return ""

    def _cell_text(props: Dict[str, Any], show_path: bool, show_last: bool, show_target: bool) -> str:
        out: List[str] = []
        if show_path:
            idx = props.get("Path_Index")
            if isinstance(idx, (int, float)) and idx > 0:
                out.append(f"{int(idx)}")
        if show_last:
            s = _fmt_num(props.get("Last_Depth_Read_cm"))
            if s: out.append(s)
        if show_target:
            s = _fmt_num(props.get("Target_Depth_cm"))
            if s: out.append(s)
        return "\n".join(out)

    overlay_entries: List[Dict[str, Any]] = []
    for (ix, iy), props in cells.items():
        if not any(k in props for k in ("Path_Index", "Last_Depth_Read_cm", "Target_Depth_cm")):
            continue
        cx = ix * step + step / 2.0
        cy = iy * step + step / 2.0
        content = _cell_text(props, SHOW_PATH_INDEX, SHOW_LAST_DEPTH, SHOW_TARGET_DEPTH)
        t = ax.text(
            cx, cy, content if content else "",
            ha="center", va="center", fontsize=PATH_TEXT_FONTSIZE, color=LABEL_COLOR,
            zorder=Z_GRID + 2, clip_on=True, visible=bool(content),
        )
        try: t.set_linespacing(1.0)
        except Exception: pass
        overlay_entries.append({"text": t, "props": props})

    # Perimetro e punti
    xs_line = easts[:] + [easts[0]]
    ys_line = norths[:] + [norths[0]]
    plt.plot(xs_line, ys_line, linewidth=PERIMETER_WIDTH, color=PERIMETER_COLOR, zorder=Z_PERIMETER)
    plt.scatter(easts, norths, s=POINT_SIZE, color=POINT_COLOR, zorder=Z_POINTS)
    for i, (x0, y0) in enumerate(zip(easts, norths), start=1):
        plt.annotate(str(i), (x0, y0), xytext=(4, 4), textcoords="offset points",
                     color=POINTS_LABEL_COLOR, zorder=Z_POINTS+1)

    # Griglia
    for k in range(N + 1):
        x = k * step; y = k * step
        plt.axvline(x=x, linewidth=GRID_LINEWIDTH, alpha=GRID_ALPHA, color=GRID_COLOR, zorder=Z_GRID)
        plt.axhline(y=y, linewidth=GRID_LINEWIDTH, alpha=GRID_ALPHA, color=GRID_COLOR, zorder=Z_GRID)

    # Limiti/label
    plt.xlim(0, extent_dm); plt.ylim(0, extent_dm)
    ax.set_aspect("equal", adjustable="box")
    plt.xlabel("East (dm)"); plt.ylabel("North (dm)")
    plt.title("Grid, Included Cells and Perimeter (dm)")
    plt.tight_layout()

    # Tooltip
    tooltip = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
        bbox=dict(boxstyle="round", fc=TOOLTIP_BOX_FC, ec=TOOLTIP_BOX_EC, alpha=0.95),
        arrowprops=dict(arrowstyle="->", lw=0.6), fontsize=TOOLTIP_FONTSIZE, zorder=1000,
    ); tooltip.set_visible(False)

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

    # Click: edit Target_Depth_cm (se presente nel file)
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
            s = _ask_number_near_figure(fig, "Edit Target_Depth_cm", msg,
                                        default=str(current) if current is not None else None)
            if s is None:
                return
            try:
                v = float(s)
            except ValueError:
                print("Valore non numerico, modifica annullata.")
                return

            v_out = str(int(v)) if v.is_integer() else f"{v}"
            lines[line_idx] = f"{key}:={v_out}\n"
            info["props"]["Target_Depth_cm"] = int(v) if v.is_integer() else v

            p = Path(source_path)
            out_path = str(p.with_name(p.stem + "_edited" + p.suffix))
            with open(out_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"Modificato {key} = {v_out}  ->  salvato in: {out_path}")
            fig.canvas.draw_idle(); return
    fig.canvas.mpl_connect("button_press_event", on_click)

    # UI Tk “Layer” (se Tk disponibile), altrimenti fallback tastiera P/L/T
    def _refresh_overlays(show_path: bool, show_last: bool, show_target: bool):
        for entry in overlay_entries:
            t = entry["text"]; props = entry["props"]
            txt = _cell_text(props, show_path, show_last, show_target)
            if txt:
                t.set_text(txt); t.set_visible(True)
            else:
                t.set_visible(False)
        fig.canvas.draw_idle()

    # scorciatoie tastiera
    def on_key(event):
        if not event.key: return
        k = event.key.lower()
        if k not in ("p", "l", "t"): return
        s = getattr(on_key, "_state", {"p": SHOW_PATH_INDEX, "l": SHOW_LAST_DEPTH, "t": SHOW_TARGET_DEPTH})
        s[k] = not s.get(k, False)
        on_key._state = s
        _refresh_overlays(s["p"], s["l"], s["t"])
    fig.canvas.mpl_connect("key_press_event", on_key)

    # pannello Tk
    created_ui = False
    try:
        parent = fig.canvas.get_tk_widget().winfo_toplevel()  # type: ignore[attr-defined]
        if parent is not None:
            import tkinter as tk
            from tkinter import ttk
            import tkinter.font as tkfont

            win = tk.Toplevel(parent); win.title("Layer")
            if LAYER_UI_ALWAYSONTOP:
                try: win.attributes("-topmost", True)
                except Exception: pass

            # posizionamento
            if LAYER_UI_GEOMETRY:
                try: win.geometry(LAYER_UI_GEOMETRY)
                except Exception: pass
            else:
                try:
                    x, y = parent.winfo_rootx(), parent.winfo_rooty()
                    win.geometry(f"+{x+60}+{y+60}")
                except Exception: pass

            # stile
            style = ttk.Style(win)
            try:
                base = tkfont.nametofont("TkDefaultFont").copy()
                base.configure(size=LAYER_UI_FONT_SIZE)
                style.configure("Layer.TCheckbutton", font=base)
                style.configure("Layer.TLabel", font=base)
                style.configure("Layer.TButton", font=base)
            except Exception:
                pass

            frame = ttk.Frame(win, padding=12); frame.pack(fill="both", expand=True)
            var_path = tk.BooleanVar(value=SHOW_PATH_INDEX)
            var_last = tk.BooleanVar(value=SHOW_LAST_DEPTH)
            var_tgt  = tk.BooleanVar(value=SHOW_TARGET_DEPTH)

            ttk.Label(frame, text="Mostra:", style="Layer.TLabel").pack(anchor="w", pady=(0,8))
            ttk.Checkbutton(frame, text="Path_Index",  variable=var_path, style="Layer.TCheckbutton").pack(anchor="w", pady=4)
            ttk.Checkbutton(frame, text="Last_Depth",  variable=var_last, style="Layer.TCheckbutton").pack(anchor="w", pady=4)
            ttk.Checkbutton(frame, text="Target_Depth",variable=var_tgt,  style="Layer.TCheckbutton").pack(anchor="w", pady=4)

            btns = ttk.Frame(frame); btns.pack(fill="x", pady=(10,0))
            ttk.Button(btns, text="Tutti",  style="Layer.TButton",
                       command=lambda: (var_path.set(True), var_last.set(True), var_tgt.set(True))).pack(side="left", padx=(0,8))
            ttk.Button(btns, text="Nessuno",style="Layer.TButton",
                       command=lambda: (var_path.set(False), var_last.set(False), var_tgt.set(False))).pack(side="left")

            def on_vars_changed(*_):
                _refresh_overlays(var_path.get(), var_last.get(), var_tgt.get())
            for v in (var_path, var_last, var_tgt):
                v.trace_add("write", on_vars_changed)

            def on_close_fig(_evt):
                try: win.destroy()
                except Exception: pass
            fig.canvas.mpl_connect("close_event", on_close_fig)

            created_ui = True
            _refresh_overlays(var_path.get(), var_last.get(), var_tgt.get())
    except Exception:
        created_ui = False

    if not created_ui:
        _refresh_overlays(SHOW_PATH_INDEX, SHOW_LAST_DEPTH, SHOW_TARGET_DEPTH)
