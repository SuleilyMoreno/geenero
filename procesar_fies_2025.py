#!/usr/bin/env python3
"""Extrae indicadores FIES 2025 del anexo publicado por el DANE.

El archivo tiene títulos en las primeras filas. Los datos comienzan en la
fila 13 de Excel (índice 12 de pandas). Se conservan únicamente las filas
de ``Centros poblados y rural disperso``.
"""

from pathlib import Path
import argparse
import pandas as pd


RURAL = "centros poblados y rural disperso"


def normalizar(s):
    return (s.astype("string").str.strip().str.lower()
            .str.replace(r"\s+", " ", regex=True))


def preparar_area(df):
    df = df.copy()
    df["Departamento"] = df["Departamento"].ffill()
    area = normalizar(df["Área"])
    return df.loc[area.eq(RURAL)].copy()


def extraer_prevalencia(path):
    # Cuadro 2: prevalencia de inseguridad alimentaria moderada/grave y grave.
    raw = pd.read_excel(path, sheet_name="Cuadro 2", header=None)
    d = raw.iloc[12:].copy()
    d = d.iloc[:, :9]
    d.columns = [
        "Departamento", "Área", "Total_Hogares",
        "Inseguridad_Moderada_Grave_Pct", "Inseguridad_Moderada_Grave_LInf",
        "Inseguridad_Moderada_Grave_LSup", "Inseguridad_Grave_Pct",
        "Inseguridad_Grave_LInf", "Inseguridad_Grave_LSup",
    ]
    d = preparar_area(d)
    for c in d.columns[2:]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["Anio"] = 2025
    d["Fuente"] = "DANE ECV 2025 - FIES, Cuadro 2"
    return d[["Anio", "Departamento", "Área", "Total_Hogares",
              "Inseguridad_Moderada_Grave_Pct", "Inseguridad_Moderada_Grave_LInf",
              "Inseguridad_Moderada_Grave_LSup", "Inseguridad_Grave_Pct",
              "Inseguridad_Grave_LInf", "Inseguridad_Grave_LSup", "Fuente"]]


def extraer_experiencias(path):
    # Cuadro 1: ocho experiencias individuales de inseguridad alimentaria.
    raw = pd.read_excel(path, sheet_name="Cuadro 1", header=None)
    d = raw.iloc[13:].copy()
    d = d.iloc[:, :70]
    d.iloc[:, 0] = d.iloc[:, 0].ffill()
    d = d.loc[normalizar(d.iloc[:, 1]).eq(RURAL)].copy()
    nombres = [
        "Preocupacion_alimentos", "Alimentos_no_saludables",
        "Poca_variedad", "Salto_comida", "Comio_menos",
        "Se_quedo_sin_alimentos", "Hambre_sin_comer",
        "No_comio_dia_entero",
    ]
    registros = []
    for _, row in d.iterrows():
        for i, nombre in enumerate(nombres):
            base = 6 + i * 8
            registros.append({
                "Anio": 2025, "Departamento": row.iloc[0],
                "Área": row.iloc[1], "Indicador": nombre,
                "Total": pd.to_numeric(row.iloc[base], errors="coerce"),
                "Porcentaje": pd.to_numeric(row.iloc[base + 4], errors="coerce"),
                "Fuente": "DANE ECV 2025 - FIES, Cuadro 1",
            })
    return pd.DataFrame(registros)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("FIES.xlsx"))
    ap.add_argument("--output-dir", type=Path, default=Path("plata"))
    args = ap.parse_args()
    prevalencia = extraer_prevalencia(args.input)
    experiencias = extraer_experiencias(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out1 = args.output_dir / "fies_2025_rural_prevalencia.parquet"
    out2 = args.output_dir / "fies_2025_rural_experiencias.parquet"
    prevalencia.to_parquet(out1, index=False)
    experiencias.to_parquet(out2, index=False)
    print(f"{out1}: {len(prevalencia):,} filas")
    print(f"{out2}: {len(experiencias):,} filas")
    print(prevalencia[["Departamento", "Inseguridad_Moderada_Grave_Pct", "Inseguridad_Grave_Pct"]].head().to_string(index=False))


if __name__ == "__main__":
    main()
