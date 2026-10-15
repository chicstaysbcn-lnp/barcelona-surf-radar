"""Motor de pronostico y ranking. Sin scraping: solo APIs documentadas."""
from __future__ import annotations

import json
import math
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Madrid")
WEATHER_FIELDS = "wind_speed_10m,wind_direction_10m,wind_gusts_10m,temperature_2m,precipitation,cloud_cover,weather_code,is_day"
WAVE_FIELDS = "wave_height,wave_direction,wave_period,swell_wave_height,swell_wave_direction,swell_wave_period"
SEA_FIELDS = "sea_level_height_msl,sea_surface_temperature"

# Una sola fuente de verdad para los perfiles de las siete playas.
# Las direcciones son azimuts *desde los que llegan* olas y viento.
# Las coordenadas y la malla marina NO describen un pico preciso.
PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "spot_profiles.json"
PROFILE_DATA = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

def load_spots(source):
    spots = []
    ids = set()
    for item in source["spots"]:
        assert item["id"] not in ids, "Duplicado en perfiles de playa"
        assert item["classification"] in ("documentado", "provisional")
        assert 0 <= item["ideal_swell_deg"] < 360
        assert 0 <= item["ideal_offshore_deg"] < 360
        ids.add(item["id"])
        spots.append({
            "id": item["id"], "name": item["name"],
            "lat": item["lat"], "lon": item["lon"],
            "swell_dir": item["ideal_swell_deg"],
            "offshore_dir": item["ideal_offshore_deg"],
            "swell_tolerance_deg": item["swell_tolerance_deg"],
            "exposure": item["exposure_factor"],
            "profile_status": item["classification"],
        })
    return spots

SPOTS = load_spots(PROFILE_DATA)

# Valores del perfil: rango de altura orientativo, no tamano real de ola en orilla.
PROFILES = {
    "principiante": (0.40, .70, 1.10),
    "intermedio": (.65, .95, 1.85),
    "avanzado": (.80, 1.20, 2.25),
}
MODELS = [
    ("weather", "AROME (Météo-France)", "https://api.open-meteo.com/v1/meteofrance", "arome_france"),
    ("weather", "ICON-EU", "https://api.open-meteo.com/v1/forecast", "icon_eu"),
    ("weather", "GFS", "https://api.open-meteo.com/v1/forecast", "gfs_seamless"),
    ("marine", "Météo-France Wave", "https://marine-api.open-meteo.com/v1/marine", "meteofrance_wave"),
    ("marine", "ECMWF WAM", "https://marine-api.open-meteo.com/v1/marine", "ecmwf_wam"),
    ("marine", "DWD EWAM", "https://marine-api.open-meteo.com/v1/marine", "dwd_ewam"),
    ("marine", "GFS Wave", "https://marine-api.open-meteo.com/v1/marine", "ncep_gfswave016"),
    ("sea", "Nivel marino", "https://marine-api.open-meteo.com/v1/marine", "best_match"),
]


