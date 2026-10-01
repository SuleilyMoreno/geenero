#!/usr/bin/env python3
"""Ejecuta el pipeline 2025: APIs externas + GEIH DANE local.

Las fuentes externas nunca se buscan en carpetas locales: se descargan desde
los endpoints suministrados por variables de entorno. GEIH se lee desde
GEIH_2025/ y se decodifica con el diccionario oficial.

Variables requeridas:
  SUPER_DATASET_ID, SUPER_ANIO_FIELD, SUPER_CIIU_FIELD
  FINAGRO_DATASET_ID, FINAGRO_YEAR_COLUMN
  TERRIDATA_URL, IGAC_URL, DIVIPOLA_CSV
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BRONCE = ROOT / "bronce"
PLATA = ROOT / "plata"
ORO = ROOT / "oro"


def requerido(nombre: str) -> str:
    valor = os.getenv(nombre)
    if not valor:
        raise SystemExit(f"Falta la variable de entorno requerida: {nombre}")
    return valor


def ejecutar(*args: str) -> None:
    print("\n$", " ".join(args))
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> None:
    BRONCE.mkdir(exist_ok=True)
    PLATA.mkdir(exist_ok=True)
    ORO.mkdir(exist_ok=True)

    # 1. GEIH: fuente local oficial, por mes y módulo. No se concatena
    # indiscriminadamente: el decodificador conserva cada esquema.
    ejecutar(
        "decodificar_geih_2025.py",
        "--datos", str(ROOT / "GEIH_2025"),
        "--diccionario", str(ROOT / "Diccionario_de_datos_GEIH_2025.xlsx"),
        "--salida", str(PLATA / "geih_2025_decodificada"),
    )

    # 2. Fuentes externas: siempre API/URL, nunca archivos locales de entrada.
    ejecutar(
        "extraer_superfinanciera_2025.py",
        "--dataset-id", requerido("SUPER_DATASET_ID"),
        "--anio-field", requerido("SUPER_ANIO_FIELD"),
        "--ciiu-field", requerido("SUPER_CIIU_FIELD"),
        "--output-dir", str(BRONCE / "superfinanciera_2025"),
    )
    ejecutar(
        "descargar_finagro_2025.py",
        "--dataset-id", requerido("FINAGRO_DATASET_ID"),
        "--year-column", requerido("FINAGRO_YEAR_COLUMN"),
    )
    ejecutar(
        "extraer_entorno_territorial_2025.py",
        "--divipola-csv", requerido("DIVIPOLA_CSV"),
        "--terridata-url", requerido("TERRIDATA_URL"),
        "--igac-url", requerido("IGAC_URL"),
        "--output", str(BRONCE / "entorno_territorial_2025.parquet"),
    )

    # 3. El resto de fuentes externas (ENUT/RIF) debe colocarse mediante sus
    # respectivos descargadores API antes de ejecutar los limpiadores Plata.
    ejecutar("limpiar_financieros_2025.py")
    ejecutar("limpiar_contexto_2025.py")
    ejecutar("construir_capa_oro_2025.py", "--plata", str(PLATA), "--oro", str(ORO))


if __name__ == "__main__":
    main()
