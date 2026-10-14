#!/usr/bin/env python3
"""Genera el dashboard adicional de factores de inclusión financiera rural.

Reutiliza la agregación validada del tablero financiero nacional y conserva el
tablero original. El nuevo HTML incluye productos GEIH, créditos por sexo y
tarjetas comparativas de monto, tasa y cantidad de créditos.
"""
from pathlib import Path
import shutil
import json
import re
import plotly.offline as plotly_offline
import duckdb
import generar_tablero_financiero_nacional_2025 as base


BASE = Path(__file__).resolve().parent
base.HTML = BASE / "factores_inclusion_financiera_dashboard.html"


if __name__ == "__main__":
    base.main()
    # Empaqueta Plotly dentro del HTML para que funcione en la vista previa
    # del editor sin depender de Internet ni de un CDN externo.
    html = base.HTML.read_text(encoding="utf-8")
    con = duckdb.connect()
    edu_sql = """
    WITH hogares AS (
      SELECT CAST(DIRECTORIO AS VARCHAR) directorio, CAST(HOGAR AS VARCHAR) hogar,
        MAX(TRY_CAST(FEX_C18 AS DOUBLE)) factor,
        MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_2 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_3 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_4 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_5 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_6 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_7 AS INTEGER)=1
                  THEN 1 ELSE 0 END) incluido
      FROM read_parquet('plata/geih_2025_decodificada/*__datos_del_hogar_y_la_vivienda.parquet')
      WHERE CAST(CLASE AS VARCHAR) IN ('2','3') GROUP BY 1,2
    ), jefes AS (
      SELECT CAST(DIRECTORIO AS VARCHAR) directorio, CAST(HOGAR AS VARCHAR) hogar,
        CASE TRY_CAST(cual_es_el_mayor_nivel_educativo_alcanzado AS INTEGER)
          WHEN 1 THEN 'Ninguno' WHEN 2 THEN 'Preescolar' WHEN 3 THEN 'Básica primaria'
          WHEN 4 THEN 'Básica secundaria' WHEN 5 THEN 'Media'
          WHEN 6 THEN 'Técnico o tecnológico' WHEN 7 THEN 'Universitario'
          WHEN 8 THEN 'Posgrado' ELSE 'Sin información' END nivel,
        CASE TRY_CAST(cual_fue_su_sexo_al_nacer AS INTEGER)
          WHEN 1 THEN 'Hombres' WHEN 2 THEN 'Mujeres' ELSE 'Sin información' END sexo
      FROM read_parquet('plata/geih_2025_decodificada/*__caracteristicas_generales_seguridad_social_en_salud_y_educacion.parquet')
      WHERE CAST(CLASE AS VARCHAR) IN ('2','3')
        AND TRY_CAST(cual_es_el_parentesco_de_con_el AS INTEGER)=1
    )
    SELECT nivel, sexo, SUM(incluido*factor)/NULLIF(SUM(factor),0)*100 tasa_inclusion,
           SUM(factor) hogares_estimados
    FROM hogares JOIN jefes USING (directorio,hogar)
    GROUP BY nivel, sexo ORDER BY nivel, sexo
    """
    edu = con.execute(edu_sql).fetchall()
    jefatura_sql = """
    WITH hogares AS (
      SELECT CAST(DIRECTORIO AS VARCHAR) directorio, CAST(HOGAR AS VARCHAR) hogar,
        MAX(TRY_CAST(total_de_personas_en_el_hogar AS INTEGER)) tamano,
        MAX(TRY_CAST(FEX_C18 AS DOUBLE)) factor,
        MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_2 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_3 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_4 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_5 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_6 AS INTEGER)=1 OR
                       TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_7 AS INTEGER)=1 THEN 1 ELSE 0 END) incluido
      FROM read_parquet('plata/geih_2025_decodificada/*__datos_del_hogar_y_la_vivienda.parquet')
      WHERE CAST(CLASE AS VARCHAR) IN ('2','3') GROUP BY 1,2
    ), jefes AS (
      SELECT CAST(DIRECTORIO AS VARCHAR) directorio, CAST(HOGAR AS VARCHAR) hogar,
        CASE TRY_CAST(cual_fue_su_sexo_al_nacer AS INTEGER) WHEN 1 THEN 'Hombres' WHEN 2 THEN 'Mujeres' ELSE 'Sin información' END sexo
      FROM read_parquet('plata/geih_2025_decodificada/*__caracteristicas_generales_seguridad_social_en_salud_y_educacion.parquet')
      WHERE CAST(CLASE AS VARCHAR) IN ('2','3') AND TRY_CAST(cual_es_el_parentesco_de_con_el AS INTEGER)=1
    )
    SELECT sexo, CASE WHEN tamano >= 6 THEN '6 o más personas' ELSE CAST(tamano AS VARCHAR) END tamano,
      SUM(incluido*factor)/NULLIF(SUM(factor),0)*100 tasa_inclusion, SUM(factor) hogares_estimados
    FROM hogares JOIN jefes USING(directorio,hogar)
    WHERE tamano IS NOT NULL GROUP BY 1,2 ORDER BY 1,2
    """
    jefatura = con.execute(jefatura_sql).fetchall()
    territorial_sql = """
    WITH contexto AS (
      SELECT LPAD(SUBSTR(CAST(DIVIPOLA AS VARCHAR),1,2),2,'0') dpto,
             ANY_VALUE(departamento) departamento,
             AVG(TRY_CAST(densidad_bancaria AS DOUBLE)) densidad_bancaria
      FROM read_parquet('plata/contexto_municipal_2025.parquet') GROUP BY 1
    ), credito AS (
      SELECT LPAD(SUBSTR(CAST(DIVIPOLA AS VARCHAR),1,2),2,'0') dpto,
             COUNT(*) FILTER (WHERE LOWER(CAST(Sexo AS VARCHAR)) IN ('f','2','femenino','mujer')) creditos_mujeres
      FROM read_parquet('plata/finagro_2025_limpia.parquet') GROUP BY 1
    )
    SELECT c.departamento, c.dpto, c.densidad_bancaria, COALESCE(k.creditos_mujeres,0) creditos_mujeres
    FROM contexto c LEFT JOIN credito k USING(dpto)
    ORDER BY creditos_mujeres DESC
    """
    territorial = con.execute(territorial_sql).fetchall()
    con.close()
    resumen = {}
    inicio = html.rfind("const D=")
    fin = html.find(",S=D.summary", inicio)
    if inicio >= 0 and fin > inicio:
        try:
            resumen = json.loads(html[inicio + len("const D="):fin]).get("summary", {})
        except json.JSONDecodeError:
            resumen = {}
    # Modificar únicamente el script de la aplicación, no el código interno
    # de Plotly, que también contiene declaraciones `const D`.
    marca = ",S=D.summary,F="
    pos = html.rfind(marca)
    if pos >= 0:
        html = html[:pos] + ";window.__DASH_DATA=D;const S=D.summary,F=" + html[pos + len(marca):]
    cdn = "<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>"
    html = html.replace(cdn, "<script>" + plotly_offline.get_plotlyjs() + "</script>", 1)
    nuevo = """
<article class='card chart wide' style='grid-column:span 12'>
  <div id='comparacion_sexo'></div>
  <div class='source'>Fuente: Finagro 2025 y Superfinanciera 2025. Comparación descriptiva por sexo; no representa personas únicas.</div>
</article>
"""
    mujeres = resumen.get("monto_mujeres", "N/D")
    hombres = resumen.get("monto_hombres", "N/D")
    tasa_m = resumen.get("tasa_mujeres", "N/D")
    tasa_h = resumen.get("tasa_hombres", "N/D")
    max_monto = max(float(mujeres or 0), float(hombres or 0), 1)
    width_m = float(mujeres or 0) / max_monto * 100
    width_h = float(hombres or 0) / max_monto * 100
    fallback = f"""<div class='comparison-fallback' style='padding:18px;color:#d7e2ed'>
      <h3 style='margin:0 0 18px'>Monto y tasa promedio por sexo</h3>
      <div style='margin:12px 0'><b>Mujeres</b> · ${float(mujeres or 0):,.0f} COP · {float(tasa_m or 0):.1f}%<div style='height:18px;background:#17212d;border-radius:9px;margin-top:6px'><div style='height:18px;width:{width_m:.2f}%;background:#20d47b;border-radius:9px'></div></div></div>
      <div style='margin:12px 0'><b>Hombres</b> · ${float(hombres or 0):,.0f} COP · {float(tasa_h or 0):.1f}%<div style='height:18px;background:#17212d;border-radius:9px;margin-top:6px'><div style='height:18px;width:{width_h:.2f}%;background:#f5b942;border-radius:9px'></div></div></div>
      <small style='color:#8293a6'>La longitud de la barra representa el monto promedio aprobado. La tasa aparece junto al valor.</small>
    </div>"""
    nuevo = nuevo.replace("<div id='comparacion_sexo'></div>", "<div id='comparacion_sexo'>" + fallback + "</div>")
    edu_rows = "".join(
        f"<div style='margin:10px 0'><b>{nivel} · {sexo}</b> · {float(tasa):.1f}%<div style='height:16px;background:#17212d;border-radius:8px'><div style='height:16px;width:{max(0,min(100,float(tasa))):.2f}%;background:{'#f06aa8' if sexo == 'Mujeres' else '#4cc9f0'};border-radius:8px'></div></div></div>"
        for nivel, sexo, tasa, _ in edu
    )
    educacion = f"""<article class='card chart wide' style='grid-column:span 12'>
      <div style='padding:18px'><h3>Inclusión financiera y educación</h3>
      <p style='color:#8293a6'>Porcentaje estimado de hogares rurales con al menos un producto financiero, según el nivel educativo y el género de la jefatura.</p>
      {edu_rows or '<p>Sin datos disponibles.</p>'}</div>
      <div class='source'>Fuente: GEIH 2025 rural. Unidad: hogar; nivel educativo del jefe de hogar; ponderación FEX_C18.</div>
    </article>"""
    html = html.replace("</section></main>", educacion + "</section></main>", 1)
    jef_rows = "".join(
        f"<div style='margin:9px 0'><b>{sexo} · {tamano}</b> · {float(tasa):.1f}% con productos financieros<div style='height:14px;background:#17212d;border-radius:7px'><div style='height:14px;width:{max(0,min(100,float(tasa))):.2f}%;background:{'#f06aa8' if sexo == 'Mujeres' else '#4cc9f0'};border-radius:7px'></div></div></div>"
        for sexo, tamano, tasa, _ in jefatura
    )
    jef_chart = f"""<article class='card chart wide' style='grid-column:span 12'><div style='padding:18px'><h3>Jefatura, tamaño del hogar e inclusión financiera</h3><p style='color:#8293a6'>Porcentaje de hogares rurales con al menos un producto financiero, según el género de la jefatura y el número de personas.</p>{jef_rows}</div><div class='source'>Fuente: GEIH 2025 rural. Unidad: hogar; ponderación FEX_C18.</div></article>"""
    terr_rows = "".join(
        f"<div style='margin:8px 0;display:grid;grid-template-columns:150px 1fr 110px;gap:10px;align-items:center'><b>{depto or dpto}</b><span style='height:14px;background:#17212d;border-radius:7px'><i style='display:block;height:14px;width:{min(100,float(creditos)/(max([float(x[3]) for x in territorial] or [1]))*100):.2f}%;background:#20d47b;border-radius:7px'></i></span><small>{int(creditos):,} créditos · densidad {float(densidad or 0):.1f}</small></div>"
        for depto, dpto, densidad, creditos in territorial[:10]
    )
    terr_chart = f"""<article class='card chart wide' style='grid-column:span 12'><div style='padding:18px'><h3>Ruralidad territorial, densidad bancaria y crédito para mujeres</h3><p style='color:#8293a6'>Top 10 departamentos por número de créditos Finagro para mujeres; la densidad bancaria se muestra junto a cada departamento.</p>{terr_rows}</div><div class='source'>Fuentes: Finagro 2025 y Contexto Municipal 2025. Unidad: departamento; los créditos son registros, no personas únicas.</div></article>"""
    html = html.replace("</section></main>", jef_chart + terr_chart + "</section></main>", 1)
    html = html.replace("</section></main>", nuevo + "</section></main>", 1)
    comparacion = """
<script>
if (window.Plotly) {
  const S2 = window.__DASH_SUMMARY || {};
  const money2 = v => Number(v).toLocaleString('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0});
  const pct2 = v => Number(v).toLocaleString('es-CO',{maximumFractionDigits:1}) + '%';
  const montoSexo = [S2.monto_mujeres || 0, S2.monto_hombres || 0];
  const tasaSexo = [S2.tasa_mujeres || 0, S2.tasa_hombres || 0];
  Plotly.newPlot('comparacion_sexo', [
    {x:['Mujeres','Hombres'], y:montoSexo, name:'Monto promedio aprobado (COP)', type:'bar', marker:{color:'#20d47b'}, text:montoSexo.map(money2), textposition:'outside', yaxis:'y'},
    {x:['Mujeres','Hombres'], y:tasaSexo, name:'Tasa promedio (%)', type:'bar', marker:{color:'#f5b942'}, text:tasaSexo.map(pct2), textposition:'outside', yaxis:'y2'}
  ], {autosize:true, paper_bgcolor:'#0d141f', plot_bgcolor:'#0d141f', font:{color:'#d7e2ed'},
    margin:{l:70,r:70,t:65,b:45}, title:{text:'Comparación financiera entre mujeres y hombres<br><sup>El monto y la tasa muestran diferencias de acceso y condiciones</sup>'},
    barmode:'group', yaxis:{title:'Monto promedio aprobado (COP)',rangemode:'tozero'}, yaxis2:{title:'Tasa promedio (%)',overlaying:'y',side:'right',rangemode:'tozero'}, legend:{orientation:'h'}, showlegend:true});
}
</script>
"""
    html = html.replace("</body>", comparacion + "</body>", 1)
    base.HTML.write_text(html, encoding="utf-8")
    # El tablero consolidado queda como archivo principal.
    shutil.copyfile(base.HTML, BASE / "financiero_dashboard.html")
    print(f"Dashboard consolidado: {BASE / 'financiero_dashboard.html'}")
    print(f"Dashboard adicional: {base.HTML}")
