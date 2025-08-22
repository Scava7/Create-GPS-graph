# -*- coding: utf-8 -*-
from pathlib import Path


def auto_pick_file(preferred_name: str = "GPS_Grid.txtrecipe") -> Path:
    """Cerca il file preferito nella cartella corrente; altrimenti il primo *.txtrecipe; altrimenti dialog.
    Lancia eccezione se non viene selezionato nulla (modalità strict).
    """
    here = Path.cwd()
    cand = here / preferred_name
    if cand.exists():
        return cand
    found = list(here.glob("*.txtrecipe"))
    if found:
        return found[0]
    

    # file dialog
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        path = filedialog.askopenfilename(
        title="Seleziona il file .txtrecipe",
        filetypes=[("Recipe file", "*.txtrecipe"), ("Tutti i file", "*.*")]
        )
        root.destroy()

        if path:
            return Path(path)
        
    except Exception:
        pass
    raise FileNotFoundError("Nessun file .txtrecipe trovato o selezionato.")