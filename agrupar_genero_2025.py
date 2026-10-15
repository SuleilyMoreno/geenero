#!/usr/bin/env python3
"""Indicadores del tablero de género rural 2025 (GEIH 2025 + ENUT 2024-2025).

Filtros: GEIH 2025 y ENUT con CLASE 2/3 (centros poblados y rural disperso).
Las uniones hogar-persona usan mes_archivo + DIRECTORIO + HOGAR + ORDEN y los
totales se expanden con FEX_C18 / meses. Los indicadores se publican como
porcentajes o promedios, no como conteos absolutos.

Salida: datos_tablero/genero_rural_2025.json (lo dibuja construir_tableros.py).
"""
from __future__ import annotations

import duckdb

from tablero_comun import FUERZA, OCUPADOS, OTRAS_FORMAS, PERSONAS, PLATA, geih, guardar_json, meses_geih, peso

ENUT = PLATA / "enut_2024_2025_limpia.parquet"
SEXO = {1: "Hombres", 2: "Mujeres"}
ACTIVIDADES = [
    ("Preparar alimentos", "cocinar_lavar_los_platos_poner_la_mesa"),
    ("Lavar y planchar ropa", "lavar_colgar_planchar_la_ropa_reparar_ropa"),
    ("Limpiar la vivienda", "limpiar_o_arreglar_la_casa_tender_las"),
    ("Cuidar niñas y niños", "cuidar_ninas_o_ninos_menores_de_5"),
    ("Cuidar personas enfermas", "cuidar_personas_enfermas_en_condicion_de_discapacidad"),
    ("Ayudar con tareas", "ayudar_a_personas_con_tareas_o_trabajos"),
    ("Traer agua", "traer_agua_para_el_uso_de_este"),
    ("Actividades agropecuarias del hogar", "plantar_regar_abonar_deshierbar_o_cosechar_en"),
]
PRINCIPAL = ["Trabajando", "Buscando trabajo", "Estudiando", "Oficios del hogar",
             "Incapacidad permanente para trabajar", "Otra actividad"]
LLAVE = "mes_archivo, DIRECTORIO, HOGAR, ORDEN"


def por_sexo(con, sql: str) -> dict:
    """Ejecuta una consulta que devuelve (sexo, valor) y la indexa por etiqueta."""
    return {SEXO[s]: v for s, v in con.execute(sql).fetchall() if s in SEXO}


