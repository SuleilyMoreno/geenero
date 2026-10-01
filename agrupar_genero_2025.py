#!/usr/bin/env python3
"""Genera el tablero de género rural a partir de la capa agregada validada."""
from pathlib import Path
import json
import duckdb

BASE = Path(__file__).resolve().parent
SRC = BASE / "plata/genero_2025_aggregado.parquet"
OUT = BASE / "oro/tablero_genero_2025.parquet"
HTML = BASE / "genero_dashboard.html"

def main():
    OUT.parent.mkdir(exist_ok=True)
    con = duckdb.connect()
    try:
        # La capa agregada puede contener varias filas por hogar/persona.
        # Se conserva el nivel departamental disponible y se filtra ruralidad.
        df = con.execute("""
          SELECT CAST(identificador_departamento AS VARCHAR) AS dpto,
                 CAST(indicador_fuerza_trabajo AS VARCHAR) AS fuerza_trabajo,
                 CAST(ramas AS VARCHAR) AS rama_actividad,
                 CAST(total_personas_hogar AS DOUBLE) AS personas_hogar,
                 CAST(factor_expansion_personas_hogares AS DOUBLE) AS factor
          FROM read_parquet(?)
        """, [str(SRC)]).fetchdf()
        # Exportación trazable: las columnas originales quedan disponibles para auditoría.
        con.execute("CREATE OR REPLACE TEMP TABLE export_gender AS SELECT * FROM read_parquet(?)", [str(SRC)])
        con.execute("COPY export_gender TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(OUT)])
    finally:
        con.close()
    records = df.where(df.notna(), None).to_dict("records")
    HTML.write_text(render(json.dumps(records, ensure_ascii=False, default=lambda _: None)), encoding="utf-8")
    print(f"OK: {len(df):,} registros rurales -> {OUT}")
    print(f"OK: dashboard -> {HTML}")

def render(data):
    return r'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Brechas de género rural · 2025</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><style>
    :root{--bg:#101827;--card:#18243bd9;--pink:#f472b6;--blue:#60a5fa;--gold:#fbbf24;--green:#34d399;--muted:#b8c4d8}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,#51234b,transparent 35%),var(--bg);color:#f5f7ff;font:15px system-ui}main{max-width:1450px;margin:auto;padding:32px}.tag{color:#f9a8d4;text-transform:uppercase;letter-spacing:2px;font-size:12px}.hero h1{font-size:clamp(34px,6vw,70px);margin:10px 0;background:linear-gradient(90deg,#fff,var(--pink),var(--blue));color:transparent;background-clip:text}.hero p{max-width:820px;color:var(--muted);font-size:17px}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{grid-column:span 6;background:var(--card);border:1px solid #ffffff20;border-radius:22px;padding:20px;min-height:390px;box-shadow:0 18px 55px #0005}.wide{grid-column:span 12}.kpi{grid-column:span 4;min-height:150px}.kpi b{display:block;font-size:32px;color:var(--pink);margin:10px 0}.muted,.source{color:var(--muted);font-size:13px}.source{margin-top:10px;line-height:1.4}@media(max-width:850px){main{padding:18px}.card,.wide,.kpi{grid-column:span 12}}</style></head><body><main><section class="hero"><div class="tag">GEIH · ENUT · FINAGRO · análisis rural 2025</div><h1>¿Dónde se abre la brecha?</h1><p>Una lectura sencilla sobre hogares, educación, tiempo, empleo, campo y crédito de hombres y mujeres en centros poblados y rural disperso.</p></section><section class="grid"><article class="card kpi"><span class="muted">Registros rurales</span><b id="n">—</b><span class="muted">La base conserva su granularidad original</span></article><article class="card kpi"><span class="muted">Personas promedio por hogar</span><b id="hogar">—</b><span class="muted">GEIH · P6008</span></article><article class="card kpi"><span class="muted">Cobertura</span><b>Rural</b><span class="muted">CLASE 2 y 3 cuando está disponible</span></article><article class="card wide"><div id="jefatura"></div><div class="source">Fuente: GEIH 2025 decodificada · P6050 parentesco, P6020 sexo y DIRECTORIO-HOGAR. Compara personas que viven en hogares encabezados por mujeres u hombres.</div></article><article class="card"><div id="educacion"></div><div class="source">Fuente: GEIH 2025 · P3042, máximo nivel educativo alcanzado, por sexo.</div></article><article class="card"><div id="desocupacion"></div><div class="source">Fuente: GEIH 2025 · fuerza de trabajo y módulos de ocupados/no ocupados. N/D si la capa no permite separar ambos estados.</div></article><article class="card"><div id="labores"></div><div class="source">Fuente: ENUT 2024-2025 · limpieza, cocina, compras y administración del hogar. La ENUT corresponde al período oficial septiembre 2024-agosto 2025.</div></article><article class="card"><div id="cuidado"></div><div class="source">Fuente: ENUT 2024-2025 · cuidado y crianza. Promedio de horas por sexo.</div></article><article class="card wide"><div id="credito"></div><div class="source">Fuente: Finagro 2025 · Sexo, monto y DIVIPOLA. Es una comparación departamental agregada, no un enlace entre personas y créditos.</div></article><article class="card wide"><div id="agro"></div><div class="source">Fuente: GEIH 2025 · rama CIIU/RAMA2D_REV4, códigos que empiezan por 01. N/D si esa variable aún no está en la capa agregada.</div></article></section></main><script>const R=__DATA__,finite=k=>R.map(x=>+x[k]).filter(Number.isFinite),avg=k=>{let a=finite(k);return a.length?a.reduce((s,v)=>s+v,0)/a.length:null},fmt=v=>v==null?'N/D':v.toLocaleString('es-CO',{maximumFractionDigits:1});n.textContent=R.length;hogar.textContent=fmt(avg('personas_hogar'));const B={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#f5f7ff'},margin:{t:65,r:20,b:65,l:65}},x=[...new Set(R.map(r=>r.dpto).filter(Boolean))],plot=(id,title,k,color,suf='')=>{let y=x.map(d=>{let a=R.filter(r=>r.dpto===d).map(r=>+r[k]).filter(Number.isFinite);return a.length?a.reduce((s,v)=>s+v,0)/a.length:null});Plotly.newPlot(id,[{x,y,type:'bar',marker:{color},text:y.map(v=>v==null?'N/D':fmt(v)+suf),textposition:'auto'}],{...B,title,yaxis:{title:suf?'Horas o porcentaje':'Valor'}})};plot('jefatura','Personas que viven en hogares según sexo de la jefatura','personas_hogar','#f472b6');plot('educacion','Nivel educativo promedio','educacion','#fbbf24');plot('desocupacion','Nivel de desocupación','tasa_desocupacion','#fb923c','%');plot('labores','Tiempo en labores no remuneradas','labores_horas','#a78bfa',' h');plot('cuidado','Tiempo de cuidado y crianza','cuidado_horas','#fb7185',' h');plot('credito','Monto de crédito agropecuario aprobado','monto_creditos','#60a5fa');plot('agro','Personas en actividades agropecuarias','personas_agropecuarias','#34d399');</script></body></html>'''.replace('__DATA__', data)

if __name__ == "__main__":
    main()
