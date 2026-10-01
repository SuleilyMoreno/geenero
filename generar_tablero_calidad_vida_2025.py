#!/usr/bin/env python3
"""generar_tablero_calidad_vida_2025.py
===================================================
Este script realiza **dos** tareas en un solo paso:

1️⃣ **Construcción del dataset**
   - Lee los parquet limpios de la carpeta ``plata/``:
     * ``geih_2025_limpia.parquet`` (datos de la GEIH).
     * ``contexto_municipal_2025.parquet`` (información territorial del DNP).
   - Calcula, a nivel municipal (``DIVIPOLA``), las métricas solicitadas.
   - Añade *place‑holders* para los indicadores que aún no disponemos.
   - Exporta la tabla resultante a ``oro/tablero_calidad_vida_2025.parquet``.

2️⃣ **Generación de un dashboard HTML interactivo**
   - Carga el parquet creado en el paso anterior.
   - Utiliza **Plotly** para generar visualizaciones dinámicas.
   - Emplea una plantilla Jinja2 con CSS "glass‑morphism" y modo oscuro.
   - Produce ``calidad_vida_dashboard.html`` en la raíz del proyecto.

Ejemplo de ejecución::
    $ python3 generar_tablero_calidad_vida_2025.py

Requisitos de paquetes (instalar si faltan)::
    pip install duckdb pandas plotly jinja2
"""

from __future__ import annotations
import json
from pathlib import Path
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jinja2 import Template

# ---------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
PLATA_DIR = BASE_DIR / "plata"
ORO_DIR = BASE_DIR / "oro"

GEIH_PATH = PLATA_DIR / "geih_2025_limpia.parquet"
CONTEXTO_PATH = PLATA_DIR / "contexto_municipal_2025.parquet"
OUTPUT_PARQUET = ORO_DIR / "tablero_calidad_vida_2025.parquet"
HTML_OUTPUT = BASE_DIR / "calidad_vida_dashboard.html"

# ---------------------------------------------------------------------
# 1️⃣ CONSTRUCCIÓN DEL DATASET CON DUCKDB
# ---------------------------------------------------------------------
def build_dataset() -> pd.DataFrame:
    """Lee los parquet, calcula los indicadores y devuelve un DataFrame.
    También escribe el resultado en ``oro/tablero_calidad_vida_2025.parquet``.
    """
    con = duckdb.connect(database=":memory:")
    # Cargar tablas
    con.execute("CREATE TABLE geih AS SELECT * FROM read_parquet(?)", [str(GEIH_PATH)])
    con.execute("CREATE TABLE contexto AS SELECT * FROM read_parquet(?)", [str(CONTEXTO_PATH)])

    # Agregaciones a nivel municipal (DIVIPOLA)
    con.execute(
        """
        CREATE TABLE agg_geih AS
        SELECT
            DIVIPOLA,
            -- 5. Promedio de personas por hogar
            AVG(numero_personas_hogar) AS promedio_personas_por_hogar,
            -- 6. Promedio de ingresos por persona (columna ya normalizada en GEIH)
            AVG(ingresos_laborales) AS promedio_ingresos_por_persona,
            -- 3. Acceso a servicios públicos: acueducto y energía (assume columnas binarias 'acueducto' y 'energia')
            AVG(CASE WHEN acueducto = 'SI' THEN 1 ELSE 0 END) AS porcentaje_acceso_acueducto,
            AVG(CASE WHEN energia = 'SI' THEN 1 ELSE 0 END) AS porcentaje_acceso_energia,
            -- 2. Pobreza multidimensional (IPM) – columna "ipm" en GEIH
            AVG(ipm) AS ipm_promedio
        FROM geih
        WHERE DIVIPOLA IS NOT NULL
        GROUP BY DIVIPOLA;
        """
    )

    # Unir con contexto y añadir placeholders
    con.execute(
        """
        CREATE TABLE tablero AS
        SELECT
            c.DIVIPOLA,
            c.departamento,
            c.grupo_municipio,
            c.indice_informalidad_tierra,
            c.densidad_bancaria,
            c.Region,
            g.ipm_promedio,
            g.porcentaje_acceso_acueducto,
            g.porcentaje_acceso_energia,
            g.promedio_personas_por_hogar,
            g.promedio_ingresos_por_persona,
            -- 1. Calidad de alimentación (placeholder)
            CAST(NULL AS DOUBLE) AS proxy_inseguridad,
            -- 4. Contaminación (placeholder)
            CAST(NULL AS DOUBLE) AS proxy_contaminacion
        FROM contexto c
        LEFT JOIN agg_geih g USING (DIVIPOLA);
        """
    )

    # Exportar a parquet
    ORO_DIR.mkdir(parents=True, exist_ok=True)
    con.execute("COPY tablero TO ? (FORMAT 'parquet', COMPRESSION 'zstd')", [str(OUTPUT_PARQUET)])

    # Cargar en pandas para usarlo después en la parte de visualización
    df = con.execute("SELECT * FROM tablero").df()
    con.close()
    return df