def iso_utc(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def round_or_none(value, places=1):
    if value is None or not isinstance(value, (float, int)) or not math.isfinite(value):
        return None
    return round(float(value), places)


def circular_mean(angles, weights=None):
    values = [(a, (weights[i] if weights else 1.0)) for i, a in enumerate(angles) if a is not None]
    if not values:
        return None
    x = sum(math.cos(math.radians(a)) * w for a, w in values)
    y = sum(math.sin(math.radians(a)) * w for a, w in values)
    return (math.degrees(math.atan2(y, x)) + 360) % 360 if abs(x) + abs(y) > 1e-9 else None


def circular_distance(a, b):
    return abs((a - b + 180) % 360 - 180)


def clip(value, lo=0, hi=1):
    return max(lo, min(hi, value))


def height_quality(height, profile):
    low, ideal, high = PROFILES[profile]
    if height <= 0:
        return 0
    if height < low:
        return clip((height - .12) / (low - .12)) * .7
    if height <= ideal:
        return .7 + .3 * (height - low) / (ideal - low)
    if height <= high:
        return 1 - .35 * (height - ideal) / (high - ideal)
    return clip(.65 - (height - high) / 1.2)


def score_hour(spot, data, profile="intermedio"):
    """Heuristica 0..100: sesgo deliberadamente prudente; nunca sustituye ver el mar."""
    wave = data.get("wave_m")
    wind = data.get("wind_kn")
    if wave is None or wind is None:
        return 0
    if data.get("is_day") is False:
        return 0
    period = data.get("period_s") or 0
    swell = data.get("swell_m")
    sway = data.get("swell_dir") if data.get("swell_dir") is not None else data.get("wave_dir")
    # Cada playa tiene un sector de swell individual. Las tres sin guias
    # especificas tienen tolerancia mayor (hipotesis, no una medicion).
    direction_quality = clip(1 - circular_distance(sway, spot["swell_dir"]) /
                             spot.get("swell_tolerance_deg", 105)) if sway is not None else .45
    # El factor de exposicion permanece neutro (=1) hasta disponer de
    # observaciones locales; no se inventan factores de amplificacion.
    h_quality = height_quality(wave * spot["exposure"], profile)
    p_quality = clip((period - 3.6) / 4.2)
    wind_dir = data.get("wind_dir")
    offshore = (1 + math.cos(math.radians(circular_distance(wind_dir, spot["offshore_dir"])))) / 2 if wind_dir is not None else .5
    calm_bonus = 1 if wind <= 4 else clip(1 - (wind - 4) / 16)
    wind_quality = .65 * calm_bonus + .35 * offshore if wind <= 8 else clip(.35 * calm_bonus + .65 * offshore - clip((wind - 13) / 18) * .55)
    swell_q = clip((swell or 0) / max(.2, wave)) if swell is not None else .5
    result = 100 * (.37 * h_quality + .22 * p_quality + .17 * wind_quality + .16 * direction_quality + .08 * swell_q)
    # Sin oleaje surfable no se compensa con tiempo soleado/viento favorable.
    if wave < .30 or period < 4.2 or direction_quality < .18 or (sway is not None and circular_distance(sway, spot["swell_dir"]) > 105):
        result = min(result, 46)
    if data.get("is_day") is None:
        result = min(result, 60)
    if (data.get("gust_kn") or 0) > 27 or (wave > 2.1 if profile != "avanzado" else wave > 2.6) or data.get("weather_code") in (95, 96, 99):
        result = min(result, 22)
    # Divergencia entre modelos, y fuente unica, reducen la fiabilidad.
    agreement = data.get("wave_spread_m")
    if agreement is not None:
        result -= min(16, agreement * 17)
    if (data.get("marine_n") or 0) < 2:
        result = min(result, 60)
    if (data.get("weather_n") or 0) < 1:
        result = 0
    return int(round(clip(result, 0, 100)))


def spot_fit(spot, swell_dir, wind_dir, wind_kn):
    """Etiquetas descriptivas; NO certifican que una rompiente funcione."""
    if swell_dir is None:
        swell = "sin dato"
    else:
        delta = circular_distance(swell_dir, spot["swell_dir"])
        swell = "favorable" if delta <= 30 else "parcial" if delta <= 75 else "desfavorable"
    if wind_dir is None or wind_kn is None:
        wind = "sin dato"
    elif wind_kn <= 3:
        wind = "flojo / calma"
    else:
        delta = circular_distance(wind_dir, spot["offshore_dir"])
        wind = "offshore probable" if delta <= 40 else "cruzado" if delta <= 125 else "onshore probable"
    return swell, wind


def get_json(url, params=None, *, payload=None, retries=1):
    body = json.dumps(payload).encode() if payload else None
    if params:
        url += "?" + urlencode(params)
    request = Request(url, data=body, headers={"User-Agent": "BarcelonaSurfRadar/1.0 personal project", "Accept": "application/json", **({"Content-Type": "application/json"} if body else {})}, method="POST" if body else "GET")
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=18) as response:
                return json.load(response)
        except (HTTPError, URLError, OSError, ValueError, TimeoutError):
            if attempt < retries:
                time.sleep(1 + attempt)
    return None


