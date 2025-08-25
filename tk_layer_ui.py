# -*- coding: utf-8 -*-
"""Finestra Tk per controllare i layer e il reload FTP (UI soltanto)."""

from typing import Callable, Dict, Optional

def open_layer_window(
    parent_tk,
    initial_state: Dict[str, bool],
    on_change: Callable[[bool, bool, bool], None],
    on_reload: Callable[[], None],
):
    """
    Crea una Toplevel con:
      - 3 check (Path_Index, Last_Depth, Target_Depth)
      - bottoni 'Tutti', 'Nessuno'
      - bottone 'Ricarica (FTP)' che invoca on_reload()
    Ritorna l'oggetto finestra (Toplevel). Non blocca il mainloop.
    """
    import tkinter as tk
    from tkinter import ttk
    import tkinter.font as tkfont
    import config as CFG

    win = tk.Toplevel(parent_tk)
    win.title("Layer")
    if getattr(CFG, "LAYER_UI_ALWAYSONTOP", True):
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

    geom = getattr(CFG, "LAYER_UI_GEOMETRY", "280x280+60+60")
    if geom:
        try:
            win.geometry(geom)
        except Exception:
            pass
    else:
        try:
            x, y = parent_tk.winfo_rootx(), parent_tk.winfo_rooty()
            win.geometry(f"+{x+60}+{y+60}")
        except Exception:
            pass

    style = ttk.Style(win)
    try:
        base = tkfont.nametofont("TkDefaultFont").copy()
        base.configure(size=getattr(CFG, "LAYER_UI_FONT_SIZE", 13))
        style.configure("Layer.TCheckbutton", font=base)
        style.configure("Layer.TLabel", font=base)
        style.configure("Layer.TButton", font=base)
    except Exception:
        pass

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)

    var_path = tk.BooleanVar(value=bool(initial_state.get("Path_Index", True)))
    var_last = tk.BooleanVar(value=bool(initial_state.get("Last_Depth", False)))
    var_tgt  = tk.BooleanVar(value=bool(initial_state.get("Target_Depth", False)))

    ttk.Label(frame, text="Mostra:", style="Layer.TLabel").pack(anchor="w", pady=(0,8))
    ttk.Checkbutton(frame, text="Path_Index",  variable=var_path, style="Layer.TCheckbutton").pack(anchor="w", pady=4)
    ttk.Checkbutton(frame, text="Last_Depth",  variable=var_last, style="Layer.TCheckbutton").pack(anchor="w", pady=4)
    ttk.Checkbutton(frame, text="Target_Depth",variable=var_tgt,  style="Layer.TCheckbutton").pack(anchor="w", pady=4)

    btns = ttk.Frame(frame); btns.pack(fill="x", pady=(10,0))
    ttk.Button(btns, text="Tutti",  style="Layer.TButton",
               command=lambda: (var_path.set(True), var_last.set(True), var_tgt.set(True))).pack(side="left", padx=(0,8))
    ttk.Button(btns, text="Nessuno",style="Layer.TButton",
               command=lambda: (var_path.set(False), var_last.set(False), var_tgt.set(False))).pack(side="left")

    # --- Pulsante Ricarica (FTP) ---
    # UI: disabilita durante l'azione; la logica di reload è delegata a on_reload()
    def _do_reload():
        try:
            btn_reload.config(state="disabled")
            win.update_idletasks()
            on_reload()
        finally:
            try:
                btn_reload.config(state="normal")
            except Exception:
                pass

    sep = ttk.Separator(frame, orient="horizontal")
    sep.pack(fill="x", pady=(10, 8))
    btn_reload = ttk.Button(frame, text="Ricarica (FTP)", style="Layer.TButton", command=_do_reload)
    btn_reload.pack(fill="x")

    def _vars_changed(*_):
        on_change(var_path.get(), var_last.get(), var_tgt.get())

    for v in (var_path, var_last, var_tgt):
        v.trace_add("write", _vars_changed)

    # Applica stato iniziale al chiamante
    _vars_changed()

    return win
