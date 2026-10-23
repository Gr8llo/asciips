"""
entities/weather.py - Effetti atmosferici giorno/notte, nuvole, precipitazioni
ed entità autonoma Seagull ('/^v^\\') in volo ad alta quota (righe 2..8).
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from config import (
    CLOUD_CONDITIONS,
    COLOR_CLOUD,
    COLOR_CLOUD_DAY,
    COLOR_DARK_CLOUD,
    COLOR_LIGHTNING,
    COLOR_MOON,
    COLOR_RAIN,
    COLOR_SEAGULL,
    COLOR_SNOW,
    COLOR_STAR_BRIGHT,
    COLOR_STAR_DIM,
    COLOR_SUN,
    PRECIPITATION_CONDITIONS,
    RAIN_CONDITIONS,
    SNOW_CONDITIONS,
    THUNDERSTORM_CONDITIONS,
    NIGHT_SKY_GRADIENT,
    RGB,
    SKY_GRADIENTS,
    WeatherCondition,
)
from engine.renderer import Renderer, lerp_rgb


SEAGULL_SPRITE: str = "/^v^\\"
SEAGULL_FRAMES: Tuple[str, str, str] = (
    "/^v^\\",
    "\\-v-/",
    " ~v~ ",
)
SEAGULL_COLOR: RGB = COLOR_SEAGULL   # Bianco brillante rgb(255, 255, 255)


# Quattro frame di animazione per il Sole (17x7) - posizione fissa, raggi e nucleo pulsanti
SUN_FRAMES: List[List[str]] = [
    [
        "    \\   |   /    ",
        "  .  .-'''-.  .  ",
        "\\   /  .~.  \\   /",
        "--- | ( @ ) | ---",
        "/   \\  `~'  /   \\",
        "  '  `-...-'  '  ",
        "    /   |   \\    ",
    ],
    [
        "     .  :  .     ",
        "  \\  .-'''-.  /  ",
        " .  /  `~'  \\  . ",
        " -- | ( O ) | -- ",
        " '  \\  .~.  /  ' ",
        "  /  `-...-'  \\  ",
        "     '  :  '     ",
    ],
    [
        "    \\   :   /    ",
        "  *  .-'''-.  *  ",
        "/   /  .~.  \\   \\",
        "=== | ( @ ) | ===",
        "\\   \\  `~'  /   /",
        "  *  `-...-'  *  ",
        "    /   :   \\    ",
    ],
    [
        "     '  |  '     ",
        "  \\  .-'''-.  /  ",
        " *  /  `~'  \\  * ",
        " -- | ( * ) | -- ",
        " *  \\  .~.  /  * ",
        "  /  `-...-'  \\  ",
        "     .  |  .     ",
    ],
]

# Quattro frame di animazione per la Luna (17x7) - falce scolpita con alone astrale scintillante
MOON_FRAMES: List[List[str]] = [
    [
        r"   *    _.._     ",
        r" .    .' .-'`  . ",
        r"     /  /   *    ",
        r"  .  |  |  ·     ",
        r"     \  '.___  * ",
        r"  *   '._  _.'   ",
        r"         ``   .  ",
    ],
    [
        r"   .    _.._   * ",
        r" +    .' .-'`    ",
        r"     /  /   ·    ",
        r"  *  |  |  .     ",
        r"     \  '.___  . ",
        r"  .   '._  _.'   ",
        r"         ``   +  ",
    ],
    [
        r"   ·    _.._   . ",
        r" .    .' .-'`  * ",
        r"     /  /   +    ",
        r"  +  |  |  *     ",
        r"     \  '.___  + ",
        r"  ·   '._  _.'   ",
        r"         ``   .  ",
    ],
    [
        r"   +    _.._   · ",
        r" *    .' .-'`  . ",
        r"     /  /   .    ",
        r"  .  |  |  ·     ",
        r"     \  '.___  . ",
        r"  *   '._  _.'   ",
        r"         ``   *  ",
    ],
]

COLOR_SUN_CORE: RGB = (255, 240, 115)
COLOR_SUN_CORONA: RGB = (255, 175, 45)
COLOR_MOON_HALO: RGB = (175, 215, 255)

CLOUD_SPRITES: List[List[str]] = [
    [
        "   .--.   ",
        " .-(   ). ",
        "(___.__)__)",
    ],
    [
        "    _ .-.    ",
        "  ( `   )_  ",
        " (    )    `)",
        "(_   (_ .  _)",
    ],
]


@dataclass
class Star:
    """Stella discreta nel cielo notturno."""
    x: int
    y: int
    glyph: str
    phase: float


@dataclass
class Cloud:
    """Singola nuvola scorrevole nel cielo."""
    x: float
    y: int
    speed: float
    sprite: List[str]


@dataclass
class WeatherParticle:
    """Particella atmosferica (goccia di pioggia o fiocco di neve)."""
    x: float
    y: float
    vx: float
    vy: float
    char: str
    phase: float = 0.0


@dataclass
class Seagull:
    """
    Entità autonoma Gabbiano in cielo con animazione ad ala battente:
    - Frame 1 (ali spiegate/alte): '/^v^\\'
    - Frame 2 (ali battute/in planata): '\\-v-/'
    - Frame 3 (ali piegate verso il basso): ' ~v~ '
    - Colore: Bianco brillante rgb(255, 255, 255)
    - Altitudine: Coordinata Y tra la riga 2 e la riga 8 del terminale
    - Comparsa: Solo con meteo CLEAR o CLOUDY; vola via rapidamente con RAIN/SNOW/STORM.
    """
    x: float
    y: int
    vx: float
    frame_tick: int = 0
    flap_interval: int = 4
    color: RGB = SEAGULL_COLOR

    @property
    def sprite(self) -> str:
        """Restituisce il frame corrente del battito d'ali."""
        idx = (self.frame_tick // max(1, self.flap_interval)) % len(SEAGULL_FRAMES)
        return SEAGULL_FRAMES[idx]

    @classmethod
    def spawn_lateral(
        cls,
        screen_width: int,
        *,
        initial: bool = False,
        slot_idx: int = 0,
        total_slots: int = 3,
    ) -> "Seagull":
        """Crea un gabbiano lateralmente (o distribuito all'avvio) tra le righe 2 e 8."""
        direction = (
            (1 if slot_idx % 2 == 0 else -1)
            if initial
            else random.choice([-1, 1])
        )
        speed = random.uniform(4.2, 6.8)
        y = random.randint(2, 8)
        if initial:
            sector = max(12, screen_width // max(1, total_slots))
            x = float(slot_idx * sector + random.randint(3, max(4, sector - 6)))
            x = max(2.0, min(float(max(6, screen_width - 8)), x))
        else:
            x = -5.0 if direction > 0 else float(screen_width + 1)
        return cls(
            x=x,
            y=y,
            vx=direction * speed,
            frame_tick=random.randint(0, 11),
            flap_interval=random.randint(3, 5),
        )

    def update(self, dt: float, *, fleeing: bool = False) -> None:
        """
        Avanza il gabbiano e aggiorna il ciclo di battito d'ali;
        accelera rapidamente verso il bordo se il meteo diventa avverso (fleeing=True).
        """
        speed_mult = 3.2 if fleeing else 1.0
        self.x += (self.vx * speed_mult) * dt
        self.frame_tick += 2 if fleeing else 1

    def is_offscreen(self, screen_width: int) -> bool:
        """Restituisce True quando il gabbiano ha superato i bordi laterali."""
        if self.vx > 0:
            return self.x > screen_width + 4
        return self.x < -8.0

    def draw(self, renderer: Renderer) -> None:
        """Disegna il frame corrente del gabbiano in bianco brillante rgb(255, 255, 255)."""
        if 2 <= self.y <= min(8, renderer.height - 2):
            renderer.draw_text(
                self.sprite,
                int(round(self.x)),
                self.y,
                self.color,
                bold=True,
                transparent=True,
            )


class WeatherSystem:
    """
    Gestisce gli elementi visivi atmosferici in funzione della WeatherCondition,
    inclusi cielo stellato, sole/luna, nuvole, gabbiani e precipitazioni.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width: int = width
        self.height: int = height
        self.time: float = 0.0
        self.condition: WeatherCondition = WeatherCondition.CLEAR
        self.stars: List[Star] = []
        self.clouds: List[Cloud] = []
        self.particles: List[WeatherParticle] = []
        self.seagulls: List[Seagull] = []
        self.next_seagull_cd: float = random.uniform(1.5, 3.0)
        self.lightning_bolt: List[Tuple[int, int, str]] = []
        self.lightning_timer: float = 0.0
        self.next_lightning_cd: float = random.uniform(2.5, 6.5)
        self.flash_intensity: float = 0.0
        self._init_stars()
        self._init_clouds()
        self._init_seagulls()

    def _init_stars(self) -> None:
        """Genera stelle discrete ('.' e '*') nella fascia alta del cielo notturno."""
        self.stars.clear()
        sky_h = max(4, int(self.height * 0.58))
        count = max(18, (self.width * sky_h) // 80)
        rng = random.Random(42)
        for _ in range(count):
            sx = rng.randint(1, max(2, self.width - 2))
            sy = rng.randint(1, max(2, sky_h))
            glyph = "*" if rng.random() < 0.30 else "."
            phase = rng.uniform(0.0, math.tau)
            self.stars.append(Star(x=sx, y=sy, glyph=glyph, phase=phase))

    def _init_clouds(self) -> None:
        self.clouds.clear()
        num_clouds = max(3, self.width // 26)
        for i in range(num_clouds):
            sprite = random.choice(CLOUD_SPRITES)
            x = (i * (self.width / num_clouds)) + random.uniform(-6.0, 6.0)
            y = random.randint(2, max(3, min(7, int(self.height * 0.24))))
            speed = random.uniform(0.9, 2.4)
            self.clouds.append(Cloud(x=x, y=y, speed=speed, sprite=sprite))

    def _init_seagulls(self) -> None:
        """Popola il cielo con 3 gabbiani iniziali solo se il meteo è CLEAR o CLOUDY."""
        self.seagulls.clear()
        if self.condition not in (
            WeatherCondition.CLEAR,
            WeatherCondition.PARTLY_CLOUDY,
        ):
            return
        initial_count = 3
        for idx in range(initial_count):
            self.seagulls.append(
                Seagull.spawn_lateral(
                    self.width,
                    initial=True,
                    slot_idx=idx,
                    total_slots=initial_count,
                )
            )

    def resize(self, width: int, height: int) -> None:
        """Adatta il sistema particellare, le stelle, le nuvole e i gabbiani alle nuove dimensioni."""
        self.width = width
        self.height = height
        self._init_stars()
        self._init_clouds()
        self._init_seagulls()
        self.particles.clear()

    def _spawn_particles(self, sea_level_y: int) -> None:
        """Mantiene il numero ottimale di particelle per pioggia, neve o temporale."""
        if (
            self.condition not in PRECIPITATION_CONDITIONS
            and self.condition != WeatherCondition.FOG
        ):
            self.particles.clear()
            return

        if self.condition == WeatherCondition.FOG:
            target_count = max(12, self.width // 2)
        elif self.condition in THUNDERSTORM_CONDITIONS:
            target_count = max(40, (self.width * sea_level_y) // 18)
        elif self.condition == WeatherCondition.DRIZZLE:
            target_count = max(18, (self.width * sea_level_y) // 42)
        else:
            target_count = max(25, (self.width * sea_level_y) // 28)

        while len(self.particles) < target_count:
            x = random.uniform(-10.0, float(self.width + 5))
            y = random.uniform(1.0, float(max(2, sea_level_y)))
            if self.condition in SNOW_CONDITIONS:
                self.particles.append(
                    WeatherParticle(
                        x=x,
                        y=y,
                        vx=random.uniform(-0.7, 0.7),
                        vy=(
                            random.uniform(2.3, 4.4)
                            if self.condition == WeatherCondition.SNOW
                            else random.uniform(1.2, 2.2)
                        ),
                        char=(
                            random.choice(["*", ".", "+"])
                            if self.condition == WeatherCondition.SNOW
                            else random.choice([".", "·", ","])
                        ),
                        phase=random.uniform(0.0, math.tau),
                    )
                )
            elif self.condition == WeatherCondition.FOG:
                self.particles.append(
                    WeatherParticle(
                        x=x,
                        y=y,
                        vx=random.uniform(-0.25, 0.25),
                        vy=random.uniform(-0.08, 0.08),
                        char=random.choice(["░", "▒", "·"]),
                    )
                )
            else:
                is_thunderstorm = self.condition in THUNDERSTORM_CONDITIONS
                speed_mult = 1.35 if is_thunderstorm else (
                    0.55 if self.condition == WeatherCondition.DRIZZLE else 1.0
                )
                self.particles.append(
                    WeatherParticle(
                        x=x,
                        y=y,
                        vx=random.uniform(-9.0, -5.0) * speed_mult,
                        vy=(
                            random.uniform(18.0, 27.0)
                            if self.condition == WeatherCondition.THUNDERSTORM_HAIL
                            else random.uniform(14.5, 21.0) * speed_mult
                        ),
                        char=(
                            "o"
                            if self.condition == WeatherCondition.THUNDERSTORM_HAIL
                            else "."
                            if self.condition == WeatherCondition.DRIZZLE
                            else "/"
                        ),
                    )
                )

        if len(self.particles) > target_count:
            self.particles = self.particles[:target_count]

    def _trigger_lightning(self, sea_level_y: int) -> None:
        """Genera un fulmine ramificato dal cielo fino al mare."""
        self.lightning_bolt.clear()
        x = random.randint(max(4, self.width // 6), max(6, (self.width * 5) // 6))
        y = 2
        while y < sea_level_y:
            dx = random.choice([-1, 0, 1])
            glyph = "\\" if dx > 0 else ("/" if dx < 0 else "|")
            self.lightning_bolt.append((x, y, glyph))
            x = max(1, min(self.width - 2, x + dx))
            y += 1
        self.lightning_timer = 0.20
        self.flash_intensity = 0.75

    def update(self, dt: float, condition: WeatherCondition, sea_level_y: int) -> None:
        """Aggiorna animazione del sole/luna, stelle, nuvole, gabbiani, particelle e fulmini."""
        if condition != self.condition:
            self.condition = condition
            self.particles.clear()

        self.time += dt

        wind_factor = 1.8 if condition in THUNDERSTORM_CONDITIONS else (
            1.3
            if condition in RAIN_CONDITIONS or condition in CLOUD_CONDITIONS
            else 0.65
        )
        for cloud in self.clouds:
            cloud.x += cloud.speed * wind_factor * dt
            if cloud.x > self.width + 4:
                cloud.x = -16.0
                cloud.y = random.randint(2, max(3, min(7, int(sea_level_y * 0.36))))

        # Gabbiani: attivi solo con CLEAR o CLOUDY; volano via rapidamente con RAIN/SNOW/STORM
        calm_sky = condition in (
            WeatherCondition.CLEAR,
            WeatherCondition.PARTLY_CLOUDY,
        )
        for gull in self.seagulls:
            gull.update(dt, fleeing=not calm_sky)
        self.seagulls = [g for g in self.seagulls if not g.is_offscreen(self.width)]

        if calm_sky:
            while len(self.seagulls) < 2:
                self.seagulls.append(Seagull.spawn_lateral(self.width, initial=False))

            self.next_seagull_cd -= dt
            if self.next_seagull_cd <= 0.0:
                if len(self.seagulls) < 4:
                    self.seagulls.append(Seagull.spawn_lateral(self.width, initial=False))
                self.next_seagull_cd = random.uniform(2.0, 4.2)

        self._spawn_particles(sea_level_y)
        for p in self.particles:
            if condition in SNOW_CONDITIONS:
                p.phase += dt * 2.4
                p.x += (p.vx + math.sin(p.phase) * 1.3) * dt
            else:
                p.x += p.vx * dt
            p.y += p.vy * dt

            if condition == WeatherCondition.FOG:
                if p.x < -5:
                    p.x = float(self.width + 3)
                elif p.x > self.width + 8:
                    p.x = -3.0
                if p.y < 1 or p.y >= sea_level_y:
                    p.y = random.uniform(2.0, max(2.0, float(sea_level_y - 1)))
                continue

            if p.y >= sea_level_y:
                p.y = random.uniform(1.0, 3.0)
                p.x = random.uniform(0.0, float(self.width + 12))
            if p.x < -5:
                p.x = float(self.width + random.randint(0, 8))
            elif p.x > self.width + 8:
                p.x = 0.0

        if condition in THUNDERSTORM_CONDITIONS:
            if self.lightning_timer > 0.0:
                self.lightning_timer = max(0.0, self.lightning_timer - dt)
                self.flash_intensity = max(0.0, self.flash_intensity - dt * 3.8)
            else:
                self.lightning_bolt.clear()
                self.flash_intensity = 0.0
                self.next_lightning_cd -= dt
                if self.next_lightning_cd <= 0.0:
                    self._trigger_lightning(sea_level_y)
                    self.next_lightning_cd = random.uniform(2.5, 6.5)
        else:
            self.lightning_bolt.clear()
            self.flash_intensity = 0.0

    def _draw_animated_sun(self, renderer: Renderer, x: int, y: int) -> None:
        """
        Disegna il Sole in posizione fissa (x, y), animando i raggi della corona
        e colorando separatamente il disco solare e i bagliori esterni.
        """
        frame_idx = int(self.time * 2.2) % len(SUN_FRAMES)
        lines = SUN_FRAMES[frame_idx]
        pulse = (math.sin(self.time * 3.5) + 1.0) * 0.5
        corona_col = lerp_rgb(COLOR_SUN_CORONA, COLOR_SUN, pulse)

        for r_idx, line in enumerate(lines):
            for c_idx, ch in enumerate(line):
                if ch == " ":
                    continue
                is_core = (1 <= r_idx <= 5) and (4 <= c_idx <= 12)
                color = COLOR_SUN_CORE if is_core else corona_col
                renderer.draw_text(
                    ch,
                    x + c_idx,
                    y + r_idx,
                    color,
                    bold=is_core or (ch in ("*", "@", "O")),
                    transparent=True,
                )

    def _draw_animated_moon(self, renderer: Renderer, x: int, y: int) -> None:
        """
        Disegna la Luna in posizione fissa (x, y), mantenendo scolpita la falce
        lunare e facendo brillare l'alone astrale circostante.
        """
        frame_idx = int(self.time * 1.6) % len(MOON_FRAMES)
        lines = MOON_FRAMES[frame_idx]
        shimmer = (math.sin(self.time * 2.5) + 1.0) * 0.5
        halo_col = lerp_rgb(COLOR_STAR_DIM, COLOR_MOON_HALO, shimmer)

        for r_idx, line in enumerate(lines):
            for c_idx, ch in enumerate(line):
                if ch == " ":
                    continue
                is_halo_spark = ch in ("*", "+", "·") or (c_idx < 4) or (c_idx > 12)
                color = halo_col if is_halo_spark else COLOR_MOON
                renderer.draw_text(
                    ch,
                    x + c_idx,
                    y + r_idx,
                    color,
                    bold=not is_halo_spark or (ch == "*"),
                    transparent=True,
                )

    def draw(self, renderer: Renderer, sea_level_y: int, *, is_day: bool = True) -> None:
        """
        Disegna cielo, stelle, luna/sole, nuvole, GABBIANI e precipitazioni (sfondo).
        """
        sky_top, sky_bottom = (
            SKY_GRADIENTS.get(self.condition, SKY_GRADIENTS[WeatherCondition.CLEAR])
            if is_day
            else NIGHT_SKY_GRADIENT
        )

        celestial_x = max(6, self.width - 24)
        celestial_y = 2

        # 1. Stelle discrete di NOTTE
        if not is_day and self.condition in (
            WeatherCondition.CLEAR,
            WeatherCondition.PARTLY_CLOUDY,
            WeatherCondition.CLOUDY,
        ):
            for star in self.stars:
                if star.y >= sea_level_y - 2:
                    continue
                if (celestial_x - 1 <= star.x <= celestial_x + 18) and (
                    celestial_y - 1 <= star.y <= celestial_y + 7
                ):
                    continue
                twinkle = (math.sin(self.time * 1.8 + star.phase) + 1.0) * 0.5
                y_ratio = star.y / max(1, sea_level_y)
                base_sky = lerp_rgb(sky_top, sky_bottom, y_ratio)
                star_col = lerp_rgb(
                    base_sky,
                    COLOR_STAR_BRIGHT if twinkle > 0.55 else COLOR_STAR_DIM,
                    0.65 + 0.35 * twinkle,
                )
                renderer.draw_text(
                    star.glyph,
                    star.x,
                    star.y,
                    star_col,
                    bold=(twinkle > 0.72 and star.glyph == "*"),
                )

        # 2. Sole o Luna in posizione fissa
        if self.condition in (
            WeatherCondition.CLEAR,
            WeatherCondition.PARTLY_CLOUDY,
        ):
            if is_day:
                self._draw_animated_sun(renderer, celestial_x, celestial_y)
            else:
                self._draw_animated_moon(renderer, celestial_x, celestial_y)

        # 3. Fulmini se attivi
        if self.lightning_bolt and self.lightning_timer > 0.0:
            for lx, ly, glyph in self.lightning_bolt:
                renderer.draw_text(glyph, lx, ly, COLOR_LIGHTNING, bold=True)

        # 4. Nuvole
        if self.condition in RAIN_CONDITIONS or self.condition in THUNDERSTORM_CONDITIONS:
            cloud_color = COLOR_DARK_CLOUD
        elif self.condition == WeatherCondition.FOG:
            cloud_color = (150, 165, 175)
        elif is_day:
            cloud_color = COLOR_CLOUD_DAY
        else:
            cloud_color = COLOR_CLOUD

        if self.condition == WeatherCondition.CLEAR:
            clouds_to_draw = self.clouds[: max(1, len(self.clouds) // 4)]
        elif self.condition == WeatherCondition.PARTLY_CLOUDY:
            clouds_to_draw = self.clouds[: max(1, len(self.clouds) // 2)]
        else:
            clouds_to_draw = self.clouds
        for cloud in clouds_to_draw:
            renderer.draw_sprite(
                cloud.sprite,
                int(round(cloud.x)),
                cloud.y,
                cloud_color,
                bold=(
                    is_day
                    and self.condition
                    in (WeatherCondition.CLEAR, WeatherCondition.PARTLY_CLOUDY)
                ),
            )

        # 5. Gabbiani ('/^v^\') in bianco brillante rgb(255, 255, 255) tra le righe 2 e 8
        for gull in self.seagulls:
            gull.draw(renderer)

        # 6. Particelle di pioggia o neve
        if self.condition in SNOW_CONDITIONS:
            for p in self.particles:
                renderer.draw_text(
                    p.char,
                    int(round(p.x)),
                    int(round(p.y)),
                    COLOR_SNOW,
                    bold=True,
                )
        elif self.condition == WeatherCondition.FOG:
            for p in self.particles:
                renderer.draw_text(
                    p.char,
                    int(round(p.x)),
                    int(round(p.y)),
                    (170, 185, 195),
                    bold=False,
                )
        elif self.condition in RAIN_CONDITIONS or self.condition in THUNDERSTORM_CONDITIONS:
            for p in self.particles:
                renderer.draw_text(
                    p.char,
                    int(round(p.x)),
                    int(round(p.y)),
                    COLOR_RAIN,
                    bold=False,
                )
