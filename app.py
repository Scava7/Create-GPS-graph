# -*- coding: utf-8 -*-
"""CLI principale: view/import/reset-included/set-target/export.
Se lanci senza subcomando, parte "view" di default.
"""
import argparse
from pathlib import Path
import sys
import matplotlib.pyplot as plt

import config as CFG
from util_paths import auto_pick_file
from recipe_parser import parse_recipe_indexed
from recipe import load_io_recipe, load_grid_recipe
from plot_view import (
    view_from_file,
    ensure_local_grid_recipe_pulled,
    ensure_local_io_recipe_pulled,
)

from dbio import (
    init_db, import_recipe_to_db,
    reset_included, set_target_value,
    export_recipe_from_db,
)


def cli():
    ap = argparse.ArgumentParser(prog="gps_grid")
    sub = ap.add_subparsers(dest="cmd")  # non-required: gestiamo default noi

    # view
    p_view = sub.add_parser("view", help="Apri il viewer interattivo su un file ricetta")
    p_view.add_argument("path", nargs="?", help="Percorso al file GRIGLIA (.txtrecipe/.txrtrecipe)")
    p_view.add_argument("--ftp-pull", action="store_true",
                        help="Forza pull da FTP (ignora config). Usato solo se 'path' è assente.")
    p_view.add_argument("--no-ftp", action="store_true",
                        help="Salta pull da FTP (ignora config). Usato solo se 'path' è assente.")

    # import
    p_imp = sub.add_parser("import", help="Importa un file ricetta in SQLite")
    p_imp.add_argument("path", help="File ricetta GRIGLIA (.txtrecipe / .txrtrecipe)")
    p_imp.add_argument("--db", default="workspace.sqlite", help="Percorso DB (default: workspace.sqlite)")
    p_imp.add_argument("--io", help="(Facoltativo) File IO.txtrecipe da unire all'import")

    # reset-included
    p_reset = sub.add_parser("reset-included", help="Imposta Included=FALSE su un set di celle già presenti nel file")
    p_reset.add_argument("--db", default="workspace.sqlite")
    p_reset.add_argument("--coords", help="Lista 'x,y;x,y;...'", default=None)
    p_reset.add_argument("--rect", nargs=4, type=int, metavar=("X0","X1","Y0","Y1"),
                         help="Rettangolo di indici (inclusivi)")

    # set-target
    p_set = sub.add_parser("set-target", help="Imposta Target_Depth_cm per coordinate")
    p_set.add_argument("--db", default="workspace.sqlite")
    p_set.add_argument("--coords", required=True, help="Lista 'x,y;x,y;...'")
    p_set.add_argument("--value", required=True, type=float, help="Valore in cm")

    # export
    p_exp = sub.add_parser("export", help="Esporta file ricetta fedele all'originale con le modifiche da DB")
    p_exp.add_argument("--db", default="workspace.sqlite")
    p_exp.add_argument("--out", default="edited.txtrecipe")

    return ap.parse_args()


def parse_coords(s: str):
    pairs = []
    for chunk in s.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        x_str, y_str = [t.strip() for t in chunk.split(",", 1)]
        pairs.append((int(x_str), int(y_str)))
    return pairs


def _pick_view_paths(path_arg, args):
    """
    Ritorna (io_path, grid_path).

    - Se 'path_arg' è fornito, è il file GRIGLIA.
    - Altrimenti, decide se fare FTP in base a config/flag per scaricare
      sia la GRIGLIA che l'IO. In caso di problemi, fa fallback ai file locali.
    """
    # Decidi la policy FTP
    want_ftp = getattr(CFG, "FTP_PULL_ON_START", True)
    if getattr(args, "ftp_pull", False):
        want_ftp = True
    if getattr(args, "no_ftp", False):
        want_ftp = False

    # 1) GRID path
    if path_arg:  # passato a mano: è il file GRIGLIA
        grid_path = Path(path_arg)
    else:
        if want_ftp:
            try:
                grid_path = Path(ensure_local_grid_recipe_pulled(silent=False, popup=True, parent_tk=None))
            except Exception:
                grid_path = auto_pick_file("GPS_Grid.txtrecipe")
        else:
            grid_path = auto_pick_file("GPS_Grid.txtrecipe")

    # 2) IO path
    io_filename = getattr(CFG, "LOCAL_IO_RECIPE_FILENAME", "IO.txtrecipe")
    if want_ftp:
        try:
            io_path = Path(ensure_local_io_recipe_pulled(silent=False, popup=True, parent_tk=None))
        except Exception:
            io_path = auto_pick_file(io_filename)
    else:
        io_path = auto_pick_file(io_filename)

    return io_path, grid_path


# SHIM di compatibilità per eventuali chiamate legacy che si aspettano UNA sola path (la griglia)
def _pick_view_path(path_arg, args):
    _, grid_path = _pick_view_paths(path_arg, args)
    return grid_path


def main():
    args = cli()

    try:
        # DEFAULT: se nessun subcomando, apri il viewer
        if args.cmd is None or args.cmd == "view":
            path_arg = getattr(args, "path", None)

            # Scegli i due file
            io_path, grid_path = _pick_view_paths(path_arg, args)
            print(f"[view] IO:   {io_path}")
            print(f"[view] GRID: {grid_path}")

            # Carica separatamente e unisci
            io_only = load_io_recipe(str(io_path))  # solo IO.GPS.Cfg/Vis/Sts.*
            grid_only, lines, key_to_line = load_grid_recipe(str(grid_path))  # solo GVL.GPS_Grid_data[..]

            merged = {}
            merged.update(io_only)
            merged.update(grid_only)

            # Apri il viewer passando RIGHE/MAPPA del SOLO file GRIGLIA (edit sicuri)
            view_from_file(merged, lines, key_to_line, str(grid_path))
            plt.show()
            return

        if args.cmd == "import":
            print(f"[import] Inizializzo DB: {args.db}")
            init_db(args.db)

            # Importa GRIGLIA
            print(f"[import] Import GRID da: {args.path}")
            data, lines, key_to_line = parse_recipe_indexed(args.path)

            # (Facoltativo) unisci IO se fornito
            if args.io:
                print(f"[import] Unisco IO da: {args.io}")
                io_only = load_io_recipe(args.io)
                data.update(io_only)

            import_recipe_to_db(args.db, data, lines, key_to_line)
            print(f"[import] Completato su {args.db}")
            return

        if args.cmd == "reset-included":
            if args.coords:
                coords = parse_coords(args.coords)
                print(f"[reset-included] Coords: {coords}")
                reset_included(args.db, coords=coords)
            elif args.rect:
                x0, x1, y0, y1 = args.rect
                print(f"[reset-included] Rect: ({x0},{x1},{y0},{y1})")
                reset_included(args.db, rect=(x0, x1, y0, y1))
            else:
                print("Specificare --coords o --rect")
                return
            print("[reset-included] Operazione completata.")
            return

        if args.cmd == "set-target":
            coords = parse_coords(args.coords)
            print(f"[set-target] Coords: {coords}  -> value={args.value}")
            set_target_value(args.db, coords, args.value)
            print("[set-target] Target aggiornati.")
            return

        if args.cmd == "export":
            print(f"[export] DB: {args.db}  -> out: {args.out}")
            export_recipe_from_db(args.db, args.out)
            print(f"[export] Esportato su: {args.out}")
            return

    except SystemExit as e:
        # require_* può lanciare SystemExit: rendiamo il messaggio chiaro e usciamo con status 1
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERRORE] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
