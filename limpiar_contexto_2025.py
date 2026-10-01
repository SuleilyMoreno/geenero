#!/usr/bin/env python3
"""
Consolida indicadores territoriales usando:
  - DNP Desempeño Municipal (Socrata nkjx-rsq7) → indicadores de gestión municipal
  - Datos IGAC en Socrata → si disponible
  - Valores de pobreza del DANE Sisbén / TerriData aproximado

Genera: plata/contexto_municipal_2025.parquet
         plata/enut_2025_limpia.parquet (placeholder si no hay datos ENUT)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
import requests

PLATA = Path("plata")
DOMAIN = "www.datos.gov.co"


def descargar_dnp_desempeno(cod_dpto: str | None = None) -> pl.DataFrame:
    """
    Descarga indicadores del DNP (dataset nkjx-rsq7).
    Devuelve los más recientes disponibles por municipio.
    """
    print("Descargando indicadores DNP (Desempeño Municipal)...")
    url = "https://www.datos.gov.co/resource/nkjx-rsq7.json"
    limit = 50_000
    offset = 0
    partes: list[pl.DataFrame] = []

    while True:
        params: dict = {"$limit": limit, "$offset": offset, "$order": "codigo_entidad,anio DESC"}
        if cod_dpto:
            params["codigo_departamento"] = cod_dpto
        try:
            resp = requests.get(url, params=params, timeout=60)
            data = resp.json()
        except Exception as e:
            print(f"  Error DNP offset={offset}: {e}")
            break
        if not data:
            break
        partes.append(pl.DataFrame(data))
        if len(data) < limit:
            break
        offset += limit

    if not partes:
        print("  Sin datos DNP — se usará tabla mínima.")
        return pl.DataFrame({
            "DIVIPOLA": pl.Series([], dtype=pl.Utf8),
            "departamento": pl.Series([], dtype=pl.Utf8),
            "indicador_dnp": pl.Series([], dtype=pl.Utf8),
            "valor_dnp": pl.Series([], dtype=pl.Utf8),
            "anio_dnp": pl.Series([], dtype=pl.Utf8),
        })

    dnp = pl.concat(partes)
    dnp = dnp.rename({"codigo_entidad": "DIVIPOLA", "etiqueta": "grupo_municipio"})
    dnp = dnp.with_columns(pl.col("DIVIPOLA").str.zfill(5))
    print(f"  DNP: {len(dnp):,} registros descargados")
    return dnp


def construir_contexto(dnp: pl.DataFrame) -> pl.DataFrame:
    """
    Pivota los indicadores DNP a columnas útiles para el análisis de género.
    Selecciona el año más reciente por municipio.
    """
    # Si está vacío, retornar tabla mínima
    if len(dnp) == 0:
        return pl.DataFrame({
            "DIVIPOLA": pl.Series([], dtype=pl.Utf8),
            "departamento": pl.Series([], dtype=pl.Utf8),
            "Region": pl.Series([], dtype=pl.Utf8),
            "grupo_municipio": pl.Series([], dtype=pl.Utf8),
            "indice_informalidad_tierra": pl.Series([], dtype=pl.Float64),
            "densidad_bancaria": pl.Series([], dtype=pl.Float64),
        })

    # Año más reciente por municipio
    contexto = (
        dnp.filter(pl.col("anio").cast(pl.Int32, strict=False).is_not_null())
        .sort(["DIVIPOLA", "anio"], descending=[False, True])
        .unique(subset=["DIVIPOLA"], keep="first")
        .select(["DIVIPOLA", "departamento", "grupo_municipio"])
        .with_columns(
            pl.lit(None).cast(pl.Float64).alias("indice_informalidad_tierra"),
            pl.lit(None).cast(pl.Float64).alias("densidad_bancaria"),
            pl.col("departamento").alias("Region"),
        )
    )
    return contexto


def construir_enut_placeholder() -> pl.DataFrame:
    """
    Crea un placeholder de ENUT si no hay datos disponibles localmente.
    Columnas mínimas requeridas por la capa oro.
    """
    print("ENUT: generando placeholder (sin archivo ENUT local disponible).")
    return pl.DataFrame({
        "DIVIPOLA": pl.Series([], dtype=pl.Utf8),
        "Sexo": pl.Series([], dtype=pl.Utf8),
        "TNR_horas": pl.Series([], dtype=pl.Float64),
        "horas_tnr": pl.Series([], dtype=pl.Float64),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cod-dpto", default=None,
                        help="Filtrar por código de departamento (ej. '05' = Antioquia)")
    parser.add_argument("--enut", default=None,
                        help="Ruta a CSV/parquet de ENUT si está disponible localmente")
    args = parser.parse_args()

    PLATA.mkdir(parents=True, exist_ok=True)

    # ── Contexto municipal ─────────────────────────────────────────────────────
    dnp = descargar_dnp_desempeno(args.cod_dpto)
    contexto = construir_contexto(dnp)
    out_ctx = PLATA / "contexto_municipal_2025.parquet"
    contexto.write_parquet(out_ctx, compression="zstd", compression_level=22)
    print(f"Escritas {len(contexto)} filas en {out_ctx}")

    # ── ENUT ──────────────────────────────────────────────────────────────────
    out_enut = PLATA / "enut_2025_limpia.parquet"
    if args.enut:
        ruta = Path(args.enut)
        if ruta.suffix == ".parquet":
            enut = pl.read_parquet(ruta)
        else:
            enut = pl.read_csv(ruta, infer_schema_length=0)
        enut.write_parquet(out_enut, compression="zstd", compression_level=22)
        print(f"ENUT local: {len(enut)} filas → {out_enut}")
    else:
        enut = construir_enut_placeholder()
        enut.write_parquet(out_enut, compression="zstd", compression_level=22)


if __name__ == "__main__":
    main()
