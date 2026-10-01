#!/usr/bin/env python3
"""Construye los modelos analíticos de la capa Oro 2025 con DuckDB."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb


BASE_DIR = Path(__file__).resolve().parent
PLATA = BASE_DIR / "plata"
ORO = BASE_DIR / "oro"


def exigir(*rutas: Path) -> None:
    faltantes = [str(r) for r in rutas if not r.exists()]
    if faltantes:
        raise FileNotFoundError("Faltan insumos: " + ", ".join(faltantes))


def crear_calidad_vida(con: duckdb.DuckDBPyConnection) -> None:
    destino = ORO / "tablero_calidad_vida_2025.parquet"
    print("Generando tablero_calidad_vida_2025.parquet...")
    con.execute(f"""
        COPY (
            SELECT
                g.DIVIPOLA,
                g.Sexo,
                2025 AS anio,
                AVG(try_cast(g.ingresos_laborales AS DOUBLE))
                    AS Promedio_Ingresos,
                AVG(try_cast(g.empleo_formal AS DOUBLE)) * 100
                    AS Porcentaje_Empleo_Formal,
                AVG(try_cast(e.horas_tnr AS DOUBLE))
                    AS Promedio_Horas_Cuidado_TNR
            FROM read_parquet('{PLATA / "geih_2025_limpia.parquet"}') AS g
            LEFT JOIN read_parquet('{PLATA / "enut_2025_limpia.parquet"}') AS e
              ON g.DIVIPOLA = e.DIVIPOLA
             AND g.Sexo = e.Sexo
            WHERE try_cast(g.anio AS INTEGER) = 2025
            GROUP BY g.DIVIPOLA, g.Sexo
        ) TO '{destino}'
        (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 22)
    """)
    print(f"✓ Creado: {destino}")


def crear_financiero(con: duckdb.DuckDBPyConnection) -> None:
    destino = ORO / "tablero_financiero_nacional_2025.parquet"
    print("Generando tablero_financiero_nacional_2025.parquet...")
    con.execute(f"""
        COPY (
            SELECT
                s.DIVIPOLA,
                s.Sexo,
                c.Region,
                s.Linea_Credito,
                2025 AS anio,
                COUNT(*) AS Total_Creditos_Otorgados,
                AVG(try_cast(s.monto AS DOUBLE))
                    AS Monto_Promedio_Desembolsado,
                MEDIAN(try_cast(s.tasa AS DOUBLE))
                    AS Mediana_Tasa_Interes,
                MAX(try_cast(c.indice_informalidad_tierra AS DOUBLE))
                    AS Indice_Informalidad_Tierra,
                MAX(try_cast(c.densidad_bancaria AS DOUBLE))
                    AS Densidad_Bancaria
            FROM read_parquet('{PLATA / "superfinanciera_2025_limpia.parquet"}') AS s
            LEFT JOIN read_parquet('{PLATA / "contexto_municipal_2025.parquet"}') AS c
              ON s.DIVIPOLA = c.DIVIPOLA
            WHERE try_cast(s.anio AS INTEGER) = 2025
            GROUP BY s.DIVIPOLA, s.Sexo, c.Region, s.Linea_Credito
        ) TO '{destino}'
        (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 22)
    """)
    print(f"✓ Creado: {destino}")


def main() -> None:
    ORO.mkdir(parents=True, exist_ok=True)
    exigir(
        PLATA / "geih_2025_limpia.parquet",
        PLATA / "enut_2025_limpia.parquet",
        PLATA / "superfinanciera_2025_limpia.parquet",
        PLATA / "finagro_2025_limpia.parquet",
        PLATA / "contexto_municipal_2025.parquet",
    )
    con = duckdb.connect(database=":memory:")
    try:
        crear_calidad_vida(con)
        crear_financiero(con)
    finally:
        con.close()
    print("\nProceso finalizado. Revisa /oro/.")


if __name__ == "__main__":
    main()
