"""Avisos de Telegram: solo sesiones confirmadas >=2 horas, una por fecha."""
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Madrid")


def sessions(snapshot, profile="intermedio", now=None):
    now = now or datetime.now(timezone.utc)
    candidates = []
    for spot in snapshot.get("spots", []):
        hrs = spot.get("hours", [])
        for h1, h2 in zip(hrs, hrs[1:]):
            t1 = datetime.fromisoformat(h1["time"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(h2["time"].replace("Z", "+00:00"))
            if t1 < now + timedelta(minutes=30) or t1 > now + timedelta(hours=42) or t2 - t1 != timedelta(hours=1):
                continue
            if not (h1.get("is_day") and h2.get("is_day")) or h1.get("danger") or h2.get("danger"):
                continue
            if min(h1.get("marine_n", 0), h2.get("marine_n", 0)) < 2:
                continue
            if min(h1.get("weather_n", 0), h2.get("weather_n", 0)) < 1:
                continue
            if min(h1.get("scores", {}).get(profile, 0), h2.get("scores", {}).get(profile, 0)) < 60:
                continue
            score = round((h1["scores"][profile] + h2["scores"][profile]) / 2)
            candidates.append({"date": t1.astimezone(LOCAL_TZ).strftime("%Y-%m-%d"),
                               "time": t1.astimezone(LOCAL_TZ).strftime("%H:%M"), "score": score,
                               "spot": spot["name"], "id": spot["id"], "hour": h1})
    return sorted(candidates, key=lambda s: (-s["score"], s["date"], s["time"]))


def choose_alert(snapshot, state, threshold=76, now=None):
    now = now or datetime.now(timezone.utc)
    sent = state.get("sent", {})
    # Dias con alertas previas no se vuelven a notificar por cambio marginal.
    for s in sessions(snapshot, now=now):
        if s["score"] >= threshold and s["date"] not in sent:
            return s
    return None


def get_site_url():
    override = os.environ.get("SITE_URL", "").strip()
    if override:
        return override.rstrip("/") + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, project = repo.split("/", 1)
        return f"https://{owner}.github.io/{project}/"
    return None


def deliver_telegram(alert, link):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    hour = alert["hour"]
    wave = hour.get("wave_m")
    period = hour.get("period_s")
    wind = hour.get("wind_kn")
    text = (f"🏄 <b>¡Ventana de surf en Barcelona!</b>\n\n"
            f"📍 <b>{html.escape(alert['spot'])}</b> · {alert['score']}/100\n"
            f"🗓 {html.escape(alert['date'])} desde las {alert['time']} (2 h)\n"
            f"🌊 Olas {wave if wave is not None else '—'} m · período {period if period is not None else '—'} s\n"
            f"💨 Viento {wind if wind is not None else '—'} kn\n"
            f"🔗 <a href=\"{html.escape(link, quote=True)}\">Ver ranking y pronóstico</a>\n\n"
            f"⚠️ Confirma bandera, corrientes y condiciones reales antes de entrar.")
    # En horario nocturno de Barcelona se envia silenciosamente.
    hour_local = datetime.now(timezone.utc).astimezone(LOCAL_TZ).hour
    quiet = hour_local < 8 or hour_local >= 22
    request = Request("https://api.telegram.org/bot" + token + "/sendMessage",
                      data=urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true", "disable_notification": "true" if quiet else "false"}).encode(),
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(request, timeout=15) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram respondio sin confirmar el envio")
    return True


def maybe_notify(snapshot, state_path, now=None):
    now = now or datetime.now(timezone.utc)
    state_path = Path(state_path)
    state = json.loads(state_path.read_text()) if state_path.exists() else {"sent": {}}
    state.setdefault("sent", {})
    state["sent"] = {k: v for k, v in state["sent"].items() if k >= (now.astimezone(LOCAL_TZ).date() - timedelta(days=3)).isoformat()}
    threshold = max(65, min(94, int(os.getenv("ALERT_THRESHOLD", "76"))))
    alert = choose_alert(snapshot, state, threshold, now)
    if alert and get_site_url() and deliver_telegram(alert, get_site_url()):
        state["sent"][alert["date"]] = {"spot": alert["id"], "score": alert["score"], "sent_at": now.isoformat()}
        print("Telegram enviado para", alert["date"], alert["spot"])
    elif alert:
        print("Sin Telegram configurado o URL disponible; no marcamos envio como realizado")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
