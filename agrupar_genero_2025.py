#!/usr/bin/env python3
"""Indicadores del tablero de género rural 2025 (GEIH 2025 + ENUT 2024-2025).

Filtros: GEIH 2025 y ENUT con CLASE 2/3 (centros poblados y rural disperso).
Las uniones hogar-persona usan mes_archivo + DIRECTORIO + HOGAR + ORDEN y los
totales se expanden con FEX_C18 / meses. Los indicadores se publican como
porcentajes o promedios, no como conteos absolutos.

Salida: datos_tablero/genero_rural_2025.json (lo dibuja construir_tableros.py).
"""
from __future__ import annotations

import re

import duckdb

from tablero_comun import FUERZA, OCUPADOS, OTRAS_FORMAS, PERSONAS, PLATA, geih, guardar_json, meses_geih, peso

ENUT = PLATA / "enut_2024_2025_limpia.parquet"
SEXO = {1: "Hombres", 2: "Mujeres"}
ACTIVIDADES = [  # GEIH, módulo Otras formas de trabajo: columna decodificada (código DANE)
    ("Preparar alimentos", "cocinar_lavar_los_platos_poner_la_mesa"),            # P3076S1
    ("Lavar y planchar ropa", "lavar_colgar_planchar_la_ropa_reparar_ropa"),     # P3077S1
    ("Limpiar la vivienda", "limpiar_o_arreglar_la_casa_tender_las"),            # P3078S1
    ("Cuidar niñas y niños", "cuidar_ninas_o_ninos_menores_de_5"),               # P3079S1
    ("Cuidar personas enfermas", "cuidar_personas_enfermas_en_condicion_de_discapacidad"),  # P3081S1
    ("Ayudar con tareas", "ayudar_a_personas_con_tareas_o_trabajos"),            # P3082S1
    ("Traer agua", "traer_agua_para_el_uso_de_este"),                            # P3092
    ("Actividades agropecuarias del hogar", "plantar_regar_abonar_deshierbar_o_cosechar_en"),  # P3094
]
PRINCIPAL = ["Trabajando", "Buscando trabajo", "Estudiando", "Oficios del hogar",
             "Incapacidad permanente para trabajar", "Otra actividad"]
# ENUT 2024-2025: bloques de actividades no remuneradas (horas + minutos del día de referencia).
ENUT_BLOQUES = {
    "trabajo_domestico": ("P1143", "P1142", "P1136", "P1141", "P1140"),  # I2 alimentos, I3 ropa, I4 limpieza, I5 reparaciones, I6 compras
    "cuidado": ("P1135", "P1134", "P1133", "P1132", "P1131", "P1137", "P1114"),  # I12-I16 cuidado directo, I11 menores de 5, I17 apoyo
    "autoconsumo": ("P1126",),  # I8 huerta, animales, leña
}
LLAVE = "mes_archivo, DIRECTORIO, HOGAR, ORDEN"


def por_sexo(con, sql: str) -> dict:
    """Ejecuta una consulta que devuelve (sexo, valor) y la indexa por etiqueta."""
    return {SEXO[s]: v for s, v in con.execute(sql).fetchall() if s in SEXO}


def horas_enut(cols: list[str], prefijos: tuple[str, ...]) -> str:
    """Suma horas + minutos/60 de todos los pares de tiempo de los bloques.

    Cada actividad trae horas (A1) y minutos (A2); en P1140 y P1131 hay un
    segundo par (A3/A4) para la modalidad presencial o una segunda persona.
    """
    partes = []
    for c in cols:
        m = re.match(r"^(P\d{4}S\d+)A([13])$", c)
        if m and m.group(1).startswith(prefijos):
            minutos = f"{m.group(1)}A{int(m.group(2)) + 1}"
            if minutos in cols:
                partes.append(f"COALESCE(TRY_CAST({c} AS DOUBLE),0)+COALESCE(TRY_CAST({minutos} AS DOUBLE),0)/60")
    return "+".join(partes) or "0"


