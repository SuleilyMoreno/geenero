#!/usr/bin/env python3
"""Indicadores del tablero territorial (departamentos) 2025.

Grano: departamento (DPTO = 2 primeros dígitos de DIVIPOLA). Cada fuente se
agrega a DPTO antes de unirse 1:1:
  - Ruralidad: categorías DNP por municipio (referencias/categorias_ruralidad_dnp.csv).
  - IPM 2025 (TerriData), FIES 2025 rural (unión por código DPTO).
  - Inclusión financiera: % de hogares rurales GEIH 2025 con al menos un producto.
  - El crédito rural por departamento lo aporta credito_rural_2025.json.

Salida: datos_tablero/departamentos_rural_2025.json
"""
from __future__ import annotations

import csv
from collections import Counter

import duckdb

from generar_tablero_calidad_vida_2025 import FIES_PREV, IPM_SQL, TERRIDATA
from tablero_comun import (DEPARTAMENTOS, RURALIDAD_CSV, VIVIENDA, dpto_por_nombre, geih,
                           guardar_json, meses_geih, peso, previo)

PRODUCTOS = "cuales_de_los_siguientes_productos_financieros_utiliza"
# Productos 1-7: cuenta corriente, ahorros, CDT, crédito vivienda, vehículo, libre inversión, tarjeta.
INCLUIDO = " OR ".join(f"TRY_CAST({PRODUCTOS}{'' if i == 1 else f'_{i}'} AS INTEGER)=1" for i in range(1, 8))
# P5222S11: plataforma móvil (Nequi, Daviplata, Bancolombia a la mano, Movii...).
INCLUIDO_MOVIL = f"{INCLUIDO} OR TRY_CAST({PRODUCTOS}_11 AS INTEGER)=1"


def main() -> None:
    with RURALIDAD_CSV.open(encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f, delimiter=";"))
    total = Counter(r["Municipaly"].zfill(5)[:2] for r in filas)
    rurales = Counter(r["Municipaly"].zfill(5)[:2] for r in filas
                      if r["Categoria_"].strip().lower() in {"rural", "rural disperso"})

    con = duckdb.connect()
    n = meses_geih(con)
    ant = {d["DPTO"]: d for d in previo("departamentos_rural_2025.json").get("por_dpto", [])}
    pendientes = []
    if TERRIDATA.exists():
        ipm = dict(con.execute(IPM_SQL).fetchall())
    else:
        ipm = {d: r.get("ipm") for d, r in ant.items()}
        pendientes.append("IPM (TerriData): se conservan los valores publicados; falta plata/terridata_dim1_limpia.parquet para recalcular.")
    # FIES publica los hogares en miles.
    fies = {dpto_por_nombre(d): (v, v / 100 * t * 1000 if v is not None and t is not None else None) for d, v, t in con.execute(
        f"SELECT Departamento, Inseguridad_Moderada_Grave_Pct, Total_Hogares FROM read_parquet('{FIES_PREV}')").fetchall()}
    inclusion = {d: r for d, *r in con.execute(f"""
        WITH h AS (SELECT LPAD(CAST(DPTO AS VARCHAR),2,'0') DPTO, MAX({peso('x', n)}) w,
                          MAX(CASE WHEN {INCLUIDO} THEN 1 ELSE 0 END) incluido,
                          MAX(CASE WHEN {INCLUIDO_MOVIL} THEN 1 ELSE 0 END) incluido_movil
                   FROM {geih(VIVIENDA)} x GROUP BY mes_archivo, 1, DIRECTORIO, HOGAR)
        SELECT DPTO, 100*SUM(incluido*w)/NULLIF(SUM(w),0), 100*SUM(incluido_movil*w)/NULLIF(SUM(w),0),
               SUM(incluido*w), SUM(incluido_movil*w), SUM(w) FROM h GROUP BY 1""").fetchall()}
    con.close()

    guardar_json("departamentos_rural_2025.json", {
        "origen": f"Categorías de ruralidad DNP, TerriData IPM 2025, FIES 2025 rural y GEIH 2025 ({n} meses) rural.",
        "pendientes": pendientes,
        "por_dpto": [{
            "DPTO": d, "departamento": nombre,
            "municipios_total": total[d], "municipios_rurales": rurales[d],
            "ruralidad_pct": 100 * rurales[d] / total[d] if total[d] else None,
            "ipm": ipm.get(d), "inseguridad_alimentaria": fies.get(d, (None, None))[0],
            "inseguridad_hogares": fies.get(d, (None, None))[1],
            "inclusion_financiera_pct": inclusion.get(d, [None] * 5)[0],
            "inclusion_con_movil_pct": inclusion.get(d, [None] * 5)[1],
            "hogares_incluidos": inclusion.get(d, [None] * 5)[2],
            "hogares_incluidos_movil": inclusion.get(d, [None] * 5)[3],
            "hogares_estimados": inclusion.get(d, [None] * 5)[4],
        } for d, nombre in DEPARTAMENTOS.items()],
    })


if __name__ == "__main__":
    main()
