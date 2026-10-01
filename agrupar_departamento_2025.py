#!/usr/bin/env python3
"""
agrupar_departamento_2025.py
----------------------------
Genera un dataset a nivel de *departamento* (identificador de 5 dígitos, `DIVIPOLA`)
que combina:

  * GEIH 2025 (`plata/geih_2025_limpia.parquet`)
  * Créditos Superfinanciera 2025 (`plata/superfinanciera_2025_limpia.parquet`)
  * Créditos Finagro 2025 (`plata/finagro_2025_limpia.parquet`)
  * Contexto municipal DNP (`plata/contexto_municipal_2025.parquet`)

El archivo resultante se guarda en:
    plata/departamento_2025_aggregado.parquet
"""

from __future__ import annotations
import argparse
from pathlib import Path
import polars as pl

PLATA = Path("plata")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geih", default=str(PLATA / "geih_2025_limpia.parquet"))
    parser.add_argument("--super", default=str(PLATA / "superfinanciera_2025_limpia.parquet"))
    parser.add_argument("--finagro", default=str(PLATA / "finagro_2025_limpia.parquet"))
    parser.add_argument("--contexto", default=str(PLATA / "contexto_municipal_2025.parquet"))
    parser.add_argument("--out", default=str(PLATA / "departamento_2025_aggregado.parquet"))
    args = parser.parse_args()

    # 1️⃣ Load data
    geih = pl.read_parquet(args.geih)
    superf = pl.read_parquet(args.super)
    finag = pl.read_parquet(args.finagro)
    contexto = pl.read_parquet(args.contexto)

    # 2️⃣ Combine credit data and aggregate by DIVIPOLA
    creditos = pl.concat([
        superf.select(["DIVIPOLA", "Sexo", "Linea_Credito", "anio", "monto", "tasa"]),
        finag.select(["DIVIPOLA", "Sexo", "Linea_Credito", "anio", "monto", "tasa"])
    ])

    creditos_agg = (
        creditos
        .group_by("DIVIPOLA")
        .agg([
            pl.col("monto").sum().alias("total_monto"),
            pl.col("monto").mean().alias("monto_promedio"),
            pl.col("tasa").mean().alias("tasa_promedio"),
            pl.len().alias("num_creditos")
        ])
    )

    # 3️⃣ Income and formal employment averages from GEIH per DIVIPOLA
    ingreso_agg = (
        geih
        .group_by("DIVIPOLA")
        .agg([
            pl.col("ingresos_laborales").mean().alias("ingreso_promedio"),
            pl.col("empleo_formal").mean().alias("empleo_formal_promedio")
        ])
    )

    # 4️⃣ Merge context (DNP) + credit aggregates + ingreso aggregates
    merged = (
        contexto
        .join(creditos_agg, on="DIVIPOLA", how="left")
        .join(ingreso_agg, on="DIVIPOLA", how="left")
    )

    # 5️⃣ Fill missing values
    merged = merged.with_columns([
        pl.col("total_monto").fill_null(0),
        pl.col("num_creditos").fill_null(0),
        pl.col("monto_promedio").fill_null(0),
        pl.col("tasa_promedio").fill_null(0),
        pl.col("ingreso_promedio").fill_null(0),
        pl.col("empleo_formal_promedio").fill_null(0)
    ])

    # 6️⃣ Save
    PLATA.mkdir(parents=True, exist_ok=True)
    merged.write_parquet(args.out, compression="zstd", compression_level=22)
    print(f"Dataset departamental creado → {args.out} (filas: {merged.height})")

if __name__ == "__main__":
    main()