def main() -> None:
    con = duckdb.connect()
    n = meses_geih(con)
    personas = f"""SELECT mes_archivo, DIRECTORIO, HOGAR, ORDEN,
        TRY_CAST(cual_fue_su_sexo_al_nacer AS INTEGER) sexo,
        TRY_CAST(cual_es_el_parentesco_de_con_el AS INTEGER) parentesco,
        {peso('g', n)} w FROM {geih(PERSONAS)} g"""

    # Hogares: tamaño y sexo de quien ejerce la jefatura (parentesco = 1).
    con.execute(f"""CREATE TEMP TABLE hogares AS WITH p AS ({personas})
        SELECT mes_archivo, DIRECTORIO, HOGAR, COUNT(DISTINCT ORDEN) personas,
               MAX(CASE WHEN parentesco=1 THEN sexo END) sexo_jefe,
               MAX(CASE WHEN parentesco=1 THEN w END) w
        FROM p GROUP BY 1,2,3""")
    jefatura = por_sexo(con, "SELECT sexo_jefe, SUM(personas*w)/NULLIF(SUM(w),0) FROM hogares GROUP BY 1")
    jefatura_femenina = con.execute(
        "SELECT 100*SUM(CASE WHEN sexo_jefe=2 THEN w ELSE 0 END)/NULLIF(SUM(w),0) FROM hogares WHERE sexo_jefe IS NOT NULL").fetchone()[0]

    # Ocupados: cada fila del módulo Ocupados es una persona ocupada.
    ocupados = f"""SELECT p.sexo, p.w, CAST(o.rama_de_actividad_empleo_principal AS VARCHAR) rama,
        TRY_CAST(o.ingreso_laborales AS DOUBLE) ingreso
        FROM {geih(OCUPADOS)} o JOIN ({personas}) p USING ({LLAVE})"""
    occ = por_sexo(con, f"SELECT sexo, SUM(w) FROM ({ocupados}) GROUP BY 1")
    agro = por_sexo(con, f"SELECT sexo, SUM(w) FROM ({ocupados}) WHERE lpad(rama,2,'0') LIKE '01%' GROUP BY 1")
    total_occ, total_agro = sum(occ.values()), sum(agro.values())
    ingreso = {SEXO[s]: {"media": m, "mediana": md, "n": k} for s, m, md, k in con.execute(f"""
        SELECT sexo, SUM(ingreso*w)/NULLIF(SUM(w),0), median(ingreso), COUNT(*)
        FROM ({ocupados}) WHERE ingreso > 0 GROUP BY 1""").fetchall() if s in SEXO}

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

    # ENUT: horas por día ponderadas con FEX_C, población rural de 10 años o más (P6040 >= 10:
    # quienes responden el diario de actividades). Las personas que no realizan la actividad cuentan con 0.
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{ENUT}')").fetchall()]
    bloques = {k: horas_enut(cols, v) for k, v in ENUT_BLOQUES.items()}
    fex = "TRY_CAST(replace(CAST(FEX_C AS VARCHAR), ',', '.') AS DOUBLE)"  # la ENUT publica FEX_C con coma decimal
    sel = ",".join(f"SUM(({e})*{fex})/NULLIF(SUM({fex}),0)" for e in bloques.values())
    tiempo = {SEXO[r[0]]: dict(zip(bloques, r[1:])) for r in con.execute(f"""
        SELECT TRY_CAST(P6020 AS INTEGER), {sel} FROM read_parquet('{ENUT}')
        WHERE CAST(CLASE AS VARCHAR) IN ('2','3') AND TRY_CAST(P6040 AS INTEGER) >= 10 GROUP BY 1""").fetchall() if r[0] in SEXO}
    muestra = {
        "personas": con.execute(f"SELECT COUNT(*) FROM {geih(PERSONAS)}").fetchone()[0],
        "ocupados": con.execute(f"SELECT COUNT(*) FROM {geih(OCUPADOS)}").fetchone()[0],
        "hogares": con.execute("SELECT COUNT(*) FROM hogares").fetchone()[0],
        "enut_personas": con.execute(f"SELECT COUNT(*) FROM read_parquet('{ENUT}') WHERE CAST(CLASE AS VARCHAR) IN ('2','3') AND TRY_CAST(P6040 AS INTEGER) >= 10").fetchone()[0],
    }
    con.close()

    guardar_json("genero_rural_2025.json", {
        "muestra": muestra,
        "origen": f"GEIH 2025 ({n} meses) y ENUT 2024-2025, zona rural (CLASE 2/3).",
        "pendientes": [],
        "jefatura_personas_promedio": jefatura,
        "jefatura_femenina_pct": jefatura_femenina,
        "tiempo_enut_horas_dia": tiempo,
        "participacion_mujeres": {"valor": 100 * occ.get("Mujeres", 0) / total_occ if total_occ else None,
                                  "universo": "ocupados"},
        "agro_pct": {s: 100 * v / total_agro for s, v in agro.items()} if total_agro else {},
        "ocupados_pct": {s: 100 * v / total_occ for s, v in occ.items()} if total_occ else {},
        "ingreso_laboral": ingreso,
        "actividades": {"etiquetas": [a for a, _ in ACTIVIDADES], **actividades},
        "actividad_principal": {"etiquetas": PRINCIPAL, **principal},
    })


if __name__ == "__main__":
    main()
