#!/usr/bin/env python3
"""Inclusión financiera de los hogares rurales 2025 (GEIH 2025, CLASE 2/3).

Unidad: hogar (mes_archivo + DIRECTORIO + HOGAR), expandido con FEX_C18 / meses.
El sexo y el nivel educativo corresponden a la persona jefe de hogar
(parentesco = 1). Los datos de crédito (Finagro y Superfinanciera) los aporta
extraer_credito_rural_2025.py.

Salida: datos_tablero/inclusion_financiera_rural_2025.json
"""
from __future__ import annotations

import duckdb

from agrupar_departamento_2025 import INCLUIDO, INCLUIDO_MOVIL, PRODUCTOS
from tablero_comun import PERSONAS, VIVIENDA, geih, guardar_json, meses_geih, peso

# P5222S1..S11 (la S8A1 «¿Cuál?» es texto y no se usa).
NOMBRES = ["Cuenta corriente", "Cuenta de ahorros", "CDT", "Crédito de vivienda", "Crédito de vehículo",
           "Crédito de libre inversión", "Tarjeta de crédito", "Otro producto", "Ningún producto", "No sabe",
           "Plataforma móvil (Nequi, Daviplata…)"]
# P3042, nivel educativo más alto alcanzado (GEIH 2021 en adelante).
NIVEL = """CASE WHEN cod IN (1,2) THEN '1. Ninguno o preescolar'
    WHEN cod=3 THEN '2. Básica primaria' WHEN cod=4 THEN '3. Básica secundaria'
    WHEN cod IN (5,6) THEN '4. Media' WHEN cod IN (7,8,9) THEN '5. Normalista, técnica o tecnológica'
    WHEN cod=10 THEN '6. Universitaria' WHEN cod BETWEEN 11 AND 13 THEN '7. Posgrado' END"""


def main() -> None:
    con = duckdb.connect()
    n = meses_geih(con)
    marcas = ",".join(
        f"MAX(CASE WHEN TRY_CAST({PRODUCTOS}{'' if i == 1 else f'_{i}'} AS INTEGER)=1 THEN 1 ELSE 0 END) p{i}"
        for i in range(1, 12))
    con.execute(f"""CREATE TEMP TABLE h AS
      WITH v AS (SELECT mes_archivo, DIRECTORIO, HOGAR, MAX({peso('x', n)}) w,
                        MAX(TRY_CAST(total_de_personas_en_el_hogar AS INTEGER)) tamano,
                        MAX(CASE WHEN {INCLUIDO} THEN 1 ELSE 0 END) incluido,
                        MAX(CASE WHEN {INCLUIDO_MOVIL} THEN 1 ELSE 0 END) incluido_movil, {marcas}
                 FROM {geih(VIVIENDA)} x GROUP BY 1,2,3),
      j AS (SELECT mes_archivo, DIRECTORIO, HOGAR,
                   CASE TRY_CAST(cual_fue_su_sexo_al_nacer AS INTEGER) WHEN 1 THEN 'Hombres' WHEN 2 THEN 'Mujeres' END sexo,
                   TRY_CAST(cual_es_el_mayor_nivel_educativo_alcanzado AS INTEGER) cod
            FROM {geih(PERSONAS)} WHERE TRY_CAST(cual_es_el_parentesco_de_con_el AS INTEGER)=1)
      SELECT v.*, j.sexo, {NIVEL} nivel FROM v LEFT JOIN j USING (mes_archivo, DIRECTORIO, HOGAR)""")
    productos = con.execute("SELECT " + ",".join(f"100*SUM(p{i}*w)/SUM(w)" for i in range(1, 12)) + " FROM h").fetchone()
    tasa = "100*SUM(incluido*w)/NULLIF(SUM(w),0)"
    educacion = con.execute(f"""SELECT nivel, sexo, {tasa}, COUNT(*) FROM h
        WHERE sexo IS NOT NULL AND nivel IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""").fetchall()
    tamano = con.execute(f"""SELECT CASE WHEN tamano>=6 THEN '6 o más' ELSE CAST(tamano AS VARCHAR) END t, sexo, {tasa}, COUNT(*)
        FROM h WHERE sexo IS NOT NULL AND tamano IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""").fetchall()
    por_sexo = dict(con.execute(f"SELECT sexo, {tasa} FROM h WHERE sexo IS NOT NULL GROUP BY 1").fetchall())
    tasa_movil = tasa.replace("incluido", "incluido_movil")
    por_sexo_movil = dict(con.execute(f"SELECT sexo, {tasa_movil} FROM h WHERE sexo IS NOT NULL GROUP BY 1").fetchall())
    nacional = con.execute(f"SELECT {tasa}, {tasa_movil}, COUNT(*) FROM h").fetchone()
    con.close()

    guardar_json("inclusion_financiera_rural_2025.json", {
        "origen": f"GEIH 2025 ({n} meses), hogares rurales (CLASE 2/3).",
        "pendientes": [],
        "productos_pct": sorted(({"producto": p, "pct": v} for p, v in zip(NOMBRES, productos)), key=lambda x: -x["pct"]),
        "inclusion_nacional": {"tradicional": nacional[0], "con_movil": nacional[1], "hogares_muestra": nacional[2]},
        "inclusion_por_sexo_jefatura": por_sexo,
        "inclusion_movil_por_sexo_jefatura": por_sexo_movil,
        # Se omiten celdas con menos de 30 hogares en la muestra (estimación inestable).
        "inclusion_por_educacion": [{"nivel": a, "sexo": s, "pct": v, "hogares_muestra": m} for a, s, v, m in educacion if m >= 30],
        "inclusion_por_tamano": [{"tamano": a, "sexo": s, "pct": v, "hogares_muestra": m} for a, s, v, m in tamano if m >= 30],
    })


if __name__ == "__main__":
    main()
