"""
entities/sea.py - Simulazione sinusoidale delle onde, creste in primo piano e fauna marina
con orientamento direzionale rigoroso (vx > 0 verso destra, vx < 0 verso sinistra).
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from config import (
    COLOR_FISH_DEEP,
    COLOR_FISH_NIGHT,
    COLOR_FISH_SHALLOW,
    COLOR_ICE_FLOE,
    COLOR_SEA_DEEP_DAY,
    COLOR_SEA_TEXTURE,
    COLOR_WAVE_CREST,
    COLOR_WAVE_FOAM,
    COLOR_WAVE_FOAM_DAY,
    COLOR_WAVE_SURFACE,
    COLOR_WAVE_SURFACE_DAY,
    DAY_SEA_GRADIENTS,
    SNOW_CONDITIONS,
    SEA_GRADIENTS,
    SEA_LEVEL_RATIO,
    WAVE_PARAMS,
    WeatherCondition,
)
from engine.renderer import Renderer, lerp_rgb


# Sprite pesci orientati in modo inequivocabile
SMALL_FISH_RIGHT: List[str] = ["><>"]  # vx > 0 (verso DESTRA)
SMALL_FISH_LEFT: List[str] = ["<><"]   # vx < 0 (verso SINISTRA)


@dataclass
class IceFloe:
    """Lastra di ghiaccio galleggiante per la modalità meteo SNOW (banchisa)."""
    x: float
    width: int
    speed: float
    pattern: str


@dataclass
class FishMember:
    """Singolo esemplare all'interno di un banco di pesci."""
    dx: float
    dy: float
    kind: str  # "small" oppure "big"
    phase_offset: float


@dataclass
class FishSchool:
    """
    Banco di pesci con velocità vx esplicita:
    - Se vx > 0 si muove verso DESTRA e usa lo sprite orientato a DESTRA.
    - Se vx < 0 si muove verso SINISTRA e usa lo sprite orientato a SINISTRA.
    """
    x: float
    depth_offset: float
    direction: int
    base_speed: float
    vx: float
    wave_freq: float
    wave_amp: float
    wave_offset: float
    burst_timer: float = 0.0
    glide_duration: float = 1.1
    burst_duration: float = 0.28
    flee_timer: float = 0.0
    members: List[FishMember] = field(default_factory=list)