# ---------------------------------------------------------------------
# 2️⃣ GENERACIÓN DEL DASHBOARD HTML
# ---------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Dashboard Calidad de Vida – 2025</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: "Segoe UI", Arial, sans-serif;
            background: #0b0c10; /* dark background */
            color: #c5c6c7;
        }
        .container {
            max-width: 1200px;
            margin: auto;
            padding: 2rem;
        }
        h1 {
            text-align: center;
            color: #66fcf1;
            margin-bottom: 2rem;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1.5rem;
        }
        .card {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 30px rgba(0,0,0,0.5);
        }
        .kpi {
            font-size: 2.2rem;
            font-weight: bold;
            text-align: center;
            color: #45a29e;
        }
        .kpi-label {
            text-align: center;
            margin-top: 0.5rem;
            font-size: 1rem;
            color: #c5c6c7;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Calidad de Vida – Créditos Rurales 2025</h1>
        <div class="grid">
            <!-- KPI cards -->
            <div class="card">
                <div class="kpi" id="kpi-ipm"></div>
                <div class="kpi-label">IPM promedio (multidimensional)</div>
            </div>
            <div class="card">
                <div class="kpi" id="kpi-poblacion-hogar"></div>
                <div class="kpi-label">Personas por hogar (promedio)</div>
            </div>
            <div class="card">
                <div class="kpi" id="kpi-ingreso"></div>
                <div class="kpi-label">Ingreso promedio por persona (COP)</div>
            </div>
            <!-- Charts -->
            <div class="card" id="chart-servicios"></div>
            <div class="card" id="chart-inseguridad"></div>
            <div class="card" id="chart-contaminacion"></div>
        </div>
    </div>

    <script>
        // --- DATA INJECTION -------------------------------------------------
        const data = {{ data_json|safe }};
        // KPI values (global averages)
        document.getElementById('kpi-ipm').textContent = (data.ipm_promedio_mean ?? 0).toFixed(2);
        document.getElementById('kpi-poblacion-hogar').textContent = (data.promedio_personas_por_hogar_mean ?? 0).toFixed(2);
        document.getElementById('kpi-ingreso').textContent = Number(data.promedio_ingresos_por_persona_mean ?? 0).toLocaleString('es-CO');

        // --- GRÁFICO DE SERVICIOS PÚBLICOS (Barras apiladas) -------------
        const servTraceAcueducto = {
            x: data.departamento_labels,
            y: data.porcentaje_acceso_acueducto,
            name: 'Acueducto',
            type: 'bar',
            marker: {color: '#66fcf1'}
        };
        const servTraceEnergia = {
            x: data.departamento_labels,
            y: data.porcentaje_acceso_energia,
            name: 'Energía',
            type: 'bar',
            marker: {color: '#45a29e'}
        };
        Plotly.newPlot('chart-servicios', [servTraceAcueducto, servTraceEnergia], {
            barmode: 'group',
            title: {text: 'Cobertura de Servicios Públicos por Departamento', font: {color: '#c5c6c7'}},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)',
            font: {color: '#c5c6c7'}
        });

        // --- GRÁFICO DE INSEGURIDAD ALIMENTARIA (placeholder) -----------
        const insegData = data.proxy_inseguridad.map((v,i)=>({dept:data.departamento_labels[i], val: v}));
        const insegTrace = {
            x: insegData.map(d=>d.dept),
            y: insegData.map(d=>d.val),
            type: 'scatter',
            mode: 'lines+markers',
            marker: {color: '#ff6b6b'}
        };
        Plotly.newPlot('chart-inseguridad', [insegTrace], {
            title: {text: 'Inseguridad Alimentaria (placeholder)', font: {color: '#c5c6c7'}},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)',
            font: {color: '#c5c6c7'}
        });

        // --- GRÁFICO DE CONTAMINACIÓN (placeholder) -----------------------
        const contData = data.proxy_contaminacion.map((v,i)=>({dept:data.departamento_labels[i], val: v}));
        const contTrace = {
            x: contData.map(d=>d.dept),
            y: contData.map(d=>d.val),
            type: 'bar',
            marker: {color: '#f5c518'}
        };
        Plotly.newPlot('chart-contaminacion', [contTrace], {
            title: {text: 'Contaminación (placeholder)', font: {color: '#c5c6c7'}},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)',
            font: {color: '#c5c6c7'}
        });
    </script>
