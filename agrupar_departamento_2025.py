#!/usr/bin/env python3
"""Capa oro y dashboard territorial departamental 2025."""
from __future__ import annotations
import json
import re
from pathlib import Path
import duckdb
import pandas as pd
from dashboard_config import apply_common_style

BASE = Path(__file__).resolve().parent
PLATA, ORO = BASE / "plata", BASE / "oro"
# La antigua geih_2025_limpia.parquet ya no se usa. Esta capa disponible conserva
# la llave departamental; las métricas individuales quedan N/D hasta integrar
# directamente los módulos GEIH decodificados.
CTX, GEIH, FIN = (PLATA / x for x in ("contexto_municipal_2025.parquet", "departamento_2025_aggregado.parquet", "finagro_2025_limpia.parquet"))
FIES = PLATA / 'fies_2025_rural_prevalencia.parquet'
OUT, HTML = ORO / "tablero_departamentos_2025.parquet", BASE / "departamentos_dashboard.html"

def pick(cols, *names): return next((x for x in names if x in cols), None)
def qi(x): return '"' + x.replace('"', '""') + '"'

def build_dataset() -> pd.DataFrame:
    con = duckdb.connect()
    try:
        for n, p in (("c", CTX), ("g", GEIH), ("f", FIN), ("t", PLATA/'terridata_dim1_limpia.parquet'), ("fi", FIES)):
            con.execute(f"CREATE TEMP TABLE {n} AS SELECT * FROM read_parquet(?)", [str(p)])
        cols = {n: {r[0] for r in con.execute(f"DESCRIBE {n}").fetchall()} for n in ("c", "g", "f", "t", "fi")}
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
        rural_sql = "COALESCE(r.municipios_rurales,0)"
        ipm_sql = f"AVG(TRY_CAST({qi(ipm)} AS DOUBLE))" if ipm else "CAST(NULL AS DOUBLE)"
        jefa_sql = f"SUM(CASE WHEN TRY_CAST({qi(jefe)} AS DOUBLE)=1 AND TRY_CAST({qi(sexo2)} AS DOUBLE)=2 THEN 1 ELSE 0 END)" if jefe and sexo2 else "CAST(NULL AS BIGINT)"
        ocupado = f"lower(trim(CAST({qi(act)} AS VARCHAR))) IN ('1','si','sí','ocupado','ocupada')" if act else "FALSE"
        desocupado = f"lower(trim(CAST({qi(act)} AS VARCHAR))) IN ('2','desocupado','desocupada')" if act else "FALSE"
        def rate(sex):
            condition = f"AND lower(trim(CAST({qi(gs)} AS VARCHAR))) IN ({sex})" if gs else ""
            return f"SUM(CASE WHEN {desocupado} {condition} THEN 1 ELSE 0 END)::DOUBLE/NULLIF(SUM(CASE WHEN ({ocupado} OR {desocupado}) {condition} THEN 1 ELSE 0 END),0)"
        count_credit = f"COUNT({qi(credito)})" if credito else "COUNT(*)"
        sql = f"""
        WITH ruralidad AS (SELECT LPAD(SUBSTR(CAST(DIVIPOLA AS VARCHAR),1,2),2,'0') AS DPTO,
          COUNT(DISTINCT CASE WHEN lower(CAST("Dato Cualitativo" AS VARCHAR)) IN ('rural','rural disperso') THEN DIVIPOLA END) municipios_rurales
          FROM t WHERE indicador_nombre='categoria_de_ruralidad' GROUP BY 1),
        fies AS (SELECT lower(CAST(Departamento AS VARCHAR)) departamento, AVG(Inseguridad_Moderada_Grave_Pct) inseguridad_alimentaria FROM fi WHERE Departamento <> 'Total nacional' GROUP BY 1),
        terri AS (SELECT LPAD(SUBSTR(CAST(DIVIPOLA AS VARCHAR),1,2),2,'0') DPTO, AVG(dato_numerico) ipm FROM t WHERE indicador_nombre='ipm' AND Año=2025 AND RIGHT(DIVIPOLA,3)='000' GROUP BY 1),
        contexto AS (SELECT {dept} AS DPTO,MAX(CAST({qi(cs)} AS VARCHAR)) AS departamento,
          COUNT(DISTINCT {qi(cd)}) AS municipios_total,{rural_sql} AS municipios_rurales,{ipm_sql} AS ipm_promedio,{jefa_sql} AS mujeres_cabeza_hogar FROM c LEFT JOIN ruralidad r ON r.DPTO={dept} GROUP BY 1,r.municipios_rurales),
        actividad AS (SELECT {gd_expr} AS DPTO,{rate("'m','masculino','hombre'")} AS tasa_desocupacion_hombres,
          {rate("'f','femenino','mujer'")} AS tasa_desocupacion_mujeres FROM g GROUP BY 1),
        creditos AS (SELECT {fd_expr} AS DPTO,{count_credit} AS cantidad_creditos_agrarios FROM f GROUP BY 1),
        claves AS (SELECT DPTO FROM contexto UNION SELECT DPTO FROM actividad UNION SELECT DPTO FROM creditos)
        SELECT k.DPTO,c.departamento,c.municipios_total,c.municipios_rurales,100.0*c.municipios_rurales/NULLIF(c.municipios_total,0) ruralidad_pct,te.ipm,fies.inseguridad_alimentaria,c.ipm_promedio,
          CAST(NULL AS DOUBLE) AS proxy_inseguridad,c.mujeres_cabeza_hogar,
          a.tasa_desocupacion_hombres,a.tasa_desocupacion_mujeres,
          cr.cantidad_creditos_agrarios FROM claves k LEFT JOIN contexto c USING(DPTO)
          LEFT JOIN actividad a USING(DPTO) LEFT JOIN creditos cr USING(DPTO)
          LEFT JOIN terri te USING(DPTO) LEFT JOIN fies ON lower(c.departamento)=fies.departamento ORDER BY k.DPTO"""
        df = con.execute(sql).fetchdf()
        inclusion_sql = """
        WITH hogares AS (
          SELECT LPAD(SUBSTR(CAST(DPTO AS VARCHAR),1,2),2,'0') DPTO,
            MAX(TRY_CAST(FEX_C18 AS DOUBLE)) factor,
            MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza AS INTEGER)=1 OR
              TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_2 AS INTEGER)=1 OR
              TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_3 AS INTEGER)=1 OR
              TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_4 AS INTEGER)=1 OR
              TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_5 AS INTEGER)=1 OR
              TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_6 AS INTEGER)=1 OR
              TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_7 AS INTEGER)=1 THEN 1 ELSE 0 END) incluido
          FROM read_parquet('plata/geih_2025_decodificada/*__datos_del_hogar_y_la_vivienda.parquet')
          WHERE CAST(CLASE AS VARCHAR) IN ('2','3') GROUP BY 1, DIRECTORIO, HOGAR
        )
        SELECT DPTO, 100.0*SUM(incluido*factor)/NULLIF(SUM(factor),0) inclusion_financiera_pct
        FROM hogares GROUP BY 1
        """
        inclusion = con.execute(inclusion_sql).fetchdf()
        df = df.merge(inclusion, on='DPTO', how='left')
        ORO.mkdir(exist_ok=True)
        df.to_parquet(OUT, index=False, compression='zstd')
        return df
    finally: con.close()

