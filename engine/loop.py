"""
engine/loop.py - Game loop principale su asciimatics, gestione spawn/respawn navi,
collisioni balistiche, ridimensionamento terminale (SIGWINCH), HUD meteo multiriga
e Menù modale in sovraimpressione ([M] / [Esc]).
"""

from __future__ import annotations
from datetime import datetime
import json
import math
from pathlib import Path
import random
import time
from typing import Dict, List, Optional, Tuple
from asciimatics.event import KeyboardEvent
from asciimatics.screen import Screen

from config import (
    AppearanceMode,
    BIG_HUD_MIN_HEIGHT,
    BIG_HUD_MIN_WIDTH,
    COLOR_WAVE_CREST,
    DEFAULT_FPS,
    FALLBACK_PHRASES,
    FPS_STEP,
    HudMode,
    MAX_FPS,
    MIN_FPS,
    PHRASES_FILE,
    RGB,
    SHIP_FIRE_COOLDOWN_MAX,
    SHIP_FIRE_COOLDOWN_MIN,
    SHIP_FIRE_RANGE_MAX,
    SHIP_FIRE_RANGE_MIN,
    SHIP_PALETTES,
    SHIP_RESPAWN_DELAY_MAX,
    SHIP_RESPAWN_DELAY_MIN,
    SNOW_CONDITIONS,
)
from engine.big_font import BIG_FONT_5X, BIG_HUD_GOLD, render_big_text
from engine.renderer import Renderer
from engine.weather_thread import WeatherSnapshot, WeatherState
from entities.projectile import (
    CombatParticle,
    ImpactEffect,
    Projectile,
    spawn_impact_explosion,
    spawn_muzzle_smoke,
)
from entities.sea import Sea
from entities.ship import SHIP_CLASSES, Ship, ShipState
from entities.weather import WeatherSystem


COLOR_MENU_BG: RGB = (12, 22, 42)
COLOR_MENU_BORDER: RGB = (220, 185, 95)
COLOR_MENU_TITLE: RGB = (255, 215, 0)
COLOR_MENU_TEXT: RGB = (240, 245, 255)
COLOR_MENU_KEY: RGB = (120, 220, 255)


def load_phrases(path: Path = PHRASES_FILE) -> Tuple[List[str], List[str]]:
    """
    Carica le liste sail_banners e cannon_insults dal file JSON.
    In caso di file mancante, illeggibile o JSON corrotto, usa FALLBACK_PHRASES.
    """
    default_banners = list(FALLBACK_PHRASES["sail_banners"])
    default_insults = list(FALLBACK_PHRASES["cannon_insults"])
    try:
        with path.open("r", encoding="utf-8") as f:
            data: Dict[str, List[str]] = json.load(f)
        if not isinstance(data, dict):
            return default_banners, default_insults
        raw_banners = data.get("sail_banners", [])
        raw_insults = data.get("cannon_insults", [])
        banners = (
            [str(s).strip() for s in raw_banners if str(s).strip()]
            if isinstance(raw_banners, list)
            else []
        )
        insults = (
            [str(s).strip() for s in raw_insults if str(s).strip()]
            if isinstance(raw_insults, list)
            else []
        )
        return (banners or default_banners, insults or default_insults)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return default_banners, default_insults


