"""
entities/ship.py - Entità veliero ad altissima leggibilità a distanza:
- Scafo marrone noce vivo rgb(210, 130, 60) e alberi in BOLD (A_BOLD)
- Vele bianche/crema a contrasto netto senza toni grigi o slavati
- Badge '[ FRASE ]' a sfondo pieno crema luminoso rgb(245, 235, 180) o oro rgb(255, 215, 0)
  centrato sulla vela maestra (o su cartiglio dedicato sopra lo scafo se troppo lungo).
"""

from __future__ import annotations
from dataclasses import dataclass
import enum
import math
import random
from typing import Dict, List, Optional, Tuple

from config import (
    COLOR_HULL_SMOKE_DARK,
    COLOR_SHIP_BADGE_CREAM,
    COLOR_SHIP_BADGE_GOLD,
    COLOR_SHIP_BANNER,
    COLOR_SHIP_BANNER_DAY,
    COLOR_SHIP_CANNON,
    COLOR_SHIP_DAMAGED,
    COLOR_SHIP_DECK,
    COLOR_SHIP_HULL,
    COLOR_SHIP_HULL_DAY,
    COLOR_SHIP_MAST,
    COLOR_SHIP_SAIL,
    COLOR_SHIP_SAIL_DAY,
    COLOR_SHIP_SUBMERGED,
    COLOR_SHIP_WAKE,
    COLOR_SMOKE,
    COLOR_WAVE_FOAM,
    RGB,
    SHIP_FIRE_COOLDOWN_MAX,
    SHIP_FIRE_COOLDOWN_MIN,
    SHIP_MAX_HP,
    SHIP_MAX_SPEED,
    SHIP_MIN_SPEED,
    SHIP_PALETTES,
    SHIP_SINK_SPEED,
)
from engine.renderer import Renderer, lerp_rgb
from entities.sea import Sea


class ShipState(enum.Enum):
    """Stati del ciclo di vita di una nave."""
    SAILING = "sailing"
    SINKING = "sinking"
    SUNK = "sunk"


_MIRROR_CHAR_MAP: Dict[str, str] = {
    "/": "\\",
    "\\": "/",
    "(": ")",
    ")": "(",
    "<": ">",
    ">": "<",
    "[": "]",
    "]": "[",
    "{": "}",
    "}": "{",
}


def mirror_ascii_line(line: str) -> str:
    """Inverte orizzontalmente una riga ASCII specchiando i caratteri direzionali."""
    return "".join(_MIRROR_CHAR_MAP.get(ch, ch) for ch in reversed(line))


def _normalize_template(lines: List[str]) -> List[str]:
    """Uniforma tutte le righe del template alla medesima larghezza massima."""
    max_len = max(len(r) for r in lines)
    return [r.ljust(max_len) for r in lines]


# 1. Galeone da guerra (pesante, 3 alberi con vele solide, batteria di cannoni [o])
GALEONE_RIGHT: List[str] = _normalize_template([
    r"         |~           |~           |~   ",
    r"        /|\          /|\          /|\   ",
    r"       /___\     /_________\     /___\  ",
    r"      /_____\   /___________\   /_____\ ",
    r"  ___ /_____\  /_____________\  /_____\ ",
    r" |---\  (|)          (|)          (|) /^",
    r" |===+===+============+============+==\ ",
    r" |  [o]  [o]   [o]   [o]   [o]   [o]   )",
    r" \====================================/ ",
    r"  \____|_______|_____________|_______/  ",
])
GALEONE_LEFT: List[str] = [mirror_ascii_line(row) for row in GALEONE_RIGHT]

# 2. Brigantino/Fregata (2 alberi con vele bombate solide, cannoni [o] in murata)
BRIG_RIGHT: List[str] = _normalize_template([
    r"          |~             |~           ",
    r"         /|\            /|\           ",
    r"        /___\       /_________\       ",
    r"       /_____\     /___________\      ",
    r"  ___  (_____)    (_____________)  /^ ",
    r" |---\   (|)            (|)       /   ",
    r" |===+====+==============+=======/    ",
    r"  \  [o]   [o]    [o]    [o]    /     ",
    r"   \___________________________/      ",
])
BRIG_LEFT: List[str] = [mirror_ascii_line(row) for row in BRIG_RIGHT]

