#!/usr/bin/env python3
"""Pasa archivos locales ENUT 2025 y RIF 2025 a Parquet sin limpiarlos.

Busca archivos cuyo nombre contenga ``ENUT`` o ``RIF`` dentro de
/descargas_estaticas/. La lectura fuerza todas las columnas a String para
evitar inferencias o errores de tipos en archivos pesados.

Dependencias:
    pip install polars fastexcel openpyxl
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl


DEFAULT_INPUT = Path("descargas_estaticas")
DEFAULT_OUTPUT = Path("bronce/encuestas_2025")
EXTENSIONES = {".csv", ".xlsx", ".xlsm", ".xls"}


def leer_csv_como_texto(ruta: Path) -> pl.DataFrame:
    return pl.read_csv(
        ruta,
        infer_schema=False,
        try_parse_dates=False,
        encoding="utf8-lossy",
    )


def leer_excel_como_texto(ruta: Path) -> pl.DataFrame:
    # fastexcel permite leer xlsx/xlsm. schema_overrides impide inferencias
    # numéricas y temporales; los nombres y valores se conservan sin limpiar.
    return pl.read_excel(
        ruta,
        sheet_id=1,
        schema_overrides=pl.String,
        infer_schema_length=0,
    )


def leer(ruta: Path) -> pl.DataFrame:
    if ruta.suffix.lower() == ".csv":
        return leer_csv_como_texto(ruta)
    if ruta.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return leer_excel_como_texto(ruta)
    raise ValueError(f"Extensión no soportada: {ruta}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de entrada: {args.input_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    archivos = sorted(
        ruta for ruta in args.input_dir.iterdir()
        if ruta.is_file()
        and ruta.suffix.lower() in EXTENSIONES
        and ("enut" in ruta.name.lower() or "rif" in ruta.name.lower())
    )
    if not archivos:
        raise FileNotFoundError("No se encontraron archivos ENUT/RIF CSV o Excel")

    for ruta in archivos:
        frame = leer(ruta)
        salida = args.output_dir / f"{ruta.stem}.parquet"
        frame.write_parquet(salida, compression="zstd", compression_level=22)
        print(f"{ruta.name}: {frame.height:,} filas x {frame.width:,} columnas -> {salida}")


if __name__ == "__main__":
    main()
