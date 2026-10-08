#!/usr/bin/env python3
"""Procesa los microdatos locales de la ENUT 2024-2025 del DANE.

No etiqueta el operativo como año calendario 2025: la operación cubre
septiembre de 2024 a agosto de 2025.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def cargar_diccionario(path: Path) -> dict[str, str]:
    """Obtiene el texto de la pregunta y una etiqueta corta para cada variable ENUT."""
    raw = pd.read_excel(path, header=None)
    out = {}
    for row in raw.itertuples(index=False, name=None):
        vals = [str(v).strip() for v in row if pd.notna(v)]
        if not vals:
            continue
        code = vals[0]
        if not code.startswith("P"):
            continue
        text = next((v for v in vals[1:] if len(v) > 12), "")
        if not text:
            continue
        text = text.replace("${NP_CC_C2}", "la persona").replace("${diar}-${mesr}-${anior}", "el día").strip()
        if "limpieza y mantenimiento" in text.lower(): short = "Labores de limpieza y mantenimiento"
        elif "cuidado personal" in text.lower(): short = "Cuidado personal"
        elif "cuidar" in text.lower() or "cuidado" in text.lower(): short = "Cuidado de personas"
        elif "aliment" in text.lower() or "cocinar" in text.lower(): short = "Preparación de alimentos"
        else: short = text[:100]
        out.setdefault(code, {"pregunta": text, "tema": short})
    return out

def read_csv(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, sep=";", encoding="latin1", dtype=str, low_memory=False)
    d.columns = [str(c).lstrip("ï»¿").strip() for c in d.columns]
    return d

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("ENUT"))
    ap.add_argument("--output", type=Path, default=Path("plata/enut_2024_2025_limpia.parquet"))
    ap.add_argument("--diccionario", type=Path, default=Path("Diccionario_ENUT_2024_2025_1.xlsx"))
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
    # Diccionario legible para auditoría y para que el dashboard no dependa de
    # códigos opacos. Las columnas originales y sus llaves se conservan.
    dic = cargar_diccionario(args.diccionario)
    base["periodo_operativo"] = "septiembre 2024-agosto 2025"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    base.to_parquet(args.output, index=False, compression="zstd")
    import json
    (args.output.parent / "enut_diccionario_decodificado.json").write_text(
        json.dumps(dic, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Compatibilidad explícita: no se presenta como año calendario; contiene el mismo archivo etiquetado.
    compat = args.output.parent / "enut_2025_limpia.parquet"
    base.to_parquet(compat, index=False, compression="zstd")
    print(f"OK: {len(base):,} personas ENUT 2024-2025 -> {args.output}")
    print(f"Compatibilidad: {compat} (periodo_fuente=ENUT 2024-2025; no es año calendario 2025)")

if __name__ == "__main__": main()
