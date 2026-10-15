#!/usr/bin/env python3
"""Indicadores del tablero de calidad de vida rural 2025.

Fuentes y filtros:
  - GEIH 2025, módulos Vivienda/hogar y Ocupados, CLASE 2/3 (rural).
  - FIES/ECV 2025, área "Centros poblados y rural disperso".
  - TerriData: IPM 2025 departamental.
Grano de integración: departamento (DPTO). Cada fuente se agrega primero a DPTO
y después se une 1:1; FIES se une por código DPTO (no por nombre).

Salida: datos_tablero/calidad_vida_rural_2025.json
"""
from __future__ import annotations

import duckdb

from tablero_comun import (DEPARTAMENTOS, OCUPADOS, PLATA, VIVIENDA, dpto_por_nombre, geih,
                           guardar_json, meses_geih, peso, previo)

FIES_PREV = PLATA / "fies_2025_rural_prevalencia.parquet"
FIES_EXP = PLATA / "fies_2025_rural_experiencias.parquet"
TERRIDATA = PLATA / "terridata_dim1_limpia.parquet"
SERVICIOS = [  # columna decodificada -> servicio (P4030S1, S2, S3, S4, S5)
    ("energia", "Energía eléctrica", "con_cuales_de_los_siguientes_servicios_cuenta"),
    ("gas", "Gas natural", "con_cuales_de_los_siguientes_servicios_cuenta_3"),
    ("alcantarillado", "Alcantarillado", "con_cuales_de_los_siguientes_servicios_cuenta_4"),
    ("basuras", "Recolección de basuras", "con_cuales_de_los_siguientes_servicios_cuenta_5"),
    ("acueducto", "Acueducto", "con_cuales_de_los_siguientes_servicios_cuenta_7"),
]
SI = "('1','Si','SI','Sí')"
IPM_SQL = f"""SELECT DPTO, AVG(dato_numerico) ipm FROM read_parquet('{TERRIDATA}')
    WHERE indicador_nombre='ipm' AND "Año"=2025 AND RIGHT(DIVIPOLA,3)='000' GROUP BY 1"""


