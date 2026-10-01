#!/usr/bin/env python3
"""
agrupar_genero_2025.py
----------------------
Genera un dataset a nivel de *persona* que combina la información de:
  * GEIH 2025 (viviendas y ocupados) – ya está limpita en `plata/geih_2025_limpia.parquet`
  * Créditos de Superfinanciera 2025 (`plata/superfinanciera_2025_limpia.parquet`)
  * Créditos de Finagro 2025 (`plata/finagro_2025_limpia.parquet`)

Se unen los datos por `DIVIPOLA` y `Sexo` y se calculan indicadores
agrupados por sexo:
  - número total de créditos
  - monto promedio desembolsado
  - tasa promedio de interés
  - ingreso promedio de la persona (GEIH)
El resultado se guarda en `plata/genero_2025_aggregado.parquet`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

PLATA = Path("plata")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geih", default=str(PLATA / "geih_2025_limpia.parquet"), help="Parquet de GEIH 2025")
    parser.add_argument("--super", default=str(PLATA / "superfinanciera_2025_limpia.parquet"), help="Parquet de Superfinanciera 2025")
    parser.add_argument("--finagro", default=str(PLATA / "finagro_2025_limpia.parquet"), help="Parquet de Finagro 2025")
    parser.add_argument("--out", default=str(PLATA / "genero_2025_aggregado.parquet"), help="Archivo de salida")
    args = parser.parse_args()

    # Cargar fuentes
    geih = pl.read_parquet(args.geih)
    superf = pl.read_parquet(args.super)
    finag = pl.read_parquet(args.finagro)

    # Unir créditos (Super + Finagro) en una sola tabla
    creditos = pl.concat([superf.select(["DIVIPOLA", "Sexo", "Linea_Credito", "anio", "monto", "tasa"]),
                         finag.select(["DIVIPOLA", "Sexo", "Linea_Credito", "anio", "monto", "tasa"] )])

    # Agrupar créditos por DIVIPOLA y Sexo para obtener totales
    creditos_agg = (
        creditos
        .group_by(["DIVIPOLA", "Sexo"])
        .agg([
            pl.col("monto").sum().alias("total_monto"),
            pl.col("monto").mean().alias("monto_promedio"),
            pl.col("tasa").mean().alias("tasa_promedio"),
            pl.count().alias("num_creditos")
        ])
    )

    # Unir con GEIH (que ya contiene ingreso y otras variables por persona)
    # Vamos a hacer una izquierda join sobre DIVIPOLA y Sexo, manteniendo todas las filas de GEIH.
    joined = geih.join(creditos_agg, on=["DIVIPOLA", "Sexo"], how="left")

    # Completar valores nulos (personas sin crédito)
    joined = joined.with_columns([
        pl.col("total_monto").fill_null(0),
        pl.col("num_creditos").fill_null(0),
        pl.col("monto_promedio").fill_null(0),
        pl.col("tasa_promedio").fill_null(0)
    ])

    # Guardar
    PLATA.mkdir(parents=True, exist_ok=True)
    joined.write_parquet(args.out, compression="zstd", compression_level=22)
    print(f"Dataset a nivel de género creado → {args.out} (filas: {joined.height})")

if __name__ == "__main__":
    main()
