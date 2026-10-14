#!/usr/bin/env python3
"""Añade una clasificación binaria urbano/rural sin inventar ruralidad."""
from pathlib import Path
import duckdb

BASE = Path(__file__).resolve().parent

def main():
    con = duckdb.connect()
    try:
        # Encuestas: CLASE 1 = cabecera; 2/3 = resto rural.
        for p in sorted((BASE / 'plata/geih_2025_decodificada').glob('*.parquet')):
            con.execute(f"""COPY (
                SELECT *, CASE WHEN CAST(CLASE AS VARCHAR)='1' THEN 'Urbano'
                    WHEN CAST(CLASE AS VARCHAR) IN ('2','3') THEN 'Rural'
                    ELSE 'Sin clasificar' END AS clasificacion_urbano_rural
                FROM read_parquet('{p}')
            ) TO '{p}.tmp.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)""")
            Path(f'{p}.tmp.parquet').replace(p)
        enut = BASE / 'plata/enut_2024_2025_limpia.parquet'
        if enut.exists():
            con.execute(f"""COPY (SELECT *, CASE WHEN CAST(CLASE AS VARCHAR)='1' THEN 'Urbano'
                WHEN CAST(CLASE AS VARCHAR) IN ('2','3') THEN 'Rural' ELSE 'Sin clasificar' END AS clasificacion_urbano_rural
                FROM read_parquet('{enut}')) TO '{enut}.tmp.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)""")
            Path(f'{enut}.tmp.parquet').replace(enut)
            compat = BASE / 'plata/enut_2025_limpia.parquet'
            con.execute(f"COPY (SELECT * FROM read_parquet('{enut}')) TO '{compat}.tmp.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
            Path(f'{compat}.tmp.parquet').replace(compat)
        # FIES ya viene agregado: sus áreas se reducen a Rural/Urbano.
        for p in [BASE/'plata/fies_2025_rural_prevalencia.parquet', BASE/'plata/fies_2025_rural_experiencias.parquet']:
            if p.exists():
                con.execute(f"""COPY (SELECT *, CASE WHEN lower(CAST(Área AS VARCHAR)) LIKE '%cabecera%' THEN 'Urbano'
                    WHEN lower(CAST(Área AS VARCHAR)) LIKE '%rural%' OR lower(CAST(Área AS VARCHAR)) LIKE '%centros poblados%' THEN 'Rural'
                    ELSE 'Sin clasificar' END AS clasificacion_urbano_rural FROM read_parquet('{p}'))
                    TO '{p}.tmp.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)""")
                Path(f'{p}.tmp.parquet').replace(p)
        # No se imputa clasificación a fuentes municipales sin tabla oficial.
        for p in [BASE/'plata/contexto_municipal_2025.parquet', BASE/'plata/finagro_2025_limpia.parquet', BASE/'plata/superfinanciera_2025_limpia.parquet']:
            if p.exists():
                con.execute(f"COPY (SELECT *, 'Sin clasificar' AS clasificacion_urbano_rural FROM read_parquet('{p}') WHERE TRUE) TO '{p}.tmp.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
                Path(f'{p}.tmp.parquet').replace(p)
        print('OK: clasificación urbano/rural añadida sin imputaciones territoriales.')
    finally: con.close()

if __name__ == '__main__': main()
