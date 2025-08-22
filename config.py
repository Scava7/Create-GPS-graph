# -*- coding: utf-8 -*-
"""Configurazioni grafiche e UI."""


# Figure
FIG_SIZE = (8, 8) # pollici; il viewer rispetta i limiti dati dal file, senza padding
FIG_BG = "white"
AX_BG = "white"


# Griglia (disegnata per ultima, sopra tutto)
GRID_COLOR = "lightgray"
GRID_ALPHA = 0.6
GRID_LINEWIDTH = 0.8
Z_GRID = 100


# Celle Included
INCLUDED_FACE = "green"
INCLUDED_ALPHA = 0.35
INCLUDED_EDGE = None
INCLUDED_EDGEWIDTH = 0.0
Z_INCLUDED = 10


# Perimetro e punti
PERIMETER_COLOR = "tab:blue"
PERIMETER_WIDTH = 2.0
Z_PERIMETER = 20


POINT_COLOR = "black"
POINT_SIZE = 90
Z_POINTS = 25
LABEL_COLOR = "black"


# Tooltip
TOOLTIP_BOX_FC = "white"
TOOLTIP_BOX_EC = "0.5"
TOOLTIP_FONTSIZE = 9
TOOLTIP_OFFSET = 12 # pixel di offset; il quadrante decide segno e allineamento