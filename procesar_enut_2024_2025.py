#!/usr/bin/env python3
"""Procesa los microdatos locales de la ENUT 2024-2025 del DANE.

No etiqueta el operativo como año calendario 2025: la operación cubre
septiembre de 2024 a agosto de 2025.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def read_csv(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, sep=";", encoding="latin1", dtype=str, low_memory=False)
    d.columns = [str(c).lstrip("ï»¿").strip() for c in d.columns]
    return d

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("ENUT"))
    ap.add_argument("--output", type=Path, default=Path("plata/enut_2024_2025_limpia.parquet"))
    args = ap.parse_args()
    c1, c3, c8 = read_csv(args.input / "ENUT_C1.csv"), read_csv(args.input / "ENUT_C3.csv"), read_csv(args.input / "ENUT_C8.csv")
    keys = ["DIRECTORIO", "SECUENCIA_P", "ORDEN"]
    # C1 es vivienda/hogar; C3 y C8 son persona/uso del tiempo.
    base = c3.merge(c1[["DIRECTORIO", "DPTO", "CLASE", "REGION1", "REGION2", "FEX_C"]], on="DIRECTORIO", how="left", validate="many_to_one")
    base = base.merge(c8, on=keys, how="left", validate="one_to_one", suffixes=("", "_C8"))
    base["periodo_fuente"] = "ENUT 2024-2025"
    base["anio_recoleccion_filtrable"] = pd.NA
    # Conserva los códigos y agrega tipos numéricos auxiliares para las variables de tiempo.
    for col in base.columns:
        if col.startswith("P"):
            converted = pd.to_numeric(base[col], errors="coerce")
            if converted.notna().any(): base[col + "_num"] = converted
    args.output.parent.mkdir(parents=True, exist_ok=True)
    base.to_parquet(args.output, index=False, compression="zstd")
    # Compatibilidad explícita: no se presenta como año calendario; contiene el mismo archivo etiquetado.
    compat = args.output.parent / "enut_2025_limpia.parquet"
    base.to_parquet(compat, index=False, compression="zstd")
    print(f"OK: {len(base):,} personas ENUT 2024-2025 -> {args.output}")
    print(f"Compatibilidad: {compat} (periodo_fuente=ENUT 2024-2025; no es año calendario 2025)")

if __name__ == "__main__": main()
