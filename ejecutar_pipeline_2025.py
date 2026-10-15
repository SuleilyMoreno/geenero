#!/usr/bin/env python3
"""Ejecuta el pipeline 2025 del estudio (filtros: ruralidad + año 2025).

  1. Microdatos locales DANE/DNP -> plata/   (GEIH, ENUT, FIES, TerriData)
  2. Crédito rural por API (Finagro jjvv-55ck, Superfinanciera w9zh-vetq)
  3. Indicadores agregados -> datos_tablero/*.json
  4. Tableros HTML -> index.html + 4 tableros

Uso:
  python ejecutar_pipeline_2025.py                 # todo (requiere microdatos)
  python ejecutar_pipeline_2025.py --sin-microdatos   # solo crédito por API + HTML
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def ejecutar(*args: str) -> None:
    print("\n$", " ".join(args))
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def si_existe(entrada: str, *args: str) -> None:
    """Ejecuta el paso solo si su insumo local existe; si no, los generadores
    conservan los valores ya publicados y lo indican en el aviso del tablero."""
    if any((ROOT / entrada).parent.glob((ROOT / entrada).name)):
        ejecutar(*args)
    else:
        print(f"\n(omitido) {args[0]}: no se encontró {entrada}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sin-microdatos", action="store_true",
                    help="No recalcula GEIH/ENUT/FIES/TerriData; usa los JSON existentes en datos_tablero/")
    args = ap.parse_args()

    if not args.sin_microdatos:
        (ROOT / "plata").mkdir(exist_ok=True)
        ejecutar("decodificar_geih_2025.py", "--datos", "GEIH_2025",
                 "--diccionario", "Diccionario_de_datos_GEIH_2025.xlsx", "--salida", "plata/geih_2025_decodificada")
        ejecutar("procesar_enut_2024_2025.py")
        si_existe("FIES.xlsx", "procesar_fies_2025.py")
        si_existe("Terridata1/TerriData_Dim*.xlsx", "procesar_terridata.py")

    ejecutar("extraer_credito_rural_2025.py")

    if not args.sin_microdatos:
        ejecutar("agrupar_genero_2025.py")
        ejecutar("generar_tablero_calidad_vida_2025.py")
        ejecutar("agrupar_departamento_2025.py")
        ejecutar("generar_tablero_financiero_nacional_2025.py")

    ejecutar("construir_tableros.py")


if __name__ == "__main__":
    main()
