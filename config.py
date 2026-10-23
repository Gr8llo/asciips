"""
config.py - Parametri globali, palette RGB naturali (Giorno e Notte), costanti fisiche e codici WMO.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Dict, Tuple

# Percorsi di base
BASE_DIR: Path = Path(__file__).resolve().parent
PHRASES_FILE: Path = BASE_DIR / "phrases.json"

# Parametri di default CLI e runtime
DEFAULT_CITY: str = "Bologna"
MIN_FPS: int = 5
MAX_FPS: int = 120
FPS_STEP: int = 5
DEFAULT_FPS: int = MIN_FPS
DEFAULT_MAX_SHIPS: int = 3
WEATHER_POLL_INTERVAL_SEC: int = 600  # 10 minuti (600 secondi)
HTTP_TIMEOUT_SEC: int = 8

# Endpoint API Open-Meteo (nessun token richiesto)
GEOCODING_API_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API_URL: str = "https://api.open-meteo.com/v1/forecast"


class WeatherCondition(str, Enum):
    """Condizioni meteo supportate dal motore."""
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly-cloudy"
    OVERCAST = "overcast"
    CLOUDY = "cloudy"
    DRIZZLE = "drizzle"
    RAIN = "rain"
    RAIN_SHOWERS = "rain-showers"
    SNOW = "snow"
    SNOW_GRAINS = "snow-grains"
    FOG = "fog"
    THUNDERSTORM = "thunderstorm"
    THUNDERSTORM_HAIL = "thunderstorm-hail"
    STORM = "thunderstorm"


class TimeOfDay(str, Enum):
    """Fascia oraria (giorno o notte) derivata dal meteo locale."""
    DAY = "day"
    NIGHT = "night"


class AppearanceMode(str, Enum):
    """Modalita' cromatica automatica o scelta manualmente."""
    AUTO = "auto"
    LIGHT = "light"
    DARK = "dark"


RAIN_CONDITIONS = {
    WeatherCondition.DRIZZLE,
    WeatherCondition.RAIN,
    WeatherCondition.RAIN_SHOWERS,
}
SNOW_CONDITIONS = {WeatherCondition.SNOW, WeatherCondition.SNOW_GRAINS}
THUNDERSTORM_CONDITIONS = {
    WeatherCondition.THUNDERSTORM,
    WeatherCondition.THUNDERSTORM_HAIL,
}
PRECIPITATION_CONDITIONS = RAIN_CONDITIONS | SNOW_CONDITIONS | THUNDERSTORM_CONDITIONS
CLOUD_CONDITIONS = {
    WeatherCondition.PARTLY_CLOUDY,
    WeatherCondition.OVERCAST,
    WeatherCondition.CLOUDY,
    WeatherCondition.FOG,
}


# Mappatura codici WMO (World Meteorological Organization) secondo PRD
def map_wmo_to_condition(
    wmo_code: int, *, is_day: bool | None = None
) -> WeatherCondition:
    """Converte un codice meteo WMO nella corrispondente condizione di gioco."""
    if wmo_code == 0:
        return WeatherCondition.CLEAR
    if wmo_code in (1, 2):
        return (
            WeatherCondition.CLOUDY
            if is_day is False
            else WeatherCondition.PARTLY_CLOUDY
        )
    if wmo_code == 3:
        return WeatherCondition.OVERCAST
    if wmo_code in (45, 48):
        return WeatherCondition.FOG
    if wmo_code in (51, 53, 55, 56, 57):
        return WeatherCondition.DRIZZLE
    if wmo_code in (61, 63, 65, 66, 67):
        return WeatherCondition.RAIN
    if wmo_code in (71, 73, 75, 76, 85, 86):
        return WeatherCondition.SNOW
    if wmo_code == 77:
        return WeatherCondition.SNOW_GRAINS
    if wmo_code in (80, 81, 82):
        return WeatherCondition.RAIN_SHOWERS
    if wmo_code in (95, 97, 98):
        return WeatherCondition.THUNDERSTORM
    if wmo_code in (96, 99):
        return WeatherCondition.THUNDERSTORM_HAIL
    return WeatherCondition.OVERCAST


# Tipo colore RGB 24-bit
RGB = Tuple[int, int, int]