def generate_dashboard(df: pd.DataFrame):
    data = json.dumps(df.astype(object).where(pd.notna(df), None).to_dict('records'), ensure_ascii=False, allow_nan=False, default=lambda _: None)
    html = """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Colombia territorial · 2025</title><script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script><style>:root{--bg:#07131d;--card:#102536dd;--a:#38bdf8;--b:#f59e0b;--muted:#9fb2c2}*{box-sizing:border-box}body{margin:0;color:#e9f4f8;font:15px system-ui;background:radial-gradient(circle at 80% 0,#164e63,transparent 35%),linear-gradient(135deg,var(--bg),#111827)}main{max-width:1450px;margin:auto;padding:34px}.tag{color:#67e8f9;letter-spacing:2px;text-transform:uppercase;font-size:12px}.hero h1{font-size:clamp(32px,6vw,70px);margin:8px 0;background:linear-gradient(90deg,#fff,var(--a),var(--b));color:transparent;background-clip:text}.hero p{color:var(--muted);max-width:800px;font-size:17px}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{grid-column:span 6;min-height:390px;padding:20px;border:1px solid #ffffff20;border-radius:22px;background:var(--card);backdrop-filter:blur(14px);box-shadow:0 18px 55px #0005}.wide{grid-column:span 12}.kpi{grid-column:span 4;min-height:140px}.kpi b{display:block;font-size:32px;color:var(--a);margin:12px 0}.muted{color:var(--muted);font-size:13px}@media(max-width:850px){main{padding:18px}.card,.wide,.kpi{grid-column:span 12}}</style></head><body><main><section class='hero'><div class='tag'>Análisis territorial · 2025</div><h1>El territorio cuenta una historia distinta</h1><p>Explora cómo cambian la ruralidad, la pobreza multidimensional, el empleo y el crédito agrario entre departamentos.</p></section><section class='grid'><article class='card kpi'><span class='muted'>Departamentos</span><b id='n'>—</b><span class='muted'>con presencia en las fuentes</span></article><article class='card kpi'><span class='muted'>Municipios rurales</span><b id='r'>—</b><span class='muted'>clasificados como Rural/Rural disperso</span></article><article class='card kpi'><span class='muted'>Crédito agrario</span><b id='c'>—</b><span class='muted'>aprobaciones contabilizadas</span></article><article class='card wide'><div id='map'></div></article><article class='card'><div id='rural'></div></article><article class='card'><div id='credit'></div></article><article class='card'><div id='ipm'></div></article><article class='card'><div id='unemp'></div></article></section></main><script>const R=__DATA__,N=k=>R.map(x=>+x[k]).filter(Number.isFinite),SUM=k=>N(k).reduce((a,b)=>a+b,0),F=x=>x==null?'Sin dato':x.toLocaleString('es-CO',{maximumFractionDigits:1});n.textContent=R.length;r.textContent=F(SUM('municipios_rurales'));c.textContent=F(SUM('cantidad_creditos_agrarios'));const B={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#e9f4f8'},margin:{t:55,r:20,b:70,l:55}},x=R.map(r=>r.departamento||r.DPTO);Plotly.newPlot('map',[{type:'choropleth',locations:R.map(r=>r.DPTO),z:R.map(r=>Number.isFinite(+r.municipios_rurales)?+r.municipios_rurales:null),geojson:'https://raw.githubusercontent.com/martynafford/natural-earth-geojson/master/50m文化.json',featureidkey:'properties.DPTO',colorscale:'Viridis',colorbar:{title:'Municipios rurales'}}],{...B,title:'Mapa coroplético · ruralidad',geo:{scope:'south america',showland:true,landcolor:'#172b3a',bgcolor:'transparent',fitbounds:'locations'}});const bar=k=>({x:N(k),y:x.filter((_,i)=>Number.isFinite(+R[i][k])),type:'bar',orientation:'h',marker:{color:'#38bdf8'}});Plotly.newPlot('rural',[bar('municipios_rurales')],{...B,title:'Municipios rurales por departamento',yaxis:{automargin:true}});Plotly.newPlot('credit',[bar('cantidad_creditos_agrarios')],{...B,title:'Crédito agrario: concentración territorial',yaxis:{automargin:true}});Plotly.newPlot('ipm',[bar('ipm_promedio')],{...B,title:'IPM promedio departamental',yaxis:{automargin:true}});Plotly.newPlot('unemp',[{x:x,y:R.map(r=>r.tasa_desocupacion_hombres),name:'Hombres',type:'bar',marker:{color:'#38bdf8'}},{x:x,y:R.map(r=>r.tasa_desocupacion_mujeres),name:'Mujeres',type:'bar',marker:{color:'#f59e0b'}}],{...B,title:'Desocupación por sexo',barmode:'group',xaxis:{tickangle:-45},yaxis:{tickformat:'.0%'}});</script></body></html>""".replace('__DATA__', data)
    html = html.replace("<article class='card wide'><div id='map'></div></article>", "")
    html = re.sub(r"Plotly\.newPlot\('map'.*?;const bar", "const bar", html, count=1)
    html = html.replace("<article class='card'><div id='rural'></div></article>", "<article class='card wide'><div id='map_ipm'></div><div class='muted'>El color más oscuro representa un IPM más alto.</div></article><article class='card wide'><div id='map_food'></div><div class='muted'>El color más oscuro representa mayor inseguridad alimentaria.</div></article><article class='card wide'><div id='map_rural'></div><div class='muted'>El color más oscuro representa una mayor proporción de municipios rurales.</div></article><article class='card wide'><div id='map_inclusion'></div><div class='muted'>El color más oscuro representa mayor inclusión financiera.</div></article><article class='card'><div id='rural'></div></article>")
    maps = """<script>const GEO_SOURCES=['https://geoportal.dane.gov.co/mparcgis/rest/services/Territoriales_DANE/Serv_Territoriales_DANE_2025/MapServer/1/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson','https://raw.githubusercontent.com/ytolosa/mapas-colombia/main/output/geojson/col_departamentos_inset_nacional.geojson'];const mapRows=R.filter(x=>x.DPTO&&x.departamento);const mapBase={autosize:true,paper_bgcolor:'#102536',plot_bgcolor:'#102536',font:{color:'#e9f4f8'},margin:{l:20,r:20,t:55,b:20}};function normalizaGeojson(g){g.features.forEach(f=>{const p=f.properties||{},k=['dpto_ccdgo','DPTO_CCDGO','dpto_codigo','codigo','COD_DPTO'].find(k=>p[k]!=null);if(k)p.dpto_ccdgo=String(p[k]).padStart(2,'0');else{const nk=['dpto_nombre','DPTO_CNMBR','nombre','NOMBRE'].find(k=>p[k]!=null);if(nk){const limpia=s=>String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');const nombre=limpia(p[nk]);const fila=mapRows.find(x=>limpia(x.departamento)===nombre);if(fila)p.dpto_ccdgo=String(fila.DPTO).padStart(2,'0')}}});return g}function drawMap(id,key,title,scale,geojson){const valid=mapRows.filter(x=>Number.isFinite(+x[key]));Plotly.newPlot(id,[{type:'choropleth',locations:valid.map(x=>String(x.DPTO).padStart(2,'0')),z:valid.map(x=>+x[key]),customdata:valid.map(x=>[x.departamento]),geojson:geojson,featureidkey:'properties.dpto_ccdgo',colorscale:scale,colorbar:{title:key==='ruralidad_pct'?'Porcentaje':key==='ipm'?'IPM':'Porcentaje',thickness:18,len:.82,ticks:'outside',outlinecolor:'#dbeafe',titlefont:{color:'#e9f4f8'},tickfont:{color:'#e9f4f8'}},hovertemplate:'Departamento: %{customdata[0]}<br>Valor: %{z:.1f}<extra></extra>'}],{...mapBase,title:{text:title+'<br><sup>Los tonos oscuros indican valores más altos</sup>'},geo:{scope:'south america',showland:true,fitbounds:'locations',landcolor:'#172b3a',bgcolor:'#102536'}})}function loadMapSource(i){if(i>=GEO_SOURCES.length)throw new Error('No fue posible cargar ninguna fuente geográfica');return fetch(GEO_SOURCES[i]).then(r=>{if(!r.ok)throw new Error('Fuente geográfica no disponible');return r.json()}).catch(()=>loadMapSource(i+1))}loadMapSource(0).then(g=>{const geojson=normalizaGeojson(g);drawMap('map_ipm','ipm','IPM por departamento','Blues',geojson);drawMap('map_food','inseguridad_alimentaria','Inseguridad alimentaria por departamento','Reds',geojson);drawMap('map_rural','ruralidad_pct','Nivel de ruralidad por departamento','Greens',geojson)}).catch(error=>{['map_ipm','map_food','map_rural'].forEach(id=>{document.getElementById(id).innerHTML='<p style="color:#fbbf24;padding:30px">No se pudo cargar el mapa. Abra el archivo mediante un servidor local y verifique la conexión.</p>'});console.error(error)});</script>"""
    maps = maps.replace("drawMap('map_rural','ruralidad_pct','Nivel de ruralidad por departamento','Greens',geojson)", "drawMap('map_rural','ruralidad_pct','Nivel de ruralidad por departamento','Greens',geojson);drawMap('map_inclusion','inclusion_financiera_pct','Índice de inclusión financiera',[[0,'#eff6ff'],[0.25,'#bfdbfe'],[0.5,'#60a5fa'],[0.75,'#2563eb'],[1,'#082f75']],geojson)")
    # En este tablero se conserva el mapa territorial y se reemplazan las
    # cuatro barras generales por el ranking solicitado de créditos.
    for old in [
        "<article class='card'><div id='rural'></div></article>",
        "<article class='card'><div id='credit'></div></article>",
        "<article class='card'><div id='ipm'></div></article>",
        "<article class='card'><div id='unemp'></div></article>",
    ]:
        html = html.replace(old, "")
    html = html.replace("</section></main>", "<article class='card wide'><div id='top_creditos'></div><div class='muted'>Los valores corresponden a registros de créditos agropecuarios de Finagro.</div></article></section></main>", 1)
    html = re.sub(r"Plotly\.newPlot\('rural'.*?\);Plotly\.newPlot\('credit'.*?\);Plotly\.newPlot\('ipm'.*?\);Plotly\.newPlot\('unemp'.*?\);", "", html, count=1)
    html = html.replace('</body></html>', maps + '</body></html>')
    top_chart = """<script>const topCreditos=R.filter(x=>Number.isFinite(+x.cantidad_creditos_agrarios)).sort((a,b)=>+b.cantidad_creditos_agrarios-+a.cantidad_creditos_agrarios).slice(0,10);Plotly.newPlot('top_creditos',[{x:topCreditos.map(x=>+x.cantidad_creditos_agrarios),y:topCreditos.map(x=>x.departamento||x.DPTO),type:'bar',orientation:'h',marker:{color:'#38bdf8'},text:topCreditos.map(x=>Number(x.cantidad_creditos_agrarios).toLocaleString('es-CO')),textposition:'auto'}],{autosize:true,paper_bgcolor:'#102536',plot_bgcolor:'#102536',font:{color:'#e9f4f8'},margin:{l:150,r:30,t:55,b:35},title:{text:'Top 10 departamentos por créditos agropecuarios solicitados<br><sup>Los departamentos están ordenados de mayor a menor número de créditos</sup>'},xaxis:{title:'Número de créditos'},yaxis:{autorange:'reversed'}});</script>"""
    html = html.replace('</body></html>', top_chart + '</body></html>')
    html = html.replace('clasificados como Rural/Rural disperso', 'TerriData: Rural/Rural disperso (año disponible)')
    html = html.replace("title:'Municipios rurales por departamento'", "title:'Municipios rurales por departamento<br><sup>TerriData · clasificación disponible de 2000</sup>'")
    html = html.replace("paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#e9f4f8'},margin:{t:55,r:20,b:70,l:55}", "autosize:true,paper_bgcolor:'#102536',plot_bgcolor:'#102536',font:{color:'#e9f4f8'},margin:{l:20,r:20,t:40,b:20},showlegend:false")
    HTML.write_text(apply_common_style(html), encoding='utf-8')

def main():
    df=build_dataset();generate_dashboard(df);print(f'OK: {len(df):,} departamentos -> {OUT}');print(f'OK: dashboard -> {HTML}')

if __name__=='__main__': main()
