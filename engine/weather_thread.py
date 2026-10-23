"""
engine/weather_thread.py - Thread demone asincrono per il recupero del meteo da Open-Meteo.
Esegue geocodifica della città e polling periodico del meteo corrente (incluso giorno/notte)
senza bloccare il main thread.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple

from config import (
    AppearanceMode,
    DEFAULT_CITY,
    FORECAST_API_URL,
    GEOCODING_API_URL,
    HTTP_TIMEOUT_SEC,
    TimeOfDay,
    WEATHER_POLL_INTERVAL_SEC,
    WeatherCondition,
    map_wmo_to_condition,
)


def _default_time_of_day_from_clock() -> TimeOfDay:
    """Determina giorno/notte in base all'ora locale di sistema."""
    hour = datetime.now().hour
    return TimeOfDay.DAY if 7 <= hour < 19 else TimeOfDay.NIGHT


@dataclass
class WeatherSnapshot:
    """Rappresentazione immutabile dello stato meteo per il main thread."""
    city: str
    condition: WeatherCondition
    time_of_day: TimeOfDay
    wmo_code: int
    temperature_c: Optional[float]
    apparent_temperature_c: Optional[float]
    relative_humidity_pct: Optional[float]
    wind_speed_kmh: float
    is_forced: bool
    is_time_forced: bool
    appearance_mode: AppearanceMode
    status_note: str
    last_updated: float
    city_local_time: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @property
    def is_day(self) -> bool:
        """Restituisce True se la scena è in modalità diurna."""
        return self.time_of_day == TimeOfDay.DAY


