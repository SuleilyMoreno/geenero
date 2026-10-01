#!/usr/bin/env python3
"""Genera la tabla maestra financiera nacional 2025 con DuckDB."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


def ident(nombre: str) -> str:
    return '"' + nombre.replace('"', '""') + '"'


def literal(ruta: str) -> str:
    return "'" + ruta.replace("'", "''") + "'"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plata", default="/plata")
    parser.add_argument("--output", default="/oro/tablero_financiero_nacional_2025.parquet")
    parser.add_argument("--anio", default="anio")
    parser.add_argument("--sexo", default="Sexo")
    parser.add_argument("--region", default="Región")
    parser.add_argument("--linea", default="Línea_Credito")
    parser.add_argument("--monto", default="monto")
    parser.add_argument("--tasa", default="tasa")
    parser.add_argument("--informalidad", default="indice_informalidad_tierra")
    parser.add_argument("--densidad-bancaria", default="indice_densidad_bancaria")
    args = parser.parse_args()

    base = Path(args.plata)
    sf = base / "superfinanciera_2025_limpia.parquet"
    finagro = base / "finagro_2025_limpia.parquet"
    contexto = base / "contexto_municipal_2025.parquet"
    salida = Path(args.output)
    salida.parent.mkdir(parents=True, exist_ok=True)

    # Se filtra cada fuente antes del JOIN para garantizar que el maestro sea
    # estrictamente de 2025 y evitar multiplicaciones innecesarias de filas.
    sql = f"""
    COPY (
        WITH sf AS (
            SELECT
                CAST(DIVIPOLA AS VARCHAR) AS DIVIPOLA,
                CAST({ident(args.sexo)} AS VARCHAR) AS Sexo,
                CAST({ident(args.region)} AS VARCHAR) AS Region,
                CAST({ident(args.linea)} AS VARCHAR) AS Linea_Credito,
                try_cast({ident(args.monto)} AS DOUBLE) AS monto_sf,
                try_cast({ident(args.tasa)} AS DOUBLE) AS tasa_sf
            FROM read_parquet({literal(str(sf))})
            WHERE try_cast({ident(args.anio)} AS INTEGER) = 2025
        ),
        fg AS (
            SELECT
                CAST(DIVIPOLA AS VARCHAR) AS DIVIPOLA,
                try_cast({ident(args.monto)} AS DOUBLE) AS monto_fg,
                try_cast({ident(args.tasa)} AS DOUBLE) AS tasa_fg,
                try_cast({ident(args.anio)} AS INTEGER) AS anio_fg
            FROM read_parquet({literal(str(finagro))})
            WHERE try_cast({ident(args.anio)} AS INTEGER) = 2025
        ),
        ctx AS (
            SELECT
                CAST(DIVIPOLA AS VARCHAR) AS DIVIPOLA,
                try_cast({ident(args.informalidad)} AS DOUBLE) AS informalidad_tierra,
                try_cast({ident(args.densidad_bancaria)} AS DOUBLE) AS densidad_bancaria
            FROM read_parquet({literal(str(contexto))})
        )
        SELECT
            sf.DIVIPOLA,
            sf.Sexo,
            sf.Region AS "Región",
            sf.Linea_Credito AS "Línea_Credito",
            2025 AS anio,
            AVG(COALESCE(sf.monto_sf, fg.monto_fg)) AS monto_promedio_desembolsado,
            MEDIAN(COALESCE(sf.tasa_sf, fg.tasa_fg)) AS mediana_tasa_interes,
            COUNT(*) AS conteo_creditos,
            MAX(ctx.informalidad_tierra) AS indice_informalidad_tierra,
            MAX(ctx.densidad_bancaria) AS indice_densidad_bancaria
        FROM sf
        LEFT JOIN fg ON sf.DIVIPOLA = fg.DIVIPOLA
        LEFT JOIN ctx ON sf.DIVIPOLA = ctx.DIVIPOLA
        GROUP BY sf.DIVIPOLA, sf.Sexo, sf.Region, sf.Linea_Credito
    ) TO {literal(str(salida))}
    (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 22);
    """

    con = duckdb.connect()
    try:
        con.execute(sql)
        print(f"Tabla maestra escrita en {salida}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
