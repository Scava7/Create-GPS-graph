# recipe.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, Tuple, List
import re
from recipe_parser import parse_recipe_indexed

_IO_PREFIX = ("IO.GPS.Cfg.", "IO.GPS.Vis.", "IO.GPS.Sts.")
_GRID_RE = re.compile(r"^GVL\.GPS_Grid_data\[\d+\]\[\d+\]\.[A-Za-z_]\w*$")

def load_io_recipe(io_path: str) -> Dict[str, Any]:
    """Ritorna solo IO.GPS.(Cfg|Vis|Sts).* da IO.txtrecipe."""
    data, _lines, _k2l = parse_recipe_indexed(io_path)
    return {k: v for k, v in data.items() if k.startswith(_IO_PREFIX)}

def load_grid_recipe(grid_path: str) -> Tuple[Dict[str, Any], List[str], Dict[str, int]]:
    """Ritorna (dati_griglia_filtrati, righe_file, mappa_chiave->linea) dal file GPS_Grid.txtrecipe."""
    data, lines, k2l = parse_recipe_indexed(grid_path)
    grid = {k: v for k, v in data.items() if _GRID_RE.match(k)}
    return grid, lines, k2l