# 3. Caravella/Vascello corsaro (2 alberi con vele latine/quadre solide, cannoni [o])
CARAVELLA_RIGHT: List[str] = _normalize_template([
    r"           |~             |~          ",
    r"          /|\            /|\          ",
    r"         /___\       /_________\      ",
    r"        /_____\     /___________\     ",
    r"  __   /_______\   /_____________\ /^ ",
    r" |  \__   (|)            (|)      /   ",
    r" \===+=====+==============+======/    ",
    r"  \   [o]   [o]    [o]    [o]   /     ",
    r"   \___________________________/      ",
])
CARAVELLA_LEFT: List[str] = [mirror_ascii_line(row) for row in CARAVELLA_RIGHT]

# Alias per retrocompatibilità
BASE_SHIP_RIGHT: List[str] = GALEONE_RIGHT
BASE_SHIP_LEFT: List[str] = GALEONE_LEFT


@dataclass(frozen=True)
class ShipClassSpec:
    """
    Specifica strutturale per una classe navale con coordinate fisse (riga e colonne)
    per la vela maestra e per il cartiglio/pennone sopra lo scafo.
    """
    name: str
    right_art: List[str]
    left_art: List[str]
    max_hp: int
    speed_range: Tuple[float, float]
    sail_row: int
    sail_span_right: Tuple[int, int]
    cartouche_row: int
    cartouche_span_right: Tuple[int, int]


SHIP_CLASSES: Dict[str, ShipClassSpec] = {
    "galeone": ShipClassSpec(
        name="galeone",
        right_art=GALEONE_RIGHT,
        left_art=GALEONE_LEFT,
        max_hp=140,
        speed_range=(SHIP_MIN_SPEED, SHIP_MAX_SPEED * 0.85),
        sail_row=4,
        sail_span_right=(16, 29),
        cartouche_row=5,
        cartouche_span_right=(8, 36),
    ),
    "brigantino": ShipClassSpec(
        name="brigantino",
        right_art=BRIG_RIGHT,
        left_art=BRIG_LEFT,
        max_hp=SHIP_MAX_HP,
        speed_range=(SHIP_MIN_SPEED * 1.05, SHIP_MAX_SPEED),
        sail_row=4,
        sail_span_right=(19, 32),
        cartouche_row=5,
        cartouche_span_right=(7, 33),
    ),
    "caravella": ShipClassSpec(
        name="caravella",
        right_art=CARAVELLA_RIGHT,
        left_art=CARAVELLA_LEFT,
        max_hp=90,
        speed_range=(SHIP_MIN_SPEED * 1.15, SHIP_MAX_SPEED),
        sail_row=4,
        sail_span_right=(20, 33),
        cartouche_row=5,
        cartouche_span_right=(8, 33),
    ),
}


@dataclass
class HullSmokeParticle:
    """Particella incandescente ('@', '*', 'o') che sale dallo scafo danneggiato."""
    x: float
    y: float
    vx: float
    vy: float
    char: str
    age: float = 0.0
    ttl: float = 1.4