# Palette Cielo Naturale (Top -> Horizon)
SKY_GRADIENTS: Dict[WeatherCondition, Tuple[RGB, RGB]] = {
    WeatherCondition.CLEAR: ((45, 115, 195), (120, 185, 235)),
    WeatherCondition.PARTLY_CLOUDY: ((55, 115, 175), (125, 175, 215)),
    WeatherCondition.OVERCAST: ((48, 70, 98), (105, 125, 148)),
    WeatherCondition.CLOUDY: ((40, 75, 125), (95, 135, 175)),
    WeatherCondition.DRIZZLE: ((40, 60, 86), (86, 116, 145)),
    WeatherCondition.RAIN: ((25, 45, 75), (65, 95, 130)),
    WeatherCondition.RAIN_SHOWERS: ((30, 48, 78), (74, 108, 145)),
    WeatherCondition.SNOW: ((45, 75, 115), (130, 160, 195)),
    WeatherCondition.SNOW_GRAINS: ((70, 100, 135), (150, 175, 200)),
    WeatherCondition.FOG: ((100, 115, 125), (165, 175, 180)),
    WeatherCondition.THUNDERSTORM: ((10, 18, 35), (30, 45, 70)),
    WeatherCondition.THUNDERSTORM_HAIL: ((16, 22, 40), (42, 48, 72)),
}

NIGHT_SKY_GRADIENT: Tuple[RGB, RGB] = ((5, 10, 25), (15, 25, 45))

# Palette Mare Notturno (Surface -> Deep)
SEA_GRADIENTS: Dict[WeatherCondition, Tuple[RGB, RGB]] = {
    WeatherCondition.CLEAR: ((30, 130, 190), (10, 45, 95)),
    WeatherCondition.PARTLY_CLOUDY: ((28, 120, 175), (8, 42, 88)),
    WeatherCondition.OVERCAST: ((27, 100, 145), (8, 38, 72)),
    WeatherCondition.CLOUDY: ((25, 115, 170), (8, 40, 85)),
    WeatherCondition.DRIZZLE: ((25, 110, 160), (7, 37, 78)),
    WeatherCondition.RAIN: ((22, 105, 160), (6, 35, 75)),
    WeatherCondition.RAIN_SHOWERS: ((24, 108, 162), (7, 36, 76)),
    WeatherCondition.SNOW: ((50, 150, 210), (14, 55, 110)),
    WeatherCondition.SNOW_GRAINS: ((62, 155, 200), (20, 65, 115)),
    WeatherCondition.FOG: ((65, 120, 145), (32, 75, 100)),
    WeatherCondition.THUNDERSTORM: ((20, 95, 145), (5, 28, 65)),
    WeatherCondition.THUNDERSTORM_HAIL: ((24, 98, 145), (8, 32, 68)),
}

# Palette Mare Diurno: da turchese/ciano brillante rgb(30, 160, 210) a blu oceano rgb(15, 80, 140)
DAY_SEA_GRADIENTS: Dict[WeatherCondition, Tuple[RGB, RGB]] = {
    WeatherCondition.CLEAR: ((30, 160, 210), (15, 80, 140)),
    WeatherCondition.PARTLY_CLOUDY: ((30, 150, 200), (15, 75, 135)),
    WeatherCondition.OVERCAST: ((28, 125, 170), (12, 62, 110)),
    WeatherCondition.CLOUDY: ((28, 145, 195), (14, 72, 130)),
    WeatherCondition.DRIZZLE: ((28, 138, 188), (13, 67, 122)),
    WeatherCondition.RAIN: ((25, 130, 180), (12, 65, 120)),
    WeatherCondition.RAIN_SHOWERS: ((27, 135, 186), (13, 66, 120)),
    WeatherCondition.SNOW: ((55, 175, 225), (20, 90, 150)),
    WeatherCondition.SNOW_GRAINS: ((75, 180, 220), (30, 98, 150)),
    WeatherCondition.FOG: ((100, 150, 170), (65, 105, 130)),
    WeatherCondition.THUNDERSTORM: ((22, 115, 165), (10, 55, 105)),
    WeatherCondition.THUNDERSTORM_HAIL: ((30, 118, 165), (12, 57, 105)),
}

# Colori RGB per gli elementi atmosferici e marini
COLOR_SUN: RGB = (255, 215, 0)
COLOR_MOON: RGB = (240, 242, 210)
COLOR_STAR_BRIGHT: RGB = (220, 235, 255)
COLOR_STAR_DIM: RGB = (120, 150, 195)
COLOR_CLOUD_DAY: RGB = (220, 230, 245)
COLOR_CLOUD: RGB = (195, 205, 218)
COLOR_DARK_CLOUD: RGB = (105, 118, 135)
COLOR_RAIN: RGB = (95, 160, 220)
COLOR_SNOW: RGB = (235, 245, 255)
COLOR_LIGHTNING: RGB = (255, 250, 190)
COLOR_ICE_FLOE: RGB = (210, 245, 255)