</body>
</html>
"""

def generate_dashboard(df: pd.DataFrame) -> None:
    """Crea ``calidad_vida_dashboard.html`` a partir del DataFrame ``df``.
    Se agrupan los datos por *departamento* para simplificar las visualizaciones.
    """
    # Preparar datos agregados por departamento (para los charts de barras)
    agg = (
        df.groupby(["departamento"], as_index=False)
        .agg({
            "ipm_promedio": "mean",
            "porcentaje_acceso_acueducto": "mean",
            "porcentaje_acceso_energia": "mean",
            "promedio_personas_por_hogar": "mean",
            "promedio_ingresos_por_persona": "mean",
            "proxy_inseguridad": "first",  # placeholder, same value per dept
            "proxy_contaminacion": "first",
        })
    )

    # Valores globales para los KPI (promedios generales)
    global_means = {
        "ipm_promedio_mean": df["ipm_promedio"].mean(),
        "promedio_personas_por_hogar_mean": df["promedio_personas_por_hogar"].mean(),
        "promedio_ingresos_por_persona_mean": df["promedio_ingresos_por_persona"].mean(),
    }

    # Convertir a JSON consumible por el script del HTML
    payload = {
        "departamento_labels": agg["departamento"].tolist(),
        "ipm_promedio": agg["ipm_promedio"].tolist(),
        "porcentaje_acceso_acueducto": agg["porcentaje_acceso_acueducto"].tolist(),
        "porcentaje_acceso_energia": agg["porcentaje_acceso_energia"].tolist(),
        "proxy_inseguridad": agg["proxy_inseguridad"].fillna(0).tolist(),
        "proxy_contaminacion": agg["proxy_contaminacion"].fillna(0).tolist(),
        **global_means,
    }
    json_data = json.dumps(payload, ensure_ascii=False)

    # Renderizar la plantilla Jinja2
    tmpl = Template(HTML_TEMPLATE)
    html_content = tmpl.render(data_json=json_data)

    # Guardar archivo HTML
    HTML_OUTPUT.write_text(html_content, encoding="utf-8")
    print(f"✅ Dashboard HTML creado → {HTML_OUTPUT}")

# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
def main() -> None:
    # Paso 1: generar el parquet consolidado y obtener el DataFrame
    df = build_dataset()
    # Paso 2: generar dashboard estático interactivo
    generate_dashboard(df)

if __name__ == "__main__":
    main()
