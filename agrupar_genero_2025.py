#!/usr/bin/env python3
"""Capa oro y dashboard de storytelling para brechas de género 2025."""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
import pandas as pd

BASE = Path(__file__).resolve().parent
PLATA, ORO = BASE / "plata", BASE / "oro"
GEIH = PLATA / "geih_2025_limpia.parquet"
ENUT = PLATA / "enut_2025_limpia.parquet"
FINAGRO = PLATA / "finagro_2025_limpia.parquet"
SALIDA, HTML = ORO / "tablero_genero_2025.parquet", BASE / "genero_dashboard.html"

def pick(cols, *names):
    return next((x for x in names if x in cols), None)

def qi(x):
    return '"' + x.replace('"', '""') + '"'

def build_dataset() -> pd.DataFrame:
    con = duckdb.connect()
    try:
        for name, path in (("geih", GEIH), ("enut", ENUT), ("finagro", FINAGRO)):
            con.execute(f"CREATE TEMP TABLE {name} AS SELECT * FROM read_parquet(?)", [str(path)])
        cols = {t: {r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()} for t in ("geih", "enut", "finagro")}
        gd, gs = pick(cols["geih"], "DIVIPOLA"), pick(cols["geih"], "SEXO", "Sexo")
        ed, es = pick(cols["enut"], "DIVIPOLA"), pick(cols["enut"], "SEXO", "Sexo")
        fd, fs = pick(cols["finagro"], "DIVIPOLA"), pick(cols["finagro"], "SEXO", "Sexo")
        if not (gd and gs): raise ValueError("GEIH requiere DIVIPOLA y SEXO/Sexo")
        # Equivalentes disponibles en los parquet normalizados.
        jefe, sexo_original = pick(cols["geih"], "P6050"), pick(cols["geih"], "P6020")
        educ = pick(cols["geih"], "P3042", "nivel_educativo", "maximo_nivel_educativo")
        actividad = pick(cols["geih"], "OCI", "indicador_ocupados", "Ocupado")
        rama = pick(cols["geih"], "RAMA2D_REV4", "CIIU", "rama_actividad_empleo_principal_2", "rama_actividad_empleo_principal")
        tnr = pick(cols["enut"], "tiempo_tnr", "TNR_horas", "horas_tnr")
        cuidado = pick(cols["enut"], "tiempo_cuidado_personas", "horas_cuidado_personas", "cuidado_personas")
        monto = pick(cols["finagro"], "monto_aprobado", "monto")
        credito = pick(cols["finagro"], "id_credito")
        jefatura = f"SUM(CASE WHEN TRY_CAST({qi(jefe)} AS DOUBLE)=1 THEN 1 ELSE 0 END)" if jefe else "CAST(NULL AS BIGINT)"
        hombres = f"SUM(CASE WHEN TRY_CAST({qi(jefe)} AS DOUBLE)=1 AND TRY_CAST({qi(sexo_original)} AS DOUBLE)=1 THEN 1 ELSE 0 END)" if jefe and sexo_original else "CAST(NULL AS BIGINT)"
        mujeres = f"SUM(CASE WHEN TRY_CAST({qi(jefe)} AS DOUBLE)=1 AND TRY_CAST({qi(sexo_original)} AS DOUBLE)=2 THEN 1 ELSE 0 END)" if jefe and sexo_original else "CAST(NULL AS BIGINT)"
        edu_sql = f"AVG(TRY_CAST({qi(educ)} AS DOUBLE))" if educ else "CAST(NULL AS DOUBLE)"
        ocupado = f"lower(trim(CAST({qi(actividad)} AS VARCHAR))) IN ('1','si','sí','ocupado','ocupada')" if actividad else "FALSE"
        desocupado = f"lower(trim(CAST({qi(actividad)} AS VARCHAR))) IN ('2','desocupado','desocupada')" if actividad else "FALSE"
        agro = f"SUM(CASE WHEN {ocupado} AND CAST({qi(rama)} AS VARCHAR) LIKE '01%' THEN 1 ELSE 0 END)" if rama else "CAST(NULL AS BIGINT)"
        tnr_expr = f"AVG(TRY_CAST({qi(tnr)} AS DOUBLE))" if tnr else "CAST(NULL AS DOUBLE)"
        cuidado_expr = f"AVG(TRY_CAST({qi(cuidado)} AS DOUBLE))" if cuidado else "CAST(NULL AS DOUBLE)"
        enut_sql = f"SELECT {qi(ed)} AS DIVIPOLA,{qi(es)} AS SEXO,{tnr_expr} AS tiempo_tnr_promedio,{cuidado_expr} AS tiempo_cuidado_promedio FROM enut GROUP BY 1,2" if ed and es else "SELECT NULL::VARCHAR DIVIPOLA,NULL::VARCHAR SEXO,NULL::DOUBLE tiempo_tnr_promedio,NULL::DOUBLE tiempo_cuidado_promedio WHERE FALSE"
        fin_sql = f"SELECT {qi(fd)} AS DIVIPOLA,{qi(fs)} AS SEXO,SUM(TRY_CAST({qi(monto)} AS DOUBLE)) AS monto_creditos,COUNT({qi(credito) if credito else '*'}) AS aprobaciones FROM finagro GROUP BY 1,2" if fd and fs and monto else "SELECT NULL::VARCHAR DIVIPOLA,NULL::VARCHAR SEXO,NULL::DOUBLE monto_creditos,NULL::BIGINT aprobaciones WHERE FALSE"
        sql = f"""
        WITH g AS (SELECT {qi(gd)} AS DIVIPOLA,{qi(gs)} AS SEXO,{jefatura} AS jefes_hogar,{hombres} AS jefes_hombres,{mujeres} AS jefas_mujeres,
          {edu_sql} AS nivel_educativo_promedio,{agro} AS personas_agropecuarias,
          SUM(CASE WHEN {desocupado} THEN 1 ELSE 0 END)::DOUBLE/NULLIF(SUM(CASE WHEN {ocupado} OR {desocupado} THEN 1 ELSE 0 END),0) AS tasa_desocupacion
          FROM geih GROUP BY 1,2), e AS ({enut_sql}), f AS ({fin_sql}), claves AS (SELECT DIVIPOLA,SEXO FROM g UNION SELECT DIVIPOLA,SEXO FROM e UNION SELECT DIVIPOLA,SEXO FROM f)
        SELECT k.DIVIPOLA,k.SEXO,g.jefes_hogar,g.jefes_hombres,g.jefas_mujeres,e.tiempo_tnr_promedio,e.tiempo_cuidado_promedio,g.nivel_educativo_promedio,g.tasa_desocupacion,
          f.monto_creditos,f.aprobaciones,g.personas_agropecuarias,
          CASE WHEN f.monto_creditos IS NULL THEN NULL ELSE f.monto_creditos END AS monto_aprobado
        FROM claves k LEFT JOIN g USING(DIVIPOLA,SEXO) LEFT JOIN e USING(DIVIPOLA,SEXO) LEFT JOIN f USING(DIVIPOLA,SEXO)"""
        df = con.execute(sql).fetchdf(); ORO.mkdir(exist_ok=True)
        con.execute("COPY (" + sql + ") TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(SALIDA)])
        return df
    finally: con.close()

def generate_dashboard(df: pd.DataFrame):
    data = json.dumps(df.astype(object).where(pd.notna(df), None).to_dict("records"), ensure_ascii=False, allow_nan=False, default=lambda _: None)
    html = """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Brecha de género · 2025</title><script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script><style>:root{--bg:#0b1020;--card:#17213bd9;--pink:#fb7185;--blue:#60a5fa;--muted:#a8b4ca}*{box-sizing:border-box}body{margin:0;color:#edf2ff;font:15px system-ui;background:radial-gradient(circle at 85% 0,#5b214c,transparent 35%),linear-gradient(135deg,var(--bg),#101827)}main{max-width:1450px;margin:auto;padding:34px}.hero{margin-bottom:22px}.tag{color:#fda4af;letter-spacing:2px;text-transform:uppercase;font-size:12px}.hero h1{font-size:clamp(32px,6vw,68px);margin:8px 0;background:linear-gradient(90deg,#fff,var(--pink),var(--blue));color:transparent;background-clip:text}.hero p{color:var(--muted);max-width:780px;font-size:17px}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{grid-column:span 6;background:var(--card);border:1px solid #ffffff20;border-radius:22px;padding:20px;backdrop-filter:blur(15px);box-shadow:0 18px 55px #0005;min-height:390px}.full{grid-column:span 12}.insight{grid-column:span 4;min-height:150px}.insight b{font-size:30px;display:block;margin:10px 0;color:var(--pink)}.muted{color:var(--muted);font-size:13px}@media(max-width:850px){main{padding:18px}.card,.full,.insight{grid-column:span 12}}</style></head><body><main><section class='hero'><div class='tag'>GEIH · ENUT · FINAGRO / 2025</div><h1>¿Dónde se abre la brecha?</h1><p>Un recorrido visual desde quién lidera los hogares, pasa por el tiempo de cuidado y termina en el acceso al crédito agropecuario.</p></section><section class='grid'><article class='insight card'><span class='muted'>Territorios comparados</span><b id='n'>—</b><span class='muted'>combinaciones municipio-sexo</span></article><article class='insight card'><span class='muted'>Brecha de aprobación</span><b id='gap'>—</b><span class='muted'>monto hombres − mujeres</span></article><article class='insight card'><span class='muted'>Datos ENUT</span><b id='enut'>—</b><span class='muted'>registros disponibles</span></article><article class='card full'><div id='credit'></div></article><article class='card'><div id='care'></div></article><article class='card'><div id='unemp'></div></article><article class='card'><div id='heads'></div></article><article class='card'><div id='agro'></div></article></section></main><script>const R=__DATA__,M=k=>{let a=R.map(x=>+x[k]).filter(Number.isFinite);return a.length?a.reduce((a,b)=>a+b,0)/a.length:null},F=x=>x==null?'Sin dato':x.toLocaleString('es-CO',{maximumFractionDigits:1}),B={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#edf2ff'},margin:{t:55,r:20,b:80,l:55}},S=[...new Set(R.map(x=>x.SEXO))].filter(Boolean),colors=['#60a5fa','#fb7185'];n.textContent=R.length;gap.textContent=F(M('monto_aprobado'));enut.textContent=R.filter(x=>x.tiempo_tnr_promedio!=null).length;let grp=(k)=>S.map(s=>({x:R.filter(x=>x.SEXO===s).map(x=>x.DIVIPOLA),y:R.filter(x=>x.SEXO===s).map(x=>Number(x[k])),name:s,type:'bar'}));Plotly.newPlot('credit',grp('monto_creditos'),{...B,title:'El crédito agropecuario: ¿quién recibe el capital?',barmode:'group',yaxis:{title:'Monto aprobado (COP)'}});Plotly.newPlot('care',grp('tiempo_cuidado_promedio'),{...B,title:'El tiempo de cuidado también es trabajo',barmode:'group',yaxis:{title:'Horas promedio'}});Plotly.newPlot('unemp',grp('tasa_desocupacion'),{...B,title:'Desocupación por sexo',barmode:'group',yaxis:{tickformat:'.0%',title:'Tasa'}});Plotly.newPlot('heads',grp('jefes_hogar'),{...B,title:'Jefatura de hogar por territorio',barmode:'group'});Plotly.newPlot('agro',grp('personas_agropecuarias'),{...B,title:'Participación en actividades agropecuarias',barmode:'group'});</script></body></html>""".replace('__DATA__', data)
    HTML.write_text(html, encoding='utf-8')

def main():
    df=build_dataset(); generate_dashboard(df); print(f'OK: {len(df):,} filas -> {SALIDA}'); print(f'OK: dashboard -> {HTML}')

if __name__=='__main__': main()
