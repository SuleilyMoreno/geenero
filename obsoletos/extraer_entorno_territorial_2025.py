#!/usr/bin/env python3
"""Consolida indicadores territoriales 2025 de TerriData e IGAC/SNR.

Los endpoints se reciben como plantillas porque TerriData publica distintos
servicios según la ficha/indicador. Cada plantilla debe contener ``{codigo}``.
El endpoint IGAC/SNR debe responder como ArcGIS REST (``features``).

Uso:
  python extraer_entorno_territorial_2025.py \
    --divipola-csv divipola_1101.csv \
    --terridata-url 'https://.../{codigo}' \
    --igac-url 'https://.../FeatureServer/0/query?where=mpcodigo%3D%27{codigo}%27&outFields=*&f=json'
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import polars as pl
import requests


OUT = Path("/bronce/entorno_territorial_2025.parquet")
YEAR = 2025


def valor_2025(payload: Any) -> dict[str, Any]:
    """Normaliza respuestas TerriData/JSON a una fila con año 2025."""
    if isinstance(payload, dict) and isinstance(payload.get("features"), list):
        filas = [x.get("attributes", {}) for x in payload["features"]]
    elif isinstance(payload, dict):
        filas = payload.get("data", payload.get("results", [payload]))
        if isinstance(filas, dict):
            filas = [filas]
    elif isinstance(payload, list):
        filas = payload
    else:
        return {}
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        anio = fila.get("anio", fila.get("año", fila.get("year", fila.get("vigencia"))))
        if anio is None or str(anio) == str(YEAR):
            return fila
    return {}


def pedir(session: requests.Session, url: str) -> dict[str, Any]:
    try:
        response = session.get(url, timeout=(15, 90))
        response.raise_for_status()
        return valor_2025(response.json())
    except (requests.RequestException, ValueError) as exc:
        print(f"ERROR GET {url}: {exc}")
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--divipola-csv", required=True, help="CSV con una columna codigo_divipola")
    parser.add_argument("--terridata-url", required=True, help="URL plantilla con {codigo}")
    parser.add_argument("--igac-url", required=True, help="URL plantilla con {codigo}")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    div = pl.read_csv(args.divipola_csv, infer_schema_length=100)
    posibles = [c for c in div.columns if c.lower() in {"codigo_divipola", "divipola", "codigo"}]
    if not posibles:
        raise ValueError("El CSV debe tener codigo_divipola, divipola o codigo")
    codigos = div.select(pl.col(posibles[0]).cast(pl.Utf8).str.zfill(5)).unique().to_series().to_list()
    if len(codigos) != 1101:
        raise ValueError(f"Se esperaban 1.101 códigos DIVIPOLA únicos; se encontraron {len(codigos)}")

    filas: list[dict[str, Any]] = []
    with requests.Session() as session:
        for codigo in codigos:
            terri = pedir(session, args.terridata_url.format(codigo=codigo))
            igac = pedir(session, args.igac_url.format(codigo=codigo))
            filas.append({
                "codigo_divipola": codigo,
                "anio": YEAR,
                "pobreza_multidimensional": terri.get("pobreza_multidimensional"),
                "ruralidad": terri.get("ruralidad"),
                "informalidad_tierra": igac.get("icminformal", igac.get("informalidad")),
                "gini_tierras": igac.get("icmgini", igac.get("gini")),
                "terri_data_raw": str(terri),
                "igac_snr_raw": str(igac),
            })

    resultado = pl.DataFrame(filas)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    resultado.write_parquet(args.output, compression="zstd", compression_level=22)
    print(f"Escritas {resultado.height} filas en {args.output}")


if __name__ == "__main__":
    main()
