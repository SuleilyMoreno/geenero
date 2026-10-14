#!/usr/bin/env python3
"""Extrae por lotes datos SODA de la Superintendencia Financiera.

Ejemplo:
    python extraer_superfinanciera_2025.py \
        --dataset-id ID_DEL_DATASET \
        --anio-field anio_desembolso \
        --ciiu-field ciiu

Los nombres de columna deben ser los identificadores API (no necesariamente
los nombres visibles en la página de Datos Abiertos Colombia).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from sodapy import Socrata


DOMAIN = "www.datos.gov.co"
DEFAULT_LIMIT = 100_000
DEFAULT_OUTPUT = "/bronce/superfinanciera_2025"


def extraer(
    dataset_id: str,
    anio_field: str,
    ciiu_field: str,
    output_dir: str,
    limit: int = DEFAULT_LIMIT,
) -> int:
    """Descarga todos los lotes que cumplen exclusivamente los dos filtros."""
    destino = Path(output_dir)
    destino.mkdir(parents=True, exist_ok=True)

    # Los únicos dos filtros de la consulta SODA son año=2025 y CIIU empieza
    # por 01. substr() usa posiciones 1-based en SoQL.
    where = f"{anio_field} = '2025' AND substr({ciiu_field}, 1, 2) = '01'"

    app_token = os.getenv("SODAPY_APP_TOKEN")
    cliente = Socrata(DOMAIN, app_token, timeout=120)
    offset = 0
    lote = 0

    try:
        while True:
            registros = cliente.get(
                dataset_id,
                where=where,
                limit=limit,
                offset=offset,
            )
            if not registros:
                break

            frame = pd.DataFrame.from_records(registros)
            ruta = destino / f"lote_{lote}.parquet"
            frame.to_parquet(ruta, index=False)
            print(f"{ruta}: {len(frame):,} registros")

            recibidos = len(registros)
            offset += recibidos
            lote += 1
            if recibidos < limit:
                break
    finally:
        cliente.close()

    print(f"Extracción terminada: {lote} archivo(s), offset final={offset:,}")
    return lote


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True, help="ID Socrata, por ejemplo abcd-1234")
    parser.add_argument("--anio-field", required=True, help="Identificador API del año de desembolso")
    parser.add_argument("--ciiu-field", required=True, help="Identificador API de actividad económica/CIIU")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit debe ser mayor que cero")
    extraer(args.dataset_id, args.anio_field, args.ciiu_field, args.output_dir, args.limit)


if __name__ == "__main__":
    main()
