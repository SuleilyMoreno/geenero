#!/usr/bin/env python3
"""
Limpia y estandariza los datos de crédito de la Superfinanciera y Finagro.
Genera parquet listos para la capa oro.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import polars as pl

PLATA = Path("plata")


def procesar_superfinanciera(con: duckdb.DuckDBPyConnection) -> None:
    """Limpia los lotes de Superfinanciera 2025."""
    patron = "bronce/superfinanciera_2025/*.parquet"
    out = PLATA / "superfinanciera_2025_limpia.parquet"
    try:
        sql = f"""
        COPY (
            SELECT
                lpad(regexp_replace(coalesce(cast(codigo_municipio AS VARCHAR), ''), '[^0-9]', '', 'g'), 5, '0') AS DIVIPOLA,
                CASE
                    WHEN upper(trim(cast(sexo AS VARCHAR))) IN ('M', 'MASCULINO', 'H', 'HOMBRE', 'MALE') THEN 'M'
                    WHEN upper(trim(cast(sexo AS VARCHAR))) IN ('F', 'FEMENINO', 'MUJER', 'FEMALE') THEN 'F'
                    ELSE 'N'
                END AS Sexo,
                tipo_de_cr_dito AS Linea_Credito,
                2025 AS anio,
                cast(montos_desembolsados AS DOUBLE) AS monto,
                cast(tasa_efectiva_promedio AS DOUBLE) AS tasa
            FROM read_parquet('{patron}')
            WHERE montos_desembolsados IS NOT NULL
              AND tasa_efectiva_promedio IS NOT NULL
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 22);
        """
        con.execute(sql)
        cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out}')").fetchone()[0]
        print(f"Superfinanciera: {cnt:,} registros → {out}")
    except Exception as e:
        print(f"ERROR Superfinanciera: {e}")
        # Placeholder vacío con columnas mínimas
        pl.DataFrame({
            "DIVIPOLA": pl.Series([], dtype=pl.Utf8),
            "Sexo": pl.Series([], dtype=pl.Utf8),
            "Linea_Credito": pl.Series([], dtype=pl.Utf8),
            "anio": pl.Series([], dtype=pl.Int32),
            "monto": pl.Series([], dtype=pl.Float64),
            "tasa": pl.Series([], dtype=pl.Float64),
        }).write_parquet(out)


def procesar_finagro(con: duckdb.DuckDBPyConnection) -> None:
    """Limpia los datos locales de Finagro 2025."""
    origen = "bronce/finagro_2025/finagro_raw.parquet"
    out = PLATA / "finagro_2025_limpia.parquet"
    try:
        sql = f"""
        COPY (
            SELECT
                DIVIPOLA,
                CASE
                    WHEN upper(trim(Sexo)) IN ('M', 'MASCULINO', 'H', 'HOMBRE', 'MALE') THEN 'M'
                    WHEN upper(trim(Sexo)) IN ('F', 'FEMENINO', 'MUJER', 'FEMALE') THEN 'F'
                    ELSE 'N'
                END AS Sexo,
                linea_credito AS Linea_Credito,
                anio,
                monto,
                tasa
            FROM read_parquet('{origen}')
            WHERE monto IS NOT NULL
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 22);
        """
        con.execute(sql)
        cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out}')").fetchone()[0]
        print(f"Finagro: {cnt:,} registros → {out}")
    except Exception as e:
        print(f"ERROR Finagro: {e}")
        pl.DataFrame({
            "DIVIPOLA": pl.Series([], dtype=pl.Utf8),
            "Sexo": pl.Series([], dtype=pl.Utf8),
            "Linea_Credito": pl.Series([], dtype=pl.Utf8),
            "anio": pl.Series([], dtype=pl.Int32),
            "monto": pl.Series([], dtype=pl.Float64),
            "tasa": pl.Series([], dtype=pl.Float64),
        }).write_parquet(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Argumentos heredados del pipeline para compatibilidad
    parser.add_argument("--super-dir", default="bronce/superfinanciera_2025")
    parser.add_argument("--finagro", default="bronce/finagro_2025/finagro_raw.parquet")
    parser.add_argument("--monto", default="monto")
    parser.add_argument("--tasa", default="tasa")
    parser.add_argument("--sexo", default="sexo")
    parser.add_argument("--anio", default="anio")
    parser.add_argument("--divipola", default="DIVIPOLA")
    parser.parse_args()

    PLATA.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        procesar_superfinanciera(con)
        procesar_finagro(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