class Sea:
    """
    Gestisce la superficie del mare tramite sovrapposizione di onde sinusoidali,
    calcola l'altezza locale dell'acqua per il galleggiamento/affondamento delle navi
    e disegna profondità, pesci e creste delle onde in primo piano.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width: int = width
        self.height: int = height
        self.time: float = 0.0
        self.tick: int = 0
        self.condition: WeatherCondition = WeatherCondition.CLEAR
        self._ice_floes: List[IceFloe] = []
        self.fish_schools: List[FishSchool] = []
        self._init_ice_floes()
        self._init_fish_schools()

    def _create_school(
        self,
        *,
        initial: bool = False,
        forced_direction: Optional[int] = None,
    ) -> FishSchool:
        """
        Crea un banco di pesci ('><>' verso destra, '<><' verso sinistra),
        calibrando la velocità in funzione della profondità.
        """
        direction = (
            forced_direction
            if forced_direction in (-1, 1)
            else random.choice([-1, 1])
        )
        sea_depth = max(6, self.height - self.base_sea_y - 2)
        depth_offset = float(random.uniform(2.5, float(max(4, sea_depth - 1))))

        depth_ratio = max(0.0, min(1.0, depth_offset / max(1.0, float(sea_depth))))
        base_speed = (4.3 - 2.2 * depth_ratio) * random.uniform(0.90, 1.12)

        x = (
            random.uniform(6.0, float(max(14, self.width - 18)))
            if initial
            else (-20.0 if direction > 0 else float(self.width + 14))
        )

        members: List[FishMember] = []
        count = random.randint(3, 6)
        for i in range(count):
            dx = float(i * random.uniform(3.4, 4.8) + random.uniform(-0.6, 0.6))
            dy = random.uniform(-1.1, 1.1)
            members.append(
                FishMember(
                    dx=dx,
                    dy=dy,
                    kind="small",
                    phase_offset=random.uniform(0.0, math.tau),
                )
            )

        burst_dur = random.uniform(0.24, 0.34)
        glide_dur = random.uniform(0.85, 1.45)
        return FishSchool(
            x=x,
            depth_offset=depth_offset,
            direction=direction,
            base_speed=base_speed,
            vx=direction * base_speed,
            wave_freq=random.uniform(0.16, 0.28),
            wave_amp=random.uniform(0.45, 0.95),
            wave_offset=random.uniform(0.0, math.tau),
            burst_timer=random.uniform(0.0, burst_dur + glide_dur),
            glide_duration=glide_dur,
            burst_duration=burst_dur,
            members=members,
        )

    def _init_fish_schools(self) -> None:
        """Popola il mare con banchi di pesci."""
        self.fish_schools.clear()
        self.fish_schools.append(
            self._create_school(initial=True, forced_direction=1)
        )
        self.fish_schools.append(
            self._create_school(initial=True, forced_direction=-1)
        )
        self.fish_schools.append(
            self._create_school(initial=True, forced_direction=1)
        )

    def _init_ice_floes(self) -> None:
        """Genera lastre di ghiaccio per la banchisa in caso di neve."""
        self._ice_floes.clear()
        count = max(4, self.width // 24)
        for i in range(count):
            w = random.randint(6, 13)
            x = (i * (self.width / count)) + random.uniform(-4.0, 4.0)
            body = "".join(random.choice(["=", "_", "~", "-"]) for _ in range(w - 2))
            pattern = f"[{body}]"
            self._ice_floes.append(
                IceFloe(
                    x=x % max(1, self.width),
                    width=w,
                    speed=random.uniform(0.5, 1.3),
                    pattern=pattern,
                )
            )

    def resize(self, width: int, height: int) -> None:
        """Aggiorna le dimensioni del mare in seguito a SIGWINCH."""
        self.width = width
        self.height = height
        self._init_ice_floes()
        self._init_fish_schools()

    @property
    def base_sea_y(self) -> int:
        """Restituisce la riga media dell'orizzonte marino."""
        return max(10, min(self.height - 6, int(self.height * SEA_LEVEL_RATIO)))

    def wave_offset_at(self, x: float, depth: float = 0.0) -> float:
        """
        Calcola lo scostamento verticale dell'onda nella colonna x al tempo corrente.
        Usa la sovrapposizione di due armoniche sinusoidali per un moto naturale.
        """
        amp, freq, phase_speed, _ = WAVE_PARAMS.get(
            self.condition, WAVE_PARAMS[WeatherCondition.CLEAR]
        )
        if self.condition in SNOW_CONDITIONS:
            amp = min(amp, 0.06)
        depth_ratio = max(
            0.0,
            min(1.0, depth / max(1.0, self.height - self.base_sea_y - 1)),
        )
        amp *= 1.0 - 0.72 * depth_ratio
        depth_phase = depth * 0.12
        primary = math.sin(x * freq - self.time * phase_speed + depth_phase)
        secondary = 0.42 * math.cos(
            x * (freq * 1.65)
            + self.time * (phase_speed * 0.6)
            + depth_phase * 1.7
        )
        return amp * (primary + secondary * 0.55)

    def surface_y_at(self, x: float, depth: float = 0.0) -> float:
        """Restituisce la quota del pelo dell'acqua sulla corsia prospettica richiesta."""
        return float(self.base_sea_y) + depth + self.wave_offset_at(x, depth)

    def get_surface_profile(self, depth: float = 0.0) -> List[int]:
        """Restituisce le quote della superficie per colonna su una corsia di profondita'."""
        return [
            int(round(self.surface_y_at(float(x), depth)))
            for x in range(self.width)
        ]

    def wave_slope_at(self, x: float, depth: float = 0.0) -> float:
        """Calcola la derivata spaziale approssimata dell'onda per il rollio navale."""
        return (
            self.wave_offset_at(x + 1.5, depth)
            - self.wave_offset_at(x - 1.5, depth)
        ) / 3.0

    def update(
        self,
        dt: float,
        condition: WeatherCondition,
        sinking_boxes: Optional[List[Tuple[float, float, float, float]]] = None,
    ) -> None:
        """
        Avanza la fase delle onde, la banchisa e la fauna marina garantendo che vx
        determini in modo coerente direzione di movimento e orientamento dello sprite.
        """
        self.time += dt
        self.tick += 1
        self.condition = condition

        if condition in SNOW_CONDITIONS:
            for floe in self._ice_floes:
                floe.x += floe.speed * dt
                if floe.x > self.width + 4:
                    floe.x = -float(floe.width)

        sea_depth = max(4.0, float(self.height - self.base_sea_y - 2))
        boxes = sinking_boxes or []

        for idx, school in enumerate(self.fish_schools):
            school_y = float(self.base_sea_y) + school.depth_offset
            for s_left, s_top, s_right, s_bottom in boxes:
                if (s_left - 8.0 <= school.x <= s_right + 8.0) and (
                    s_top - 3.0 <= school_y <= s_bottom + 6.0
                ):
                    if school.flee_timer <= 0.0:
                        ship_mid = (s_left + s_right) * 0.5
                        school.direction = -1 if school.x < ship_mid else 1
                    school.flee_timer = 1.25
                    break

            cycle_total = school.burst_duration + school.glide_duration
            school.burst_timer = (school.burst_timer + dt) % max(0.2, cycle_total)
            is_bursting = school.burst_timer < school.burst_duration

            if school.flee_timer > 0.0:
                school.flee_timer = max(0.0, school.flee_timer - dt)
                speed_mult = 2.8
                school.depth_offset = min(sea_depth, school.depth_offset + 3.2 * dt)
            elif is_bursting:
                speed_mult = 2.2
            else:
                glide_t = (school.burst_timer - school.burst_duration) / max(
                    0.1, school.glide_duration
                )
                speed_mult = 0.85 - 0.25 * min(1.0, glide_t)

            school.direction = 1 if school.direction >= 0 else -1
            school.vx = school.direction * (school.base_speed * speed_mult)
            school.x += school.vx * dt

            if school.vx > 0 and school.x > self.width + 16:
                self.fish_schools[idx] = self._create_school(initial=False)
            elif school.vx < 0 and school.x < -32:
                self.fish_schools[idx] = self._create_school(initial=False)

    @staticmethod
    def _sprite_for_fish(kind: str, vx: float) -> List[str]:
        """
        Restituisce lo sprite orientato in base alla velocità orizzontale vx:
        - Se vx > 0 (si muove verso DESTRA): testa/bocca a DESTRA ('><>').
        - Se vx < 0 (si muove verso SINISTRA): testa/bocca a SINISTRA ('<><').
        """
        return SMALL_FISH_RIGHT if vx >= 0.0 else SMALL_FISH_LEFT

    def draw_subsurface_volume(self, renderer: Renderer, *, is_day: bool = True) -> None:
        """
        Disegna il mare di fondo e i pesci sotto il livello del mare.
        """
        base_y = self.base_sea_y
        if is_day:
            sea_top, sea_bottom = DAY_SEA_GRADIENTS.get(
                self.condition, (COLOR_WAVE_SURFACE_DAY, COLOR_SEA_DEEP_DAY)
            )
            sub_crest_color = lerp_rgb(COLOR_WAVE_SURFACE_DAY, COLOR_WAVE_FOAM_DAY, 0.35)
        else:
            sea_top, sea_bottom = SEA_GRADIENTS.get(
                self.condition, SEA_GRADIENTS[WeatherCondition.CLEAR]
            )
            sub_crest_color = lerp_rgb(COLOR_WAVE_SURFACE, COLOR_WAVE_CREST, 0.40)

        sea_rows = max(1, self.height - base_y)

        for row_idx in range(1, sea_rows + 2):
            y = base_y - 1 + row_idx
            if y < 0 or y >= self.height:
                continue

            depth_t = max(0.0, min(1.0, row_idx / max(1, sea_rows)))
            if is_day:
                row_fg = lerp_rgb(sea_top, sea_bottom, depth_t)
            else:
                row_fg = lerp_rgb(
                    lerp_rgb(COLOR_WAVE_SURFACE, sea_top, 0.4),
                    lerp_rgb(COLOR_SEA_TEXTURE, sea_bottom, 0.5),
                    depth_t,
                )

            stride = 2 if depth_t < 0.32 else (3 if depth_t < 0.68 else 4)
            shift = int(self.time * (2.4 - depth_t * 1.1) + row_idx * 5)

            for x in range((shift % stride), self.width, stride):
                surf_y = int(round(self.surface_y_at(float(x))))
                if y <= surf_y:
                    continue

                dy = y - surf_y
                wave_val = math.sin(x * 0.26 - self.time * 1.7 + row_idx * 1.1)
                if dy == 1:
                    glyph = "≈" if wave_val > 0.2 else "~"
                    renderer.draw_text(glyph, x, y, sub_crest_color, bold=False, transparent=True)
                elif dy == 2 and wave_val > -0.35:
                    glyph = "~" if wave_val > 0.25 else "-"
                    renderer.draw_text(glyph, x, y, row_fg, bold=False, transparent=True)
                elif wave_val > -0.25:
                    if depth_t < 0.48:
                        glyph = "~" if wave_val > 0.45 else ("-" if wave_val > 0.0 else ".")
                    else:
                        glyph = "." if wave_val > 0.35 else ("," if wave_val > 0.0 else "-")
                    renderer.draw_text(glyph, x, y, row_fg, bold=False, transparent=True)

        # Disegna i pesci sotto il livello del mare
        for school in self.fish_schools:
            for member in school.members:
                sprite_lines = self._sprite_for_fish(member.kind, school.vx)

                osc_y = (
                    math.sin(
                        self.tick * school.wave_freq
                        + school.wave_offset
                        + member.phase_offset
                    )
                    * school.wave_amp
                )
                base_fx = int(round(school.x + member.dx))
                center_fy = int(round(base_y + school.depth_offset + member.dy + osc_y))
                half_h = len(sprite_lines) // 2

                fish_depth_t = max(
                    0.0,
                    min(1.0, (center_fy - base_y) / max(1, sea_rows)),
                )
                fish_col = lerp_rgb(COLOR_FISH_SHALLOW, COLOR_FISH_DEEP, fish_depth_t)
                if not is_day:
                    fish_col = lerp_rgb(fish_col, COLOR_FISH_NIGHT, 0.25)

                for r_off, line in enumerate(sprite_lines):
                    ry = center_fy - half_h + r_off
                    if ry >= self.height:
                        continue
                    for c_off, ch in enumerate(line):
                        if ch == " ":
                            continue
                        rx = base_fx + c_off
                        if 0 <= rx < self.width:
                            surf_y = int(round(self.surface_y_at(float(rx))))
                            if ry > surf_y + 1:
                                renderer.draw_text(
                                    ch,
                                    rx,
                                    ry,
                                    fish_col,
                                    bold=(fish_depth_t < 0.45),
                                    transparent=True,
                                )

    def draw_perspective_wave_tracks(
        self, renderer: Renderer, *, is_day: bool = True
    ) -> None:
        """Disegna le onde lontane dietro alle navi della scena prospettica."""
        base_y = self.base_sea_y
        _, freq, phase_speed, _ = WAVE_PARAMS.get(
            self.condition, WAVE_PARAMS[WeatherCondition.CLEAR]
        )

        foam_col = COLOR_WAVE_FOAM_DAY if is_day else COLOR_WAVE_FOAM

        sea_depth = max(0, self.height - base_y - 2)
        track_spacing = max(3, sea_depth // 5)
        depth = float(track_spacing)
        while depth < sea_depth:
            ratio = depth / max(1.0, float(sea_depth))
            track_color = lerp_rgb(foam_col, COLOR_SEA_TEXTURE, 0.55 + ratio * 0.3)
            for x in range(self.width):
                y = int(round(self.surface_y_at(float(x), depth)))
                if not 0 <= y < self.height:
                    continue
                phase_val = math.sin(
                    x * (freq * 1.1)
                    - self.time * (phase_speed * 0.8)
                    + depth * 0.12
                )
                if phase_val > 0.5:
                    glyph = "~" if ratio < 0.45 else "."
                    renderer.draw_text(
                        glyph,
                        x,
                        y,
                        track_color,
                        bold=False,
                        transparent=True,
                    )
            depth += track_spacing

    def draw_surface_crests(self, renderer: Renderer, *, is_day: bool = True) -> None:
        """Disegna la cresta all'orizzonte davanti allo scafo."""
        base_y = self.base_sea_y
        _, freq, phase_speed, crest_prob = WAVE_PARAMS.get(
            self.condition, WAVE_PARAMS[WeatherCondition.CLEAR]
        )

        foam_col = COLOR_WAVE_FOAM_DAY if is_day else COLOR_WAVE_FOAM
        surf_col = COLOR_WAVE_SURFACE_DAY if is_day else COLOR_WAVE_SURFACE
        mid_col = lerp_rgb(surf_col, foam_col, 0.55) if is_day else COLOR_WAVE_CREST

        for x in range(self.width):
            offset = self.wave_offset_at(float(x))
            y = int(round(base_y + offset))
            if 0 <= y < self.height:
                phase_val = math.sin(x * (freq * 1.35) - self.time * (phase_speed * 1.3))
                if offset < -0.38 or phase_val > (0.72 - crest_prob * 0.4):
                    ch = "^"
                    color = foam_col
                    bold = True
                elif phase_val > 0.15:
                    ch = "≈"
                    color = foam_col
                    bold = True
                elif phase_val > -0.45:
                    ch = "~"
                    color = mid_col
                    bold = True
                else:
                    ch = "~"
                    color = surf_col
                    bold = False

                renderer.draw_text(ch, x, y, color, bold=bold, transparent=True)

        # Una crosta continua copre le onde durante entrambi gli stati nevosi.
        if self.condition in SNOW_CONDITIONS:
            for x in range(self.width):
                y = int(round(self.surface_y_at(float(x))))
                if not 0 <= y < self.height:
                    continue
                glyph = "=" if (x // 4) % 3 else "_"
                color = COLOR_ICE_FLOE if x % 11 < 7 else COLOR_WAVE_FOAM_DAY
                renderer.draw_text(glyph, x, y, color, bold=True, transparent=True)

            for floe in self._ice_floes:
                fx = int(round(floe.x))
                fy = int(round(self.surface_y_at(floe.x + floe.width * 0.5)))
                renderer.draw_text(
                    floe.pattern,
                    fx,
                    fy,
                    COLOR_ICE_FLOE,
                    bold=True,
                    transparent=True,
                )
            return

    def draw_surface_and_depths(self, renderer: Renderer, *, is_day: bool = True) -> None:
        """Metodo combinato che disegna profondità e superficie."""
        self.draw_subsurface_volume(renderer, is_day=is_day)
        self.draw_perspective_wave_tracks(renderer, is_day=is_day)
        self.draw_surface_crests(renderer, is_day=is_day)