class WeatherState:
    """
    Struttura dati condivisa e thread-safe per lo stato meteorologico e la fascia oraria (giorno/notte).
    Permette al thread di background di aggiornare i dati e al game loop di leggerli
    in modo atomico senza lock prolungati.
    """

    def __init__(
        self,
        city: str = DEFAULT_CITY,
        forced_condition: Optional[WeatherCondition] = None,
        forced_time: Optional[TimeOfDay] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._city: str = city
        self._forced_condition: Optional[WeatherCondition] = forced_condition
        self._forced_time: Optional[TimeOfDay] = forced_time
        self._condition: WeatherCondition = (
            forced_condition if forced_condition is not None else WeatherCondition.CLEAR
        )
        self._time_of_day: TimeOfDay = (
            forced_time if forced_time is not None else _default_time_of_day_from_clock()
        )
        self._live_time_of_day: TimeOfDay = self._time_of_day
        self._appearance_mode = (
            AppearanceMode.LIGHT
            if forced_time == TimeOfDay.DAY
            else AppearanceMode.DARK
            if forced_time == TimeOfDay.NIGHT
            else AppearanceMode.AUTO
        )
        self._wmo_code: int = self._default_wmo_for_condition(self._condition)
        self._live_wmo_code: int = self._wmo_code
        self._has_live_data: bool = False
        self._temperature_c: Optional[float] = None
        self._apparent_temperature_c: Optional[float] = None
        self._relative_humidity_pct: Optional[float] = None
        self._wind_speed_kmh: float = 10.0
        self._status_note: str = (
            f"FORCED ({self._condition.value.upper()})"
            if forced_condition is not None
            else "In attesa di Open-Meteo..."
        )
        self._last_updated: float = 0.0
        self._city_local_time: Optional[datetime] = None
        self._city_time_monotonic: Optional[float] = None
        self._latitude: Optional[float] = None
        self._longitude: Optional[float] = None

    @staticmethod
    def _default_wmo_for_condition(condition: WeatherCondition) -> int:
        mapping = {
            WeatherCondition.CLEAR: 0,
            WeatherCondition.PARTLY_CLOUDY: 1,
            WeatherCondition.OVERCAST: 3,
            WeatherCondition.CLOUDY: 2,
            WeatherCondition.DRIZZLE: 51,
            WeatherCondition.RAIN: 61,
            WeatherCondition.RAIN_SHOWERS: 80,
            WeatherCondition.SNOW: 73,
            WeatherCondition.SNOW_GRAINS: 77,
            WeatherCondition.FOG: 45,
            WeatherCondition.THUNDERSTORM: 95,
            WeatherCondition.THUNDERSTORM_HAIL: 96,
        }
        return mapping.get(condition, 0)

    def cycle_appearance_mode(self) -> AppearanceMode:
        """Cicla tra automatico, tema chiaro e tema scuro."""
        cycle_order = (
            AppearanceMode.AUTO,
            AppearanceMode.LIGHT,
            AppearanceMode.DARK,
        )
        with self._lock:
            idx = cycle_order.index(self._appearance_mode)
            self._appearance_mode = cycle_order[(idx + 1) % len(cycle_order)]
            if self._appearance_mode == AppearanceMode.AUTO:
                self._forced_time = None
                self._time_of_day = self._live_time_of_day
            else:
                self._time_of_day = (
                    TimeOfDay.DAY
                    if self._appearance_mode == AppearanceMode.LIGHT
                    else TimeOfDay.NIGHT
                )
                self._forced_time = self._time_of_day
            return self._appearance_mode

    def toggle_time_of_day(self) -> TimeOfDay:
        """Compatibilita' per i chiamanti storici del toggle giorno/notte."""
        with self._lock:
            self._time_of_day = (
                TimeOfDay.NIGHT
                if self._time_of_day == TimeOfDay.DAY
                else TimeOfDay.DAY
            )
            self._appearance_mode = (
                AppearanceMode.DARK
                if self._time_of_day == TimeOfDay.NIGHT
                else AppearanceMode.LIGHT
            )
            self._forced_time = self._time_of_day
            return self._time_of_day

    def cycle_weather(self) -> Optional[WeatherCondition]:
        """
        Cambia ciclicamente tutti i meteo forzati (tasto W), poi torna al meteo live.
        """
        cycle_order = [
            WeatherCondition.CLEAR,
            WeatherCondition.PARTLY_CLOUDY,
            WeatherCondition.OVERCAST,
            WeatherCondition.CLOUDY,
            WeatherCondition.DRIZZLE,
            WeatherCondition.RAIN,
            WeatherCondition.RAIN_SHOWERS,
            WeatherCondition.SNOW,
            WeatherCondition.SNOW_GRAINS,
            WeatherCondition.FOG,
            WeatherCondition.THUNDERSTORM,
            WeatherCondition.THUNDERSTORM_HAIL,
            None,
        ]
        with self._lock:
            if self._forced_condition is None:
                next_forced: Optional[WeatherCondition] = WeatherCondition.CLEAR
            else:
                try:
                    idx = cycle_order.index(self._forced_condition)
                    next_forced = cycle_order[(idx + 1) % len(cycle_order)]
                except ValueError:
                    next_forced = WeatherCondition.CLEAR

            self._forced_condition = next_forced
            if next_forced is not None:
                self._condition = next_forced
                self._wmo_code = self._default_wmo_for_condition(next_forced)
                self._status_note = f"FORCED ({next_forced.value.upper()})"
            else:
                self._wmo_code = self._live_wmo_code
                self._condition = map_wmo_to_condition(
                    self._live_wmo_code,
                    is_day=self._live_time_of_day == TimeOfDay.DAY,
                )
                self._status_note = "LIVE" if self._has_live_data else "LIVE (API)"
            return self._forced_condition

    def update(
        self,
        *,
        city: Optional[str] = None,
        wmo_code: int,
        temperature_c: Optional[float],
        wind_speed_kmh: float,
        apparent_temperature_c: Optional[float] = None,
        relative_humidity_pct: Optional[float] = None,
        city_local_time: Optional[datetime] = None,
        is_day: Optional[bool] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        status_note: str = "LIVE",
    ) -> None:
        """Aggiorna lo stato meteo in modo thread-safe."""
        with self._lock:
            if city:
                self._city = city
            if latitude is not None:
                self._latitude = latitude
            if longitude is not None:
                self._longitude = longitude
            self._live_wmo_code = wmo_code
            self._has_live_data = True
            if is_day is not None:
                self._live_time_of_day = TimeOfDay.DAY if is_day else TimeOfDay.NIGHT
            if self._forced_condition is None:
                self._wmo_code = wmo_code
                self._condition = map_wmo_to_condition(wmo_code, is_day=is_day)
                self._status_note = status_note
            else:
                self._status_note = f"FORCED ({self._forced_condition.value.upper()})"
            if self._appearance_mode == AppearanceMode.AUTO and is_day is not None:
                self._time_of_day = self._live_time_of_day
            self._temperature_c = temperature_c
            self._apparent_temperature_c = apparent_temperature_c
            self._relative_humidity_pct = relative_humidity_pct
            self._wind_speed_kmh = wind_speed_kmh
            self._last_updated = time.time()
            if city_local_time is not None:
                self._city_local_time = city_local_time
                self._city_time_monotonic = time.monotonic()

    def set_error(self, note: str) -> None:
        """Registra un errore di rete mantenendo l'ultimo meteo valido."""
        with self._lock:
            self._status_note = note

    def snapshot(self) -> WeatherSnapshot:
        """Restituisce una copia atomica dello stato corrente."""
        with self._lock:
            return WeatherSnapshot(
                city=self._city,
                condition=self._condition,
                time_of_day=self._time_of_day,
                wmo_code=self._wmo_code,
                temperature_c=self._temperature_c,
                apparent_temperature_c=self._apparent_temperature_c,
                relative_humidity_pct=self._relative_humidity_pct,
                wind_speed_kmh=self._wind_speed_kmh,
                is_forced=self._forced_condition is not None,
                is_time_forced=self._appearance_mode != AppearanceMode.AUTO,
                appearance_mode=self._appearance_mode,
                status_note=self._status_note,
                last_updated=self._last_updated,
                city_local_time=(
                    self._city_local_time
                    + timedelta(
                        seconds=max(
                            0.0,
                            time.monotonic() - self._city_time_monotonic,
                        )
                    )
                    if self._city_local_time is not None
                    and self._city_time_monotonic is not None
                    else self._city_local_time
                ),
                latitude=self._latitude,
                longitude=self._longitude,
            )


class WeatherPollerThread(threading.Thread):
    """
    Thread demone che interroga le API Open-Meteo (geocoding + forecast)
    all'avvio e poi ogni 10 minuti (600 secondi).
    """

    def __init__(
        self,
        state: WeatherState,
        city: str = DEFAULT_CITY,
        poll_interval: int = WEATHER_POLL_INTERVAL_SEC,
    ) -> None:
        super().__init__(name="OpenMeteoPoller", daemon=True)
        self.state = state
        self.city_query = city
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._coords_cache: Optional[Tuple[float, float, str]] = None

    def stop(self) -> None:
        """Richiede l'arresto pulito del thread."""
        self._stop_event.set()

    def _http_get_json(self, url: str) -> dict:
        """Esegue una richiesta GET HTTP e restituisce il JSON decodificato."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AsciiShips/1.0 (Python urllib; TUI Naval Screensaver)"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)

    def _geocode_city(self, city_name: str) -> Tuple[float, float, str]:
        """Converte il nome della città in (latitudine, longitudine, nome_risolto)."""
        if self._coords_cache is not None:
            return self._coords_cache

        params = urllib.parse.urlencode(
            {"name": city_name, "count": 1, "language": "it", "format": "json"}
        )
        url = f"{GEOCODING_API_URL}?{params}"
        data = self._http_get_json(url)
        results = data.get("results")
        if not results:
            raise ValueError(f"Città non trovata: '{city_name}'")

        first = results[0]
        lat = float(first["latitude"])
        lon = float(first["longitude"])
        resolved_name = str(first.get("name", city_name))
        country = first.get("country_code", "")
        if country:
            resolved_name = f"{resolved_name} ({country})"

        self._coords_cache = (lat, lon, resolved_name)
        return self._coords_cache

    def _fetch_current_weather(
        self, lat: float, lon: float
    ) -> Tuple[int, Optional[float], Optional[float], Optional[float], float, Optional[bool], Optional[datetime]]:
        """Recupera condizioni correnti e orario locale da Open-Meteo."""
        params = urllib.parse.urlencode(
            {
                "latitude": f"{lat:.4f}",
                "longitude": f"{lon:.4f}",
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day",
                "timezone": "auto",
            }
        )
        url = f"{FORECAST_API_URL}?{params}"
        data = self._http_get_json(url)

        current = data.get("current", {})
        if not current and "current_weather" in data:
            cw = data["current_weather"]
            wmo_code = int(cw.get("weathercode", 0))
            temp = float(cw["temperature"]) if "temperature" in cw else None
            apparent = float(cw["apparent_temperature"]) if cw.get("apparent_temperature") is not None else None
            humidity = float(cw["relative_humidity_2m"]) if cw.get("relative_humidity_2m") is not None else None
            wind = float(cw.get("windspeed", 10.0))
            is_day_val = cw.get("is_day")
            is_day = bool(int(is_day_val)) if is_day_val is not None else None
            city_time = (
                datetime.fromisoformat(str(cw["time"]))
                if cw.get("time")
                else None
            )
            return wmo_code, temp, apparent, humidity, wind, is_day, city_time

        wmo_code = int(current.get("weather_code", 0))
        temp_val = current.get("temperature_2m")
        temp = float(temp_val) if temp_val is not None else None
        apparent_val = current.get("apparent_temperature")
        apparent = float(apparent_val) if apparent_val is not None else None
        humidity_val = current.get("relative_humidity_2m")
        humidity = float(humidity_val) if humidity_val is not None else None
        wind = float(current.get("wind_speed_10m", 10.0))
        is_day_val = current.get("is_day")
        is_day = bool(int(is_day_val)) if is_day_val is not None else None
        city_time = (
            datetime.fromisoformat(str(current["time"]))
            if current.get("time")
            else None
        )
        return wmo_code, temp, apparent, humidity, wind, is_day, city_time

    def fetch_once(self) -> None:
        """Esegue un singolo ciclo di geocodifica + recupero meteo."""
        try:
            lat, lon, resolved_city = self._geocode_city(self.city_query)
            (
                wmo_code,
                temp_c,
                apparent_temp_c,
                humidity_pct,
                wind_kmh,
                is_day,
                city_local_time,
            ) = self._fetch_current_weather(lat, lon)
            snap = self.state.snapshot()
            note = f"FORCED ({snap.condition.value.upper()})" if snap.is_forced else "LIVE"
            self.state.update(
                city=resolved_city,
                wmo_code=wmo_code,
                temperature_c=temp_c,
                apparent_temperature_c=apparent_temp_c,
                relative_humidity_pct=humidity_pct,
                wind_speed_kmh=wind_kmh,
                city_local_time=city_local_time,
                is_day=is_day,
                latitude=lat,
                longitude=lon,
                status_note=note,
            )
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as exc:
            snap = self.state.snapshot()
            if snap.is_forced:
                self.state.set_error(f"FORCED ({snap.condition.value.upper()}) [Offline]")
            else:
                self.state.set_error(f"Offline ({type(exc).__name__})")

    def run(self) -> None:
        """Ciclo principale del thread demone."""
        while not self._stop_event.is_set():
            self.fetch_once()
            if self._stop_event.wait(timeout=self.poll_interval):
                break