def open_meteo_fetch(spot, definition):
    kind, name, endpoint, model = definition
    fields = {"weather": WEATHER_FIELDS, "marine": WAVE_FIELDS, "sea": SEA_FIELDS}[kind]
    args = {
        "latitude": spot["lat"], "longitude": spot["lon"],
        "hourly": fields, "models": model, "forecast_days": 4,
        "timezone": "UTC", "timeformat": "iso8601",
    }
    if kind in ("marine", "sea"):
        args["cell_selection"] = "sea"
    else:
        args["wind_speed_unit"] = "kn"
    # El mismo codigo funciona con la API de Open-Meteo comercial.
    api_key = os.getenv("OPEN_METEO_API_KEY", "").strip()
    if api_key:
        args["apikey"] = api_key
        endpoint = endpoint.replace("api.open-meteo.com", "customer-api.open-meteo.com").replace("marine-api.open-meteo.com", "customer-marine-api.open-meteo.com")
    response = get_json(endpoint, args)
    if not isinstance(response, dict) or not isinstance(response.get("hourly"), dict):
        return kind, name, {}
    hourly = response["hourly"]
    result = {}
    for i, stamp in enumerate(hourly.get("time", [])):
        try:
            moment = iso_utc(stamp + ("Z" if "+" not in stamp and not stamp.endswith("Z") else ""))
        except (TypeError, ValueError):
            continue
        result[moment] = {key: (values[i] if isinstance(values, list) and i < len(values) else None) for key, values in hourly.items() if key != "time"}
    return kind, name, result


def windy_fetch(spot, model, kind):
    """Adaptador opcional. NUNCA utilizar claves de testing para alertas reales."""
    key = os.getenv("WINDY_API_KEY", "").strip()
    # La API de testing altera deliberadamente los pronosticos.
    # Confirmacion explicita para evitar enviar avisos basados en testing.
    if os.getenv("WINDY_PRODUCTION", "") != "1":
        return None
    if not key:
        return None
    params = ["wind", "windGust", "temp", "precip"] if kind == "weather" else ["waves", "swell1"]
    response = get_json("https://api.windy.com/api/point-forecast/v2", payload={
        "lat": spot["lat"], "lon": spot["lon"], "model": model,
        "parameters": params, "levels": ["surface"], "key": key,
    })
    if not isinstance(response, dict) or not isinstance(response.get("ts"), list):
        return None
    name = "Windy AROME" if kind == "weather" else "Windy GFS Wave"
    result = {}
    for index, epoch in enumerate(response["ts"]):
        time_str = datetime.fromtimestamp(epoch / 1000, timezone.utc).isoformat().replace("+00:00", "Z")
        def item(k):
            series = response.get(k, [])
            return series[index] if isinstance(series, list) and index < len(series) else None
        if kind == "weather":
            u, v = item("wind_u-surface"), item("wind_v-surface")
            speed = math.hypot(u, v) * 1.943844 if u is not None and v is not None else None
            direction = (math.degrees(math.atan2(-u, -v)) + 360) % 360 if speed is not None else None
            r = {"wind_speed_10m": speed, "wind_direction_10m": direction, "wind_gusts_10m": (item("gust-surface") or 0) * 1.943844,
                 "temperature_2m": item("temp-surface"), "precipitation": item("past3hprecip-surface"), "is_day": None}
            if r["temperature_2m"] is not None:
                r["temperature_2m"] -= 273.15  # Windy temperatura en K
        else:
            r = {"wave_height": item("waves_height-surface"), "wave_direction": item("waves_direction-surface"), "wave_period": item("waves_period-surface"),
                 "swell_wave_height": item("swell1_height-surface"), "swell_wave_direction": item("swell1_direction-surface"), "swell_wave_period": item("swell1_period-surface")}
        result[time_str] = r
    return kind, name, result


def avg(values):
    v = [float(item) for item in values if isinstance(item, (int, float)) and math.isfinite(item)]
    return statistics.mean(v) if v else None


