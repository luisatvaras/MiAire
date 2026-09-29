#!/usr/bin/env python3
"""Descarga el AQI actual (EE. UU.) de CAMS vía Open-Meteo para la malla de
puntos sobre México y lo guarda en mexico_aq.json, que es lo que lee la
página. Lo corre GitHub Actions cada 3 horas (.github/workflows/mexico-aq.yml),
así la página nunca le pregunta directo a Open-Meteo (tiene límite de
consultas por conexión).

La malla se lee del propio index.html (const MEXICO_GRID), para que siempre
coincida con la versión publicada. Solo usa la librería estándar.
"""

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def main():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    grid = json.loads(re.search(r"const MEXICO_GRID = (\[.*?\]\]);", html).group(1))

    query = urllib.parse.urlencode({
        "latitude": ",".join(str(lat) for _, lat in grid),
        "longitude": ",".join(str(lon) for lon, _ in grid),
        "current": "us_aqi",
    })
    with urllib.request.urlopen(f"{API_URL}?{query}", timeout=60) as response:
        results = json.load(response)
    if isinstance(results, dict):  # un solo punto no viene en lista
        results = [results]

    points = [
        [lon, lat, result["current"]["us_aqi"]]
        for (lon, lat), result in zip(grid, results)
        if result.get("current", {}).get("us_aqi") is not None
    ]
    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "source": "CAMS (Copernicus) vía Open-Meteo, AQI EE. UU.",
        "points": points,  # [lon, lat, aqi]
    }
    (ROOT / "mexico_aq.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"OK: {len(points)} puntos")


if __name__ == "__main__":
    main()