def main() -> None:
    con = duckdb.connect()
    n = meses_geih(con)
    flags = ",".join(f"MAX(CASE WHEN CAST(\"{c}\" AS VARCHAR) IN {SI} THEN 1 ELSE 0 END) {k}" for k, _, c in SERVICIOS)
    con.execute(f"""CREATE TEMP TABLE hogares AS
      WITH v AS (
        SELECT mes_archivo, LPAD(CAST(DPTO AS VARCHAR),2,'0') DPTO, DIRECTORIO, HOGAR,
               MAX({peso('x', n)}) w, MAX(TRY_CAST(total_de_personas_en_el_hogar AS DOUBLE)) personas, {flags},
               -- P5080 5-7: leña o carbón de leña, carbón mineral, desechos
               MAX(CASE WHEN TRY_CAST(con_que_energia_o_combustibe_cocinan_principalmente AS INTEGER) IN (5,6,7) THEN 1 ELSE 0 END) amb_cocina,
               -- P5040 2-5: la tiran a fuente de agua o lote, la queman o entierran, otra forma
               MAX(CASE WHEN TRY_CAST(como_eliminan_principalmente_la_basura_en_este AS INTEGER) IN (2,3,4,5) THEN 1 ELSE 0 END) amb_basura,
               -- P5020 3-6: inodoro sin conexión, letrina, bajamar, sin servicio sanitario
               MAX(CASE WHEN TRY_CAST(el_servicio_sanitario_que_utiliza_el_hogar AS INTEGER) IN (3,4,5,6) THEN 1 ELSE 0 END) amb_sanitario
        FROM {geih(VIVIENDA)} x GROUP BY 1,2,3,4),
      o AS (
        SELECT mes_archivo, DIRECTORIO, HOGAR, COUNT(DISTINCT ORDEN) ocupados,
               SUM(COALESCE(TRY_CAST(ingreso_laborales AS DOUBLE),0)) ingreso
        FROM {geih(OCUPADOS)} GROUP BY 1,2,3)
      SELECT v.*, GREATEST(amb_cocina, amb_basura, amb_sanitario) contaminacion, COALESCE(o.ocupados,0) ocupados, o.ingreso, o.ingreso/NULLIF(v.personas,0) ingreso_persona
      FROM v LEFT JOIN o USING (mes_archivo, DIRECTORIO, HOGAR)""")

    def pct(expr: str) -> str:
        return f"100*SUM(CAST(({expr}) AS DOUBLE)*w)/NULLIF(SUM(w),0)"

    def n(expr: str) -> str:  # hogares estimados (Σ w) que cumplen la condición
        return f"SUM(CAST(({expr}) AS DOUBLE)*w)"

    cob = ",".join(f"{pct(k)} cobertura_{k}" for k, _, _ in SERVICIOS)
    geih_dpto = con.execute(f"""SELECT DPTO, COUNT(*) hogares_muestra, SUM(w) hogares_estimados, SUM(personas*w)/SUM(w) personas_hogar,
          {n('contaminacion')} contaminacion_n, {n('acueducto')} acueducto_n,
          SUM(ingreso_persona*w) FILTER (WHERE ocupados>0)/SUM(w) FILTER (WHERE ocupados>0) ingreso_persona_media,
          {pct('contaminacion')} contaminacion_proxy_pct, {cob}
        FROM hogares GROUP BY 1""").fetchdf().set_index("DPTO")
    nacional = con.execute(f"SELECT COUNT(*), {pct('contaminacion')}, {cob} FROM hogares").fetchone()
    servicios_n = con.execute("SELECT " + ",".join(n(k) for k, _, _ in SERVICIOS) + ", SUM(w), " + n("contaminacion") + " FROM hogares").fetchone()
    hogares_estimados = servicios_n[-2]
    nombres_amb = ["Cocina con leña, carbón o desechos", "Quema, entierra o tira la basura", "Sanitario sin conexión o sin servicio"]
    ambiental = dict(zip(nombres_amb, con.execute(f"SELECT {pct('amb_cocina')}, {pct('amb_basura')}, {pct('amb_sanitario')} FROM hogares").fetchone()))
    ambiental_n = dict(zip(nombres_amb, con.execute(f"SELECT {n('amb_cocina')}, {n('amb_basura')}, {n('amb_sanitario')} FROM hogares").fetchone()))

    def resumen(col: str) -> dict:
        r = con.execute(f"""SELECT COUNT(*), quantile_cont({col},0.05), quantile_cont({col},0.25), median({col}),
            quantile_cont({col},0.75), quantile_cont({col},0.95), AVG({col})
            FROM hogares WHERE ocupados>0 AND {col}>=0""").fetchone()
        return dict(zip(["n", "p5", "q1", "mediana", "q3", "p95", "media"], r))

    proporcion = "LEAST(ocupados/NULLIF(personas,0),1)"
    grupos_ocu = [f"{proporcion}=0", f"{proporcion}>0 AND {proporcion}<=0.5", f"{proporcion}>0.5 AND {proporcion}<1", f"{proporcion}>=1"]
    ocupacion = con.execute("SELECT " + ",".join(pct(g) for g in grupos_ocu) + " FROM hogares").fetchone()
    ocupacion_n = con.execute("SELECT " + ",".join(n(g) for g in grupos_ocu) + " FROM hogares").fetchone()

    # FIES y TerriData son anexos que se procesan aparte; si no están, se conservan
    # los valores ya publicados y se avisa en el tablero.
    ant, pendientes = previo("calidad_vida_rural_2025.json"), []
    ant_dpto = {d["DPTO"]: d for d in ant.get("por_dpto", [])}
    if TERRIDATA.exists():
        ipm = dict(con.execute(IPM_SQL).fetchall())
        terri_cols = [r[0] for r in con.execute(f"SELECT DISTINCT indicador_nombre FROM read_parquet('{TERRIDATA}')").fetchall()]
        componentes = [c for c in terri_cols if c.endswith("centros_poblados_y_rural_disperso")]
        ipm_rural = {k.replace("_en_centros_poblados_y_rural_disperso", "").replace("ipm_centros_poblados_y_rural_disperso", "IPM rural total")
                     .replace("_", " "): v for k, v in con.execute(f"""SELECT indicador_nombre, AVG(dato_numerico) FROM read_parquet('{TERRIDATA}')
            WHERE indicador_nombre IN ({','.join(repr(c) for c in componentes) or "''"}) AND RIGHT(DIVIPOLA,3)='000'
            GROUP BY 1""").fetchall()}
    else:
        ipm = {d: r.get("ipm") for d, r in ant_dpto.items()}
        ipm_rural = ant.get("ipm_rural_componentes", {})
        pendientes.append("IPM (TerriData): se conservan los valores publicados; falta plata/terridata_dim1_limpia.parquet para recalcular.")
    if FIES_PREV.exists():
        # El anexo FIES publica los hogares en miles: se multiplican por 1.000.
        fies, fies_hog = {}, {}
        for nombre, valor, total in con.execute(f"""SELECT Departamento, Inseguridad_Moderada_Grave_Pct, Total_Hogares
                FROM read_parquet('{FIES_PREV}')""").fetchall():
            d = "00" if str(nombre).strip().lower() == "total nacional" else dpto_por_nombre(nombre)
            fies[d] = valor
            fies_hog[d] = valor / 100 * total * 1000 if valor is not None and total is not None else None
        exp = [{"indicador": i.replace("_", " "), "pct": nac if nac is not None else prom, "hogares": h * 1000 if h else None}
               for i, nac, prom, h in con.execute(f"""
            SELECT Indicador, AVG(Porcentaje) FILTER (WHERE lower(Departamento)='total nacional'), AVG(Porcentaje),
                   AVG(Total) FILTER (WHERE lower(Departamento)='total nacional')
            FROM read_parquet('{FIES_EXP}') GROUP BY 1 ORDER BY 3 DESC""").fetchall()]
    else:
        fies = {d: r.get("inseguridad_alimentaria") for d, r in ant_dpto.items()} | {"00": ant.get("fies_rural_nacional")}
        fies_hog = {d: r.get("inseguridad_hogares") for d, r in ant_dpto.items()} | {"00": ant.get("fies_rural_hogares")}
        exp = ant.get("fies_experiencias", [])
        pendientes.append("FIES (inseguridad alimentaria): se conservan los valores publicados (promedio simple departamental; "
                          "Valle del Cauca y San Andrés sin dato). Falta plata/fies_2025_rural_*.parquet para recalcular por código DPTO.")
    hogar, persona = resumen("ingreso"), resumen("ingreso_persona")
    con.close()

    por_dpto = []
    for d, nombre in DEPARTAMENTOS.items():
        fila = geih_dpto.loc[d].to_dict() if d in geih_dpto.index else {}
        por_dpto.append({"DPTO": d, "departamento": nombre, **{k: (None if v != v else v) for k, v in fila.items()},
                         "inseguridad_alimentaria": fies.get(d), "inseguridad_hogares": fies_hog.get(d), "ipm": ipm.get(d)})
    guardar_json("calidad_vida_rural_2025.json", {
        "origen": f"GEIH 2025 ({n} meses), FIES/ECV 2025 y TerriData, zona rural.",
        "pendientes": pendientes,
        "hogares_muestra": nacional[0],
        "hogares_estimados": hogares_estimados,
        "servicios": [{"servicio": s, "pct": v, "hogares": h} for (_, s, _), v, h in zip(SERVICIOS, nacional[2:], servicios_n)],
        "contaminacion_pct": nacional[1],
        "contaminacion_hogares": servicios_n[-1],
        "contaminacion_componentes": ambiental,
        "contaminacion_componentes_hogares": ambiental_n,
        "ingreso": {"hogar": hogar, "persona": persona},
        "ocupacion_hogar": [{"grupo": g, "pct": v, "hogares": h} for g, v, h in
                            zip(["Ninguna persona", "Hasta la mitad", "Más de la mitad", "Todo el hogar"], ocupacion, ocupacion_n)],
        "fies_rural_nacional": fies.get("00"),
        "fies_rural_hogares": fies_hog.get("00"),
        "fies_experiencias": exp,
        "ipm_rural_componentes": ipm_rural,
        "por_dpto": por_dpto,
    })


if __name__ == "__main__":
    main()
