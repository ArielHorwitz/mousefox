"""Home of `Palette`."""

import kvex as kx


DARK_GREEN = 0.24, 0.32, 0.13
LIGHT_GREEN = 0.72, 0.80, 0.60
LIGHT_BLUE = 0.47, 0.56, 0.82
DARK_BLUE = 0.16, 0.22, 0.34
DARK_PURPLE = 0.26, 0.11, 0.20


class Palette:
    """Color palette values."""
    # Background
    BG_BASE = kx.XColor(*DARK_PURPLE, v=0.4)
    BG_BASE2 = kx.XColor(*DARK_PURPLE, v=0.3)
    BG_MAIN = kx.XColor(*DARK_GREEN, v=0.4)
    BG_MAIN2 = kx.XColor(*DARK_GREEN, v=0.3)
    BG_ALT = kx.XColor(*DARK_BLUE, v=0.4)
    BG_ALT2 = kx.XColor(*DARK_BLUE, v=0.3)
    # Foreground
    BASE = kx.XColor(*DARK_PURPLE)
    MAIN = kx.XColor(*DARK_GREEN)
    MAIN_LIGHT = kx.XColor(*LIGHT_GREEN)
    ALT = kx.XColor(*DARK_BLUE)
    ALT_LIGHT = kx.XColor(*LIGHT_BLUE)
