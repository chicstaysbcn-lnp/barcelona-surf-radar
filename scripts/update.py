#!/usr/bin/env python3
"""Ejecutar cada seis horas con Github Actions: python3 scripts/update.py."""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alerts import maybe_notify
from forecast import generate_snapshot

ROOT = Path(__file__).resolve().parent.parent


def main():
    print("Actualizando datos de Barcelona Surf Radar...", datetime.now(timezone.utc).isoformat(), flush=True)
    snapshot = generate_snapshot()
    path = ROOT / "data/latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Escritura atomica: una falla de red no destruye la ultima prediccion valida.
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(path)
    print(f"Actualizadas {snapshot['spots_available']}/{snapshot['spots_expected']} playas", flush=True)
    try:
        maybe_notify(snapshot, ROOT / "state/alerts.json")
    except Exception as error:
        print("ERROR avisos Telegram:", type(error).__name__, str(error)[:250], file=sys.stderr)
        # No se confirma alerta si fallo el envio. Datos si quedan publicados.
        if os.environ.get("FAIL_ON_NOTIFICATION_ERROR") == "1":
            raise


if __name__ == "__main__":
    main()
