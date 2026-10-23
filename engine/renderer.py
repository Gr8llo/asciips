"""
engine/renderer.py - Pipeline grafica unificata per Giorno e Notte:
Sfondo trasparente/uniforme senza blocchi rettangolari opachi sulle onde;
tutta la scena (cielo, onde, profondità marine, navi e proiettili) è disegnata
in Foreground con sfumature continue.
"""

from __future__ import annotations
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple
from asciimatics.screen import Screen

from config import (
    DAY_SEA_GRADIENTS,
    RGB,
    SEA_GRADIENTS,
    SKY_GRADIENTS,
    WeatherCondition,
)


def clamp_byte(value: float) -> int:
    """Limita un valore numerico all'intervallo intero [0, 255]."""
    return max(0, min(255, int(round(value))))


def lerp_rgb(color_a: RGB, color_b: RGB, t: float) -> RGB:
    """Interpolazione lineare continua tra due colori RGB 24-bit."""
    t = max(0.0, min(1.0, t))
    return (
        clamp_byte(color_a[0] + (color_b[0] - color_a[0]) * t),
        clamp_byte(color_a[1] + (color_b[1] - color_a[1]) * t),
        clamp_byte(color_a[2] + (color_b[2] - color_a[2]) * t),
    )


def ansi_truecolor_fg(rgb: RGB) -> str:
    """Genera la sequenza di escape ANSI TrueColor (24-bit) per il primo piano."""
    r, g, b = rgb
    return f"\x1b[38;2;{r};{g};{b}m"


def ansi_truecolor_bg(rgb: RGB) -> str:
    """Genera la sequenza di escape ANSI TrueColor (24-bit) per lo sfondo."""
    r, g, b = rgb
    return f"\x1b[48;2;{r};{g};{b}m"


# Tabella completa xterm-256 (16..255) per matching euclideo accurato
_CUBE_STEPS = (0, 95, 135, 175, 215, 255)
_XTERM_PALETTE: List[Tuple[int, RGB]] = []
for _ri, _rv in enumerate(_CUBE_STEPS):
    for _gi, _gv in enumerate(_CUBE_STEPS):
        for _bi, _bv in enumerate(_CUBE_STEPS):
            _idx = 16 + 36 * _ri + 6 * _gi + _bi
            _XTERM_PALETTE.append((_idx, (_rv, _gv, _bv)))
for _gi in range(24):
    _gv = 8 + _gi * 10
    _XTERM_PALETTE.append((232 + _gi, (_gv, _gv, _gv)))


@lru_cache(maxsize=8192)
def rgb_to_xterm256(rgb: RGB) -> int:
    """
    Converte una tupla RGB 24-bit nell'indice colore xterm-256 percettivamente più vicino,
    preservando la saturazione e la tinta (es. marroni legno caldi, blu profondi, bordeaux).
    """
    r, g, b = rgb
    best_idx = 16
    best_dist = 10**9
    rg = r - g
    gb = g - b
    rb = r - b
    for idx, (pr, pg, pb) in _XTERM_PALETTE:
        dr = r - pr
        dg = g - pg
        db = b - pb
        drg = rg - (pr - pg)
        dgb = gb - (pg - pb)
        drb = rb - (pr - pb)
        dist = (
            2 * dr * dr
            + 4 * dg * dg
            + 3 * db * db
            + (drg * drg + 2 * dgb * dgb + drb * drb)
        )
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


