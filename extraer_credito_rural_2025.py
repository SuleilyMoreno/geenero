#!/usr/bin/env python3
"""Crédito agropecuario rural 2025 por sexo: Finagro + Superintendencia Financiera.

Consulta agregados SoQL en datos.gov.co (no descarga microdatos completos) y
aplica los filtros del estudio:
  - Año 2025: fecha_credito (Finagro) / fecha_corte (Superfinanciera).
  - Ruralidad: municipio con categoría DNP Rural o Rural disperso.
  - Superfinanciera: CIIU del deudor que empieza por 01 (agricultura y ganadería).

Correcciones frente a la versión anterior:
  - Superfinanciera publica filas agregadas: se cuentan créditos con
    SUM(numero_de_creditos), no con COUNT(*).
  - Monto promedio = suma de montos / número de créditos.
  - Tasa = promedio ponderado por monto y sin las filas con tasa 0 (sin dato).
  - Finagro se toma del dataset vigente jjvv-55ck (el w3uf-w9ey termina en 2024).

Salida: datos_tablero/credito_rural_2025.json
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date

from tablero_comun import ANIO, DATOS, DEPARTAMENTOS, municipios_rurales, sexo_estandar

DOMINIO = "https://www.datos.gov.co/resource"
FINAGRO_ID = "jjvv-55ck"
SUPER_ID = "w9zh-vetq"
RANGO = f"'{ANIO}-01-01' and '{ANIO}-12-31T23:59:59'"


def soql(dataset: str, **params: str) -> list[dict]:
    """Ejecuta una consulta SoQL paginada y devuelve todas las filas."""
    filas, offset, limite = [], 0, 50_000
    token = os.getenv("SODAPY_APP_TOKEN")
    while True:
        query = {f"${k}": v for k, v in params.items()} | {"$limit": str(limite), "$offset": str(offset)}
        req = urllib.request.Request(f"{DOMINIO}/{dataset}.json?{urllib.parse.urlencode(query)}")
        if token:
            req.add_header("X-App-Token", token)
        with urllib.request.urlopen(req, timeout=600) as r:
            lote = json.load(r)
        filas += lote
        if len(lote) < limite:
            return filas
        offset += limite


def num(x: object) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def finagro(rurales: set[str]) -> dict:
    filas = soql(
        FINAGRO_ID,
        select="cod_municipio,sexo,linea_credito,tipo_productor,count(*) as n,"
               "sum(valor_credito) as monto,sum(plazo) as plazo,"
               "sum(case(garantia_fag=1,1,true,0)) as fag,"
               "sum(case(tasa_indexacion='IBR',puntos_adicionales,true,0)) as puntos_ibr,"
               "sum(case(tasa_indexacion='IBR',1,true,0)) as n_ibr",
        where=f"fecha_credito between {RANGO}",
        group="cod_municipio,sexo,linea_credito,tipo_productor",
        order="cod_municipio,sexo,linea_credito,tipo_productor",
    )
    total_2025 = int(sum(num(f["n"]) for f in filas))
    acc = defaultdict(lambda: defaultdict(float))
    dpto = defaultdict(lambda: defaultdict(float))
    linea = defaultdict(lambda: defaultdict(float))
    productor = defaultdict(lambda: defaultdict(float))
    linea_monto = defaultdict(lambda: defaultdict(float))
    for f in filas:
        mun = str(f.get("cod_municipio", "")).split(".")[0].zfill(5)
        if mun not in rurales:
            continue
        s = sexo_estandar(f.get("sexo"))
        for k in ("n", "monto", "plazo", "fag", "puntos_ibr", "n_ibr"):
            acc[s][k] += num(f.get(k))
        dpto[mun[:2]][s] += num(f["n"])
        linea[s][f.get("linea_credito") or "Sin dato"] += num(f["n"])
        linea_monto[s][f.get("linea_credito") or "Sin dato"] += num(f.get("monto"))
        productor[s][f.get("tipo_productor") or "Sin dato"] += num(f["n"])

    # La mediana no se puede sumar entre grupos: se pide por sexo con el filtro rural.
    codigos = ",".join(str(int(c)) for c in sorted(rurales))
    medianas = {
        sexo_estandar(m["sexo"]): num(m["mediana"])
        for m in soql(FINAGRO_ID, select="sexo,median(valor_credito) as mediana",
                      where=f"fecha_credito between {RANGO} AND cod_municipio in ({codigos})",
                      group="sexo")
    }
    por_sexo = {
        s: {
            "creditos": int(a["n"]),
            "monto_total": a["monto"],
            "monto_promedio": a["monto"] / a["n"] if a["n"] else None,
            "monto_mediana": medianas.get(s),
            "plazo_promedio_meses": a["plazo"] / a["n"] if a["n"] else None,
            "pct_con_garantia_fag": 100 * a["fag"] / a["n"] if a["n"] else None,
            "margen_ibr_puntos": a["puntos_ibr"] / a["n_ibr"] if a["n_ibr"] else None,
        }
        for s, a in acc.items()
    }
    return {
        "dataset": FINAGRO_ID,
        "registros_2025_todos_los_municipios": total_2025,
        "registros_2025_rurales": int(sum(a["n"] for a in acc.values())),
        "por_sexo": por_sexo,
        "por_dpto": {d: dict(v) for d, v in sorted(dpto.items())},
        "linea_credito": {s: dict(v) for s, v in linea.items()},
        # Monto promedio por línea = monto total de la línea ÷ créditos de la línea.
        "linea_monto_promedio": {s: {k: linea_monto[s][k] / linea[s][k] for k in linea[s] if linea[s][k]} for s in linea},
        "tipo_productor": {s: dict(v) for s, v in productor.items()},
    }


def superfinanciera(rurales: set[str]) -> dict:
    filas = soql(
        SUPER_ID,
        select="codigo_municipio,sexo,tipo_de_cr_dito,count(*) as filas,"
               "sum(numero_de_creditos) as creditos,sum(montos_desembolsados) as monto,"
               "sum(case(tasa_efectiva_promedio>0,montos_desembolsados,true,0)) as monto_con_tasa,"
               "sum(case(tasa_efectiva_promedio>0,tasa_efectiva_promedio*montos_desembolsados,true,0)) as tasa_x_monto",
        where=f"fecha_corte between {RANGO} AND starts_with(codigo_ciiu,'01')",
        group="codigo_municipio,sexo,tipo_de_cr_dito",
        order="codigo_municipio,sexo,tipo_de_cr_dito",
    )
    total_filas = int(sum(num(f["filas"]) for f in filas))
    acc = defaultdict(lambda: defaultdict(float))
    dpto = defaultdict(lambda: defaultdict(float))
    tipo = defaultdict(lambda: defaultdict(float))
    tipo_det = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for f in filas:
        mun = str(f.get("codigo_municipio", "")).zfill(5)
        if mun not in rurales:
            continue
        s = sexo_estandar(f.get("sexo"))
        for k in ("filas", "creditos", "monto", "monto_con_tasa", "tasa_x_monto"):
            acc[s][k] += num(f.get(k))
        dpto[mun[:2]][s] += num(f["creditos"])
        t = f.get("tipo_de_cr_dito") or "Sin dato"
        tipo[s][t] += num(f["creditos"])
        for k in ("creditos", "monto", "monto_con_tasa", "tasa_x_monto"):
            tipo_det[s][t][k] += num(f.get(k))
    por_sexo = {
        s: {
            "filas_agregadas": int(a["filas"]),
            "creditos": int(a["creditos"]),
            "monto_total": a["monto"],
            "monto_promedio": a["monto"] / a["creditos"] if a["creditos"] else None,
            "tasa_ponderada_ea": a["tasa_x_monto"] / a["monto_con_tasa"] if a["monto_con_tasa"] else None,
            "pct_monto_sin_tasa": 100 * (1 - a["monto_con_tasa"] / a["monto"]) if a["monto"] else None,
        }
        for s, a in acc.items()
    }
    return {
        "dataset": SUPER_ID,
        "filas_2025_ciiu01_todos_los_municipios": total_filas,
        "filas_2025_ciiu01_rurales": int(sum(a["filas"] for a in acc.values())),
        "creditos_2025_ciiu01_rurales": int(sum(a["creditos"] for a in acc.values())),
        "por_sexo": por_sexo,
        "por_dpto": {d: dict(v) for d, v in sorted(dpto.items())},
        "tipo_credito": {s: dict(v) for s, v in tipo.items()},
        # Por tipo de crédito: monto promedio por crédito y tasa ponderada por monto (sin tasas 0).
        "tipo_credito_condiciones": {s: {t: {"creditos": a["creditos"],
                                             "monto_promedio": a["monto"] / a["creditos"] if a["creditos"] else None,
                                             "tasa_ponderada_ea": a["tasa_x_monto"] / a["monto_con_tasa"] if a["monto_con_tasa"] else None}
                                         for t, a in v.items()} for s, v in tipo_det.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", default=str(DATOS / "credito_rural_2025.json"))
    args = ap.parse_args()
    rurales = municipios_rurales()
    datos = {
        "meta": {
            "anio": ANIO,
            "filtro_ruralidad": "Municipios con categoría DNP Rural o Rural disperso",
            "municipios_rurales": len(rurales),
            "fecha_extraccion": date.today().isoformat(),
            "departamentos": DEPARTAMENTOS,
        },
        "finagro": finagro(rurales),
        "superfinanciera": superfinanciera(rurales),
    }
    DATOS.mkdir(exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    fg, sf = datos["finagro"], datos["superfinanciera"]
    print(f"Finagro 2025: {fg['registros_2025_todos_los_municipios']:,} registros; rurales {fg['registros_2025_rurales']:,}")
    print(f"Superfinanciera 2025 CIIU 01: {sf['filas_2025_ciiu01_todos_los_municipios']:,} filas; "
          f"rurales {sf['filas_2025_ciiu01_rurales']:,} filas = {sf['creditos_2025_ciiu01_rurales']:,} créditos")
    print(f"OK -> {args.salida}")


if __name__ == "__main__":
    main()
