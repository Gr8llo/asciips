"""
engine/big_font.py - Dizionario e renderer per caratteri ASCII a blocchi giganti (5 righe)
utilizzati dal Big HUD (orologio HH:MM:SS e temperatura XX°C) su schermi grandi.
"""

from __future__ import annotations
from typing import Dict, List

# Colorazione di default per il Big HUD: Oro brillante (RGB 24-bit)
BIG_HUD_GOLD = (255, 215, 0)
BIG_FONT_HEIGHT: int = 5

# Matrice font gigante a 5 righe d'altezza (blocchi solidi '█', '▀', '▄')
BIG_FONT_5X: Dict[str, List[str]] = {
    "0": [
        "████",
        "█  █",
        "█  █",
        "█  █",
        "████",
    ],
    "1": [
        " ██ ",
        "███ ",
        " ██ ",
        " ██ ",
        "████",
    ],
    "2": [
        "████",
        "   █",
        "████",
        "█   ",
        "████",
    ],
    "3": [
        "████",
        "   █",
        "████",
        "   █",
        "████",
    ],
    "4": [
        "█  █",
        "█  █",
        "████",
        "   █",
        "   █",
    ],
    "5": [
        "████",
        "█   ",
        "████",
        "   █",
        "████",
    ],
    "6": [
        "████",
        "█   ",
        "████",
        "█  █",
        "████",
    ],
    "7": [
        "████",
        "   █",
        "  ██",
        "  █ ",
        "  █ ",
    ],
    "8": [
        "████",
        "█  █",
        "████",
        "█  █",
        "████",
    ],
    "9": [
        "████",
        "█  █",
        "████",
        "   █",
        "████",
    ],
    ":": [
        "    ",
        " ██ ",
        "    ",
        " ██ ",
        "    ",
    ],
    "-": [
        "    ",
        "    ",
        "████",
        "    ",
        "    ",
    ],
    "°": [
        "█▀█ ",
        "▀▀▀ ",
        "    ",
        "    ",
        "    ",
    ],
    "C": [
        "████",
        "█   ",
        "█   ",
        "█   ",
        "████",
    ],
    " ": [
        "  ",
        "  ",
        "  ",
        "  ",
        "  ",
    ],
}

# Alias per retrocompatibilità
BIG_FONT: Dict[str, List[str]] = BIG_FONT_5X


def render_big_text(text: str, spacing: int = 1) -> List[str]:
    """
    Converte una stringa (es. '12:34:56' o '24°C') in 5 righe di testo ASCII a blocchi.
    Tutti i glifi utilizzano larghezza fissa in colonne ASCII/UTF-8 per evitare disallineamenti.
    """
    if not text:
        return ["" for _ in range(BIG_FONT_HEIGHT)]

    sep = " " * max(0, spacing)
    glyph_columns: List[List[str]] = [
        BIG_FONT_5X.get(ch, BIG_FONT_5X[" "]) for ch in text
    ]

    return [
        sep.join(col[row] for col in glyph_columns)
        for row in range(BIG_FONT_HEIGHT)
    ]
