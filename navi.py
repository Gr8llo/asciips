#!/usr/bin/env python3
"""
navi.py - Entry point CLI per AsciiShips.
Gestisce i parametri da riga di comando (inclusa forzatura meteo e giorno/notte),
avvia il thread demone per Open-Meteo e lancia il game loop TUI basato su asciimatics.
"""

from __future__ import annotations
import argparse
import sys
from typing import Optional, Sequence

from config import (
    DEFAULT_CITY,
    DEFAULT_FPS,
    DEFAULT_MAX_SHIPS,
    MAX_FPS,
    MIN_FPS,
    TimeOfDay,
    WeatherCondition,
)
from engine.loop import run_asciimatics_loop
from engine.weather_thread import WeatherPollerThread, WeatherState


def _normalize_time_choice(val: str) -> TimeOfDay:
    """Converte l'argomento CLI (day/night o giorno/notte) nell'enum TimeOfDay."""
    v = val.strip().lower()
    if v in ("day", "giorno"):
        return TimeOfDay.DAY
    if v in ("night", "notte"):
        return TimeOfDay.NIGHT
    raise argparse.ArgumentTypeError(
        f"Valore non valido '{val}'. Usa: day, night, giorno, notte."
    )


def _normalize_weather_choice(val: str) -> str:
    """Mantiene `storm` come alias storico di `thunderstorm`."""
    normalized = val.strip().lower()
    return (
        WeatherCondition.THUNDERSTORM.value
        if normalized == "storm"
        else normalized
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Analizza gli argomenti CLI secondo le specifiche del PRD."""
    parser = argparse.ArgumentParser(
        prog="navi.py",
        description="AsciiShips - Battaglia navale procedurale TUI con meteo Open-Meteo in tempo reale.",
    )
    parser.add_argument(
        "--city",
        type=str,
        default=DEFAULT_CITY,
        help=f'Nome della città per il meteo in tempo reale (default: "{DEFAULT_CITY}").',
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help=f"Frame rate di esecuzione (default: {DEFAULT_FPS}).",
    )
    parser.add_argument(
        "--max-ships",
        type=int,
        default=DEFAULT_MAX_SHIPS,
        help=f"Numero massimo di navi contemporanee a schermo (default: {DEFAULT_MAX_SHIPS}).",
    )
    parser.add_argument(
        "--force-weather",
        type=_normalize_weather_choice,
        choices=[c.value for c in WeatherCondition] + ["storm"],
        default=None,
        help="Forza una condizione meteo di debug senza dipendere dalla rete.",
    )

    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument(
        "--force-time",
        type=_normalize_time_choice,
        default=None,
        metavar="{day,night,giorno,notte}",
        help="Forza la modalità diurna (day/giorno) o notturna (night/notte).",
    )
    time_group.add_argument(
        "--day",
        action="store_const",
        const=TimeOfDay.DAY,
        dest="force_time",
        help="Scorciatoia per forzare la modalità GIORNO.",
    )
    time_group.add_argument(
        "--night",
        action="store_const",
        const=TimeOfDay.NIGHT,
        dest="force_time",
        help="Scorciatoia per forzare la modalità NOTTE.",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Funzione principale di avvio di AsciiShips."""
    args = parse_args(argv)

    fps = max(MIN_FPS, min(MAX_FPS, args.fps))
    max_ships = max(2, min(10, args.max_ships))
    forced_cond = (
        WeatherCondition(args.force_weather)
        if args.force_weather is not None
        else None
    )
    forced_time: Optional[TimeOfDay] = args.force_time

    weather_state = WeatherState(
        city=args.city,
        forced_condition=forced_cond,
        forced_time=forced_time,
    )

    # Avvia il thread demone per Open-Meteo (permette il ritorno al meteo LIVE col tasto W)
    poller: Optional[WeatherPollerThread] = WeatherPollerThread(
        state=weather_state, city=args.city
    )
    poller.start()

    try:
        run_asciimatics_loop(
            weather_state=weather_state,
            fps=fps,
            max_ships=max_ships,
        )
    finally:
        if poller is not None:
            poller.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
