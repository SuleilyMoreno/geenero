#!/usr/bin/env python3
"""Descarga y filtra microdatos FINAGRO 2025 (desembolsos o FAG).

CSV estático:
  python descargar_finagro_2025.py --csv-url URL --year-column anio

Socrata:
  python descargar_finagro_2025.py --dataset-id abcd-1234 \
      --year-column anio_desembolso
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import polars as pl
import requests
from sodapy import Socrata


DOMAIN = "www.datos.gov.co"
OUT_DIR = Path("/bronce/finagro_2025")
OUT_FILE = OUT_DIR / "finagro_raw.parquet"
RAW_FILE = OUT_DIR / "finagro_download.csv"
YEAR = "2025"


def descargar_csv(url: str, destino: Path, chunk_size: int = 8 * 1024 * 1024) -> None:
    """Descarga el CSV por streaming, sin mantenerlo en RAM."""
    with requests.get(url, stream=True, timeout=(30, 600)) as response:
        response.raise_for_status()
        with destino.open("wb") as archivo:
            for bloque in response.iter_content(chunk_size=chunk_size):
                if bloque:
                    archivo.write(bloque)


def descargar_socrata(dataset_id: str, year_column: str, destino: Path, limit: int) -> None:
    """Descarga desde SODA en páginas aplicando estrictamente año=2025."""
    cliente = Socrata(DOMAIN, os.getenv("SODAPY_APP_TOKEN"), timeout=120)
    offset = 0
    primera_pagina = True
    try:
        with destino.open("w", newline="", encoding="utf-8") as archivo:
            escritor = None
            while True:
                # Filtro deliberadamente único: año 2025.
                filas = cliente.get(
                    dataset_id,
                    where=f"{year_column} = '2025'",
                    limit=limit,
                    offset=offset,
                )
                if not filas:
                    break
                if escritor is None:
                    escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
                    escritor.writeheader()
                escritor.writerows(filas)
                offset += len(filas)
                primera_pagina = False
                if len(filas) < limit:
                    break
    finally:
        cliente.close()
    if primera_pagina:
        destino.write_text("", encoding="utf-8")


def convertir_filtrar(raw: Path, output: Path, year_column: str) -> None:
    """Lee el crudo con Polars, filtra 2025 y escribe Parquet comprimido."""
    muestra = pl.read_csv(raw, n_rows=0, infer_schema_length=0)
    if year_column not in muestra.columns:
        raise ValueError(f"No existe la columna de año {year_column!r}. Columnas: {muestra.columns}")
    frame = pl.read_csv(raw, infer_schema_length=10_000, try_parse_dates=False)
    filtrado = frame.filter(pl.col(year_column).cast(pl.Utf8).str.strip_chars() == YEAR)
    filtrado.write_parquet(output, compression="zstd", compression_level=22)
    print(f"Filas 2025: {filtrado.height:,}; salida: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    fuente = parser.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--csv-url", help="URL directa al CSV estático de FINAGRO")
    fuente.add_argument("--dataset-id", help="ID del dataset Socrata")
    parser.add_argument("--year-column", required=True, help="Nombre exacto de la columna de año")
    parser.add_argument("--limit", type=int, default=100_000, help="Tamaño de página SODA")
    parser.add_argument("--keep-raw", action="store_true", help="Conservar el CSV temporal")
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit debe ser positivo")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.csv_url:
        descargar_csv(args.csv_url, RAW_FILE)
    else:
        descargar_socrata(args.dataset_id, args.year_column, RAW_FILE, args.limit)
    convertir_filtrar(RAW_FILE, OUT_FILE, args.year_column)
    if not args.keep_raw:
        RAW_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
