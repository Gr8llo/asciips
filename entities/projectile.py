"""
entities/projectile.py - Proiettili balistici che trasportano le frasi di cannon_insults
lungo una traiettoria parabolica con scia ed esplosione/splash all'impatto.
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple

from config import (
    CANNON_DAMAGE_MAX,
    CANNON_DAMAGE_MIN,
    COLOR_EXPLOSION_ORANGE,
    COLOR_EXPLOSION_YELLOW,
    COLOR_MUZZLE_SMOKE,
    COLOR_PROJECTILE_BG,
    COLOR_PROJECTILE_BG_ALT,
    COLOR_PROJECTILE_FLASH,
    COLOR_PROJECTILE_TEXT,
    COLOR_PROJECTILE_TRAIL,
    COLOR_SMOKE,
    GRAVITY,
    RGB,
)
from engine.renderer import Renderer, lerp_rgb


@dataclass
class CombatParticle:
    """
    Particella effimera per sbuffi di fumo alla bocca di fuoco (3-4 frame)
    ed esplosioni all'impatto sullo scafo (3-5 frame).
    """
    x: float
    y: float
    vx: float
    vy: float
    char: str
    color: RGB
    frames_left: int
    total_frames: int
    bold: bool = True

    @property
    def ttl(self) -> int:
        """Restituisce i frame di vita residui della particella."""
        return self.frames_left

    @property
    def active(self) -> bool:
        """Restituisce True finché la particella ha vita residua (ttl > 0)."""
        return self.frames_left > 0

    def update(self, dt: float) -> None:
        """Avanza la particella e riduce i frame residui di vita."""
        if self.frames_left <= 0:
            return
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.frames_left -= 1

    def draw(self, renderer: Renderer) -> None:
        """Disegna la particella sfumando leggermente il colore negli ultimi frame."""
        if self.frames_left <= 0:
            return
        ratio = self.frames_left / max(1, self.total_frames)
        col = (
            self.color
            if ratio > 0.45
            else lerp_rgb(COLOR_SMOKE, self.color, ratio)
        )
        renderer.draw_text(
            self.char,
            int(round(self.x)),
            int(round(self.y)),
            col,
            bold=self.bold and ratio > 0.35,
            transparent=True,
        )


def spawn_muzzle_smoke(
    origin_x: float, origin_y: float, direction: int
) -> List[CombatParticle]:
    """
    Genera 3-4 particelle di fumo grigio chiaro ('o', '°', '.', '*') vicino
    alla bocca del cannone che si dissolvono entro 3-4 frame.
    """
    glyphs = ("o", "°", ".", "*")
    count = random.randint(3, 4)
    particles: List[CombatParticle] = []
    dir_sign = 1.0 if direction >= 0 else -1.0

    for i in range(count):
        frames = random.randint(3, 4)
        smoke_tone = lerp_rgb(COLOR_MUZZLE_SMOKE, COLOR_SMOKE, random.uniform(0.0, 0.45))
        particles.append(
            CombatParticle(
                x=origin_x + dir_sign * random.uniform(0.3, 1.8),
                y=origin_y + random.uniform(-0.6, 0.4),
                vx=dir_sign * random.uniform(5.0, 12.0),
                vy=random.uniform(-6.0, -1.5),
                char=glyphs[i % len(glyphs)],
                color=smoke_tone,
                frames_left=frames,
                total_frames=frames,
                bold=(i < 2),
            )
        )
    return particles


def spawn_impact_explosion(hit_x: float, hit_y: float) -> List[CombatParticle]:
    """
    Genera nel punto d'impatto una piccola esplosione particellare ('*', '#', '@', '%')
    con colori caldi (arancio rgb(255,140,0) e giallo rgb(255,220,0)) che si espande
    leggermente per 3-5 frame per poi sparire.
    """
    glyphs = ("*", "#", "@", "%")
    warm_colors = (COLOR_EXPLOSION_ORANGE, COLOR_EXPLOSION_YELLOW)
    count = random.randint(6, 9)
    particles: List[CombatParticle] = []

    for i in range(count):
        angle = (math.tau * i / count) + random.uniform(-0.3, 0.3)
        speed = random.uniform(8.0, 18.0)
        frames = random.randint(3, 5)
        particles.append(
            CombatParticle(
                x=hit_x + math.cos(angle) * 0.5,
                y=hit_y + math.sin(angle) * 0.35,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * (speed * 0.6),
                char=glyphs[i % len(glyphs)],
                color=warm_colors[i % len(warm_colors)],
                frames_left=frames,
                total_frames=frames,
                bold=True,
            )
        )
    return particles


@dataclass
class ImpactEffect:
    """Effetto visivo temporaneo di esplosione (colpo a segno) o splash (in acqua)."""
    x: float
    y: float
    is_hit: bool
    text: str
    timer: float = 0.55


@dataclass
class Projectile:
    """
    Proiettile testuale lanciato da una nave verso un'altra.
    Segue la legge del moto parabolico:
      x(t) = x0 + vx * t
      h(t) = h0 + vy * t - 0.5 * g * t^2
    Poiché a schermo l'asse Y è orientato verso il basso (y_screen = -h):
      y_screen(t) = y0 - vy * t + 0.5 * g * t^2
    """
    owner_id: int
    x0: float
    y0: float
    vx: float
    vy: float  # Velocità iniziale verticale verso l'alto (celle/s)
    text: str
    water_depth: float = 0.0
    damage: int = field(
        default_factory=lambda: random.randint(CANNON_DAMAGE_MIN, CANNON_DAMAGE_MAX)
    )
    elapsed: float = 0.0
    active: bool = True
    trail: List[Tuple[int, int]] = field(default_factory=list)

    @classmethod
    def launch_towards(
        cls,
        *,
        owner_id: int,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        text: str,
        water_depth: float = 0.0,
        gravity: float = GRAVITY,
    ) -> "Projectile":
        """
        Calcola la velocità iniziale (vx, vy) per colpire le vicinanze di (target_x, target_y)
        con un arco parabolico realistico sempre ascendente alla partenza.
        """
        dx = (target_x + random.uniform(-1.5, 1.5)) - start_x
        if abs(dx) < 4.0:
            dx = 4.0 if dx >= 0.0 else -4.0
        dy = start_y - target_y  # Positivo se il bersaglio è più in alto

        dist = abs(dx)
        min_arc_time = math.sqrt(2.0 * (abs(dy) + 3.5) / max(1.0, gravity))
        flight_time = max(
            1.0,
            min_arc_time,
            min(2.8, dist / random.uniform(16.0, 22.0)),
        )

        vx = dx / flight_time
        # Da h(T) - h0 = vy * T - 0.5 * g * T^2  =>  vy = (dy + 0.5 * g * T^2) / T
        vy = (dy + 0.5 * gravity * (flight_time ** 2)) / flight_time

        return cls(
            owner_id=owner_id,
            x0=start_x,
            y0=start_y,
            vx=vx,
            vy=vy,
            text=text,
            water_depth=max(0.0, water_depth),
        )

    @property
    def is_descending(self) -> bool:
        """Restituisce True quando il proiettile ha superato il vertice della parabola."""
        return (self.vy - GRAVITY * self.elapsed) <= 0.0

    @property
    def x(self) -> float:
        """Posizione X istantanea."""
        return self.x0 + self.vx * self.elapsed

    @property
    def y(self) -> float:
        """
        Posizione Y istantanea a schermo secondo la formula parabolica:
        y(t) = y0 - (vy * t - 0.5 * g * t^2)
        """
        parabolic_rise = (self.vy * self.elapsed) - (0.5 * GRAVITY * (self.elapsed ** 2))
        return self.y0 - parabolic_rise

    def update(self, dt: float) -> None:
        """Avanza il tempo di volo e aggiorna la scia balistica."""
        if not self.active:
            return

        cur_pos = (int(round(self.x)), int(round(self.y)))
        if not self.trail or self.trail[-1] != cur_pos:
            self.trail.append(cur_pos)
            if len(self.trail) > 6:
                self.trail.pop(0)

        self.elapsed += dt

    def draw(self, renderer: Renderer) -> None:
        """
        Disegna la scia luminosa e il proiettile verbale evidenziato come palla di fuoco
        leggibile a distanza: formato '* FRASE *' in BOLD con flash visivo brillante a sfondo pieno.
        """
        if not self.active:
            return

        # 1. Scia balistica brillante in BOLD
        for i, (tx, ty) in enumerate(self.trail[:-1]):
            glyph = "•" if i < len(self.trail) // 2 else "*"
            trail_col = (
                COLOR_EXPLOSION_ORANGE
                if i < len(self.trail) // 2
                else COLOR_PROJECTILE_TRAIL
            )
            renderer.draw_text(
                glyph,
                tx,
                ty,
                trail_col,
                bold=True,
                transparent=True,
            )

        # 2. Palla di fuoco verbale '* FRASE *' in BOLD con flash visivo brillante
        label = f"* {self.text} *"
        px = int(round(self.x - len(label) * 0.5))
        py = int(round(self.y))

        flash_phase = int(self.elapsed * 14.0) % 2 == 0
        fg_col = COLOR_PROJECTILE_FLASH if flash_phase else COLOR_PROJECTILE_TEXT
        bg_col = COLOR_PROJECTILE_BG if flash_phase else COLOR_PROJECTILE_BG_ALT

        renderer.draw_text(
            label,
            px,
            py,
            fg_col,
            bg_rgb=bg_col,
            bold=True,
            transparent=False,
        )
