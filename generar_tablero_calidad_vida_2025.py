#!/usr/bin/env python3
"""Integra Contexto Municipal, GEIH decodificada y FIES sin mezclar granularidades."""
from pathlib import Path
import json
import re
import duckdb
from dashboard_config import apply_common_style

BASE = Path(__file__).resolve().parent
PLATA, ORO = BASE / 'plata', BASE / 'oro'
CTX = PLATA / 'contexto_municipal_2025.parquet'
FIES = PLATA / 'fies_2025_rural_prevalencia.parquet'
OUT, HTML = ORO / 'tablero_calidad_vida_2025.parquet', BASE / 'calidad_vida_dashboard.html'

def main():
    ORO.mkdir(exist_ok=True)
    con = duckdb.connect()
    try:
        sql = r'''
        WITH contexto_departamento AS (
          SELECT SUBSTR(CAST(DIVIPOLA AS VARCHAR),1,2) DPTO,
                 MAX(departamento) departamento,
                 COUNT(DISTINCT DIVIPOLA) municipios,
                 COUNT(DISTINCT CASE WHEN lower(COALESCE(clasificacion_urbano_rural,'')) LIKE '%rural%' THEN DIVIPOLA END) municipios_rurales,
                 AVG(TRY_CAST(densidad_bancaria AS DOUBLE)) densidad_bancaria_promedio
          FROM read_parquet(?) GROUP BY 1
        ), viviendas AS (
          SELECT LPAD(CAST(DPTO AS VARCHAR),2,'0') DPTO,
                 CAST(DIRECTORIO AS VARCHAR) DIRECTORIO, CAST(HOGAR AS VARCHAR) HOGAR,
                 MAX(TRY_CAST(total_de_personas_en_el_hogar AS DOUBLE)) personas_hogar,
                 MAX(CASE WHEN CAST(con_cuales_de_los_siguientes_servicios_cuenta_7 AS VARCHAR) IN ('1','Si','SI','Sí') THEN 1 ELSE 0 END) acueducto,
                 MAX(CASE WHEN CAST(con_cuales_de_los_siguientes_servicios_cuenta AS VARCHAR) IN ('1','Si','SI','Sí') THEN 1 ELSE 0 END) energia,
                 MAX(CASE WHEN CAST(con_cuales_de_los_siguientes_servicios_cuenta_3 AS VARCHAR) IN ('1','Si','SI','Sí') THEN 1 ELSE 0 END) gas,
                 MAX(CASE WHEN CAST(con_cuales_de_los_siguientes_servicios_cuenta_4 AS VARCHAR) IN ('1','Si','SI','Sí') THEN 1 ELSE 0 END) alcantarillado,
                 MAX(CASE WHEN CAST(con_cuales_de_los_siguientes_servicios_cuenta_5 AS VARCHAR) IN ('1','Si','SI','Sí') THEN 1 ELSE 0 END) basuras,
                 MAX(CASE WHEN TRY_CAST(con_que_energia_o_combustibe_cocinan_principalmente AS INTEGER) IN (5,6,7)
                               OR TRY_CAST(como_eliminan_principalmente_la_basura_en_este AS INTEGER) IN (2,3,4,5)
                               OR TRY_CAST(el_servicio_sanitario_que_utiliza_el_hogar AS INTEGER) IN (3,4,5,6)
                          THEN 1 ELSE 0 END) contaminacion_proxy
          FROM read_parquet(?) WHERE CAST(CLASE AS VARCHAR) IN ('2','3') GROUP BY 1,2,3
        ), geih_hogares AS (
          SELECT DPTO, AVG(personas_hogar) promedio_personas_hogar,
                 COUNT(*) hogares_observados, SUM(acueducto) hogares_acueducto, SUM(energia) hogares_energia, SUM(gas) hogares_gas, SUM(alcantarillado) hogares_alcantarillado, SUM(basuras) hogares_basuras,
                 100.0*SUM(acueducto)/NULLIF(COUNT(*),0) cobertura_acueducto,
                 100.0*SUM(energia)/NULLIF(COUNT(*),0) cobertura_energia,
                 100.0*SUM(contaminacion_proxy)/NULLIF(COUNT(*),0) contaminacion_proxy
          FROM viviendas GROUP BY 1
        ), ingresos AS (
          SELECT LPAD(CAST(DPTO AS VARCHAR),2,'0') DPTO, CAST(DIRECTORIO AS VARCHAR) DIRECTORIO, CAST(HOGAR AS VARCHAR) HOGAR,
                 SUM(COALESCE(TRY_CAST(ingreso_laborales AS DOUBLE),0)) ingreso_hogar
          FROM read_parquet(?) WHERE CAST(CLASE AS VARCHAR) IN ('2','3') GROUP BY 1,2,3
        ), geih_ingresos AS (
          SELECT i.DPTO, AVG(i.ingreso_hogar/NULLIF(v.personas_hogar,0)) media_ingreso_persona
          FROM ingresos i JOIN viviendas v USING(DPTO,DIRECTORIO,HOGAR) GROUP BY 1
        ), fies_departamento AS (
          SELECT c.DPTO, AVG(f.Inseguridad_Moderada_Grave_Pct) inseguridad_alimentaria
          FROM read_parquet(?) f JOIN contexto_departamento c ON lower(f.Departamento)=lower(c.departamento)
          WHERE f.Departamento <> 'Total nacional' GROUP BY c.DPTO
        ), terridata AS (
          SELECT DPTO, AVG(ipm) ipm
          FROM read_parquet(?)
          WHERE ipm IS NOT NULL AND RIGHT(DIVIPOLA,3)='000'
          GROUP BY DPTO
        )
        SELECT c.DPTO,c.departamento,c.municipios,c.municipios_rurales,c.densidad_bancaria_promedio,
               f.inseguridad_alimentaria,t.ipm,
               g.hogares_observados,g.hogares_acueducto,g.hogares_energia,g.hogares_gas,g.hogares_alcantarillado,g.hogares_basuras,g.cobertura_acueducto,g.cobertura_energia,g.contaminacion_proxy,
               g.promedio_personas_hogar,i.media_ingreso_persona,
               'departamental' nivel_geografico,
               'Contexto Municipal agregado por DPTO + GEIH rural CLASE 2/3 + FIES por departamento' metodologia
        FROM contexto_departamento c LEFT JOIN geih_hogares g USING(DPTO)
        LEFT JOIN geih_ingresos i USING(DPTO) LEFT JOIN fies_departamento f USING(DPTO)
        LEFT JOIN terridata t USING(DPTO)
        ORDER BY c.DPTO
        '''
        args = [str(CTX), str(PLATA/'geih_2025_decodificada/*__datos_del_hogar_y_la_vivienda.parquet'), str(PLATA/'geih_2025_decodificada/*__ocupados.parquet'), str(FIES), str(PLATA/'terridata_indicadores_2025.parquet')]
        df = con.execute(sql, args).fetchdf()
        con.execute('CREATE OR REPLACE TEMP TABLE resultado AS ' + sql, args)
        con.execute('COPY resultado TO ? (FORMAT PARQUET, COMPRESSION ZSTD)', [str(OUT)])
    finally:
        con.close()
    con2 = duckdb.connect()
    try:
        alimentacion = con2.execute("SELECT Indicador, AVG(Porcentaje) porcentaje FROM read_parquet(?) GROUP BY Indicador ORDER BY porcentaje DESC", [str(PLATA/'fies_2025_rural_experiencias.parquet')]).fetchdf().to_dict('records')
        ipm_cols = ['ipm_centros_poblados_y_rural_disperso','analfabetismo_en_centros_poblados_y_rural_disperso','bajo_logro_educativo_en_centros_poblados_y_rural_disperso','sin_acceso_a_fuente_de_agua_mejorada_en_centros_poblados_y_rural_disperso','trabajo_informal_en_centros_poblados_y_rural_disperso','hacinamiento_critico_en_centros_poblados_y_rural_disperso']
        ipm_cols = [x for x in ipm_cols if x in [r[0] for r in con2.execute("SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet(?))", [str(PLATA/'terridata_indicadores_2025.parquet')]).fetchall()]]
        ipm_detalle = con2.execute("SELECT " + ','.join(f'AVG({x}) AS {x}' for x in ipm_cols) + " FROM read_parquet(?) WHERE RIGHT(DIVIPOLA,3)='000'", [str(PLATA/'terridata_indicadores_2025.parquet')]).fetchdf().iloc[0].dropna().to_dict() if ipm_cols else {}
        extras = con2.execute("""
          WITH v AS (SELECT CAST(DIRECTORIO AS VARCHAR) d,CAST(HOGAR AS VARCHAR) h,MAX(TRY_CAST(total_de_personas_en_el_hogar AS DOUBLE)) personas,
            MAX(CASE WHEN TRY_CAST(con_que_energia_o_combustibe_cocinan_principalmente AS INTEGER) IN (5,6,7)
                          OR TRY_CAST(como_eliminan_principalmente_la_basura_en_este AS INTEGER) IN (2,3,4,5)
                          OR TRY_CAST(el_servicio_sanitario_que_utiliza_el_hogar AS INTEGER) IN (3,4,5,6)
                     THEN 1 ELSE 0 END) contaminado
            FROM read_parquet(?) WHERE CAST(CLASE AS VARCHAR) IN ('2','3') GROUP BY 1,2),
          i AS (SELECT CAST(DIRECTORIO AS VARCHAR) d,CAST(HOGAR AS VARCHAR) h,
                   COUNT(DISTINCT CAST(SECUENCIA_P AS VARCHAR)) personas_ocupadas,
                   SUM(COALESCE(TRY_CAST(ingreso_laborales AS DOUBLE),0)) ingreso_hogar
            FROM read_parquet(?) WHERE CAST(CLASE AS VARCHAR) IN ('2','3') GROUP BY 1,2)
          SELECT v.personas,v.contaminado,COALESCE(i.personas_ocupadas,0) personas_ocupadas,
                 COALESCE(i.personas_ocupadas,0)/NULLIF(v.personas,0) proporcion_ocupadas,
                 i.ingreso_hogar,i.ingreso_hogar/NULLIF(v.personas,0) ingreso_persona FROM v LEFT JOIN i USING(d,h)
        """, [str(PLATA/'geih_2025_decodificada/*__datos_del_hogar_y_la_vivienda.parquet'), str(PLATA/'geih_2025_decodificada/*__ocupados.parquet')]).fetchdf()
    finally: con2.close()
    rows_json = json.dumps(df.astype(object).where(df.notna(), None).to_dict('records'), ensure_ascii=False, allow_nan=False, default=lambda _: None)
    html = render(rows_json)
    # Estos gráficos se retiraron del tablero: también se eliminan del HTML
    # base para que no reaparezcan al volver a ejecutar este generador.
    html = re.sub(r"<article class=[\"']card wide[\"']><div id=[\"']servicios[\"']>.*?</article>", '', html)
    html = re.sub(r"<article class=[\"']card[\"']><div id=[\"']alimentacion[\"']>.*?</article>", '', html)
    html = re.sub(r"<article class=[\"']card[\"']><div id=[\"']ipm[\"']>.*?</article>", '', html)
    html = re.sub(r"<article class=[\"']card wide[\"']><div id=[\"']rural[\"']>.*?</article>", '', html)
    html = re.sub(r"<article class=[\"']card wide[\"']><div id=[\"']ipm_fies[\"']>.*?</article>", '', html)
    html = re.sub(r"Plotly\.newPlot\('servicios'.*?\);", '', html, count=1)
    html = re.sub(r"Plotly\.newPlot\('rural'.*?\);", '', html, count=1)
    html = re.sub(r"Plotly\.newPlot\('ipm_fies'.*?\);", '', html, count=1)
    # Se conservan las tarjetas de inseguridad alimentaria e IPM, pero se
    # eliminan sus gráficos principales (dona/pastel y barra de progreso).
    html = re.sub(r"Plotly\.newPlot\('alimentacion'.*?\);", '', html, count=1)
    html = re.sub(r"Plotly\.newPlot\('ipm'.*?\);", '', html, count=1)
    html = html.replace('</section></main>', "<article class='card wide'><div id='servicios'></div><div class='source'>Fuente: GEIH rural, CLASE 2/3. Cobertura = hogares con respuesta afirmativa / hogares observados.</div></article></section></main>")
    html = html.replace('IPM: N/D. No existe en Contexto Municipal; debe incorporarse TerriData mediante DPTO.', 'Fuente: TerriData1/TerriData_Dim14.xlsx, IPM 2025, unido mediante DPTO.')
    html = html.replace('N/D: falta integrar TerriData', 'Promedio departamental informado por TerriData')
    det = json.dumps({'alimentacion': alimentacion, 'ipm_detalle': ipm_detalle, 'contaminacion_hogares': int(extras.contaminado.fillna(0).sum()), 'total_hogares': int(len(extras)), 'ingreso_persona': extras.ingreso_persona.dropna().clip(lower=0).tolist(), 'ingreso_hogar': extras.ingreso_hogar.dropna().clip(lower=0).tolist(), 'proporcion_ocupadas': extras.proporcion_ocupadas.dropna().clip(lower=0).tolist()}, ensure_ascii=False, allow_nan=False)
    html = html.replace('</section></main>', "<article class='card wide'><div id='alimentacion_detalle'></div><div class='source'>Fuente: FIES/ECV 2025. Promedio departamental de hogares que reportan cada experiencia.</div></article><article class='card wide'><div id='ipm_detalle'></div><div class='source'>Fuente: TerriData1 Dim14, componentes rurales del IPM 2025.</div></article><article class='card wide'><div id='ipm_fies'></div><div class='source'>Fuente: TerriData1 IPM 2025 + FIES/ECV 2025. Comparación departamental; no es una relación causal.</div></article><article class='card wide' id='contaminacion_card'><div id='contaminacion_waffle'></div><div class='source'>Fuente: GEIH rural. Proxy compuesto de factores ambientales del hogar: basura, saneamiento y combustible de cocina. No es una medición directa de calidad del aire.</div></article><article class='card wide'><div id='ocupacion_hogar'></div><div class='source'>Fuente: GEIH rural. Personas ocupadas en la base de ocupados / personas totales del hogar en la base de vivienda.</div></article><article class='card'><div id='sueldos_persona'></div><div class='source'>Fuente: GEIH rural. Distribución del ingreso laboral del hogar dividido por personas del hogar.</div></article><article class='card'><div id='sueldos_hogar'></div><div class='source'>Fuente: GEIH rural. Distribución del ingreso laboral total del hogar.</div></article></section></main>")
    html = html.replace('</body></html>', "<script>const DET=" + det + ";let al=DET.alimentacion,il=Object.keys(DET.ipm_detalle);Plotly.newPlot('alimentacion_detalle',[{x:al.map(x=>x.Indicador.replaceAll('_',' ')),y:al.map(x=>x.porcentaje),type:'bar',marker:{color:'#f87171'},text:al.map(x=>fmt(x.porcentaje)+'%'),textposition:'auto'}],{...B,title:{text:'Experiencias relacionadas con inseguridad alimentaria<br><sup>Porcentaje de hogares que reporta cada situación</sup>'},xaxis:{tickangle:-35},yaxis:{range:[0,100],title:'Hogares (%)'}});Plotly.newPlot('ipm_detalle',[{x:il.map(x=>DET.ipm_detalle[x]),y:il.map(x=>x.replace('_en_centros_poblados_y_rural_disperso','').replaceAll('_',' ')),type:'bar',orientation:'h',marker:{color:'#60a5fa'},text:il.map(x=>fmt(DET.ipm_detalle[x])+'%'),textposition:'auto'}],{...B,title:{text:'Dimensiones asociadas al IPM rural<br><sup>Los componentes no deben sumarse entre sí</sup>'},xaxis:{range:[0,100],title:'Porcentaje (%)'},yaxis:{autorange:'reversed'}});let usable=R.filter(x=>Number.isFinite(+x.ipm)&&Number.isFinite(+x.inseguridad_alimentaria)).sort((a,b)=>b.ipm-a.ipm).slice(0,10);Plotly.newPlot('ipm_fies',[{x:usable.map(x=>x.departamento),y:usable.map(x=>x.ipm),name:'IPM',type:'bar',marker:{color:'#60a5fa'}},{x:usable.map(x=>x.departamento),y:usable.map(x=>x.inseguridad_alimentaria),name:'Inseguridad alimentaria',type:'bar',marker:{color:'#f87171'}}],{...B,showlegend:true,title:{text:'IPM e inseguridad alimentaria en los departamentos con mayor IPM<br><sup>Ambas cifras son porcentajes; no implica causalidad</sup>'},barmode:'group',xaxis:{tickangle:-35},yaxis:{range:[0,100],title:'Porcentaje (%)'}});</script></body></html>")
    html = re.sub(r"Plotly\.newPlot\('alimentacion'.*?;Plotly\.newPlot\('ipm'", "Plotly.newPlot('alimentacion',[{values:[food||0,Math.max(0,100-(food||0))],labels:['Afectados','Resto'],type:'pie',hole:.72,marker:{colors:['#f87171','#243b53']},textinfo:'none'}],{...B,title:{text:'Inseguridad alimentaria<br><sup>El segmento rojo muestra el porcentaje de hogares afectados</sup>'}});Plotly.newPlot('ipm'", html, count=1)
    html = re.sub(r"Plotly\.newPlot\('ipm'.*?\);let labels=", "Plotly.newPlot('ipm',[{x:[ip||0],y:['IPM'],type:'bar',orientation:'h',marker:{color:'#60a5fa'},text:[ip==null?'N/D':fmt(ip)+'%'],textposition:'auto'}],{...B,title:{text:'Pobreza multidimensional (IPM)<br><sup>La barra muestra el porcentaje frente al 100%</sup>'},xaxis:{range:[0,100],title:'Porcentaje del municipio (%)'},yaxis:{showticklabels:false}});let labels=", html, count=1)
    html = html.replace("mediana_personas_hogar", "promedio_personas_hogar").replace("personas.textContent=fmt(med('promedio_personas_hogar'))", "personas.textContent=fmt(avg('promedio_personas_hogar'))").replace("mediana_ingreso_persona", "media_ingreso_persona").replace("ingreso.textContent=COP(med('media_ingreso_persona'))", "ingreso.textContent=COP(avg('media_ingreso_persona'))").replace("const food=avg('inseguridad_alimentaria');", "const food=avg('inseguridad_alimentaria'),ip=avg('ipm');").replace("Mediana GEIH rural", "Media GEIH rural")
    html = html.replace("let labels=['Acueducto','Energía'],vals=[avg('cobertura_acueducto'),avg('cobertura_energia')];", "let servicePairs=[['Acueducto',avg('cobertura_acueducto')],['Energía',avg('cobertura_energia')]].sort((a,b)=>(b[1]||-1)-(a[1]||-1)),labels=servicePairs.map(x=>x[0]),vals=servicePairs.map(x=>x[1]);")
    html = html.replace('</body></html>', "</body></html>")
    extra_js = "<script>const E=" + det + ";let n=E.total_hogares,a=E.contaminacion_hogares,pct=n?100*a/n:0,grid='';for(let i=0;i<100;i++)grid+=`<span style=\"display:inline-block;width:18px;height:18px;margin:2px;background:${i<Math.round(pct)?'#f87171':'#243b53'}\"></span>`;document.getElementById('contaminacion_waffle').innerHTML='<h3>Hogares afectados por el proxy de contaminación</h3><p style=\"font-size:28px\">'+a.toLocaleString('es-CO')+' de '+n.toLocaleString('es-CO')+' hogares ('+pct.toFixed(1)+'%)</p><div style=\"max-width:440px\">'+grid+'</div><p> Cada cuadrado representa aproximadamente 1 de cada 100 hogares.</p>';let oc=E.proporcion_ocupadas.map(x=>Math.min(1,Math.max(0,x))),buckets=[['Ninguna persona',oc.filter(x=>x===0).length],['Hasta la mitad',oc.filter(x=>x>0&&x<=.5).length],['Más de la mitad',oc.filter(x=>x>.5&&x<1).length],['Todo el hogar',oc.filter(x=>x>=1).length]];Plotly.newPlot('ocupacion_hogar',[{x:buckets.map(x=>x[1]),y:buckets.map(x=>x[0]),type:'bar',orientation:'h',marker:{color:['#f87171','#fbbf24','#60a5fa','#36d399']},text:buckets.map(x=>x[1].toLocaleString('es-CO')+' hogares'),textposition:'auto'}],{...B,title:{text:'Personas ocupadas por hogar<br><sup>La mayoría de hogares tiene al menos una persona ocupada</sup>'},xaxis:{title:'Número de hogares'},yaxis:{autorange:'reversed'}});const P={paper_bgcolor:'#102536',plot_bgcolor:'#102536',font:{color:'#edf8f4'},margin:{l:20,r:20,t:40,b:35},autosize:true,showlegend:false};Plotly.newPlot('sueldos_persona',[{y:E.ingreso_persona,type:'box',marker:{color:'#60a5fa'},boxmean:true}],{...P,title:'Ingreso por persona<br><sup>La caja muestra la distribución y sus valores extremos</sup>',yaxis:{title:'Pesos colombianos'}});Plotly.newPlot('sueldos_hogar',[{y:E.ingreso_hogar,type:'box',marker:{color:'#36d399'},boxmean:true}],{...P,title:'Ingreso total del hogar<br><sup>La caja muestra la distribución y sus valores extremos</sup>',yaxis:{title:'Pesos colombianos'}});</script>";
    extra_js = extra_js.replace('Hogares afectados por el proxy de contaminación', 'Hogares expuestos a factores ambientales adversos')
    html = html.replace('</body></html>', extra_js+'</body></html>')
    cards = "<article class='card kpi'><div class='label'>Hogares con inseguridad alimentaria</div><div class='value' id='kpi_alimentacion'>N/D</div><div class='source'>FIES/ECV 2025, área rural.</div></article><article class='card kpi'><div class='label'>Pobreza multidimensional</div><div class='value' id='kpi_ipm'>N/D</div><div class='source'>TerriData1, IPM 2025.</div></article>"
    html = html.replace("<article class='card wide'><div id='alimentacion_detalle'>", cards + "<article class='card wide'><div id='alimentacion_detalle'>")
    html = html.replace('</body></html>', "<script>document.getElementById('kpi_alimentacion').textContent=fmt(avg('inseguridad_alimentaria'))+'%';document.getElementById('kpi_ipm').textContent=fmt(avg('ipm'))+'%';</script></body></html>")
    html = html.replace('</body></html>', "<script>let totalHogares=R.reduce((total,fila)=>total+(Number(fila.hogares_observados)||0),0),servicios=[['Acueducto','hogares_acueducto','#36d399'],['Energía eléctrica','hogares_energia','#60a5fa'],['Gas natural','hogares_gas','#fbbf24'],['Alcantarillado','hogares_alcantarillado','#a78bfa'],['Recolección de basuras','hogares_basuras','#f87171']],contenedor=document.getElementById('servicios');contenedor.innerHTML='<div style=\"display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px\"><div id=\"servicio_0\"></div><div id=\"servicio_1\"></div><div id=\"servicio_2\"></div><div id=\"servicio_3\"></div><div id=\"servicio_4\"></div></div>';servicios.forEach(([nombre,clave,color],i)=>{let hogares=R.reduce((total,fila)=>total+(Number(fila[clave])||0),0),porcentaje=totalHogares?100*hogares/totalHogares:0;Plotly.newPlot('servicio_'+i,[{type:'indicator',mode:'gauge+number',value:porcentaje,number:{suffix:'%',font:{size:25,color:'#edf8f4'}},gauge:{axis:{range:[0,100],visible:false},bar:{color:color},bgcolor:'#243b53',borderwidth:0,steps:[{range:[0,porcentaje],color:color},{range:[porcentaje,100],color:'#243b53'}],threshold:{line:{color:color,width:4},thickness:.8,value:porcentaje}}}],{...B,height:220,title:{text:nombre,font:{size:15,color:'#edf8f4'}},annotations:[{text:hogares.toLocaleString('es-CO')+' hogares',xref:'paper',yref:'paper',x:.5,y:.08,showarrow:false,font:{size:14,color:'#9fb2c2'}}]})});</script></body></html>")
    # Limpieza final: el comparativo IPM-FIES no forma parte de este tablero.
    html = re.sub(r"<article class=[\"']card wide[\"']><div id=[\"']ipm_fies[\"']>.*?</article>", '', html)
    html = re.sub(r"Plotly\.newPlot\('ipm_fies'.*?\);", '', html, count=1)
    HTML.write_text(apply_common_style(html), encoding='utf-8')
    print(f'OK: {len(df):,} departamentos -> {OUT}')
    print(f'OK: dashboard -> {HTML}')

