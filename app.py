# -*- coding: utf-8 -*-
"""CLI principale: view/import/reset-included/set-target/export.
Se lanci senza subcomando, parte "view" di default.
"""
import argparse
from pathlib import Path
import sys
import matplotlib.pyplot as plt

from util_paths import auto_pick_file
from recipe_parser import parse_recipe_indexed
from plot_view import view_from_file
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
    p_view.add_argument("path", nargs="?", help="Percorso al file (.txtrecipe o .txrtrecipe)")

    # import
    p_imp = sub.add_parser("import", help="Importa un file ricetta in SQLite")
    p_imp.add_argument("path", help="File ricetta (.txtrecipe / .txrtrecipe)")
    p_imp.add_argument("--db", default="workspace.sqlite", help="Percorso DB (default: workspace.sqlite)")

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

def main():
    args = cli()

    try:
        # DEFAULT: se nessun subcomando, apri il viewer
        if args.cmd is None or args.cmd == "view":
            path_arg = getattr(args, "path", None)
            path = Path(path_arg) if path_arg else auto_pick_file()
            print(f"[view] Carico: {path}")
            data, lines, key_to_line = parse_recipe_indexed(str(path))
            view_from_file(data, lines, key_to_line, str(path))
            plt.show()
            return

        if args.cmd == "import":
            print(f"[import] Inizializzo DB: {args.db}")
            init_db(args.db)
            print(f"[import] Import da: {args.path}")
            data, lines, key_to_line = parse_recipe_indexed(args.path)
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