class Renderer:
    """
    Gestore del rendering per AsciiShips sopra asciimatics.screen.Screen.
    Usa per Giorno e Notte lo stesso identico metodo grafico trasparente in Foreground
    (zero blocchi opachi a gradoni sulle onde o attorno alle navi).
    """

    def __init__(self, screen: Screen) -> None:
        self.screen: Screen = screen
        self.width: int = screen.width
        self.height: int = screen.height
        self.flash_intensity: float = 0.0
        self.is_day: bool = True
        self.condition: WeatherCondition = WeatherCondition.CLEAR
        self._row_gradient_rgb: List[RGB] = [(0, 0, 0)] * max(1, self.height)
        self._surface_y_by_col: List[int] = [int(self.height * 0.68)] * max(1, self.width)

    def sync_dimensions(self) -> None:
        """Sincronizza le dimensioni con lo Screen asciimatics corrente."""
        self.width = self.screen.width
        self.height = self.screen.height
        if len(self._row_gradient_rgb) != self.height:
            self._row_gradient_rgb = [(0, 0, 0)] * max(1, self.height)
        if len(self._surface_y_by_col) != self.width:
            self._surface_y_by_col = [int(self.height * 0.68)] * max(1, self.width)

    def set_wave_profile(self, surface_y_by_col: Sequence[int]) -> None:
        """Registra la quota verticale dell'onda per ogni colonna x."""
        self.sync_dimensions()
        for x in range(min(self.width, len(surface_y_by_col))):
            self._surface_y_by_col[x] = surface_y_by_col[x]

    def is_underwater(self, x: int, y: int) -> bool:
        """Restituisce True se la cella (x, y) si trova sulla superficie o sotto il mare."""
        if 0 <= x < len(self._surface_y_by_col):
            return y >= self._surface_y_by_col[x]
        return False

    def compute_vertical_gradients(
        self,
        condition: WeatherCondition,
        sea_level_y: int,
        *,
        is_day: bool = True,
    ) -> None:
        """Calcola la curva continua di colore RGB riga per riga per cielo e mare."""
        self.sync_dimensions()
        sky_top, sky_bottom = SKY_GRADIENTS.get(
            condition, SKY_GRADIENTS[WeatherCondition.CLEAR]
        )
        sea_map = DAY_SEA_GRADIENTS if is_day else SEA_GRADIENTS
        sea_top, sea_bottom = sea_map.get(
            condition, sea_map[WeatherCondition.CLEAR]
        )

        horizon = max(1, min(self.height - 1, sea_level_y))
        sea_span = max(1, self.height - horizon)

        for y in range(self.height):
            if y < horizon:
                t = y / max(1, horizon - 1)
                rgb = lerp_rgb(sky_top, sky_bottom, t)
            else:
                t = (y - horizon) / max(1, sea_span - 1)
                rgb = lerp_rgb(sea_top, sea_bottom, t)

            if self.flash_intensity > 0.01:
                rgb = lerp_rgb(rgb, (210, 225, 250), min(0.75, self.flash_intensity))

            self._row_gradient_rgb[y] = rgb

    def get_row_bg_rgb(self, y: int) -> RGB:
        """Restituisce il colore di riferimento del gradiente verticale alla riga y."""
        if 0 <= y < len(self._row_gradient_rgb):
            return self._row_gradient_rgb[y]
        return (5, 10, 25)

    def draw_background(
        self,
        condition: WeatherCondition,
        sea_level_y: int,
        *,
        is_day: bool = True,
    ) -> None:
        """
        Pulisce il frame buffer lasciando lo sfondo uniforme e trasparente
        (senza alcun blocco solido rettangolare sul mare o sulle onde).
        """
        self.condition = condition
        self.is_day = is_day
        self.compute_vertical_gradients(condition, sea_level_y, is_day=is_day)
        self.screen.clear_buffer(
            Screen.COLOUR_WHITE,
            Screen.A_NORMAL,
            Screen.COLOUR_BLACK,
        )

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        fg_rgb: RGB,
        *,
        bg_rgb: Optional[RGB] = None,
        bold: bool = False,
        transparent: bool = True,
    ) -> None:
        """
        Disegna una stringa alle coordinate (x, y) in Foreground su sfondo trasparente.
        """
        if y < 0 or y >= self.height or not text:
            return

        if x >= self.width or x + len(text) <= 0:
            return

        if self.flash_intensity > 0.05:
            fg_rgb = lerp_rgb(fg_rgb, (245, 250, 255), min(0.6, self.flash_intensity))

        fg_idx = rgb_to_xterm256(fg_rgb)
        bg_idx = (
            rgb_to_xterm256(bg_rgb)
            if bg_rgb is not None
            else Screen.COLOUR_BLACK
        )
        attr = Screen.A_BOLD if bold else Screen.A_NORMAL

        self.screen.print_at(
            text,
            x,
            y,
            colour=fg_idx,
            attr=attr,
            bg=bg_idx,
            transparent=transparent,
        )

    def draw_sprite(
        self,
        lines: List[str],
        x: int,
        y: int,
        fg_rgb: RGB,
        *,
        bold: bool = False,
        transparent: bool = True,
    ) -> None:
        """Disegna uno sprite ASCII multi-riga su sfondo trasparente."""
        for row_offset, line in enumerate(lines):
            self.draw_text(
                line,
                x,
                y + row_offset,
                fg_rgb,
                bold=bold,
                transparent=transparent,
            )
