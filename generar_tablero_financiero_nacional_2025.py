#!/usr/bin/env python3
"""Capa oro financiera nacional y terminal Bloomberg web para 2025."""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
import pandas as pd

BASE=Path(__file__).resolve().parent; PLATA=BASE/'plata'; ORO=BASE/'oro'
FG=PLATA/'finagro_2025_limpia.parquet'; SF=PLATA/'superfinanciera_2025_limpia.parquet'; CTX=PLATA/'contexto_municipal_2025.parquet'
OUT=ORO/'tablero_financiero_nacional_2025.parquet'; HTML=BASE/'financiero_dashboard.html'

def pick(cols,*xs): return next((x for x in xs if x in cols),None)
def qi(x): return '"'+x.replace('"','""')+'"'

def build_dataset():
    con=duckdb.connect()
    try:
        for n,p in [('fg',FG),('sf',SF),('ctx',CTX)]: con.execute(f"CREATE TEMP TABLE {n} AS SELECT * FROM read_parquet(?)",[str(p)])
        cf={n:{r[0] for r in con.execute(f'DESCRIBE {n}').fetchall()} for n in ('fg','sf','ctx')}
        sexo_fg=pick(cf['fg'],'SEXO','Sexo'); sexo_sf=pick(cf['sf'],'SEXO','Sexo')
        monto_fg=pick(cf['fg'],'monto_aprobado','monto'); monto_sf=pick(cf['sf'],'monto_aprobado','monto')
        tasa_fg=pick(cf['fg'],'tasa_interes','tasa_efectiva','tasa'); tasa_sf=pick(cf['sf'],'tasa_interes','tasa_efectiva','tasa')
        plazo=pick(cf['fg'],'plazo_meses','plazo','plazo_credito'); cred=pick(cf['fg'],'id_credito')
        banc=pick(cf['ctx'],'corresponsales_bancarios','sucursales_fisicas','densidad_bancaria')
        def col(c,n): return f"TRY_CAST({n}.{qi(c)} AS DOUBLE)" if c else 'NULL::DOUBLE'
        def sex(c,n): return f"lower(trim(CAST({n}.{qi(c)} AS VARCHAR))) IN ('f','2','femenino','mujer')" if c else 'FALSE'
        sql=f"""
        WITH creditos AS (
          SELECT CAST(DIVIPOLA AS VARCHAR) DIVIPOLA,CAST({qi(sexo_fg) if sexo_fg else 'NULL'} AS VARCHAR) SEXO,
            {col(monto_fg,'fg')} monto,{col(tasa_fg,'fg')} tasa,{col(plazo,'fg')} plazo,'FINAGRO' fuente FROM fg
          UNION ALL SELECT CAST(DIVIPOLA AS VARCHAR),CAST({qi(sexo_sf) if sexo_sf else 'NULL'} AS VARCHAR),
            {col(monto_sf,'sf')},{col(tasa_sf,'sf')},NULL,'SUPERFINANCIERA' FROM sf
        ), cobertura AS (SELECT AVG({('TRY_CAST(ctx.'+qi(banc)+' AS DOUBLE)') if banc else 'NULL::DOUBLE'}) cobertura_bancaria FROM ctx),
        resumen AS (SELECT AVG(CASE WHEN lower(trim(SEXO)) IN ('f','2','femenino','mujer') THEN monto END) monto_promedio_mujeres,
          AVG(CASE WHEN lower(trim(SEXO)) IN ('f','2','femenino','mujer') THEN tasa END) tasa_interes_promedio_mujeres,
          AVG(CASE WHEN lower(trim(SEXO)) IN ('f','2','femenino','mujer') THEN plazo END) tiempo_promedio_credito_mujeres,
          COUNT(*) cantidad_total_creditos FROM creditos)
        SELECT 2025 anio,r.monto_promedio_mujeres,r.tasa_interes_promedio_mujeres,c.cobertura_bancaria,
          CAST(NULL AS DOUBLE) proxy_productos_financieros,r.tiempo_promedio_credito_mujeres,r.cantidad_total_creditos FROM resumen r CROSS JOIN cobertura c"""
        summary=con.execute(sql).fetchdf(); ORO.mkdir(exist_ok=True)
        con.execute("COPY ("+sql+") TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",[str(OUT)])
        raw=con.execute(f"SELECT CAST(DIVIPOLA AS VARCHAR) DIVIPOLA,CAST({qi(sexo_fg) if sexo_fg else 'NULL'} AS VARCHAR) SEXO,{col(monto_fg,'fg')} monto,{col(tasa_fg,'fg')} tasa,{col(plazo,'fg')} plazo,'FINAGRO' fuente FROM fg UNION ALL SELECT CAST(DIVIPOLA AS VARCHAR),CAST({qi(sexo_sf) if sexo_sf else 'NULL'} AS VARCHAR),{col(monto_sf,'sf')},{col(tasa_sf,'sf')},NULL,'SUPERFINANCIERA' FROM sf").fetchdf()
        return summary,raw
    finally: con.close()