def fold_hour(stamp, results, spot):
    by_kind = {kind: [(name, hours[stamp]) for k, name, hours in results if k == kind and stamp in hours] for kind in ("weather", "marine", "sea")}
    weather, marine, sea = by_kind["weather"], by_kind["marine"], by_kind["sea"]
    # Los datos solo cuentan como fuente util cuando tienen variable relevante.
    ww = [(n, d) for n, d in weather if d.get("wind_speed_10m") is not None]
    mm = [(n, d) for n, d in marine if d.get("wave_height") is not None]
    baseline = sea[0][1] if sea else {}
    wave_v = [d.get("wave_height") for _, d in mm]
    wind_v = [d.get("wind_speed_10m") for _, d in ww]
    # AROME puede no devolver cobertura, no sustituimos por ARPEGE silenciosamente.
    avg_wave = avg(wave_v)
    avg_wind = avg(wind_v)
    wave_dir = circular_mean([d.get("wave_direction") for _, d in mm])
    swell_dir = circular_mean([d.get("swell_wave_direction") for _, d in mm])
    wind_dir = circular_mean([d.get("wind_direction_10m") for _, d in ww])
    model_entries = []
    for name, item in mm:
        model_entries.append({"name": name, "type": "olas", "wave_m": round_or_none(item.get("wave_height"), 2), "period_s": round_or_none(item.get("wave_period")),
                              "swell_m": round_or_none(item.get("swell_wave_height"), 2)})
    for name, item in ww:
        model_entries.append({"name": name, "type": "viento", "wind_kn": round_or_none(item.get("wind_speed_10m")), "wind_dir": round_or_none(item.get("wind_direction_10m"), 0)})
    spread_wave = max(wave_v) - min(wave_v) if len(wave_v) >= 2 else None
    spread_wind = max(wind_v) - min(wind_v) if len(wind_v) >= 2 else None
    day_values = [d.get("is_day") for _, d in ww if d.get("is_day") is not None]
    # Preferencia temporal is_day determinista de cualquier modelo con valor.
    result = {
        "time": stamp, "wave_m": round_or_none(avg_wave, 2), "wave_dir": round_or_none(wave_dir, 0),
        "period_s": round_or_none(avg([d.get("wave_period") for _, d in mm])),
        "swell_m": round_or_none(avg([d.get("swell_wave_height") for _, d in mm]), 2),
        "swell_dir": round_or_none(swell_dir, 0),
        "swell_period_s": round_or_none(avg([d.get("swell_wave_period") for _, d in mm])),
        "wind_kn": round_or_none(avg_wind), "wind_dir": round_or_none(wind_dir, 0),
        "gust_kn": round_or_none(avg([d.get("wind_gusts_10m") for _, d in ww])),
        "temp_c": round_or_none(avg([d.get("temperature_2m") for _, d in ww])),
        "rain_mm": round_or_none(avg([d.get("precipitation") for _, d in ww])),
        "cloud_pct": round_or_none(avg([d.get("cloud_cover") for _, d in ww]), 0),
        "weather_code": next((d.get("weather_code") for _, d in ww if d.get("weather_code") is not None), None),
        "is_day": bool(day_values[0]) if day_values else None,
        "sea_level_m": round_or_none(baseline.get("sea_level_height_msl"), 2),
        "sea_temp_c": round_or_none(baseline.get("sea_surface_temperature")),
        "marine_n": len(mm), "weather_n": len(ww),
        "wave_spread_m": round_or_none(spread_wave, 2), "wind_spread_kn": round_or_none(spread_wind),
        "models": model_entries,
    }
    result["scores"] = {profile: score_hour(spot, result, profile) for profile in PROFILES}
    result["swell_fit"], result["wind_fit"] = spot_fit(spot, result["swell_dir"], result["wind_dir"], result["wind_kn"])
    if not mm or not ww:
        result["confidence"] = "sin datos"
    elif len(mm) >= 3 and len(ww) >= 2 and (spread_wave is None or spread_wave <= .25) and (spread_wind is None or spread_wind <= 5):
        result["confidence"] = "alta"
    elif len(mm) >= 2 and (spread_wave is None or spread_wave <= .5):
        result["confidence"] = "media"
    else:
        result["confidence"] = "baja"
    result["danger"] = (result.get("gust_kn") or 0) > 27 or (result.get("wave_m") or 0) > 2.1 or result["weather_code"] in (95, 96, 99)
    return result


