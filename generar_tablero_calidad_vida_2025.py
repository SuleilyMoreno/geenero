#!/usr/bin/env python3
"""Construye el tablero municipal de calidad de vida rural 2025."""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
import pandas as pd

BASE = Path(__file__).resolve().parent
PLATA, ORO = BASE / "plata", BASE / "oro"
GEIH, CONTEXTO = PLATA / "geih_2025_limpia.parquet", PLATA / "contexto_municipal_2025.parquet"
SALIDA, HTML = ORO / "tablero_calidad_vida_2025.parquet", BASE / "calidad_vida_dashboard.html"

def elegir(disponibles, *candidatas):
    return next((x for x in candidatas if x in disponibles), None)

def q(x):
    return '"' + x.replace('"', '""') + '"'

def build_dataset() -> pd.DataFrame:
    con = duckdb.connect()
    try:
        con.execute("CREATE TEMP TABLE geih AS SELECT * FROM read_parquet(?)", [str(GEIH)])
        con.execute("CREATE TEMP TABLE contexto AS SELECT * FROM read_parquet(?)", [str(CONTEXTO)])
        cg = {r[0] for r in con.execute("DESCRIBE geih").fetchall()}
        cc = {r[0] for r in con.execute("DESCRIBE contexto").fetchall()}
        div = elegir(cg, "DIVIPOLA"); hogar = elegir(cg, "SECUENCIA_H", "identificador_hogar", "identificador_hogar_persona")
        persona = elegir(cg, "SECUENCIA_P", "numero_persona_hogar")
        acueducto = elegir(cg, "P8520S1", "siguientes_servicios_cuenta_vivienda_acueduct")
        energia = elegir(cg, "P8520S5", "siguientes_servicios_cuenta_vivienda_energia")
        ingreso = elegir(cg, "INGTOT", "INGLABO", "ingresos_laborales", "ingreso_laborales")
        ipm = elegir(cc, "ipm", "indice_pobreza_multidimensional")
        if not div or not hogar:
            raise ValueError("GEIH debe contener DIVIPOLA y un identificador de hogar")
        afirmativa = lambda c: f"(TRY_CAST({q(c)} AS DOUBLE)=1 OR lower(trim(CAST({q(c)} AS VARCHAR))) IN ('si','sí','1'))"
        a, e = afirmativa(acueducto) if acueducto else "FALSE", afirmativa(energia) if energia else "FALSE"
        p = q(persona) if persona else "NULL"
        ing = f"COALESCE(TRY_CAST({q(ingreso)} AS DOUBLE),0)" if ingreso else "0.0"
        ipm_sql = f"TRY_CAST(c.{q(ipm)} AS DOUBLE)" if ipm else "CAST(NULL AS DOUBLE)"
        sql = f"""
        WITH hogares AS (
          SELECT {q(div)} AS DIVIPOLA, {q(hogar)} AS hogar,
            COUNT(DISTINCT CAST({p} AS VARCHAR)) AS personas_hogar, SUM({ing}) AS ingresos_hogar,
            MAX(CASE WHEN {a} THEN 1 ELSE 0 END) AS acueducto, MAX(CASE WHEN {e} THEN 1 ELSE 0 END) AS energia
          FROM geih WHERE {q(div)} IS NOT NULL AND {q(hogar)} IS NOT NULL GROUP BY 1,2
        ), municipal AS (
          SELECT DIVIPOLA, AVG(acueducto)*100 AS porcentaje_acceso_acueducto, AVG(energia)*100 AS porcentaje_acceso_energia,
            AVG(personas_hogar) AS promedio_personas_por_hogar,
            AVG(ingresos_hogar/NULLIF(personas_hogar,0)) AS promedio_ingresos_por_persona
          FROM hogares GROUP BY DIVIPOLA
        )
        SELECT c.DIVIPOLA,c.departamento,c.grupo_municipio,c.Region,{ipm_sql} AS ipm,
          m.porcentaje_acceso_acueducto,m.porcentaje_acceso_energia,m.promedio_personas_por_hogar,m.promedio_ingresos_por_persona,
          CAST(NULL AS DOUBLE) AS proxy_inseguridad_alimentaria,CAST(NULL AS DOUBLE) AS proxy_contaminacion
        FROM contexto c LEFT JOIN municipal m USING (DIVIPOLA)"""
        df = con.execute(sql).fetchdf(); ORO.mkdir(exist_ok=True)
        con.execute("COPY (" + sql + ") TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(SALIDA)])
        return df
    finally:
        con.close()

def generate_dashboard(df: pd.DataFrame):
    data = json.dumps(df.astype(object).where(pd.notna(df), None).to_dict("records"), ensure_ascii=False, allow_nan=False, default=lambda _: None)
    html = """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Calidad de vida rural 2025</title><script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script><style>
    :root{--c:#5eead4;--v:#a78bfa;--bg:#08111f;--card:#10213acc;--muted:#91a4bb}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0,#193a54,transparent 35%),linear-gradient(135deg,var(--bg),#111827);color:#e8f0fa;font:15px system-ui}.wrap{max-width:1450px;margin:auto;padding:34px}.hero{display:flex;justify-content:space-between;align-items:end;margin-bottom:24px}.eyebrow{color:var(--c);letter-spacing:2px;text-transform:uppercase;font-size:12px}.hero h1{font-size:clamp(30px,5vw,58px);margin:8px 0;background:linear-gradient(90deg,#fff,var(--c),var(--v));color:transparent;background-clip:text}.hero p,.note,.label{color:var(--muted)}.badge,.card{background:var(--card);border:1px solid #94b7dc33;backdrop-filter:blur(16px);box-shadow:0 15px 45px #0004}.badge{padding:10px 15px;border-radius:30px;color:var(--c)}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{grid-column:span 4;border-radius:22px;padding:20px}.chart{grid-column:span 6;min-height:390px}.wide{grid-column:span 8}.kpi{font-size:34px;font-weight:800;margin-top:14px}.note{font-size:12px;margin-top:10px}@media(max-width:850px){.wrap{padding:18px}.card,.chart,.wide{grid-column:span 12}.hero{display:block}.badge{display:inline-block;margin-top:15px}}</style></head><body><main class='wrap'><section class='hero'><div><div class='eyebrow'>Inteligencia territorial · GEIH 2025</div><h1>Calidad de vida rural</h1><p>Servicios, hogares, ingresos y brechas a nivel municipal.</p></div><div class='badge' id='count'></div></section><section class='grid'><article class='card'><div class='label'>Personas por hogar</div><div class='kpi' id='personas'>—</div><div class='note'>Promedio municipal</div></article><article class='card'><div class='label'>Ingreso por persona</div><div class='kpi' id='ingreso'>—</div><div class='note'>COP · ingreso hogar / personas hogar</div></article><article class='card'><div class='label'>IPM</div><div class='kpi' id='ipm'>—</div><div class='note'>Sin dato si no existe en contexto</div></article><article class='card chart wide'><div id='servicios'></div></article><article class='card chart'><div id='ipmchart'></div></article><article class='card chart'><div id='hogares'></div></article><article class='card chart wide'><div id='pendientes'></div></article></section></main><script>const rows=__DATA__;const n=k=>rows.map(r=>Number(r[k])).filter(Number.isFinite),m=k=>{let a=n(k);return a.length?a.reduce((x,y)=>x+y,0)/a.length:null},f=(x,c=false)=>x==null?'Sin dato':x.toLocaleString('es-CO',c?{style:'currency',currency:'COP',maximumFractionDigits:0}:{maximumFractionDigits:2});document.querySelector('#count').textContent=rows.length.toLocaleString('es-CO')+' municipios';personas.textContent=f(m('promedio_personas_por_hogar'));ingreso.textContent=f(m('promedio_ingresos_por_persona'),true);ipm.textContent=f(m('ipm'));let b={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#e8f0fa'},margin:{t:55,r:20,b:80,l:55}},x=rows.map(r=>r.departamento||r.DIVIPOLA),y=k=>rows.map(r=>Number.isFinite(Number(r[k]))?Number(r[k]):null);Plotly.newPlot('servicios',[{x,y:y('porcentaje_acceso_acueducto'),name:'Acueducto',type:'bar',marker:{color:'#5eead4'}},{x,y:y('porcentaje_acceso_energia'),name:'Energía',type:'bar',marker:{color:'#a78bfa'}}],{...b,title:'Acceso a servicios públicos (%)',barmode:'group',xaxis:{tickangle:-45}});Plotly.newPlot('ipmchart',[{labels:['IPM disponible','Sin dato'],values:[n('ipm').length,rows.length-n('ipm').length],type:'pie',hole:.62,marker:{colors:['#a78bfa','#26364d']}}],{...b,title:'Cobertura del IPM'});Plotly.newPlot('hogares',[{x,y:y('promedio_personas_por_hogar'),type:'scatter',mode:'lines+markers',line:{color:'#5eead4',width:3}}],{...b,title:'Personas por hogar',xaxis:{tickangle:-45}});Plotly.newPlot('pendientes',[{x:['Alimentación','Contaminación'],y:[0,0],type:'bar',text:['PLACEHOLDER','PLACEHOLDER'],textposition:'auto',marker:{color:['#fb7185','#fbbf24']}}],{...b,title:'Indicadores pendientes de fuente',yaxis:{visible:false},annotations:[{text:'Placeholders NULL: no hay fuente en los parquet',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false,font:{color:'#91a4bb'}}]});</script></body></html>""".replace("__DATA__", data)
    HTML.write_text(html, encoding="utf-8")

def main():
    df = build_dataset(); generate_dashboard(df)
    print(f"OK: {len(df):,} municipios -> {SALIDA}"); print(f"OK: dashboard -> {HTML}")

if __name__ == '__main__': main()