def main() -> None:
    con = duckdb.connect()
    n = meses_geih(con)
    personas = f"""SELECT mes_archivo, DIRECTORIO, HOGAR, ORDEN,
        TRY_CAST(cual_fue_su_sexo_al_nacer AS INTEGER) sexo,
        TRY_CAST(cual_es_el_parentesco_de_con_el AS INTEGER) parentesco,
        {peso('g', n)} w FROM {geih(PERSONAS)} g"""

    # Personas por hogar según el sexo de quien ejerce la jefatura (ponderado por hogar).
    jefatura = por_sexo(con, f"""
        WITH p AS ({personas}), hogares AS (
          SELECT mes_archivo, DIRECTORIO, HOGAR, COUNT(DISTINCT ORDEN) personas,
                 MAX(CASE WHEN parentesco=1 THEN sexo END) sexo_jefe,
                 MAX(CASE WHEN parentesco=1 THEN w END) w
          FROM p GROUP BY 1,2,3)
        SELECT sexo_jefe, SUM(personas*w)/NULLIF(SUM(w),0) FROM hogares GROUP BY 1""")

    # Ocupados: cada fila del módulo Ocupados es una persona ocupada.
    ocupados = f"""SELECT p.sexo, p.w, CAST(o.rama_de_actividad_empleo_principal AS VARCHAR) rama
        FROM {geih(OCUPADOS)} o JOIN ({personas}) p USING ({LLAVE})"""
    occ = por_sexo(con, f"SELECT sexo, SUM(w) FROM ({ocupados}) GROUP BY 1")
    agro = por_sexo(con, f"SELECT sexo, SUM(w) FROM ({ocupados}) WHERE lpad(rama,2,'0') LIKE '01%' GROUP BY 1")
    total_occ, total_agro = sum(occ.values()), sum(agro.values())

    # Actividad principal (P6240), porcentaje dentro de cada sexo.
    principal = {s: [0.0] * 6 for s in SEXO.values()}
    for s, cod, v in con.execute(f"""
        SELECT p.sexo, TRY_CAST(f.en_que_actividad_ocupo_la_mayor_parte AS INTEGER) cod, SUM(p.w)
        FROM {geih(FUERZA)} f JOIN ({personas}) p USING ({LLAVE})
        WHERE cod BETWEEN 1 AND 6 GROUP BY 1,2""").fetchall():
        if s in SEXO:
            principal[SEXO[s]][cod - 1] = v
    principal = {s: [100 * x / sum(v) if sum(v) else None for x in v] for s, v in principal.items()}

    # Otras formas de trabajo: % de personas de cada sexo que realiza cada actividad.
    columnas = ",".join(
        f"100*SUM(CASE WHEN TRY_CAST(o.\"{c}\" AS INTEGER)=1 THEN p.w ELSE 0 END)/NULLIF(SUM(p.w),0)"
        for _, c in ACTIVIDADES)
    actividades = {SEXO[r[0]]: list(r[1:]) for r in con.execute(f"""
        SELECT p.sexo, {columnas} FROM {geih(OTRAS_FORMAS)} o JOIN ({personas}) p USING ({LLAVE})
        GROUP BY 1""").fetchall() if r[0] in SEXO}

    # ENUT: horas por día (horas + minutos/60) ponderadas con FEX_C, población rural.
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{ENUT}')").fetchall()]

    def horas(prefijo: str) -> str:
        pares = [(c, c[:-2] + "A2") for c in cols if c.startswith(prefijo) and c.endswith("A1")]
        return "+".join(f"COALESCE(TRY_CAST({a} AS DOUBLE),0)+COALESCE(TRY_CAST({b} AS DOUBLE),0)/60"
                        for a, b in pares) or "0"

    extra = "+".join(horas(p) for p in ("P1136", "P1143", "P1140"))
    tiempo = {SEXO[s]: {"actividades_extra": e, "cuidado": c} for s, e, c in con.execute(f"""
        SELECT TRY_CAST(P6020 AS INTEGER),
               SUM(({extra})*TRY_CAST(FEX_C AS DOUBLE))/NULLIF(SUM(TRY_CAST(FEX_C AS DOUBLE)),0),
               SUM(({horas('P1137')})*TRY_CAST(FEX_C AS DOUBLE))/NULLIF(SUM(TRY_CAST(FEX_C AS DOUBLE)),0)
        FROM read_parquet('{ENUT}') WHERE CAST(CLASE AS VARCHAR) IN ('2','3') GROUP BY 1""").fetchall()
        if s in SEXO}
    muestra = {
        "personas": con.execute(f"SELECT COUNT(*) FROM {geih(PERSONAS)}").fetchone()[0],
        "enut_personas": con.execute(f"SELECT COUNT(*) FROM read_parquet('{ENUT}') WHERE CAST(CLASE AS VARCHAR) IN ('2','3')").fetchone()[0],
    }
    con.close()

    guardar_json("genero_rural_2025.json", {
        "muestra": muestra,
        "origen": f"GEIH 2025 ({n} meses) y ENUT 2024-2025, zona rural (CLASE 2/3).",
        "pendientes": [],
        "jefatura_personas_promedio": jefatura,
        "tiempo_enut_horas_dia": tiempo,
        "participacion_mujeres": {"valor": 100 * occ.get("Mujeres", 0) / total_occ if total_occ else None,
                                  "universo": "ocupados"},
        "agro_pct": {s: 100 * v / total_agro for s, v in agro.items()} if total_agro else {},
        "actividades": {"etiquetas": [a for a, _ in ACTIVIDADES], **actividades},
        "actividad_principal": {"etiquetas": PRINCIPAL, **principal},
    })


if __name__ == "__main__":
    main()