def nearest_tide(hour, next_hour):
    first = hour.get("sea_level_m")
    second = next_hour.get("sea_level_m") if next_hour else None
    if first is None or second is None:
        return "sin dato"
    delta = second - first
    return "subiendo" if delta > .015 else "bajando" if delta < -.015 else "estable"


def forecast_spot(spot, now):
    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(open_meteo_fetch, spot, definition) for definition in MODELS]
        if os.getenv("WINDY_API_KEY", "").strip() and os.getenv("WINDY_PRODUCTION", "") == "1":
            futures.extend([executor.submit(windy_fetch, spot, "arome", "weather"), executor.submit(windy_fetch, spot, "gfsWave", "marine")])
        for future in as_completed(futures):
            try:
                res = future.result()
                if res and res[2]:
                    results.append(res)
            except Exception as ex:
                errors.append(type(ex).__name__)
    if not any(k == "marine" for k, _, _ in results):
        # Ultimo intento con combinacion automatica valida en toda la zona.
        fallback = open_meteo_fetch(spot, ("marine", "Marine best match", "https://marine-api.open-meteo.com/v1/marine", "best_match"))
        if fallback[2]:
            results.append(fallback)
    if not any(k == "weather" for k, _, _ in results):
        fallback = open_meteo_fetch(spot, ("weather", "Weather best match", "https://api.open-meteo.com/v1/forecast", "best_match"))
        if fallback[2]:
            results.append(fallback)
    timestamps = sorted({t for kind, name, hours in results if kind in ("marine", "weather") for t in hours
                         if datetime.fromisoformat(t.replace("Z", "+00:00")) >= now - timedelta(hours=1)})
    hours = [fold_hour(t, results, spot) for t in timestamps[:100]]
    for index, hour in enumerate(hours):
        hour["tide_trend"] = nearest_tide(hour, hours[index + 1] if index + 1 < len(hours) else None)
    return {"id": spot["id"], "name": spot["name"], "lat": spot["lat"], "lon": spot["lon"],
            "ideal_swell_dir": spot["swell_dir"], "ideal_offshore_dir": spot["offshore_dir"],
            "profile_status": spot["profile_status"], "hours": hours,
            "source_names": sorted({name for kind, name, data in results if any(
                isinstance(value, dict) and value.get({"marine": "wave_height", "weather": "wind_speed_10m", "sea": "sea_level_height_msl"}[kind]) is not None
                for value in data.values())}), "errors": errors}


def generate_snapshot(now=None):
    now = now or datetime.now(timezone.utc)
    spots = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(forecast_spot, spot, now): spot for spot in SPOTS}
        for future in as_completed(futures):
            spot = futures[future]
            try:
                spots.append(future.result())
            except Exception as exc:
                spots.append({"id": spot["id"], "name": spot["name"], "lat": spot["lat"], "lon": spot["lon"], "hours": [], "errors": [str(exc)[:90]]})
    spots.sort(key=lambda s: next(i for i, x in enumerate(SPOTS) if x["id"] == s["id"]))
    valid_spots = sum(any(h["marine_n"] and h["weather_n"] for h in spot["hours"]) for spot in spots)
    if valid_spots == 0:
        raise RuntimeError("Ninguna playa tiene datos marinos y meteorologicos. No publicar una prevision inventada.")
    return {"status": "ok" if valid_spots == len(SPOTS) else "partial", "generated_at": now.isoformat().replace("+00:00", "Z"),
            "spot_profile_version": PROFILE_DATA["version"],
            "timezone": "Europe/Madrid", "fresh_hours": 8, "alert_threshold": max(65, min(94, int(os.getenv("ALERT_THRESHOLD", "76")))), "spots_available": valid_spots, "spots_expected": len(SPOTS),
            "method": "Media de modelos y scoring individual por perfil de playa. Azimuts documentados o provisionales; sin modelo calibrado de batimetria, refraccion ni altura de rompiente.",
            "sources": {"windy_api": bool(os.getenv("WINDY_API_KEY", "").strip() and os.getenv("WINDY_PRODUCTION", "") == "1"), "windguru": "enlace externo (no automatizado)",
                        "surf_forecast": "enlace externo (no automatizado)", "open_meteo": True},
            "spots": spots}
