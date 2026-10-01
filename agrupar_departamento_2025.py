#!/usr/bin/env python3
"""Capa oro y dashboard territorial departamental 2025."""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
import pandas as pd

BASE = Path(__file__).resolve().parent
PLATA, ORO = BASE / "plata", BASE / "oro"
CTX, GEIH, FIN = (PLATA / x for x in ("contexto_municipal_2025.parquet", "geih_2025_limpia.parquet", "finagro_2025_limpia.parquet"))
OUT, HTML = ORO / "tablero_departamentos_2025.parquet", BASE / "departamentos_dashboard.html"

def pick(cols, *names): return next((x for x in names if x in cols), None)
def qi(x): return '"' + x.replace('"', '""') + '"'

def build_dataset() -> pd.DataFrame:
    con = duckdb.connect()
    try:
        for n, p in (("c", CTX), ("g", GEIH), ("f", FIN)):
            con.execute(f"CREATE TEMP TABLE {n} AS SELECT * FROM read_parquet(?)", [str(p)])
        cols = {n: {r[0] for r in con.execute(f"DESCRIBE {n}").fetchall()} for n in ("c", "g", "f")}
        cd, gd, fd = pick(cols['c'], 'DIVIPOLA'), pick(cols['g'], 'DIVIPOLA'), pick(cols['f'], 'DIVIPOLA')
        cs, gs, fs = pick(cols['c'], 'departamento'), pick(cols['g'], 'Sexo', 'SEXO'), pick(cols['f'], 'Sexo', 'SEXO')
        rural = pick(cols['c'], 'ruralidad', 'Ruralidad', 'grupo_municipio', 'tipo_municipio')
        ipm = pick(cols['c'], 'ipm', 'indice_pobreza_multidimensional')
        jefe, sexo2 = pick(cols['g'], 'P6050'), pick(cols['g'], 'P6020')
        act = pick(cols['g'], 'OCI', 'indicador_ocupados', 'Ocupado')
        credito = pick(cols['f'], 'id_credito')
        if not (cd and gd and fd): raise ValueError('Los tres parquet requieren DIVIPOLA')
        dept = f"lpad(substr(CAST({qi(cd)} AS VARCHAR),1,2),2,'0')"
        gd_expr = f"lpad(substr(CAST({qi(gd)} AS VARCHAR),1,2),2,'0')"
        fd_expr = f"lpad(substr(CAST({qi(fd)} AS VARCHAR),1,2),2,'0')"
        rural_sql = f"COUNT(DISTINCT CASE WHEN lower(trim(CAST({qi(rural)} AS VARCHAR))) IN ('rural','rural disperso') THEN {qi(cd)} END)" if rural else "CAST(NULL AS BIGINT)"
        ipm_sql = f"AVG(TRY_CAST({qi(ipm)} AS DOUBLE))" if ipm else "CAST(NULL AS DOUBLE)"
        jefa_sql = f"SUM(CASE WHEN TRY_CAST({qi(jefe)} AS DOUBLE)=1 AND TRY_CAST({qi(sexo2)} AS DOUBLE)=2 THEN 1 ELSE 0 END)" if jefe and sexo2 else "CAST(NULL AS BIGINT)"
        ocupado = f"lower(trim(CAST({qi(act)} AS VARCHAR))) IN ('1','si','sí','ocupado','ocupada')" if act else "FALSE"
        desocupado = f"lower(trim(CAST({qi(act)} AS VARCHAR))) IN ('2','desocupado','desocupada')" if act else "FALSE"
        def rate(sex):
            condition = f"AND lower(trim(CAST({qi(gs)} AS VARCHAR))) IN ({sex})" if gs else ""
            return f"SUM(CASE WHEN {desocupado} {condition} THEN 1 ELSE 0 END)::DOUBLE/NULLIF(SUM(CASE WHEN ({ocupado} OR {desocupado}) {condition} THEN 1 ELSE 0 END),0)"
        count_credit = f"COUNT({qi(credito)})" if credito else "COUNT(*)"
        sql = f"""
        WITH contexto AS (SELECT {dept} AS DPTO,MAX(CAST({qi(cs)} AS VARCHAR)) AS departamento,
          {rural_sql} AS municipios_rurales,{ipm_sql} AS ipm_promedio,{jefa_sql} AS mujeres_cabeza_hogar FROM c GROUP BY 1),
        actividad AS (SELECT {gd_expr} AS DPTO,{rate("'m','masculino','hombre'")} AS tasa_desocupacion_hombres,
          {rate("'f','femenino','mujer'")} AS tasa_desocupacion_mujeres FROM g GROUP BY 1),
        creditos AS (SELECT {fd_expr} AS DPTO,{count_credit} AS cantidad_creditos_agrarios FROM f GROUP BY 1),
        claves AS (SELECT DPTO FROM contexto UNION SELECT DPTO FROM actividad UNION SELECT DPTO FROM creditos)
        SELECT k.DPTO,c.departamento,c.municipios_rurales,c.ipm_promedio,
          CAST(NULL AS DOUBLE) AS proxy_inseguridad,c.mujeres_cabeza_hogar,
          a.tasa_desocupacion_hombres,a.tasa_desocupacion_mujeres,
          cr.cantidad_creditos_agrarios FROM claves k LEFT JOIN contexto c USING(DPTO)
          LEFT JOIN actividad a USING(DPTO) LEFT JOIN creditos cr USING(DPTO) ORDER BY k.DPTO"""
        df = con.execute(sql).fetchdf(); ORO.mkdir(exist_ok=True)
        con.execute("COPY (" + sql + ") TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(OUT)])
        return df
    finally: con.close()

def generate_dashboard(df: pd.DataFrame):
    data = json.dumps(df.astype(object).where(pd.notna(df), None).to_dict('records'), ensure_ascii=False, allow_nan=False, default=lambda _: None)
    html = """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Colombia territorial · 2025</title><script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script><style>:root{--bg:#07131d;--card:#102536dd;--a:#38bdf8;--b:#f59e0b;--muted:#9fb2c2}*{box-sizing:border-box}body{margin:0;color:#e9f4f8;font:15px system-ui;background:radial-gradient(circle at 80% 0,#164e63,transparent 35%),linear-gradient(135deg,var(--bg),#111827)}main{max-width:1450px;margin:auto;padding:34px}.tag{color:#67e8f9;letter-spacing:2px;text-transform:uppercase;font-size:12px}.hero h1{font-size:clamp(32px,6vw,70px);margin:8px 0;background:linear-gradient(90deg,#fff,var(--a),var(--b));color:transparent;background-clip:text}.hero p{color:var(--muted);max-width:800px;font-size:17px}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{grid-column:span 6;min-height:390px;padding:20px;border:1px solid #ffffff20;border-radius:22px;background:var(--card);backdrop-filter:blur(14px);box-shadow:0 18px 55px #0005}.wide{grid-column:span 12}.kpi{grid-column:span 4;min-height:140px}.kpi b{display:block;font-size:32px;color:var(--a);margin:12px 0}.muted{color:var(--muted);font-size:13px}@media(max-width:850px){main{padding:18px}.card,.wide,.kpi{grid-column:span 12}}</style></head><body><main><section class='hero'><div class='tag'>Análisis territorial · 2025</div><h1>El territorio cuenta una historia distinta</h1><p>Explora cómo cambian la ruralidad, la pobreza multidimensional, el empleo y el crédito agrario entre departamentos.</p></section><section class='grid'><article class='card kpi'><span class='muted'>Departamentos</span><b id='n'>—</b><span class='muted'>con presencia en las fuentes</span></article><article class='card kpi'><span class='muted'>Municipios rurales</span><b id='r'>—</b><span class='muted'>clasificados como Rural/Rural disperso</span></article><article class='card kpi'><span class='muted'>Crédito agrario</span><b id='c'>—</b><span class='muted'>aprobaciones contabilizadas</span></article><article class='card wide'><div id='map'></div></article><article class='card'><div id='rural'></div></article><article class='card'><div id='credit'></div></article><article class='card'><div id='ipm'></div></article><article class='card'><div id='unemp'></div></article></section></main><script>const R=__DATA__,N=k=>R.map(x=>+x[k]).filter(Number.isFinite),SUM=k=>N(k).reduce((a,b)=>a+b,0),F=x=>x==null?'Sin dato':x.toLocaleString('es-CO',{maximumFractionDigits:1});n.textContent=R.length;r.textContent=F(SUM('municipios_rurales'));c.textContent=F(SUM('cantidad_creditos_agrarios'));const B={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#e9f4f8'},margin:{t:55,r:20,b:70,l:55}},x=R.map(r=>r.departamento||r.DPTO);Plotly.newPlot('map',[{type:'choropleth',locations:R.map(r=>r.DPTO),z:R.map(r=>Number.isFinite(+r.municipios_rurales)?+r.municipios_rurales:null),geojson:'https://raw.githubusercontent.com/martynafford/natural-earth-geojson/master/50m文化.json',featureidkey:'properties.DPTO',colorscale:'Viridis',colorbar:{title:'Municipios rurales'}}],{...B,title:'Mapa coroplético · ruralidad',geo:{scope:'south america',showland:true,landcolor:'#172b3a',bgcolor:'transparent',fitbounds:'locations'}});const bar=k=>({x:N(k),y:x.filter((_,i)=>Number.isFinite(+R[i][k])),type:'bar',orientation:'h',marker:{color:'#38bdf8'}});Plotly.newPlot('rural',[bar('municipios_rurales')],{...B,title:'Municipios rurales por departamento',yaxis:{automargin:true}});Plotly.newPlot('credit',[bar('cantidad_creditos_agrarios')],{...B,title:'Crédito agrario: concentración territorial',yaxis:{automargin:true}});Plotly.newPlot('ipm',[bar('ipm_promedio')],{...B,title:'IPM promedio departamental',yaxis:{automargin:true}});Plotly.newPlot('unemp',[{x:x,y:R.map(r=>r.tasa_desocupacion_hombres),name:'Hombres',type:'bar',marker:{color:'#38bdf8'}},{x:x,y:R.map(r=>r.tasa_desocupacion_mujeres),name:'Mujeres',type:'bar',marker:{color:'#f59e0b'}}],{...B,title:'Desocupación por sexo',barmode:'group',xaxis:{tickangle:-45},yaxis:{tickformat:'.0%'}});</script></body></html>""".replace('__DATA__', data)
    HTML.write_text(html, encoding='utf-8')

def main():
    df=build_dataset();generate_dashboard(df);print(f'OK: {len(df):,} departamentos -> {OUT}');print(f'OK: dashboard -> {HTML}')

if __name__=='__main__': main()
