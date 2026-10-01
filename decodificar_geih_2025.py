#!/usr/bin/env python3
"""Decodifica GEIH_2025 usando el diccionario oficial del DANE.

Produce un parquet por mes y módulo en ``plata/geih_2025_decodificada``.
No concatena módulos con esquemas distintos ni inventa identificadores municipales.
"""
from __future__ import annotations
import argparse, re, unicodedata
from pathlib import Path
import pandas as pd

KEYS = {"PERIODO", "MES", "PER", "DIRECTORIO", "SECUENCIA_P", "SECUENCIA_H", "ORDEN", "HOGAR", "REGIS", "AREA", "CLASE", "FEX_C18", "DPTO"}

def clean(x: object) -> str:
    s = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s

def short_name(code: str, description: object) -> str:
    if code in KEYS:
        return code
    d = clean(description)
    if not d or d == "nan":
        return code
    # Mantener nombres suficientemente cortos y únicos; el código queda en el mapa.
    words = d.split("_")
    result = "_".join(words[:7])[:58].strip("_")
    return result or code

def dictionary(path: Path) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    raw = pd.read_excel(path, sheet_name="Plantilla Diccionario de Datos", header=0, dtype=str)
    raw.columns = [str(c).strip() for c in raw.columns]
    code_col = next(c for c in raw.columns if "Nombre de la variable" in c and "columna" in c)
    desc_col = next(c for c in raw.columns if "Descripción de la variable" in c)
    domain_col = next((c for c in raw.columns if "Dominios" in c), None)
    names, domains = {}, {}
    for _, row in raw.iterrows():
        code = str(row.get(code_col, "")).strip()
        if not code or code == "nan":
            continue
        names[code] = short_name(code, row.get(desc_col, ""))
        if domain_col and pd.notna(row.get(domain_col)):
            # El diccionario puede listar ``1: Si; 2: No`` o variantes similares.
            text = str(row[domain_col])
            pairs = re.findall(r"(?:^|[;|,])\s*([A-Za-z0-9_-]+)\s*[:=]\s*([^;|,]+)", text)
            if pairs:
                domains[code] = {k.strip(): v.strip() for k, v in pairs}
    return names, domains

def unique_names(columns: list[str], names: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    used: dict[str, int] = {}; output = []; reverse = {}
    for code in columns:
        base = names.get(code, code)
        n = used.get(base, 0) + 1; used[base] = n
        target = base if n == 1 else f"{base}_{n}"
        output.append(target); reverse[target] = code
    return output, reverse

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", type=Path, default=Path("GEIH_2025"))
    ap.add_argument("--diccionario", type=Path, default=Path("Diccionario_de_datos_GEIH_2025.xlsx"))
    ap.add_argument("--salida", type=Path, default=Path("plata/geih_2025_decodificada"))
    args = ap.parse_args()
    names, domains = dictionary(args.diccionario); args.salida.mkdir(parents=True, exist_ok=True)
    total = 0
    for source in sorted(args.datos.glob("* 2025/*.CSV")):
        df = pd.read_csv(source, sep=";", encoding="latin1", dtype=str, low_memory=False)
        original = list(df.columns); new, reverse = unique_names(original, names)
        df.columns = new
        for new_col, code in reverse.items():
            if code in domains:
                df[new_col] = df[new_col].map(lambda v: domains[code].get(str(v).strip(), v) if pd.notna(v) else v)
        month = clean(source.parent.name).replace("_2025", "")
        output = args.salida / f"{month}__{clean(source.stem)}.parquet"
        df.to_parquet(output, index=False, compression="zstd")
        (output.with_suffix(".columns.csv")).write_text("codigo_dane,nombre_corto\n" + "\n".join(f"{c},{n}" for c,n in zip(original,new)), encoding="utf-8")
        total += 1; print(f"OK {source} -> {output} ({len(df):,} filas)")
    print(f"Decodificados {total} archivos. Salida: {args.salida}")

if __name__ == "__main__": main()