# Cresta delle onde e schiuma ad alto contrasto (Giorno e Notte)
COLOR_WAVE_FOAM_DAY: RGB = (200, 240, 255)
COLOR_WAVE_SURFACE_DAY: RGB = (30, 160, 210)
COLOR_SEA_DEEP_DAY: RGB = (15, 80, 140)

COLOR_WAVE_FOAM: RGB = (180, 240, 255)
COLOR_WAVE_CREST: RGB = (130, 225, 255)
COLOR_WAVE_SURFACE: RGB = (45, 145, 200)
COLOR_SEA_TEXTURE: RGB = (20, 85, 145)

# Colori delle Navi (TrueColor ad alta saturazione e contrasto per visibilità a distanza)
COLOR_SHIP_SAIL: RGB = (250, 250, 250)          # Bianco candido puro ad alto contrasto
COLOR_SHIP_SAIL_DAY: RGB = (250, 250, 250)      # Bianco candido puro ad alto contrasto
COLOR_SHIP_BADGE_CREAM: RGB = (245, 235, 180)   # Sfondo badge crema luminoso
COLOR_SHIP_BADGE_GOLD: RGB = (255, 215, 0)      # Sfondo badge oro
COLOR_SHIP_HULL: RGB = (210, 130, 60)           # Marrone noce vivo
COLOR_SHIP_HULL_DAY: RGB = (210, 130, 60)       # Marrone noce vivo
COLOR_SHIP_DECK: RGB = (225, 150, 70)           # Legname ponte caldo e saturo
COLOR_SHIP_MAST: RGB = (175, 110, 50)           # Ocra legno saturo e luminoso
COLOR_SHIP_CANNON: RGB = (235, 235, 245)        # Metallo chiaro brillante per bocche cannoni [o]
COLOR_SHIP_BANNER: RGB = (140, 0, 0)            # Cremisi/bordeaux scuro ad altissimo contrasto su badge
COLOR_SHIP_BANNER_DAY: RGB = (0, 20, 110)       # Blu navy profondo ad altissimo contrasto su badge
COLOR_SHIP_BANNER_GOLD: RGB = (255, 215, 0)     # Oro brillante
COLOR_SHIP_WAKE: RGB = (215, 250, 255)
COLOR_SHIP_SUBMERGED: RGB = (40, 125, 190)
COLOR_SHIP_DAMAGED: RGB = (255, 80, 30)
COLOR_SMOKE: RGB = (255, 200, 110)              # Scintille/fumo caldo ambrato (niente grigio scuro slavato)

# Palette cromatiche per fazioni navali (TrueColor RGB saturi con badge ad alto contrasto)
SHIP_PALETTES: Dict[str, Dict[str, RGB]] = {
    "reale": {
        "hull_day": (210, 130, 60),
        "hull_night": (210, 130, 60),
        "deck": (225, 150, 70),
        "mast": (175, 110, 50),
        "sail_day": (250, 250, 250),
        "sail_night": (250, 250, 250),
        "badge_bg": (255, 215, 0),
        "banner_day": (140, 0, 0),
        "banner_night": (140, 0, 0),
        "cannon": (235, 235, 245),
    },
    "mercantile": {
        "hull_day": (210, 130, 60),
        "hull_night": (210, 130, 60),
        "deck": (225, 150, 70),
        "mast": (175, 110, 50),
        "sail_day": (250, 250, 250),
        "sail_night": (250, 250, 250),
        "badge_bg": (245, 235, 180),
        "banner_day": (0, 20, 110),
        "banner_night": (0, 20, 110),
        "cannon": (235, 235, 245),
    },
    "corsara": {
        "hull_day": (210, 130, 60),
        "hull_night": (210, 130, 60),
        "deck": (225, 150, 70),
        "mast": (175, 110, 50),
        "sail_day": (245, 235, 180),
        "sail_night": (245, 235, 180),
        "badge_bg": (255, 215, 0),
        "banner_day": (140, 0, 0),
        "banner_night": (140, 0, 0),
        "cannon": (235, 235, 245),
    },
    "pirata": {
        "hull_day": (210, 130, 60),
        "hull_night": (210, 130, 60),
        "deck": (225, 150, 70),
        "mast": (175, 110, 50),
        "sail_day": (250, 250, 250),
        "sail_night": (245, 235, 180),
        "badge_bg": (245, 235, 180),
        "banner_day": (140, 0, 0),
        "banner_night": (0, 20, 110),
        "cannon": (235, 235, 245),
    },
}

