#!/usr/bin/env python3
"""Une y filtra los microdatos normalizados de GEIH 2025."""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl


CLAVES = [
    "identificador_vivienda",
    "numero_hogar_vivienda",
]


def columnas(ruta: Path) -> list[str]:
    if ruta.suffix.lower() == ".parquet":
        return pl.scan_parquet(ruta).collect_schema().names()
    return pl.scan_csv(ruta,
    separator=";",
    encoding="utf8-lossy",
    infer_schema=False,
    try_parse_dates=False,
)


def lazy(ruta: Path) -> pl.LazyFrame:
    if ruta.suffix.lower() == ".parquet":
        return pl.scan_parquet(ruta)
    if ruta.suffix.lower() == ".csv":
        return pl.scan_csv(
    ruta,
    separator=";",
    encoding="utf8-lossy",
    infer_schema=False,
    try_parse_dates=False)
    raise ValueError(f"Formato no soportado: {ruta}")


def buscar(carpeta: Path, palabra: str) -> Path:
    candidatos = sorted(
        p for p in carpeta.iterdir()
        if p.is_file() and p.suffix.lower() in {".csv", ".parquet"}
        and palabra in p.stem.lower()
    )
    if len(candidatos) != 1:
        raise ValueError(f"Se esperaba un archivo {palabra!r}; encontrados: {candidatos}")
    return candidatos[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
    "--input-dir",
    type=Path,
    default=Path("GEIH_2025_normalizada"),
    )
    parser.add_argument("--viviendas", type=Path)
    parser.add_argument("--personas", type=Path)
    parser.add_argument(
    "--dpto",
        default="identificador_departamento",
    )

    parser.add_argument(
        "--municipio",
        default="identificador_departamento",
    )

    parser.add_argument(
        "--ciiu",
        default="rama_actividad_empleo_principal",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("plata/geih_2025_limpia.parquet"),
    )
    args = parser.parse_args()

    viviendas = args.viviendas or buscar(
        args.input_dir,
        "datos_del_hogar_y_la_vivienda",
    )

    personas = args.personas or args.input_dir / "ocupados.csv"
    cols_v = columnas(viviendas)
    cols_p = columnas(personas)
    faltantes = [c for c in CLAVES if c not in cols_v or c not in cols_p]
    if faltantes:
        raise ValueError(f"Faltan claves de join: {faltantes}")
    for c in (args.dpto,):
        if c not in cols_v:
            raise ValueError(f"La columna {c!r} no está en Viviendas")
    # if "CLASE" not in cols_v:
    #     raise ValueError("La columna CLASE no está en Viviendas")
    if args.ciiu not in cols_p:
        raise ValueError(f"La columna CIIU {args.ciiu!r} no está en Personas")

    # Sufijos explícitos evitan ambigüedad si ambas tablas contienen columnas
    # con el mismo nombre. Se conservan las columnas de ambos archivos.
    v = lazy(viviendas).with_columns(
        [pl.col(c).cast(pl.Utf8).alias(c) for c in CLAVES] + [
        pl.col(args.dpto).cast(pl.Utf8).alias(args.dpto),
        ]
    )
    p = lazy(personas).with_columns(
        [pl.col(c).cast(pl.Utf8).alias(c) for c in CLAVES] + [
        pl.col(args.ciiu).cast(pl.Utf8).str.strip_chars().alias(args.ciiu),
        ]
    )
    resultado = (
        v.join(p, on=CLAVES, how="inner", suffix="_persona")
        # .filter(pl.col("CLASE").is_in([2, 3]))
        .filter(pl.col(args.ciiu).str.zfill(2).str.starts_with("01"))
        .with_columns(
            pl.col(args.dpto).str.extract(r"(\d+)", 1).str.zfill(5).alias("DIVIPOLA"),
            pl.lit("M").alias("Sexo"),
            pl.col("ingreso_laborales").cast(pl.Float64).alias("ingresos_laborales"),
            pl.lit(1).alias("empleo_formal"),
            pl.lit(2025).alias("anio")
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    resultado.sink_parquet(args.output, compression="zstd", compression_level=22)
    print(f"Resultado escrito en {args.output}")


if __name__ == "__main__":
    main()
