# -*- coding: utf-8 -*-
"""Supporto SQLite: init, import, reset included, set target, export fedele al file."""
import re, sqlite3
from typing import Any, Dict, List, Tuple

from recipe_parser import parse_value


def init_db(db_path: str):
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS grid_cells(
          x INT, y INT,
          included INTEGER, first_depth_cm REAL, last_depth_cm REAL,
          target_depth_cm REAL, center_east_dm REAL, center_north_dm REAL,
          edges_crossed INT, error INTEGER,
          PRIMARY KEY(x,y)
        );
        CREATE TABLE IF NOT EXISTS cfg(
          key TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS lines(
          idx INTEGER PRIMARY KEY, content TEXT
        );
        CREATE TABLE IF NOT EXISTS keys_map(
          key TEXT PRIMARY KEY, line_idx INT
        );
        """
    )
    db.commit(); db.close()


def import_recipe_to_db(db_path: str, data: Dict[str, Any], lines: List[str], key_to_line: Dict[str, int]):
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    # cfg
    for k, v in data.items():
        if k.startswith("IO.GPS.Cfg.") or k.startswith("IO.GPS.Vis."):
            cur.execute("INSERT OR REPLACE INTO cfg(key,value) VALUES(?,?)", (k, str(v)))
    # lines, keys_map
    cur.executemany("INSERT OR REPLACE INTO lines(idx,content) VALUES(?,?)", [(i, s) for i, s in enumerate(lines)])
    cur.executemany("INSERT OR REPLACE INTO keys_map(key,line_idx) VALUES(?,?)", key_to_line.items())
    # grid
    grid: Dict[Tuple[int, int], Dict[str, Any]] = {}
    import re
    grid_re = re.compile(r"^GVL\.GPS_Grid_data\[(\d+)\]\[(\d+)\]\.([A-Za-z_]\w*)$")
    for k, v in data.items():
        m = grid_re.match(k)
        if not m:
            continue
        x, y, prop = int(m.group(1)), int(m.group(2)), m.group(3)
        d = grid.setdefault((x, y), {})
        d[prop] = v
    rows = []
    for (x, y), d in grid.items():
        rows.append((
            x, y,
            1 if d.get("Included") is True else (0 if d.get("Included") is False else None),
            d.get("First_Depth_Read_cm"),
            d.get("Last_Depth_Read_cm"),
            d.get("Target_Depth_cm"),
            d.get("Center_Relative_East_dm"),
            d.get("Center_Relative_North_dm"),
            d.get("Edges_Crossed"),
            1 if d.get("Error") is True else (0 if d.get("Error") is False else None),
        ))
    cur.executemany(
        """INSERT OR REPLACE INTO grid_cells
            (x,y,included,first_depth_cm,last_depth_cm,target_depth_cm,center_east_dm,center_north_dm,edges_crossed,error)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    db.commit(); db.close()


def reset_included(db_path: str, coords=None, rect=None):
    db = sqlite3.connect(db_path); cur = db.cursor()
    if coords:
        cur.executemany("UPDATE grid_cells SET included=0 WHERE x=? AND y=? AND included IS NOT NULL", coords)
    elif rect:
        x0, x1, y0, y1 = rect
        cur.execute(
            """UPDATE grid_cells SET included=0
                   WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? AND included IS NOT NULL""",
            (x0, x1, y0, y1),
        )
    db.commit(); db.close()


def set_target_value(db_path: str, coords, value: float):
    db = sqlite3.connect(db_path); cur = db.cursor()
    cur.executemany("UPDATE grid_cells SET target_depth_cm=? WHERE x=? AND y=?", [(value, x, y) for x, y in coords])
    db.commit(); db.close()


def _patch_line(old_line: str, new_value: str) -> str:
    # sostituisce solo la parte dopo ':=' mantenendo eventuali commenti di fine riga
    parts = re.split(r"(:=\s*)", old_line, maxsplit=1)
    if len(parts) >= 3:
        head = parts[0] + parts[1]
        tail = old_line[old_line.find(parts[2]):]
        cpos = tail.find("//")
        if cpos >= 0:
            comment = tail[cpos:]
            return head + f"{new_value} " + comment + ("\n" if not tail.endswith("\n") else "")
        return head + f"{new_value}\n"
    return old_line


def export_recipe_from_db(db_path: str, out_path: str):
    db = sqlite3.connect(db_path); cur = db.cursor()
    lines = [row[0] for row in cur.execute("SELECT content FROM lines ORDER BY idx").fetchall()]

    # Included
    for x, y, incl in cur.execute("SELECT x,y,included FROM grid_cells WHERE included IS NOT NULL"):
        key = f"GVL.GPS_Grid_data[{x}][{y}].Included"
        row = cur.execute("SELECT line_idx FROM keys_map WHERE key=?", (key,)).fetchone()
        if not row:
            continue
        idx = row[0]; new_val = "TRUE" if incl == 1 else "FALSE"
        lines[idx] = _patch_line(lines[idx], new_val)

    # Target_Depth_cm
    for x, y, val in cur.execute("SELECT x,y,target_depth_cm FROM grid_cells WHERE target_depth_cm IS NOT NULL"):
        key = f"GVL.GPS_Grid_data[{x}][{y}].Target_Depth_cm"
        row = cur.execute("SELECT line_idx FROM keys_map WHERE key=?", (key,)).fetchone()
        if not row:
            continue
        idx = row[0]
        new_val = str(int(val)) if float(val).is_integer() else str(val)
        lines[idx] = _patch_line(lines[idx], new_val)

    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    db.close()