def generate_dashboard(summary,raw):
    s=summary.iloc[0].to_dict(); female=raw[raw['SEXO'].astype(str).str.lower().isin(['f','2','femenino','mujer'])]
    def vals(k): return [float(x) for x in female[k].dropna() if pd.notna(x)]
    payload=json.dumps({'summary':{k:(None if pd.isna(v) else v) for k,v in s.items()},'tasas':vals('tasa'),'plazos':vals('plazo')},allow_nan=False,default=lambda _:None)
    html="""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Financial Terminal · Colombia 2025</title><script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script><style>:root{--bg:#070b12;--panel:#0d141fcc;--line:#263342;--green:#20d47b;--amber:#f5b942;--text:#d7e2ed;--muted:#8293a6}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% -10%,#153d43,transparent 35%),var(--bg);color:var(--text);font:13px ui-monospace,SFMono-Regular,Menlo,monospace}.shell{max-width:1500px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:18px}.brand{color:var(--green);font-weight:800;letter-spacing:2px}.clock{color:var(--muted)}h1{font:28px system-ui;margin:26px 0 6px;color:#fff}.sub{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;margin-top:22px}.card{background:linear-gradient(145deg,#111b28dd,#0b111bdd);border:1px solid var(--line);border-radius:8px;padding:16px;grid-column:span 3;min-height:150px;box-shadow:0 12px 30px #0006}.chart{grid-column:span 6;min-height:390px}.wide{grid-column:span 12}.label{color:var(--muted);font-size:11px;text-transform:uppercase}.kpi{font:26px system-ui;font-weight:700;color:var(--green);margin:15px 0}.amber{color:var(--amber)}.note{font-size:11px;color:var(--muted)}@media(max-width:850px){.shell{padding:12px}.card,.chart,.wide{grid-column:span 12}}</style></head><body><main class='shell'><header class='top'><span class='brand'>NATIONAL FINANCIAL TERMINAL // CO</span><span class='clock'>LIVE SNAPSHOT · 2025</span></header><h1>Capital, cobertura y acceso</h1><div class='sub'>Panel nacional de crédito con foco en el acceso financiero de las mujeres.</div><section class='grid'><article class='card'><div class='label'>Monto promedio mujeres</div><div class='kpi' id='monto'>—</div><div class='note'>COP · Finagro + Superfinanciera</div></article><article class='card'><div class='label'>Tasa promedio mujeres</div><div class='kpi amber' id='tasa'>—</div><div class='note'>Tasa reportada por fuente</div></article><article class='card'><div class='label'>Créditos totales</div><div class='kpi' id='creditos'>—</div><div class='note'>Registros de ambas fuentes</div></article><article class='card'><div class='label'>Plazo mujeres</div><div class='kpi amber' id='plazo'>—</div><div class='note'>Meses · NULL si no existe</div></article><article class='card chart'><div id='box-tasa'></div></article><article class='card chart'><div id='box-plazo'></div></article><article class='card chart'><div id='gauge'></div></article><article class='card chart'><div id='mix'></div></article></section></main><script>const D=__DATA__,S=D.summary,F=x=>x==null?'N/D':Number(x).toLocaleString('es-CO',{maximumFractionDigits:2}),COP=x=>x==null?'N/D':Number(x).toLocaleString('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0});monto.textContent=COP(S.monto_promedio_mujeres);tasa.textContent=S.tasa_interes_promedio_mujeres==null?'N/D':F(S.tasa_interes_promedio_mujeres)+'%';creditos.textContent=F(S.cantidad_total_creditos);plazo.textContent=S.tiempo_promedio_credito_mujeres==null?'N/D':F(S.tiempo_promedio_credito_mujeres)+' meses';const B={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#d7e2ed',family:'ui-monospace'},margin:{t:55,r:20,b:45,l:55}};Plotly.newPlot('box-tasa',[{y:D.tasas,type:'box',name:'Mujeres',marker:{color:'#f5b942'},boxmean:true}],{...B,title:'Distribución de tasas · mujeres',yaxis:{title:'Tasa'}});Plotly.newPlot('box-plazo',[{y:D.plazos,type:'box',name:'Mujeres',marker:{color:'#20d47b'},boxmean:true}],{...B,title:'Dispersión de plazos · mujeres',yaxis:{title:'Meses'}});Plotly.newPlot('gauge',[{type:'indicator',mode:'gauge+number',value:S.cobertura_bancaria||0,title:{text:'Cobertura bancaria'},gauge:{axis:{visible:true},bar:{color:'#20d47b'},bgcolor:'#17212d',borderwidth:1,bordercolor:'#526273'}}],{...B});Plotly.newPlot('mix',[{labels:['Crédito registrado','Sin productos financieros'],values:[S.cantidad_total_creditos,S.proxy_productos_financieros||0],type:'pie',hole:.6,marker:{colors:['#20d47b','#263342']}}],{...B,title:'Productos financieros · proxy'});</script></body></html>""".replace('__DATA__',payload)
    HTML.write_text(html,encoding='utf-8')

def main():
    summary,raw=build_dataset();generate_dashboard(summary,raw);print(f'OK: {len(summary):,} fila nacional -> {OUT}');print(f'OK: dashboard -> {HTML}')

if __name__=='__main__': main()
