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

from generar_tablero_calidad_vida_2025 import FIES_PREV, IPM_SQL
from tablero_comun import (DEPARTAMENTOS, RURALIDAD_CSV, VIVIENDA, dpto_por_nombre, geih,
                           guardar_json, meses_geih, peso)

PRODUCTOS = "cuales_de_los_siguientes_productos_financieros_utiliza"
# Productos 1-7: cuenta corriente, ahorros, CDT, crédito vivienda, vehículo, libre inversión, tarjeta.
INCLUIDO = " OR ".join(f"TRY_CAST({PRODUCTOS}{'' if i == 1 else f'_{i}'} AS INTEGER)=1" for i in range(1, 8))


def main() -> None:
    with RURALIDAD_CSV.open(encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f, delimiter=";"))
    total = Counter(r["Municipaly"].zfill(5)[:2] for r in filas)
    rurales = Counter(r["Municipaly"].zfill(5)[:2] for r in filas
                      if r["Categoria_"].strip().lower() in {"rural", "rural disperso"})

    con = duckdb.connect()
    n = meses_geih(con)
    ipm = dict(con.execute(IPM_SQL).fetchall())
    fies = {dpto_por_nombre(d): v for d, v in con.execute(
        f"SELECT Departamento, Inseguridad_Moderada_Grave_Pct FROM read_parquet('{FIES_PREV}')").fetchall()}
    inclusion = dict(con.execute(f"""
        WITH h AS (SELECT LPAD(CAST(DPTO AS VARCHAR),2,'0') DPTO, MAX({peso('x', n)}) w,
                          MAX(CASE WHEN {INCLUIDO} THEN 1 ELSE 0 END) incluido
                   FROM {geih(VIVIENDA)} x GROUP BY mes_archivo, 1, DIRECTORIO, HOGAR)
        SELECT DPTO, 100*SUM(incluido*w)/NULLIF(SUM(w),0) FROM h GROUP BY 1""").fetchall())
    con.close()

    guardar_json("departamentos_rural_2025.json", {
        "origen": f"Categorías de ruralidad DNP, TerriData IPM 2025, FIES 2025 rural y GEIH 2025 ({n} meses) rural.",
        "pendientes": [],
        "por_dpto": [{
            "DPTO": d, "departamento": nombre,
            "municipios_total": total[d], "municipios_rurales": rurales[d],
            "ruralidad_pct": 100 * rurales[d] / total[d] if total[d] else None,
            "ipm": ipm.get(d), "inseguridad_alimentaria": fies.get(d),
            "inclusion_financiera_pct": inclusion.get(d),
        } for d, nombre in DEPARTAMENTOS.items()],
    })


if __name__ == "__main__":
    main()