def render(data):
    return r'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Calidad de vida rural · Departamentos</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><style>:root{--bg:#07131d;--card:#102536;--text:#edf8f4;--muted:#9fb2c2;--green:#36d399;--yellow:#fbbf24;--red:#f87171;--blue:#60a5fa}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,#174e4b,transparent 35%),var(--bg);color:var(--text);font:15px system-ui}.wrap{max-width:1450px;margin:auto;padding:30px}.hero h1{font-size:clamp(34px,6vw,68px);margin:8px 0;background:linear-gradient(90deg,#fff,var(--green),var(--blue));color:transparent;background-clip:text}.hero p,.source,.label{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px;margin-top:22px}.card{grid-column:span 6;background:var(--card);border:1px solid #ffffff20;border-radius:20px;padding:20px;min-height:360px;box-shadow:0 18px 45px #0005}.kpi{grid-column:span 3;min-height:170px}.value{font-size:36px;font-weight:800;margin:18px 0;color:var(--green)}.alert .value{color:var(--red)}.source{font-size:11px;line-height:1.45;margin-top:10px}.wide{grid-column:span 12}@media(max-width:850px){.wrap{padding:18px}.card,.kpi,.wide{grid-column:span 12}}</style></head><body><main class="wrap"><section class="hero"><div class="label">GEIH · FIES/ECV · CONTEXTO MUNICIPAL · 2025</div><h1>Calidad de vida por departamento</h1><p>Las métricas GEIH y FIES están disponibles a nivel departamental. Contexto Municipal se agrega desde sus municipios antes de cruzarlo, para no repetir un dato departamental en cada municipio.</p></section><section class="grid"><article class="card kpi"><div class="label">Departamentos</div><div class="value" id="n">N/D</div><div class="source">Llave: primeros dos dígitos de DIVIPOLA = DPTO.</div></article><article class="card kpi"><div class="label">Personas por hogar</div><div class="value" id="personas">N/D</div><div class="source">Mediana GEIH rural · CLASE 2/3.</div></article><article class="card kpi"><div class="label">Ingreso por persona</div><div class="value" id="ingreso">N/D</div><div class="source">Mediana GEIH rural, en COP.</div></article><article class="card kpi alert"><div class="label">Contaminación proxy</div><div class="value" id="contaminacion">N/D</div><div class="source">Hogares que cocinan con leña o carbón.</div></article><article class="card"><div id="alimentacion"></div><div class="source">Fuente: FIES/ECV 2025. Mediana departamental de inseguridad alimentaria moderada o grave.</div></article><article class="card"><div id="ipm"></div><div class="source">IPM: N/D. No existe en Contexto Municipal; debe incorporarse TerriData mediante DPTO.</div></article><article class="card wide"><div id="servicios"></div><div class="source">Fuente: GEIH decodificada, hogares rurales. Cobertura = hogares afirmativos / hogares observados × 100.</div></article><article class="card wide"><div id="rural"></div><div class="source">Fuente: Contexto Municipal. Municipios rurales contados por departamento; clasificación válida solo donde la fuente la informa.</div></article></section></main><script>const R=__DATA__,nums=k=>R.map(x=>+x[k]).filter(Number.isFinite),med=k=>{let a=nums(k).sort((x,y)=>x-y);return a.length?a[Math.floor((a.length-1)/2)]:null},avg=k=>{let a=nums(k);return a.length?a.reduce((s,x)=>s+x,0)/a.length:null},fmt=x=>x==null?'N/D':x.toLocaleString('es-CO',{maximumFractionDigits:1}),COP=x=>x==null?'N/D':x.toLocaleString('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0});n.textContent=R.length;personas.textContent=fmt(med('mediana_personas_hogar'));ingreso.textContent=COP(med('mediana_ingreso_persona'));contaminacion.textContent=fmt(avg('contaminacion_proxy'))+'%';const B={autosize:true,paper_bgcolor:'#102536',plot_bgcolor:'#102536',font:{color:'#edf8f4'},margin:{l:20,r:20,t:40,b:20},showlegend:false};const food=avg('inseguridad_alimentaria');Plotly.newPlot('alimentacion',[{type:'indicator',mode:'gauge+number',value:food||0,number:{suffix:'%',font:{size:30}},gauge:{axis:{range:[0,100]},bar:{color:'#f87171'},steps:[{range:[0,33],color:'#36d399'},{range:[33,66],color:'#fbbf24'},{range:[66,100],color:'#f87171'}]}}],{...B,title:{text:'Inseguridad alimentaria<br><sup>El rojo indica mayor proporción de hogares afectados</sup>'}});Plotly.newPlot('ipm',[{type:'indicator',mode:'gauge+number',value:0,number:{suffix:'%',font:{size:30}},gauge:{axis:{range:[0,100]},bar:{color:'#60a5fa'},steps:[{range:[0,33],color:'#36d399'},{range:[33,66],color:'#fbbf24'},{range:[66,100],color:'#f87171'}]}}],{...B,title:{text:'Pobreza multidimensional (IPM)<br><sup>N/D: falta integrar TerriData</sup>'}});let labels=['Acueducto','Energía'],vals=[avg('cobertura_acueducto'),avg('cobertura_energia')];Plotly.newPlot('servicios',[{x:vals,y:labels,type:'bar',orientation:'h',marker:{color:['#60a5fa','#36d399']},text:vals.map(v=>fmt(v)+'%'),textposition:'auto'}],{...B,title:{text:'Cobertura de servicios públicos<br><sup>Se ordena de mayor a menor cobertura</sup>'},xaxis:{range:[0,100],title:'Hogares (%)'},yaxis:{autorange:'reversed'}});let x=R.map(r=>r.departamento),y=R.map(r=>r.municipios_rurales);Plotly.newPlot('rural',[{x:y,y:x,type:'bar',orientation:'h',marker:{color:'#36d399'},text:y.map(fmt),textposition:'auto'}],{...B,title:{text:'Municipios rurales por departamento<br><sup>Se cuentan desde Contexto Municipal antes del cruce</sup>'},yaxis:{autorange:'reversed'}});</script></body></html>'''.replace('__DATA__', data)

if __name__ == '__main__': main()