# Colori Proiettili (palle di fuoco evidenziate '* FRASE *'), Particelle e HUD
COLOR_PROJECTILE_TEXT: RGB = (255, 250, 150)
COLOR_PROJECTILE_FLASH: RGB = (255, 255, 255)
COLOR_PROJECTILE_BG: RGB = (205, 30, 0)
COLOR_PROJECTILE_BG_ALT: RGB = (255, 95, 0)
COLOR_PROJECTILE_TRAIL: RGB = (255, 215, 0)
COLOR_EXPLOSION: RGB = (255, 230, 80)
COLOR_EXPLOSION_ORANGE: RGB = (255, 140, 0)
COLOR_EXPLOSION_YELLOW: RGB = (255, 220, 0)
COLOR_MUZZLE_SMOKE: RGB = (255, 225, 140)
COLOR_HULL_SMOKE_DARK: RGB = (255, 145, 35)
COLOR_SEAGULL: RGB = (255, 255, 255)
COLOR_SEAGULL_DAY: RGB = (255, 255, 255)
COLOR_SEAGULL_NIGHT: RGB = (255, 255, 255)
COLOR_FISH_DAY: RGB = (100, 220, 240)
COLOR_FISH_NIGHT: RGB = (75, 175, 210)
COLOR_FISH_SHALLOW: RGB = (100, 220, 240)
COLOR_FISH_DEEP: RGB = (35, 75, 120)
COLOR_HUD_TEXT: RGB = (185, 215, 240)

# Parametri fisici e di simulazione
SEA_LEVEL_RATIO: float = 0.68  # Posizione verticale media della linea del mare
GRAVITY: float = 9.81          # Accelerazione di gravità per traiettoria parabolica (celle/s^2)

# Parametri onde per condizione meteo: (ampiezza, frequenza_spaziale, velocità_fase, cresta_prob)
WAVE_PARAMS: Dict[WeatherCondition, Tuple[float, float, float, float]] = {
    WeatherCondition.CLEAR: (0.42, 0.13, 1.35, 0.12),
    WeatherCondition.PARTLY_CLOUDY: (0.52, 0.14, 1.55, 0.16),
    WeatherCondition.OVERCAST: (0.62, 0.15, 1.8, 0.20),
    WeatherCondition.CLOUDY: (0.68, 0.15, 1.95, 0.22),
    WeatherCondition.DRIZZLE: (0.72, 0.16, 2.1, 0.25),
    WeatherCondition.RAIN: (1.08, 0.17, 2.65, 0.35),
    WeatherCondition.RAIN_SHOWERS: (1.22, 0.18, 2.85, 0.40),
    WeatherCondition.SNOW: (0.38, 0.11, 0.95, 0.15),
    WeatherCondition.SNOW_GRAINS: (0.12, 0.10, 0.45, 0.03),
    WeatherCondition.FOG: (0.28, 0.10, 0.75, 0.08),
    WeatherCondition.THUNDERSTORM: (1.60, 0.20, 3.60, 0.50),
    WeatherCondition.THUNDERSTORM_HAIL: (1.72, 0.21, 3.8, 0.55),
}

# Parametri navali e di combattimento
SHIP_MIN_SPEED: float = 1.0       # Celle al secondo
SHIP_MAX_SPEED: float = 2.3       # Celle al secondo
SHIP_MAX_HP: int = 100
CANNON_DAMAGE_MIN: int = 25
CANNON_DAMAGE_MAX: int = 40
SHIP_FIRE_RANGE_MIN: float = 14.0
SHIP_FIRE_RANGE_MAX: float = 72.0
SHIP_FIRE_COOLDOWN_MIN: float = 4.4
SHIP_FIRE_COOLDOWN_MAX: float = 9.6
SHIP_SINK_SPEED: float = 1.8      # Celle al secondo verso il fondo durante SINKING
SHIP_RESPAWN_DELAY_MIN: float = 10.5
SHIP_RESPAWN_DELAY_MAX: float = 15.5