class Ship:
    """
    Veliero animato multi-classe con rendering BOLD saturo (scafo marrone noce vivo
    rgb(210, 130, 60)) e badge '[ FRASE ]' a sfondo pieno crema luminoso o oro
    centrato sulla vela maestra.
    """

    _next_id: int = 1

    def __init__(
        self,
        *,
        x: float,
        direction: int,
        banner: str,
        speed: Optional[float] = None,
        max_hp: Optional[int] = None,
        ship_class: Optional[str] = None,
        palette_name: Optional[str] = None,
    ) -> None:
        self.ship_id: int = Ship._next_id
        Ship._next_id += 1

        self.x: float = x
        self.y: float = 0.0
        self.direction: int = 1 if direction >= 0 else -1
        self.banner: str = " ".join(banner.strip().split()) or "BOLOGNA"

        chosen_class = (
            ship_class
            if ship_class in SHIP_CLASSES
            else random.choice(list(SHIP_CLASSES.keys()))
        )
        self.ship_class: str = chosen_class
        self.spec: ShipClassSpec = SHIP_CLASSES[chosen_class]

        chosen_palette = (
            palette_name
            if palette_name in SHIP_PALETTES
            else random.choice(list(SHIP_PALETTES.keys()))
        )
        self.palette_name: str = chosen_palette
        self.palette: Dict[str, RGB] = SHIP_PALETTES[chosen_palette]

        self.speed: float = (
            speed
            if speed is not None
            else random.uniform(*self.spec.speed_range)
        )
        resolved_hp = max_hp if max_hp is not None else self.spec.max_hp
        self.max_hp: int = resolved_hp
        self.hp: int = resolved_hp
        self.state: ShipState = ShipState.SAILING

        self.fire_cooldown: float = random.uniform(
            SHIP_FIRE_COOLDOWN_MIN * 0.6, SHIP_FIRE_COOLDOWN_MAX
        )
        self.sink_offset: float = 0.0
        self.sink_list_dir: int = random.choice([-1, 1])
        self.hit_flash_timer: float = 0.0
        self.smoke_phase: float = random.uniform(0.0, math.tau)
        self.hull_smoke: List[HullSmokeParticle] = []

        self._lines: List[str] = []
        self._banner_spans: Dict[int, Tuple[int, int]] = {}
        self.width: int = len(self.spec.right_art[0])
        self.height: int = len(self.spec.right_art)
        self._build_ascii_art()

    def _get_main_sail_span(self) -> Tuple[int, int]:
        """Restituisce l'intervallo fisso [col_start, col_end) della vela maestra."""
        s, e = self.spec.sail_span_right
        if self.direction > 0:
            return s, e
        return self.width - e, self.width - s

    def _get_cartouche_span(self) -> Tuple[int, int]:
        """Restituisce l'intervallo fisso [col_start, col_end) del cartiglio sopra lo scafo."""
        s, e = self.spec.cartouche_span_right
        if self.direction > 0:
            return s, e
        return self.width - e, self.width - s

    def _embed_fixed_span(
        self, row_idx: int, text: str, span_start: int, span_end: int
    ) -> None:
        """
        Incastona il badge `text` centrandolo nello spazio utile [span_start, span_end)
        della riga `row_idx` SENZA MAI alterare la lunghezza della riga dello sprite.
        """
        line = self._lines[row_idx]
        expected_len = len(line)
        avail = max(0, span_end - span_start)
        if avail <= 0 or not text:
            return

        clipped = text[:avail]
        pad_left = (avail - len(clipped)) // 2
        col_start = span_start + pad_left
        col_end = col_start + len(clipped)

        new_line = line[:col_start] + clipped + line[col_end:]
        assert len(new_line) == expected_len
        self._lines[row_idx] = new_line
        self._banner_spans[row_idx] = (col_start, col_end)

    def _build_ascii_art(self) -> None:
        """
        Costruisce le righe dello sprite orientato a destra o a sinistra
        e incastona il badge '[ FRASE ]' a sfondo pieno:
        - Se la frase entra nella vela maestra, formatta '[ FRASE ]' (o '[FRASE]') centrato sulla vela maestra.
        - Se la frase è troppo lunga per la vela maestra, centra '[ FRASE ]' sul cartiglio sopra lo scafo.
        """
        template = self.spec.right_art if self.direction > 0 else self.spec.left_art
        self._lines = list(template)
        self._banner_spans.clear()
        self.width = len(self._lines[0])
        self.height = len(self._lines)

        clean_banner = " ".join(self.banner.strip().split())
        if not clean_banner:
            return

        sail_start, sail_end = self._get_main_sail_span()
        sail_avail = sail_end - sail_start

        if len(clean_banner) <= sail_avail:
            if len(clean_banner) + 4 <= sail_avail:
                badge_text = f"[ {clean_banner} ]"
            elif len(clean_banner) + 2 <= sail_avail:
                badge_text = f"[{clean_banner}]"
            else:
                badge_text = clean_banner
            self._embed_fixed_span(
                self.spec.sail_row, badge_text, sail_start, sail_end
            )
        else:
            cart_start, cart_end = self._get_cartouche_span()
            cart_avail = cart_end - cart_start
            inner_max = max(1, cart_avail - 4)
            badge_text = f"[ {clean_banner[:inner_max]} ]"
            self._embed_fixed_span(
                self.spec.cartouche_row, badge_text, cart_start, cart_end
            )

    @property
    def center_x(self) -> float:
        """Coordinata X del centro della nave."""
        return self.x + self.width * 0.5

    @property
    def cannon_origin(self) -> Tuple[float, float]:
        """Punto di origine dei colpi di cannone sulle bocche di fuoco '[o]'."""
        deck_y = self.y + (self.height - 2.5)
        cannon_x = self.center_x + (self.direction * 4.5)
        return cannon_x, deck_y

    def hitbox(self) -> Tuple[float, float, float, float]:
        """Rettangolo di collisione calibrato sulla sagoma reale del veliero."""
        return (
            self.x + 2.0,
            self.y + 1.5,
            self.x + self.width - 2.0,
            self.y + self.height - 0.5,
        )

    def contains_point(self, px: float, py: float) -> bool:
        """Verifica se un proiettile in (px, py) ha colpito la nave."""
        if self.state != ShipState.SAILING:
            return False
        left, top, right, bottom = self.hitbox()
        return left <= px <= right and top <= py <= bottom

    def take_damage(self, amount: int) -> None:
        """Applica danni allo scafo e avvia lo stato SINKING se gli HP scendono a 0."""
        if self.state != ShipState.SAILING:
            return
        self.hp = max(0, self.hp - amount)
        self.hit_flash_timer = 0.22
        if self.hp <= 0:
            self.state = ShipState.SINKING

    def reverse_direction(self, new_direction: int) -> None:
        """Inverte la rotta e rigenera l'orientamento specchiato dello sprite."""
        if new_direction != self.direction:
            self.direction = 1 if new_direction >= 0 else -1
            self._build_ascii_art()

    def update(self, dt: float, sea: Sea, screen_width: int) -> None:
        """
        Aggiorna movimento orizzontale, galleggiamento sul pelo dell'acqua,
        cooldown di fuoco e discesa/inclinazione durante l'affondamento.
        """
        self.smoke_phase += dt * 4.2
        if self.hit_flash_timer > 0.0:
            self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)

        if self.state == ShipState.SAILING:
            slope = sea.wave_slope_at(self.center_x)
            effective_speed = self.speed * (1.0 - 0.12 * slope * self.direction)
            self.x += self.direction * effective_speed * dt

            if self.direction > 0 and self.x > screen_width - self.width - 2:
                self.reverse_direction(-1)
            elif self.direction < 0 and self.x < 2:
                self.reverse_direction(1)

            waterline_y = sea.surface_y_at(self.center_x)
            self.y = waterline_y - (self.height - 1.0)
            self.fire_cooldown = max(0.0, self.fire_cooldown - dt)

        elif self.state == ShipState.SINKING:
            self.x += self.direction * (self.speed * 0.20) * dt
            self.sink_offset += SHIP_SINK_SPEED * dt
            waterline_y = sea.surface_y_at(self.center_x)
            self.y = waterline_y - (self.height - 1.0) + self.sink_offset

            if self.sink_offset >= self.height + 2.5:
                self.state = ShipState.SUNK

        hp_ratio = self.hp / max(1, self.max_hp)
        if (hp_ratio < 0.5 or self.state == ShipState.SINKING) and self.state != ShipState.SUNK:
            from_stern = random.random() < 0.45
            emit_x = (
                self.center_x - self.direction * (self.width * 0.26)
                if from_stern
                else self.center_x + random.uniform(-1.2, 1.2)
            )
            emit_y = self.y + (4.2 if from_stern else 2.2)
            if emit_y < sea.surface_y_at(emit_x):
                self.hull_smoke.append(
                    HullSmokeParticle(
                        x=emit_x,
                        y=emit_y,
                        vx=random.uniform(-1.4, 1.4) - self.direction * 0.9,
                        vy=random.uniform(-4.6, -2.4),
                        char=random.choice(("*", "@", "o")),
                        age=0.0,
                        ttl=random.uniform(0.85, 1.65),
                    )
                )

        alive_smoke: List[HullSmokeParticle] = []
        for sp in self.hull_smoke:
            sp.age += dt
            sp.x += sp.vx * dt
            sp.y += sp.vy * dt
            if sp.age < sp.ttl and sp.y >= 1.0:
                alive_smoke.append(sp)
        self.hull_smoke = alive_smoke[-28:]

    def _is_stern_or_bow_wood_on_row4(self, col_idx: int) -> bool:
        """Identifica il castello di poppa ('___') o il bompresso ('/^') sulla riga 4."""
        if self.direction > 0:
            return col_idx < 6 or col_idx >= self.width - 4
        return col_idx >= self.width - 6 or col_idx < 4

    def _cell_style(
        self,
        row_idx: int,
        col_idx: int,
        ch: str,
        hp_ratio: float,
        *,
        is_day: bool = True,
    ) -> Tuple[RGB, Optional[RGB], bool, bool]:
        """
        Determina (fg_rgb, bg_rgb, bold, transparent) con attributo BOLD (A_BOLD) forzato
        per scafo, alberi, vele e badge per massimizzare la leggibilità a distanza:
        - Scafo: Marrone noce vivo rgb(210, 130, 60) in BOLD
        - Alberi e pennoni: Ocra legno saturo rgb(175, 110, 50) in BOLD
        - Vele: Bianco puro rgb(250, 250, 250) o crema luminoso rgb(245, 235, 180) in BOLD
        - Badge '[ FRASE ]': Sfondo pieno crema luminoso rgb(245, 235, 180) o oro rgb(255, 215, 0)
          con testo a contrasto netto in BOLD.
        """
        hull_base = self.palette.get(
            "hull_day" if is_day else "hull_night",
            COLOR_SHIP_HULL_DAY if is_day else COLOR_SHIP_HULL,
        )
        sail_col = self.palette.get(
            "sail_day" if is_day else "sail_night",
            COLOR_SHIP_SAIL_DAY if is_day else COLOR_SHIP_SAIL,
        )
        badge_bg = self.palette.get(
            "badge_bg",
            COLOR_SHIP_BADGE_GOLD if is_day else COLOR_SHIP_BADGE_CREAM,
        )
        banner_col = self.palette.get(
            "banner_day" if is_day else "banner_night",
            COLOR_SHIP_BANNER_DAY if is_day else COLOR_SHIP_BANNER,
        )
        deck_col = self.palette.get("deck", COLOR_SHIP_DECK)
        mast_col = self.palette.get("mast", COLOR_SHIP_MAST)
        cannon_col = self.palette.get("cannon", COLOR_SHIP_CANNON)

        if self.hit_flash_timer > 0.0:
            return COLOR_SHIP_DAMAGED, None, True, True

        # 1. Badge '[ FRASE ]' ad alto contrasto con sfondo solido crema luminoso o oro
        span = self._banner_spans.get(row_idx)
        if span is not None and span[0] <= col_idx < span[1]:
            return banner_col, badge_bg, True, False

        # 2. Stato di affondamento (SINKING) sempre in BOLD e saturo
        if self.state == ShipState.SINKING:
            if row_idx in (2, 3, 4):
                sunk_sail = lerp_rgb(sail_col, COLOR_SHIP_DAMAGED, 0.45)
                return sunk_sail, sunk_sail, True, False
            return lerp_rgb(hull_base, COLOR_SHIP_DAMAGED, 0.55), None, True, True

        # 3. Cime degli alberi e sartiame alto (righe 0 e 1) in BOLD
        if row_idx in (0, 1):
            if ch == "~":
                return COLOR_SHIP_BADGE_GOLD, None, True, True
            return mast_col, None, True, True

        # 4. Fascia delle vele (righe 2, 3, 4) a contrasto netto in BOLD
        if row_idx in (2, 3, 4):
            if row_idx == 4 and self._is_stern_or_bow_wood_on_row4(col_idx):
                return deck_col, None, True, True
            if ch == "_":
                return sail_col, sail_col, True, False
            return sail_col, None, True, True

        # 5. Base degli alberi '(|)', castello di poppa e bompresso (riga 5) in BOLD
        if row_idx == 5:
            if ch in ("(", "|", ")"):
                return mast_col, None, True, True
            return deck_col, None, True, True

        # 6. Ponte, murata con bocche dei cannoni [o] e scafo marrone noce vivo (righe >= 6) in BOLD
        if ch in ("[", "o", "]"):
            return cannon_col, None, True, True
        if ch in ("=", "+"):
            return deck_col, None, True, True
        return hull_base, None, True, True

    def _draw_waterline_splashes(self, renderer: Renderer, sea: Sea, base_x: int) -> None:
        """Disegna spruzzi bianchi dinamici ('*', '.', 'o') a prua e nella scia di poppa."""
        splash_glyphs = ("*", "o", ".", "~")
        phase_tick = int(self.smoke_phase * 2.2)

        if self.direction > 0:
            bow_start = base_x + self.width - 6
            bow_cols = (bow_start, bow_start + 1, bow_start + 2)
            stern_cols = (base_x - 2, base_x - 1, base_x, base_x + 1)
        else:
            bow_cols = (base_x + 3, base_x + 4, base_x + 5)
            stern_start = base_x + self.width - 2
            stern_cols = (stern_start, stern_start + 1, stern_start + 2, stern_start + 3)

        for i, sx in enumerate(bow_cols):
            if 0 <= sx < renderer.width:
                wy = int(round(sea.surface_y_at(float(sx))))
                glyph = splash_glyphs[(phase_tick + i) % len(splash_glyphs)]
                renderer.draw_text(
                    glyph,
                    sx,
                    wy - (1 if i == 1 and phase_tick % 2 == 0 else 0),
                    COLOR_SHIP_WAKE,
                    bold=True,
                    transparent=True,
                )

        for i, sx in enumerate(stern_cols):
            if 0 <= sx < renderer.width:
                wy = int(round(sea.surface_y_at(float(sx))))
                glyph = "o" if (phase_tick + i) % 3 == 0 else ("." if i % 2 == 0 else "*")
                col = COLOR_SHIP_WAKE if i < 2 else COLOR_WAVE_FOAM
                renderer.draw_text(glyph, sx, wy, col, bold=True, transparent=True)

    def draw(self, renderer: Renderer, sea: Sea, *, is_day: bool = True) -> None:
        """
        Disegna il veliero in BOLD saturo con scafo marrone noce vivo rgb(210, 130, 60),
        vele a contrasto netto e badge '[ FRASE ]' a sfondo pieno.
        """
        if self.state == ShipState.SUNK:
            return

        base_x = int(round(self.x))
        base_y = self.y
        hp_ratio = self.hp / max(1, self.max_hp)

        if self.state == ShipState.SINKING:
            tilt_slope = min(0.32, self.sink_offset * 0.05) * self.sink_list_dir
        else:
            tilt_slope = sea.wave_slope_at(self.center_x) * 0.14

        for row_idx, line in enumerate(self._lines):
            row_span = self._banner_spans.get(row_idx)
            for col_idx, ch in enumerate(line):
                in_banner = (
                    row_span is not None and row_span[0] <= col_idx < row_span[1]
                )
                if ch == " " and not in_banner:
                    continue

                screen_x = base_x + col_idx
                if screen_x < 0 or screen_x >= renderer.width:
                    continue

                rel_col = col_idx - (self.width * 0.5)
                cell_y_float = base_y + row_idx + (rel_col * tilt_slope)
                screen_y = int(round(cell_y_float))
                local_water_y = int(round(sea.surface_y_at(float(screen_x))))

                if self.state == ShipState.SINKING:
                    if screen_y > local_water_y + 1:
                        continue
                    if screen_y == local_water_y + 1:
                        base_col, _, _, _ = self._cell_style(
                            row_idx, col_idx, ch, hp_ratio, is_day=is_day
                        )
                        fg_col = lerp_rgb(base_col, COLOR_SHIP_SUBMERGED, 0.65)
                        bg_col = None
                        bold = True
                        trans = True
                    else:
                        fg_col, bg_col, bold, trans = self._cell_style(
                            row_idx, col_idx, ch, hp_ratio, is_day=is_day
                        )
                else:
                    fg_col, bg_col, bold, trans = self._cell_style(
                        row_idx, col_idx, ch, hp_ratio, is_day=is_day
                    )

                renderer.draw_text(
                    ch,
                    screen_x,
                    screen_y,
                    fg_col,
                    bg_rgb=bg_col,
                    bold=bold,
                    transparent=trans,
                )

        if self.state == ShipState.SAILING:
            self._draw_waterline_splashes(renderer, sea, base_x)

        if self.state == ShipState.SAILING and self.hp < self.max_hp:
            bar_len = 6
            filled = max(1, int(round(hp_ratio * bar_len)))
            hp_bar = ("▪" * filled) + ("·" * (bar_len - filled))
            hp_color = lerp_rgb((255, 70, 35), (80, 245, 100), hp_ratio)
            bar_x = int(round(self.center_x - bar_len * 0.5))
            bar_y = int(round(base_y)) - 1
            if bar_y >= 1:
                renderer.draw_text(hp_bar, bar_x, bar_y, hp_color, bold=True)

        # Faville/scintille calde e luminose dallo scafo danneggiato (mai grigio scuro)
        for sp in self.hull_smoke:
            sx = int(round(sp.x))
            sy = int(round(sp.y))
            if 0 <= sx < renderer.width and 1 <= sy < int(round(sea.surface_y_at(float(sx)))):
                life_t = sp.age / max(0.01, sp.ttl)
                glyph = sp.char if life_t < 0.5 else ("*" if life_t < 0.8 else "°")
                smoke_col = lerp_rgb(COLOR_HULL_SMOKE_DARK, COLOR_SMOKE, life_t)
                renderer.draw_text(
                    glyph,
                    sx,
                    sy,
                    smoke_col,
                    bold=True,
                    transparent=True,
                )
