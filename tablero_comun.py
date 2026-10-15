"""Constantes y utilidades compartidas por los extractores y los tableros 2025.

Filtros del estudio: ruralidad + año 2025.
- Encuestas DANE (GEIH, ENUT): CLASE 2/3 = centros poblados y rural disperso.
- FIES: área "Centros poblados y rural disperso".
- Fuentes municipales (Finagro, Superfinanciera): municipios con Categoría de
  Ruralidad DNP "Rural" o "Rural disperso" (referencias/categorias_ruralidad_dnp.csv).
"""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
RURALIDAD_CSV = BASE / "referencias" / "categorias_ruralidad_dnp.csv"
DATOS = BASE / "datos_tablero"
ANIO = 2025

DEPARTAMENTOS = {
    "05": "Antioquia", "08": "Atlántico", "11": "Bogotá D.C.", "13": "Bolívar",
    "15": "Boyacá", "17": "Caldas", "18": "Caquetá", "19": "Cauca", "20": "Cesar",
    "23": "Córdoba", "25": "Cundinamarca", "27": "Chocó", "41": "Huila",
    "44": "La Guajira", "47": "Magdalena", "50": "Meta", "52": "Nariño",
    "54": "Norte de Santander", "63": "Quindío", "66": "Risaralda", "68": "Santander",
    "70": "Sucre", "73": "Tolima", "76": "Valle del Cauca", "81": "Arauca",
    "85": "Casanare", "86": "Putumayo", "88": "San Andrés y Providencia",
    "91": "Amazonas", "94": "Guainía", "95": "Guaviare", "97": "Vaupés", "99": "Vichada",
}

# Variantes de escritura que aparecen en anexos DANE (FIES) y en el DNP.
_ALIAS = {
    "valle": "76", "bogota": "11", "bogotadc": "11", "santafedebogota": "11",
    "sanandres": "88", "archipielagodesanandresprovidenciaysantacatalina": "88",
    "sanandresprovidenciaysantacatalina": "88", "guajira": "44", "nortesantander": "54",
}


PLATA = BASE / "plata"
GEIH_DIR = PLATA / "geih_2025_decodificada"


def geih(modulo: str) -> str:
    """Subconsulta DuckDB de un módulo GEIH 2025 ya filtrado a lo rural (CLASE 2/3).

    Agrega ``mes_archivo`` (prefijo del parquet, p. ej. ``enero``) para que las
    uniones hogar-persona incluyan el mes y no mezclen viviendas de meses distintos.
    """
    patron = GEIH_DIR / f"*__{modulo}.parquet"
    return (
        "(SELECT *, regexp_extract(filename, '([^/]+?)__[^/]*$', 1) AS mes_archivo "
        f"FROM read_parquet('{patron}', filename=true, union_by_name=true) "
        "WHERE CAST(CLASE AS VARCHAR) IN ('2','3'))"
    )


# Módulos GEIH usados por los tableros.
VIVIENDA = "datos_del_hogar_y_la_vivienda"
PERSONAS = "caracteristicas_generales_seguridad_social_en_salud_y_educacion"
FUERZA = "fuerza_de_trabajo"
OCUPADOS = "ocupados"
OTRAS_FORMAS = "otras_formas_de_trabajo"


def meses_geih(con) -> int:
    """Número de meses GEIH cargados.

    Al sumar FEX_C18 de 12 meses se obtiene 12 veces la población; el factor
    anual es FEX_C18 / meses (recomendación DANE para promedios anuales).
    """
    return con.execute(f"SELECT COUNT(DISTINCT mes_archivo) FROM {geih(VIVIENDA)}").fetchone()[0] or 1


def peso(alias: str, meses: int) -> str:
    """Factor de expansión anual de la fila ``alias``."""
    return f"(COALESCE(TRY_CAST({alias}.FEX_C18 AS DOUBLE), 0) / {meses})"


def previo(nombre: str) -> dict:
    """JSON ya publicado en datos_tablero/ (para conservar indicadores de fuentes no disponibles)."""
    import json
    ruta = DATOS / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def guardar_json(nombre: str, datos: dict) -> Path:
    import json
    DATOS.mkdir(exist_ok=True)
    ruta = DATOS / nombre
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"OK -> {ruta}")
    return ruta


def limpiar_nombre(texto: object) -> str:
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


_POR_NOMBRE = {limpiar_nombre(v): k for k, v in DEPARTAMENTOS.items()} | _ALIAS


def dpto_por_nombre(nombre: object) -> str | None:
    """Devuelve el código DPTO para un nombre de departamento (sin depender de tildes)."""
    return _POR_NOMBRE.get(limpiar_nombre(nombre))


def municipios_rurales(path: Path = RURALIDAD_CSV) -> set[str]:
    """Códigos DIVIPOLA (5 dígitos) con categoría DNP Rural o Rural disperso."""
    with path.open(encoding="utf-8-sig") as f:
        filas = csv.DictReader(f, delimiter=";")
        return {
            r["Municipaly"].strip().zfill(5)
            for r in filas
            if r["Categoria_"].strip().lower() in {"rural", "rural disperso"}
        }


def sexo_estandar(valor: object) -> str:
    """Homologa los códigos de sexo de Finagro (Hombre/Mujer/NA) y Superfinanciera
    (Femenino/Masculino/No aplica/...) a Mujeres, Hombres u Otro/sin dato."""
    v = limpiar_nombre(valor)
    if v in {"mujer", "femenino", "f", "2"}:
        return "Mujeres"
    if v in {"hombre", "masculino", "h", "1"}:
        return "Hombres"
    return "Sin dato / persona jurídica"
