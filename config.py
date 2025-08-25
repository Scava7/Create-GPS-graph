# -*- coding: utf-8 -*-
"""Configurazioni grafiche, UI e FTP per il viewer Grid."""

# --- Overlay UI (Tk) ---
# finestra con i check dei layer (usa Tk/ttk)
LAYER_UI_GEOMETRY = "280x280+60+60"  # "LxH+X+Y"; metti None/"" per auto vicino alla figura
LAYER_UI_FONT_SIZE = 13              # grandezza testo check
LAYER_UI_ALWAYSONTOP = True          # finestra sempre in primo piano

# --- Figure / Assi ---
FIG_SIZE = (8, 8)      # pollici
FIG_BG = "white"
AX_BG = "white"

# --- Griglia (disegnata per ultima) ---
GRID_COLOR = "gray"
GRID_ALPHA = 0.6
GRID_LINEWIDTH = 1.5
Z_GRID = 100

# --- Celle Included ---
INCLUDED_FACE = "lightblue"
INCLUDED_ALPHA = 0.35
INCLUDED_EDGE = None
INCLUDED_EDGEWIDTH = 0.0
Z_INCLUDED = 10

# --- Perimetro e punti ---
PERIMETER_COLOR = "tab:brown"
PERIMETER_WIDTH = 2.0
Z_PERIMETER = 20

POINT_COLOR = "red"
POINT_SIZE = 90
Z_POINTS = 25
LABEL_COLOR = "black"
POINTS_LABEL_COLOR = "red"

# --- Tooltip ---
TOOLTIP_BOX_FC = "white"
TOOLTIP_BOX_EC = "0.5"
TOOLTIP_FONTSIZE = 9
TOOLTIP_OFFSET = 12  # px; il quadrante decide segno e allineamento

# --- Toolbar Matplotlib ---
HIDE_MPL_TOOLBAR = True

# --- Overlay: cosa mostrare di default + font ---
SHOW_PATH_INDEX = True
SHOW_LAST_DEPTH = False
SHOW_TARGET_DEPTH = False
PATH_TEXT_FONTSIZE = 10  # grandezza numeri dentro le celle

# --- FTP (SOLO PULL) ---
FTP_ENABLED = True
FTP_HOST = "192.168.10.30"
FTP_USER = "root"
FTP_PASS = "pdm3"
FTP_TIMEOUT = 8
FTP_PASSIVE = True

# percorso remoto del file da scaricare (percorso UNIX lato FTP)
FTP_REMOTE_PATH = "/home/cds-apps/Backup/GPS_Grid.txtrecipe"

# nome locale con cui salvare (nella cartella dello script)
LOCAL_RECIPE_FILENAME = "GPS_Grid.txtrecipe"

# prova a scaricare automaticamente prima di leggere il file
FTP_PULL_ON_START = True

# timestamp per i backup locali
BACKUP_STAMP_FMT = "%Y%m%d-%H%M%S"

# --- Popup di notifica FTP ---
FTP_POPUPS = True                # mostra popup informativi/errore
FTP_POPUPS_ON_SUCCESS = True     # popup anche se lo scarico riesce
FTP_POPUP_TITLE = "FTP – GPS_Grid"
