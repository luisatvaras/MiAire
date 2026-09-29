#!/usr/bin/env python3
"""Descarga el PM2.5 horario actual (µg/m³) de CAMS vía Open-Meteo para la
malla de puntos sobre México y lo guarda en mexico_pm25.json, que es lo que
lee la página (lo convierte al índice Plume). Lo corre GitHub Actions cada 3 horas (.github/workflows/mexico-aq.yml),
así la página nunca le pregunta directo a Open-Meteo (tiene límite de
consultas por conexión).

La malla se lee del propio index.html (const MEXICO_GRID), para que siempre
coincida con la versión publicada. Solo usa la librería estándar.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
BATCH_SIZE = 200  # coordenadas por consulta
# Open-Meteo gratis: máx. 600 consultas por minuto, y cada coordenada cuenta
# como una. Con tandas de 200 y esta pausa quedan ~300 por minuto.
PAUSE_SECONDS = 40
RETRIES = 3  # si aun así responde 429 (demasiadas consultas), espera y reintenta


def fetch_json(url):
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == RETRIES:
                raise
            print(f"429 (demasiadas consultas), reintento en {PAUSE_SECONDS * 2} s")
            time.sleep(PAUSE_SECONDS * 2)


def main():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    grid = json.loads(re.search(r"const MEXICO_GRID = (\[.*?\]\]);", html).group(1))

    # En tandas: cientos de coordenadas no caben en una sola URL.
    results = []
    for start in range(0, len(grid), BATCH_SIZE):
        batch = grid[start:start + BATCH_SIZE]
        query = urllib.parse.urlencode({
            "latitude": ",".join(str(lat) for _, lat in batch),
            "longitude": ",".join(str(lon) for lon, _ in batch),
            "current": "pm2_5",
        })
        if start:
            time.sleep(PAUSE_SECONDS)
        answer = fetch_json(f"{API_URL}?{query}")
        results += answer if isinstance(answer, list) else [answer]  # un solo punto no viene en lista

    points = [
        [lon, lat, round(result["current"]["pm2_5"], 1)]
        for (lon, lat), result in zip(grid, results)
        if result.get("current", {}).get("pm2_5") is not None
    ]
    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "source": "CAMS (Copernicus) vía Open-Meteo, PM2.5 horario en µg/m³",
        "points": points,  # [lon, lat, pm25]
    }
    (ROOT / "mexico_pm25.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"OK: {len(points)} puntos")


if __name__ == "__main__":
    main()