def _format_duration(seconds: float) -> str:
    """Formatta i secondi di sessione in MM:SS (o HH:MM:SS)."""
    total = max(0, int(seconds))
    mins, secs = divmod(total, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def _weather_hud_lines(snap: WeatherSnapshot) -> Tuple[str, ...]:
    """Prepara le righe informative meteo per l'intestazione."""
    local_clock = (
        snap.city_local_time.strftime("%H:%M:%S")
        if snap.city_local_time is not None
        else datetime.now().strftime("%H:%M:%S")
    )
    temperature = (
        f"{snap.temperature_c:.1f}°C"
        if snap.temperature_c is not None
        else "N/D"
    )
    apparent = (
        f"{snap.apparent_temperature_c:.1f}°C"
        if snap.apparent_temperature_c is not None
        else "N/D"
    )
    humidity = (
        f"{snap.relative_humidity_pct:.0f}%"
        if snap.relative_humidity_pct is not None
        else "N/D"
    )
    mode = snap.appearance_mode.value.upper()
    if snap.appearance_mode == AppearanceMode.AUTO:
        mode += f"/{'LIGHT' if snap.is_day else 'DARK'}"
    return (
        f"{snap.city} | {local_clock} | {mode}",
        (
            f"{snap.condition.value.upper()} | "
            f"{temperature} | Percepita {apparent}"
        ),
        (
            f"Umidita' {humidity} | Vento {snap.wind_speed_kmh:.0f} km/h | "
            "[W] Meteo [H] HUD [T] Tema [M] Menu'"
        ),
    )


def _compact_top_bar_line(snap: WeatherSnapshot) -> str:
    """Formatta la Top Bar compatta a riga singola per finestre con height < 30."""
    local_clock = (
        snap.city_local_time.strftime("%H:%M:%S")
        if snap.city_local_time is not None
        else datetime.now().strftime("%H:%M:%S")
    )
    temperature = (
        f"{snap.temperature_c:.1f}°C"
        if snap.temperature_c is not None
        else "N/D"
    )
    humidity = (
        f"{snap.relative_humidity_pct:.0f}%"
        if snap.relative_humidity_pct is not None
        else "N/D"
    )
    mode = "DAY" if snap.is_day else "NIGHT"
    return (
        f" {snap.city} | {local_clock} | {snap.condition.value.upper()} "
        f"| {temperature} | Umid {humidity} | Vento {snap.wind_speed_kmh:.0f}km/h "
        f"| {mode} | [Spazio] Fuoco [W] Meteo [H] HUD [M] Menu"
    )


class NavalBattleWorld:
    """
    Coordina tutte le entità della simulazione (meteo, mare, navi, proiettili),
    le statistiche di sessione, il Big HUD responsive ([H]) e il menù modale ([M]).
    """

    def __init__(
        self,
        width: int,
        height: int,
        weather_state: WeatherState,
        max_ships: int,
        target_fps: int = DEFAULT_FPS,
    ) -> None:
        self.width: int = width
        self.height: int = height
        self.weather_state: WeatherState = weather_state
        self.max_ships: int = max(2, max_ships)
        self.target_fps: int = max(MIN_FPS, min(MAX_FPS, target_fps))
        self.current_fps: float = float(self.target_fps)
        self.session_start_time: float = time.monotonic()
        self.menu_open: bool = False
        self.hud_mode: HudMode = HudMode.AUTO

        self.sail_banners, self.cannon_insults = load_phrases()
        self.sea = Sea(width, height)
        self.weather_fx = WeatherSystem(width, height)

        self.ships: List[Ship] = []
        self.projectiles: List[Projectile] = []
        self.impacts: List[ImpactEffect] = []
        self.combat_particles: List[CombatParticle] = []
        self.respawn_timers: List[float] = []
        self.sunk_counter: int = 0
        self.shots_fired_counter: int = 0

        # Popolamento iniziale con almeno 2 navi e timer per le restanti
        initial_ships = min(self.max_ships, max(2, self.max_ships - 1))
        for i in range(initial_ships):
            self._spawn_ship(initial_placement=True, slot_idx=i, total_slots=initial_ships)
        for _ in range(self.max_ships - initial_ships):
            self.respawn_timers.append(random.uniform(1.0, 3.0))

    def toggle_menu(self) -> bool:
        """Apre o chiude il menù modale in sovraimpressione ([M])."""
        self.menu_open = not self.menu_open
        return self.menu_open

    def cycle_hud_mode(self) -> HudMode:
        """Cicla manualmente la modalità dell'HUD tra AUTO, BIG e COMPACT ([H])."""
        cycle = (HudMode.AUTO, HudMode.BIG, HudMode.COMPACT)
        idx = cycle.index(self.hud_mode)
        self.hud_mode = cycle[(idx + 1) % len(cycle)]
        return self.hud_mode

    def is_big_hud_active(self) -> bool:
        """
        Determina se disegnare il Big HUD a cifre giganti su 3 righe:
        - Se HudMode.BIG: sempre attivo.
        - Se HudMode.COMPACT: sempre disattivo (usa la Top Bar compatta).
        - Se HudMode.AUTO: attivo se screen.height >= 30 e screen.width >= 100.
        """
        if self.hud_mode == HudMode.BIG:
            return True
        if self.hud_mode == HudMode.COMPACT:
            return False
        return self.height >= BIG_HUD_MIN_HEIGHT and self.width >= BIG_HUD_MIN_WIDTH

    def resize(self, width: int, height: int) -> None:
        """Adatta il mondo di gioco alle nuove dimensioni del terminale."""
        self.width = width
        self.height = height
        self.sea.resize(width, height)
        self.weather_fx.resize(width, height)
        for ship in self.ships:
            ship.x = max(2.0, min(float(max(4, width - ship.width - 2)), ship.x))

    def _choose_unique_banner(self) -> str:
        """Seleziona un banner evitando duplicati tra le navi attualmente a schermo."""
        used = {s.banner for s in self.ships}
        available = [b for b in self.sail_banners if b not in used]
        pool = available if available else self.sail_banners
        return random.choice(pool)

    def _spawn_ship(
        self,
        *,
        initial_placement: bool = False,
        slot_idx: int = 0,
        total_slots: int = 2,
    ) -> None:
        """Genera una nuova nave con classe e palette casuali dai margini o distribuita all'avvio."""
        banner = self._choose_unique_banner()
        ship_class = random.choice(list(SHIP_CLASSES.keys()))
        palette_name = random.choice(list(SHIP_PALETTES.keys()))

        if initial_placement:
            direction = 1 if (slot_idx % 2 == 0) else -1
        else:
            direction = random.choice([-1, 1])

        ship = Ship(
            x=2.0,
            direction=direction,
            banner=banner,
            ship_class=ship_class,
            palette_name=palette_name,
        )

        if initial_placement:
            sector_w = max(ship.width, self.width // max(1, total_slots))
            x = float(slot_idx * sector_w + random.randint(2, max(4, sector_w // 3)))
            ship.x = max(2.0, min(float(max(8, self.width - ship.width - 2)), x))
        else:
            ship.x = 2.0 if direction > 0 else float(max(6, self.width - ship.width - 2))

        max_depth = max(
            0.0,
            float(self.sea.height - self.sea.base_sea_y - 2),
        )
        ship.max_visible_depth = max(1.0, max_depth)
        if initial_placement:
            ship.depth_offset = max_depth * (
                slot_idx / max(1, total_slots - 1)
            )
        else:
            ship.depth_offset = random.uniform(0.0, max_depth)
        ship.depth_target = ship.depth_offset
        ship.y = (
            self.sea.surface_y_at(ship.center_x, ship.depth_offset)
            - ship.visual_height
        )
        self.ships.append(ship)

    def adjust_max_ships(self, delta: int) -> int:
        """Aumenta o diminuisce a runtime il limite massimo di navi a schermo ([+] / [-])."""
        new_max = max(1, min(10, self.max_ships + delta))
        if new_max == self.max_ships:
            return self.max_ships

        self.max_ships = new_max
        if delta > 0 and len(self.ships) < self.max_ships:
            self._spawn_ship(initial_placement=False)
        elif delta < 0:
            while len(self.ships) > self.max_ships:
                self.ships.pop()
            self.respawn_timers = self.respawn_timers[
                : max(0, self.max_ships - len(self.ships))
            ]
        return self.max_ships

    def adjust_target_fps(self, direction: int) -> int:
        """Regola il refresh obiettivo a passi di FPS_STEP, entro i limiti supportati."""
        self.target_fps = max(
            MIN_FPS,
            min(MAX_FPS, self.target_fps + direction * FPS_STEP),
        )
        return self.target_fps

    def handle_refresh_key(self, key: int) -> bool:
        """Gestisce i tasti funzione dedicati alla regolazione del refresh."""
        if key == Screen.KEY_F2:
            self.adjust_target_fps(-1)
            return True
        if key == Screen.KEY_F3:
            self.adjust_target_fps(1)
            return True
        return False

    def _fire_from_ship(
        self, attacker: Ship, target: Optional[Ship] = None
    ) -> Projectile:
        """
        Lancia una frase-proiettile da `attacker` verso `target` (oppure in avanti
        a scopo dimostrativo se `target` è None) generando lo sbuffo di fumo.
        """
        start_x, start_y = attacker.cannon_origin
        if target is not None:
            target_x = target.center_x
            target_y = target.y + target.height * 0.55
            water_depth = max(attacker.depth_offset, target.depth_offset)
        else:
            reach = min(38.0, max(18.0, self.width * 0.35))
            raw_tx = attacker.center_x + attacker.direction * reach
            target_x = max(4.0, min(float(max(10, self.width - 4)), raw_tx))
            if abs(target_x - start_x) < 10.0:
                target_x = start_x - attacker.direction * reach
            water_depth = attacker.depth_offset
            target_y = self.sea.surface_y_at(target_x, water_depth)

        insult = random.choice(self.cannon_insults)
        proj = Projectile.launch_towards(
            owner_id=attacker.ship_id,
            start_x=start_x,
            start_y=start_y,
            target_x=target_x,
            target_y=target_y,
            text=insult,
            water_depth=water_depth,
        )
        self.projectiles.append(proj)
        self.shots_fired_counter += 1
        self.combat_particles.extend(
            spawn_muzzle_smoke(start_x, start_y, attacker.direction)
        )
        attacker.fire_cooldown = random.uniform(
            SHIP_FIRE_COOLDOWN_MIN, SHIP_FIRE_COOLDOWN_MAX
        )
        return proj

    def force_salvo(self) -> int:
        """
        Forza una salva di cannonate immediata ([Spazio]):
        - Se ci sono >= 2 navi in stato SAILING, ognuna spara alla nave avversaria più vicina.
        - Se c'è 1 sola nave in stato SAILING, spara un colpo dimostrativo in avanti.
        """
        sailing_ships = [s for s in self.ships if s.state == ShipState.SAILING]
        if not sailing_ships:
            return 0

        if len(sailing_ships) == 1:
            self._fire_from_ship(sailing_ships[0], None)
            return 1

        fired = 0
        for attacker in sailing_ships:
            others = [t for t in sailing_ships if t.ship_id != attacker.ship_id]
            if others:
                target = min(others, key=lambda t: abs(t.center_x - attacker.center_x))
                self._fire_from_ship(attacker, target)
                fired += 1
        return fired

    def _handle_combat(self) -> None:
        """Verifica se le navi attive hanno un bersaglio a tiro e lancia le frasi-proiettile."""
        sailing_ships = [s for s in self.ships if s.state == ShipState.SAILING]
        if len(sailing_ships) < 2:
            return

        max_range = max(SHIP_FIRE_RANGE_MAX, self.width * 0.85)
        for attacker in sailing_ships:
            if attacker.fire_cooldown > 0.0:
                continue

            candidates: List[Ship] = []
            for target in sailing_ships:
                if target.ship_id == attacker.ship_id:
                    continue
                dist = abs(target.center_x - attacker.center_x)
                if SHIP_FIRE_RANGE_MIN <= dist <= max_range:
                    candidates.append(target)

            if candidates:
                target = min(
                    candidates, key=lambda t: abs(t.center_x - attacker.center_x)
                )
                self._fire_from_ship(attacker, target)

    def _update_projectiles(self, dt: float) -> None:
        """
        Aggiorna la traiettoria dei proiettili con sub-stepping per evitare tunneling
        a bassi FPS e verifica impatti con lo scafo avversario o con il mare.
        """
        steps = max(1, int(math.ceil(dt / 0.04)))
        sub_dt = dt / steps

        for proj in self.projectiles:
            if not proj.active:
                continue

            for _ in range(steps):
                if not proj.active:
                    break
                proj.update(sub_dt)
                px, py = proj.x, proj.y

                if px < -10.0 or px > self.width + 10.0 or py > self.height + 20.0:
                    proj.active = False
                    break

                hit_ship: Optional[Ship] = None
                for ship in self.ships:
                    if ship.ship_id != proj.owner_id and ship.contains_point(px, py):
                        hit_ship = ship
                        break

                if hit_ship is not None:
                    was_sailing = hit_ship.state == ShipState.SAILING
                    hit_ship.take_damage(proj.damage)
                    if was_sailing and hit_ship.state == ShipState.SINKING:
                        self.sunk_counter += 1
                    proj.active = False
                    self.impacts.append(
                        ImpactEffect(x=px, y=py, is_hit=True, text="BOOM!")
                    )
                    self.combat_particles.extend(spawn_impact_explosion(px, py))
                    break

                water_y = self.sea.surface_y_at(px, proj.water_depth)
                if proj.is_descending and py >= water_y:
                    proj.active = False
                    self.impacts.append(
                        ImpactEffect(x=px, y=water_y, is_hit=False, text="~SPLASH~")
                    )
                    break

        self.projectiles = [
            p
            for p in self.projectiles
            if p.active and -50.0 <= p.x <= self.width + 50.0
        ]

    def update(self, dt: float) -> None:
        """Esegue un passo di simulazione completo (sospeso quando il menù è aperto)."""
        if self.menu_open:
            return

        snap = self.weather_state.snapshot()
        condition = snap.condition

        sinking_boxes = [
            (s.x, s.y, s.x + s.width, s.y + s.height)
            for s in self.ships
            if s.state == ShipState.SINKING
        ]

        # 1. Aggiorna mare e meteo
        self.sea.update(
            dt,
            condition,
            sinking_boxes=sinking_boxes,
        )
        self.weather_fx.update(dt, condition, self.sea.base_sea_y)

        # 2. Aggiorna navi e gestisci affondamenti/respawn
        surviving_ships: List[Ship] = []
        for ship in self.ships:
            ship.update(
                dt,
                self.sea,
                self.width,
                tuple(other for other in self.ships if other is not ship),
                icebreaker=condition in SNOW_CONDITIONS,
            )
            offscreen = ship.x < -50.0 or ship.x > self.width + 50.0
            if ship.state == ShipState.SUNK or offscreen:
                self.respawn_timers.append(
                    random.uniform(SHIP_RESPAWN_DELAY_MIN, SHIP_RESPAWN_DELAY_MAX)
                )
            else:
                surviving_ships.append(ship)
        self.ships = surviving_ships

        # 3. Gestisci timer di respawn per mantenere viva la battaglia
        remaining_timers: List[float] = []
        for timer in self.respawn_timers:
            timer -= dt
            if timer <= 0.0 and len(self.ships) < self.max_ships:
                self._spawn_ship(initial_placement=False)
            else:
                remaining_timers.append(timer)
        self.respawn_timers = remaining_timers

        if len(self.ships) + len(self.respawn_timers) < self.max_ships:
            self.respawn_timers.append(
                random.uniform(SHIP_RESPAWN_DELAY_MIN, SHIP_RESPAWN_DELAY_MAX)
            )

        # 4. Combattimento e proiettili
        self._handle_combat()
        self._update_projectiles(dt)

        # 5. Aggiorna particelle di combattimento ed effetti di impatto
        for cp in self.combat_particles:
            cp.update(dt)
        self.combat_particles = [
            cp
            for cp in self.combat_particles
            if cp.active and -50.0 <= cp.x <= self.width + 50.0
        ]

        for imp in self.impacts:
            imp.timer -= dt
        self.impacts = [
            imp
            for imp in self.impacts
            if imp.timer > 0.0 and -50.0 <= imp.x <= self.width + 50.0
        ]

    def _draw_hud(self, renderer: Renderer, snap: WeatherSnapshot) -> None:
        """
        Disegna l'HUD superiore con logica responsive e toggle manuale ([H]):
        - Se il Big HUD è attivo (AUTO con height >= 30 e width >= 100, oppure HudMode.BIG):
          disegna la barra informativa compatta in riga 0 e il Big Clock [HH:MM:SS] + [XX°C]
          su 5 righe (BIG_FONT_5X) in colore oro brillante BOLD rgb(255, 215, 0) centrato in alto.
        - Se la finestra è compatta (height < 30 o HudMode.COMPACT):
          usa la Top Bar compatta a riga singola.
        """
        if self.width <= 0 or self.height <= 0:
            return

        top_bar = _compact_top_bar_line(snap)[: self.width].ljust(self.width)
        renderer.draw_text(
            top_bar,
            0,
            0,
            COLOR_MENU_TEXT,
            bg_rgb=COLOR_MENU_BG,
            bold=True,
            transparent=False,
        )

        if not self.is_big_hud_active() or self.height < 6:
            return

        clock_str = (
            snap.city_local_time.strftime("%H:%M:%S")
            if snap.city_local_time is not None
            else datetime.now().strftime("%H:%M:%S")
        )
        temp_str = (
            f"{int(round(snap.temperature_c))}°C"
            if snap.temperature_c is not None
            else "--°C"
        )
        big_label = f"{clock_str}   {temp_str}"
        big_rows = render_big_text(big_label)
        block_w = len(big_rows[0]) if big_rows else 0
        start_x = max(0, (self.width - block_w) // 2)

        for idx, row_text in enumerate(big_rows):
            ry = 1 + idx
            if ry >= self.height:
                break
            renderer.draw_text(
                row_text,
                start_x,
                ry,
                BIG_HUD_GOLD,
                bold=True,
                transparent=True,
            )

    def _draw_menu_overlay(self, renderer: Renderer, snap: WeatherSnapshot) -> None:
        """
        Disegna al centro dello schermo un riquadro ASCII modale con:
        - Sezione 1: Statistiche di Sessione
        - Sezione 2: Legenda Tasti Rapidi
        """
        if self.width < 12 or self.height < 4:
            return

        temp_str = (
            f"{snap.temperature_c:.1f}°C" if snap.temperature_c is not None else "N/D"
        )
        apparent_str = (
            f"{snap.apparent_temperature_c:.1f}°C"
            if snap.apparent_temperature_c is not None
            else "N/D"
        )
        if snap.latitude is not None and snap.longitude is not None:
            coords_str = f"({snap.latitude:.2f}°N, {snap.longitude:.2f}°E)"
        else:
            coords_str = f"[{snap.status_note}]"
        tod_label = "GIORNO" if snap.is_day else "NOTTE"
        session_time = _format_duration(time.monotonic() - self.session_start_time)
        hud_label = f"{self.hud_mode.value.upper()} ({'BIG' if self.is_big_hud_active() else 'COMPACT'})"

        box_w = max(10, min(max(52, self.width - 6), 66, self.width))
        inner_w = max(1, box_w - 2)

        def _pad_row(content: str) -> str:
            clipped = content[:inner_w]
            return f"|{clipped.ljust(inner_w)}|"

        def _center_row(content: str) -> str:
            clipped = content[:inner_w]
            return f"|{clipped.center(inner_w)}|"

        border_h = "+" + ("-" * inner_w) + "+"
        sep_h = "+" + ("-" * inner_w) + "+"

        rows: List[Tuple[str, RGB, bool]] = [
            (border_h, COLOR_MENU_BORDER, True),
            (_center_row("ASCIISHIPS - MENU DI COMANDO (IN PAUSA)"), COLOR_MENU_TITLE, True),
            (sep_h, COLOR_MENU_BORDER, True),
            (_pad_row(" SEZIONE 1 - STATISTICHE DI SESSIONE"), COLOR_MENU_TITLE, True),
            (
                _pad_row(f"   Navi attualmente in mare : {len(self.ships)} / {self.max_ships}"),
                COLOR_MENU_TEXT,
                False,
            ),
            (
                _pad_row(f"   Totale navi affondate    : {self.sunk_counter}"),
                COLOR_MENU_TEXT,
                False,
            ),
            (
                _pad_row(f"   Colpi / insulti sparati  : {self.shots_fired_counter}"),
                COLOR_MENU_TEXT,
                False,
            ),
            (
                _pad_row(f"   Citta' e Coordinate      : {snap.city} {coords_str}"),
                COLOR_MENU_TEXT,
                False,
            ),
            (
                _pad_row(
                    f"   Meteo corrente           : {snap.condition.value.upper()} | {tod_label} ({temp_str}, percepita {apparent_str})"
                ),
                COLOR_MENU_TEXT,
                False,
            ),
            (
                _pad_row(
                    f"   Umidita' / Vento         : {snap.relative_humidity_pct:.0f}% | {snap.wind_speed_kmh:.0f} km/h"
                    if snap.relative_humidity_pct is not None
                    else f"   Umidita' / Vento         : N/D | {snap.wind_speed_kmh:.0f} km/h"
                ),
                COLOR_MENU_TEXT,
                False,
            ),
            (
                _pad_row(
                    f"   Ora locale / HUD         : {(snap.city_local_time or datetime.now()).strftime('%H:%M:%S')} | HUD {hud_label}"
                ),
                COLOR_MENU_TEXT,
                False,
            ),
            (
                _pad_row(
                    f"   FPS attuali / obiettivo  : {self.current_fps:.0f} / {self.target_fps} FPS | {session_time}"
                ),
                COLOR_MENU_TEXT,
                False,
            ),
            (sep_h, COLOR_MENU_BORDER, True),
            (_pad_row(" SEZIONE 2 - LEGENDA TASTI RAPIDI"), COLOR_MENU_TITLE, True),
            (
                _pad_row("   [Spazio]  : Salva di cannonate istantanea"),
                COLOR_MENU_KEY,
                False,
            ),
            (
                _pad_row("   [W]       : Cambia meteo ciclicamente (debug/test)"),
                COLOR_MENU_KEY,
                False,
            ),
            (
                _pad_row("   [+] / [-] : Aumenta / diminuisce navi a schermo"),
                COLOR_MENU_KEY,
                False,
            ),
            (
                _pad_row("   [G] / [N] : Forza modalita' Giorno / Notte"),
                COLOR_MENU_KEY,
                False,
            ),
            (
                _pad_row("   [T]       : Tema Auto / Light / Dark"),
                COLOR_MENU_KEY,
                False,
            ),
            (
                _pad_row("   [H]       : Toggle HUD (Auto / Big Clock / Compatto)"),
                COLOR_MENU_KEY,
                False,
            ),
            (
                _pad_row("   [F2]/[F3]: Refresh -/+ 5 FPS (limiti 5-120)"),
                COLOR_MENU_KEY,
                False,
            ),
            (
                _pad_row("   [M]/[Esc] : Chiudi questo menu'"),
                COLOR_MENU_KEY,
                False,
            ),
            (
                _pad_row("   [Q]       : Esci dal programma"),
                COLOR_MENU_KEY,
                False,
            ),
            (border_h, COLOR_MENU_BORDER, True),
        ]

        box_h = len(rows)
        start_x = max(0, (self.width - box_w) // 2)
        start_y = max(1, (self.height - box_h) // 2)

        for idx, (line_str, fg_col, is_bold) in enumerate(rows):
            ry = start_y + idx
            if ry >= self.height:
                break
            renderer.draw_text(
                line_str,
                start_x,
                ry,
                fg_col,
                bg_rgb=COLOR_MENU_BG,
                bold=is_bold,
                transparent=False,
            )

    def handle_key(self, key: int) -> bool:
        """
        Processa un singolo codice tasto.
        Restituisce False se l'utente ha richiesto l'uscita dal programma ([Q] o [Esc]),
        altrimenti True.
        """
        if self.handle_refresh_key(key):
            return True
        if key in (ord("m"), ord("M")):
            self.toggle_menu()
            return True
        if key == Screen.KEY_ESCAPE:
            if self.menu_open:
                self.menu_open = False
                return True
            return False
        if key in (ord("q"), ord("Q")):
            return False
        if key == 32 or key == ord(" "):
            if not self.menu_open:
                self.force_salvo()
            return True
        if key in (ord("w"), ord("W")):
            self.weather_state.cycle_weather()
            return True
        if key in (ord("+"), ord("=")):
            self.adjust_max_ships(1)
            return True
        if key in (ord("-"), ord("_")):
            self.adjust_max_ships(-1)
            return True
        if key in (ord("g"), ord("G")):
            self.weather_state.force_day()
            return True
        if key in (ord("n"), ord("N")):
            self.weather_state.force_night()
            return True
        if key in (ord("t"), ord("T")):
            self.weather_state.cycle_appearance_mode()
            return True
        if key in (ord("h"), ord("H")):
            self.cycle_hud_mode()
            return True
        return True

    def draw(self, renderer: Renderer) -> None:
        """
        Disegna l'intera scena nell'ordine rigoroso di Z-index a ogni frame:
        1. Cielo, stelle, luna/sole, nuvole e GABBIANI (sfondo).
        2. Mare di fondo, PESCI e tutte le onde dietro le navi.
        3. NAVI e proiettili/fumo in primo piano.
        4. Header superiore (Top Bar compatta + Big HUD su schermi grandi).
        5. Menù modale in sovraimpressione se attivo.
        """
        snap = self.weather_state.snapshot()
        renderer.flash_intensity = self.weather_fx.flash_intensity

        # 1. Cielo, stelle, luna/sole, nuvole e GABBIANI (sfondo)
        renderer.set_wave_profile(self.sea.get_surface_profile())
        renderer.draw_background(snap.condition, self.sea.base_sea_y, is_day=snap.is_day)
        self.weather_fx.draw(renderer, self.sea.base_sea_y, is_day=snap.is_day)

        # 2. Mare di fondo e PESCI (sotto il livello del mare)
        self.sea.draw_subsurface_volume(renderer, is_day=snap.is_day)
        self.sea.draw_perspective_wave_tracks(renderer, is_day=snap.is_day)
        self.sea.draw_surface_crests(renderer, is_day=snap.is_day)

        # 3. NAVI e proiettili/fumo (primo piano, ben visibili sopra la linea di galleggiamento)
        for ship in self.ships:
            ship.draw(renderer, self.sea, is_day=snap.is_day)

        for proj in self.projectiles:
            proj.draw(renderer)

        for cp in self.combat_particles:
            cp.draw(renderer)

        for imp in self.impacts:
            ix = int(round(imp.x - len(imp.text) * 0.5))
            iy = int(round(imp.y))
            if imp.is_hit:
                renderer.draw_text(
                    f" {imp.text} ",
                    ix - 1,
                    iy,
                    (255, 255, 255),
                    bg_rgb=(205, 30, 0),
                    bold=True,
                    transparent=False,
                )
            else:
                renderer.draw_text(
                    imp.text,
                    ix,
                    iy,
                    COLOR_WAVE_CREST,
                    bold=True,
                    transparent=True,
                )

        # 4. HUD superiore (Top Bar compatta o Big HUD responsive)
        self._draw_hud(renderer, snap)

        # 5. Menù modale in sovraimpressione se aperto ([M])
        if self.menu_open:
            self._draw_menu_overlay(renderer, snap)


def _drain_keyboard_events(screen: Screen) -> List[int]:
    """Drena tutti gli eventi di input in coda nel frame corrente in modo non bloccante."""
    keys: List[int] = []
    while True:
        ev = screen.get_event() if hasattr(screen, "get_event") else None
        if ev is None:
            key = screen.get_key() if hasattr(screen, "get_key") else None
            if key is None:
                break
            keys.append(int(key))
        elif isinstance(ev, KeyboardEvent):
            keys.append(int(ev.key_code))
        elif isinstance(ev, int):
            keys.append(ev)
    return keys


def run_asciimatics_loop(
    weather_state: WeatherState,
    fps: int,
    max_ships: int,
) -> None:
    """
    Avvia e gestisce il game loop principale su asciimatics.screen.Screen,
    intercettando il ridimensionamento della finestra (SIGWINCH) senza perdere lo stato.
    """
    world: Optional[NavalBattleWorld] = None

    def _screen_main(screen: Screen) -> None:
        nonlocal world
        if world is None:
            world = NavalBattleWorld(
                screen.width,
                screen.height,
                weather_state=weather_state,
                max_ships=max_ships,
                target_fps=fps,
            )
        else:
            world.resize(screen.width, screen.height)

        renderer = Renderer(screen)
        last_time = time.monotonic()

        while True:
            if screen.has_resized():
                return

            start_time = time.monotonic()
            raw_dt = max(0.001, start_time - last_time)
            frame_budget = 1.0 / max(1, world.target_fps)
            dt = min(max(0.1, frame_budget), raw_dt)
            last_time = start_time
            world.current_fps = 0.85 * world.current_fps + 0.15 * min(240.0, 1.0 / raw_dt)

            for key in _drain_keyboard_events(screen):
                if not world.handle_key(key):
                    raise StopIteration

            world.update(dt)
            world.draw(renderer)
            screen.refresh()

            elapsed = time.monotonic() - start_time
            sleep_time = (1.0 / max(1, world.target_fps)) - elapsed
            if sleep_time > 0.0:
                time.sleep(sleep_time)

    while True:
        try:
            Screen.wrapper(_screen_main, catch_interrupt=True)
        except StopIteration:
            break
        except KeyboardInterrupt:
            break
