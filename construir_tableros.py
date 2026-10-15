#!/usr/bin/env python3
"""Construye el portal y los cuatro tableros HTML a partir de datos_tablero/*.json.

No consulta microdatos: solo dibuja. Los JSON los generan:
  extraer_credito_rural_2025.py        -> credito_rural_2025.json
  agrupar_genero_2025.py               -> genero_rural_2025.json
  generar_tablero_calidad_vida_2025.py -> calidad_vida_rural_2025.json
  agrupar_departamento_2025.py         -> departamentos_rural_2025.json
  generar_tablero_financiero_nacional_2025.py -> inclusion_financiera_rural_2025.json

Salidas: index.html, genero_dashboard.html, calidad_vida_dashboard.html,
departamentos_dashboard.html, financiero_dashboard.html
"""
from __future__ import annotations

import html
import json

from diccionario_variables import CALIDAD, COMUNES_GEIH, FINANCIERO, GENERO
from diccionario_variables import DEPARTAMENTOS as VAR_DEPARTAMENTOS
from tablero_comun import BASE, DATOS

TITULO = ("Identificación de los factores asociados a las diferencias en el acceso y las condiciones "
          "del crédito formal entre hombres y mujeres rurales en Colombia")
PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"
TABLEROS = [
    ("genero_dashboard.html", "Brechas de género", "Trabajo, cuidado, jefatura del hogar y acceso al crédito Finagro por sexo."),
    ("calidad_vida_dashboard.html", "Calidad de vida", "Servicios públicos, ingresos, inseguridad alimentaria y pobreza multidimensional."),
    ("departamentos_dashboard.html", "Departamentos", "Mapas de ruralidad, IPM, inseguridad alimentaria, inclusión financiera y crédito."),
    ("financiero_dashboard.html", "Crédito e inclusión financiera", "Número, monto, tasa y plazo del crédito rural por sexo; productos financieros del hogar."),
]


def cargar(nombre: str) -> dict:
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#6f6d68;
--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);--accent:#256abf;--mujeres:#d55181;--hombres:#2a78d6;
--otro:#898781;--serie:#2a78d6;--warn-bg:#fff6e0;--warn-ink:#6b4a00;--seq0:#cde2fb;--seq1:#86b6ef;--seq2:#3987e5;--seq3:#1c5cab;--seq4:#0d366b}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--muted:#a3a198;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--accent:#6da7ec;
--mujeres:#d55181;--hombres:#3987e5;--otro:#898781;--serie:#3987e5;--warn-bg:#2a2210;--warn-ink:#f3d58a}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#a3a198;
--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--accent:#6da7ec;--mujeres:#d55181;--hombres:#3987e5;--otro:#898781;
--serie:#3987e5;--warn-bg:#2a2210;--warn-ink:#f3d58a}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent)}main{max-width:1280px;margin:0 auto;padding:24px 16px 64px}
.nav{position:sticky;top:0;z-index:5;background:var(--surface);border-bottom:1px solid var(--border)}
.nav div{max-width:1280px;margin:0 auto;padding:10px 16px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.nav a{padding:6px 12px;border-radius:999px;text-decoration:none;color:var(--ink2);font-size:14px}
.nav a[aria-current="page"]{background:var(--accent);color:#fff}.nav a:hover{background:var(--grid)}
.estudio{font-size:13px;color:var(--muted);margin:0 0 6px;max-width:900px}
h1{font-size:clamp(26px,4vw,40px);line-height:1.15;margin:4px 0 8px;text-wrap:balance}
h2{font-size:22px;margin:40px 0 12px}h3{font-size:16px;margin:0 0 2px}
.lead{color:var(--ink2);max-width:820px;margin:0 0 12px}
.filtro{display:inline-flex;gap:8px;flex-wrap:wrap}.chip{border:1px solid var(--border);background:var(--surface);
border-radius:999px;padding:4px 12px;font-size:13px;color:var(--ink2)}.chip b{color:var(--ink)}
.aviso{background:var(--warn-bg);color:var(--warn-ink);border-radius:12px;padding:12px 16px;margin:16px 0;font-size:14px}
.aviso ul{margin:6px 0 0;padding-left:20px}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px;margin-top:16px}
.card{grid-column:span 6;background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:18px;min-width:0}
.card.wide{grid-column:span 12}.kpi{grid-column:span 3}
.kpi .label{font-size:13px;color:var(--ink2)}.kpi .value{font-size:30px;font-weight:700;margin:6px 0 2px}
.pair{display:flex;gap:20px;flex-wrap:wrap}.pair .value{font-size:22px;white-space:nowrap}.pair small{display:flex;align-items:center;gap:6px;color:var(--ink2)}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.sub{color:var(--ink2);font-size:13px;margin:0 0 8px}.src{color:var(--muted);font-size:12px;margin-top:8px}
.plot{width:100%;min-height:340px}.plot.tall{min-height:560px}
details{margin-top:8px}summary{cursor:pointer;color:var(--accent);font-size:13px}
.tabla{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600;background:var(--page)}td.n{text-align:right}
.pendiente{display:flex;align-items:center;justify-content:center;min-height:200px;text-align:center;
color:var(--muted);border:1px dashed var(--axis);border-radius:12px;padding:20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.tile{display:block;text-decoration:none;color:inherit;background:var(--surface);border:1px solid var(--border);
border-radius:16px;padding:18px}.tile:hover{border-color:var(--accent)}.tile b{display:block;font-size:17px;margin-bottom:4px;color:var(--accent)}
.var{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 16px;margin:8px 0}
.var summary{color:var(--ink);font-size:14px;line-height:1.5}.var summary code{color:var(--accent);font-weight:600}
.var dl{display:grid;grid-template-columns:210px 1fr;gap:8px 18px;margin:14px 0 4px;font-size:14px}.var dt{color:var(--ink2);font-weight:600}
.var dd{margin:0}.var ol{margin:0;padding-left:20px}.var dd code{background:var(--page);padding:2px 6px;border-radius:6px}
.btn{border:1px solid var(--border);background:var(--surface);color:var(--accent);border-radius:999px;padding:6px 14px;font:inherit;cursor:pointer}
@media(max-width:700px){.var dl{grid-template-columns:1fr}}
.er svg{width:100%;height:auto;display:block}.er text{font-family:system-ui,sans-serif}
@media(max-width:1000px){.kpi{grid-column:span 6}.card{grid-column:span 12}}
@media(max-width:560px){.kpi{grid-column:span 12}}
"""

JS = r"""
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const NF=(d=1)=>new Intl.NumberFormat('es-CO',{maximumFractionDigits:d});
const f1=x=>x==null||!isFinite(x)?'N/D':NF(1).format(x), f0=x=>x==null||!isFinite(x)?'N/D':NF(0).format(x);
const pct=x=>x==null||!isFinite(x)?'N/D':NF(1).format(x)+' %';
const cop=x=>x==null||!isFinite(x)?'N/D':'$'+NF(0).format(x);
const copM=x=>x==null||!isFinite(x)?'N/D':'$'+NF(1).format(x/1e6)+' M';
const wrap=(t,n=18)=>{const w=String(t).split(' ');let l=[],c='';for(const p of w){if((c+' '+p).trim().length>n&&c){l.push(c);c=p}else c=(c+' '+p).trim()}l.push(c);return l.join('<br>')};
const SEXOS=['Mujeres','Hombres'];
const colorSexo=s=>s==='Mujeres'?css('--mujeres'):s==='Hombres'?css('--hombres'):css('--otro');
function base(extra={}){return Object.assign({autosize:true,paper_bgcolor:css('--surface'),plot_bgcolor:css('--surface'),
 font:{family:'system-ui,-apple-system,Segoe UI,sans-serif',color:css('--ink'),size:13},margin:{l:10,r:20,t:10,b:40},
 hoverlabel:{bgcolor:css('--surface'),bordercolor:css('--axis'),font:{color:css('--ink')}},
 legend:{orientation:'h',y:1.08,x:0,traceorder:'normal',font:{color:css('--ink2')}},separators:',.',bargap:.28,bargroupgap:.08,
 xaxis:{tickangle:0,automargin:true,exponentformat:'none',separatethousands:true,gridcolor:css('--grid'),linecolor:css('--axis'),zerolinecolor:css('--axis'),tickfont:{color:css('--ink2')},title:{font:{color:css('--ink2')}}},
 yaxis:{tickangle:0,automargin:true,gridcolor:css('--grid'),linecolor:css('--axis'),zerolinecolor:css('--axis'),tickfont:{color:css('--ink2')},title:{font:{color:css('--ink2')}}}},extra)}
const CFG={displaylogo:false,responsive:true,modeBarButtonsToRemove:['lasso2d','select2d']};
function deep(a,b){for(const k in b){if(b[k]&&typeof b[k]==='object'&&!Array.isArray(b[k])&&a[k])deep(a[k],b[k]);else a[k]=b[k]}return a}
function plot(id,traces,lay={}){const el=document.getElementById(id);if(!el)return;Plotly.react(el,traces,deep(base(),lay),CFG)}
// Barras horizontales agrupadas por sexo: categorías en el eje Y (sin rotar etiquetas).
function barrasSexo(id,cats,series,{fmt=pct,titulo='Porcentaje (%)',rango=null,orden=null}={}){
 const sx=Object.keys(series);plot(id,sx.map(s=>({type:'bar',orientation:'h',name:s,y:cats.map(c=>wrap(c,22)),x:series[s],
  marker:{color:colorSexo(s),cornerradius:4},text:series[s].map(fmt),textposition:'outside',cliponaxis:false,
  textfont:{color:css('--ink2')},hovertemplate:'%{y}<br>'+s+': %{text}<extra></extra>'})),
  {barmode:'group',height:Math.max(320,cats.length*sx.length*30+100),yaxis:{autorange:'reversed'},xaxis:{title:{text:titulo},range:rango},margin:{l:10,r:60,t:30,b:50}})}
function barras(id,cats,vals,{fmt=pct,titulo='Porcentaje (%)',rango=null,color=null,h=null}={}){
 plot(id,[{type:'bar',orientation:'h',y:cats.map(c=>wrap(c,24)),x:vals,marker:{color:color||css('--serie'),cornerradius:4},
  text:vals.map(fmt),textposition:'outside',cliponaxis:false,textfont:{color:css('--ink2')},hovertemplate:'%{y}: %{text}<extra></extra>'}],
  {showlegend:false,height:h||Math.max(300,cats.length*30+80),yaxis:{autorange:'reversed'},xaxis:{title:{text:titulo},range:rango},margin:{l:10,r:70,t:10,b:50}})}
// Tabla accesible gemela del gráfico.
function tabla(id,cabeza,filas){const el=document.getElementById(id);if(!el)return;
 el.innerHTML='<details><summary>Ver tabla de datos</summary><div class="tabla"><table><thead><tr>'+cabeza.map(c=>'<th>'+c+'</th>').join('')+
 '</tr></thead><tbody>'+filas.map(r=>'<tr>'+r.map((v,i)=>'<td'+(i?' class="n"':'')+'>'+v+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></details>'}
function txt(id,v){const el=document.getElementById(id);if(el)el.textContent=v}
let DIBUJAR=()=>{};
addEventListener('DOMContentLoaded',()=>{DIBUJAR();matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>DIBUJAR())});
"""


def nav(actual: str) -> str:
    enlaces = [("index.html", "Inicio")] + [(a, t) for a, t, _ in TABLEROS]
    return "<nav class='nav' aria-label='Tableros'><div>" + "".join(
        f"<a href='{a}'{' aria-current=\"page\"' if a == actual else ''}>{t}</a>" for a, t in enlaces) + "</div></nav>"


def filtros() -> str:
    return ("<div class='filtro'><span class='chip'>Ruralidad: <b>centros poblados y rural disperso</b> "
            "(encuestas) · <b>municipios Rural / Rural disperso DNP</b> (crédito)</span>"
            "<span class='chip'>Año: <b>2025</b></span></div>")


def aviso(pendientes: list[str]) -> str:
    if not pendientes:
        return ""
    return ("<div class='aviso' role='note'><b>Indicadores que cambian al re-ejecutar el pipeline con los microdatos.</b>"
            "<ul>" + "".join(f"<li>{html.escape(p)}</li>" for p in pendientes) + "</ul></div>")


def variables(filas: list[dict]) -> str:
    """Sección «Variables creadas»: una ficha desplegable por variable."""
    esc = html.escape
    fichas = "".join(
        f"<details class='var'><summary><code>{esc(v['variable'])}</code> — {esc(v['representa'])}</summary><dl>"
        f"<dt>Base y columnas originales</dt><dd>{esc(v['fuente'])}</dd>"
        f"<dt>Universo y filtros</dt><dd>{esc(v['universo'])}</dd>"
        f"<dt>Cálculo paso a paso</dt><dd><ol>{''.join(f'<li>{esc(p)}</li>' for p in v['pasos'])}</ol></dd>"
        f"<dt>Fórmula</dt><dd><code>{esc(v['formula'])}</code></dd>"
        f"<dt>Cómo leerla</dt><dd>{esc(v['lectura'])}</dd></dl></details>" for v in filas)
    return ("<h2 id='variables'>Variables creadas en este tablero</h2><p class='lead'>Variables que no existen en las bases "
            "originales. Cada ficha indica de qué columnas sale, a qué población se aplica, cómo se calculó paso a paso "
            "y cómo leer el resultado.</p><p><button class='btn' type='button' onclick=\"document.querySelectorAll('details.var')"
            ".forEach(d=>d.open=!d.open)\">Abrir o cerrar todas las fichas</button></p>" + fichas)


def pagina(archivo: str, titulo: str, lead: str, cuerpo: str, datos: dict, script: str, extra_head: str = "") -> None:
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titulo)} · Crédito rural 2025</title><style>{CSS}</style>{extra_head}
<script src="{PLOTLY}"></script></head><body>{nav(archivo)}
<main><p class="estudio">{TITULO}</p><h1>{html.escape(titulo)}</h1><p class="lead">{lead}</p>{filtros()}{cuerpo}</main>
<script>const DATA={json.dumps(datos, ensure_ascii=False, default=float)};{JS}{script}</script></body></html>"""
    (BASE / archivo).write_text(doc, encoding="utf-8")
    print(f"OK -> {archivo}")


def card(id_: str, titulo: str, sub: str, fuente: str, wide: bool = False, tall: bool = False) -> str:
    return (f"<article class='card{' wide' if wide else ''}'><h3>{titulo}</h3><p class='sub'>{sub}</p>"
            f"<div id='{id_}' class='plot{' tall' if tall else ''}' role='img' aria-label='{html.escape(titulo)}'></div>"
            f"<div id='{id_}_t'></div><p class='src'>{fuente}</p></article>")


def kpi(id_: str, etiqueta: str, fuente: str, par: bool = False) -> str:
    if par:
        valor = ("<div class='pair'>" + "".join(
            f"<div><small><span class='dot' style='background:var(--{s.lower()})'></span>{s}</small>"
            f"<div class='value' id='{id_}_{s.lower()}'>N/D</div></div>" for s in ("Mujeres", "Hombres")) + "</div>")
    else:
        valor = f"<div class='value' id='{id_}'>N/D</div>"
    return f"<article class='card kpi'><div class='label'>{etiqueta}</div>{valor}<p class='src'>{fuente}</p></article>"


# ───────────────────────────── Tableros ─────────────────────────────

def tablero_genero(g: dict, cr: dict) -> None:
    cuerpo = aviso(g.get("pendientes", [])) + "<section class='grid'>" + "".join([
        kpi("part", "Mujeres dentro del total de personas ocupadas", "GEIH 2025 rural, ponderado."),
        kpi("jfem", "Hogares rurales con jefatura femenina", "GEIH 2025 rural, ponderado."),
        kpi("agro", "Mujeres entre quienes trabajan en el agro", "GEIH 2025 rural, rama de actividad 01."),
        kpi("credm", "Créditos Finagro rurales otorgados a mujeres", "% sobre créditos con sexo conocido."),
        kpi("tdom", "Horas al día en trabajo doméstico no remunerado", "ENUT 2024-2025 rural, 10 años o más.", par=True),
        kpi("tcui", "Horas al día de cuidado no remunerado", "ENUT 2024-2025 rural, 10 años o más.", par=True),
        kpi("ing", "Ingreso laboral mensual mediano", "GEIH 2025 rural, ocupados con ingreso.", par=True),
        kpi("jef", "Personas por hogar según el sexo de la jefatura", "GEIH 2025 rural.", par=True),
        card("comp", "Mujeres y hombres entre los ocupados y en el agro", "Composición por sexo de las personas ocupadas rurales "
             "y de las ocupadas en agricultura y ganadería.", "Fuente: GEIH 2025 rural, módulo Ocupados (RAMA2D_R4 = 01)."),
        card("ingreso", "Ingreso laboral mensual por sexo", "Mediana y media de los ocupados rurales con ingreso.",
             "Fuente: GEIH 2025 rural, INGLABO. Media ponderada; mediana de la muestra."),
        card("principal", "Actividad principal de mujeres y hombres", "Actividad en la que cada persona ocupó la mayor parte "
             "del tiempo la semana pasada (P6240). Porcentaje dentro de cada sexo.", "Fuente: GEIH 2025, zona rural. Expandido con FEX_C18 ÷ 12.", wide=True),
        card("labores", "Trabajo no remunerado del hogar", "Porcentaje de personas de cada sexo que realizó cada actividad "
             "(una persona puede realizar varias).", "Fuente: GEIH 2025, módulo Otras formas de trabajo, zona rural.", wide=True),
        card("horas", "Tiempo diario en trabajo no remunerado", "Horas promedio por día de las personas de 10 años o más, "
             "incluidas las que no realizan la actividad (promedio poblacional).", "Fuente: ENUT 2024-2025 (sep. 2024 – ago. 2025), zona rural."),
        card("credito", "Créditos Finagro desembolsados en municipios rurales", "Número de créditos de 2025 por sexo de la "
             "persona beneficiaria.", "Fuente: Finagro, dataset jjvv-55ck. Un crédito no equivale a una persona única."),
    ]) + "</section>" + variables(GENERO)
    script = r"""DIBUJAR=()=>{const g=DATA.g,c=DATA.c;
 txt('part',pct(g.participacion_mujeres.valor));txt('jfem',pct(g.jefatura_femenina_pct));txt('agro',pct(g.agro_pct.Mujeres));
 const cm=c.por_sexo.Mujeres.creditos,ch=c.por_sexo.Hombres.creditos;txt('credm',pct(100*cm/(cm+ch)));
 SEXOS.forEach(s=>{const k=s.toLowerCase(),T=g.tiempo_enut_horas_dia[s]||{};txt('tdom_'+k,f1(T.trabajo_domestico)+' h');txt('tcui_'+k,f1(T.cuidado)+' h');
  txt('ing_'+k,copM((g.ingreso_laboral[s]||{}).mediana));txt('jef_'+k,NF(2).format(g.jefatura_personas_promedio[s]))});
 const filas=[['Ocupados rurales',g.ocupados_pct],['Ocupados en el agro',g.agro_pct]];
 plot('comp',SEXOS.map(s=>({type:'bar',orientation:'h',name:s,y:filas.map(f=>f[0]),x:filas.map(f=>f[1][s]),marker:{color:colorSexo(s),line:{color:css('--surface'),width:2}},
  text:filas.map(f=>pct(f[1][s])),textposition:'inside',insidetextanchor:'middle',textfont:{color:'#fff'},hovertemplate:'%{y}<br>'+s+': %{text}<extra></extra>'})),
  {barmode:'stack',height:260,yaxis:{autorange:'reversed'},xaxis:{title:{text:'Porcentaje (%)'},range:[0,100]},margin:{l:10,r:20,t:30,b:50}});
 tabla('comp_t',['Grupo','Mujeres','Hombres'],filas.map(f=>[f[0],pct(f[1].Mujeres),pct(f[1].Hombres)]));
 const I=g.ingreso_laboral,mi=['Mediana','Media'];
 barrasSexo('ingreso',mi,Object.fromEntries(SEXOS.map(s=>[s,[I[s].mediana/1e6,I[s].media/1e6]])),{fmt:x=>'$'+f1(x)+' M',titulo:'Millones de pesos al mes'});
 tabla('ingreso_t',['Medida','Mujeres','Hombres'],mi.map((m,i)=>[m,cop([I.Mujeres.mediana,I.Mujeres.media][i]),cop([I.Hombres.mediana,I.Hombres.media][i])]));
 const P=g.actividad_principal;barrasSexo('principal',P.etiquetas,{Mujeres:P.Mujeres,Hombres:P.Hombres},{rango:[0,100]});
 tabla('principal_t',['Actividad','Mujeres','Hombres'],P.etiquetas.map((e,i)=>[e,pct(P.Mujeres[i]),pct(P.Hombres[i])]));
 const A=g.actividades;barrasSexo('labores',A.etiquetas,{Mujeres:A.Mujeres,Hombres:A.Hombres},{rango:[0,100]});
 tabla('labores_t',['Actividad','Mujeres','Hombres'],A.etiquetas.map((e,i)=>[e,pct(A.Mujeres[i]),pct(A.Hombres[i])]));
 const T=g.tiempo_enut_horas_dia,ks=['trabajo_domestico','cuidado','autoconsumo'],cats=['Trabajo doméstico','Cuidado de personas','Producción para autoconsumo'];
 barrasSexo('horas',cats,Object.fromEntries(SEXOS.map(s=>[s,ks.map(k=>T[s][k])])),{fmt:x=>f1(x)+' h',titulo:'Horas por día'});
 tabla('horas_t',['Actividad','Mujeres','Hombres'],cats.map((e,i)=>[e,f1(T.Mujeres[ks[i]])+' h',f1(T.Hombres[ks[i]])+' h']));
 const ko=['Mujeres','Hombres','Sin dato / persona jurídica'].filter(k=>c.por_sexo[k]),v=ko.map(k=>c.por_sexo[k].creditos),tot=v.reduce((a,b)=>a+b,0);
 plot('credito',[{type:'bar',orientation:'h',y:ko.map(k=>wrap(k,16)),x:v,marker:{color:ko.map(colorSexo),cornerradius:4},text:v.map(x=>f0(x)+' ('+pct(100*x/tot)+')'),
  textposition:'outside',cliponaxis:false,textfont:{color:css('--ink2')},hovertemplate:'%{y}: %{text}<extra></extra>'}],{showlegend:false,yaxis:{autorange:'reversed'},xaxis:{title:{text:'Número de créditos'}},margin:{l:10,r:130,t:10,b:50}});
 tabla('credito_t',['Sexo','Créditos','% del total'],ko.map((k,i)=>[k,f0(v[i]),pct(100*v[i]/tot)]));};"""
    pagina("genero_dashboard.html", "Brechas de género en la ruralidad",
           "Comparación entre mujeres y hombres de centros poblados y rural disperso: trabajo, cuidado, ingresos, jefatura del hogar y crédito.",
           cuerpo, {"g": g, "c": cr["finagro"]}, script)


def tablero_calidad(q: dict, deptos: dict) -> None:
    ipm = {d["DPTO"]: d["ipm"] for d in deptos["por_dpto"]}
    for d in q["por_dpto"]:
        d["ipm"] = ipm.get(d["DPTO"], d.get("ipm"))  # una sola fuente de IPM para todos los tableros
    cuerpo = aviso(q.get("pendientes", [])) + "<section class='grid'>" + "".join([
        kpi("hog", "Hogares rurales encuestados", "GEIH 2025, CLASE 2/3 (muestra sin expandir)."),
        kpi("fies", "Hogares con inseguridad alimentaria moderada o grave", "FIES/ECV 2025, total nacional rural."),
        kpi("ipm", "Pobreza multidimensional (IPM)", "TerriData 2025. Promedio simple de departamentos."),
        kpi("amb", "Hogares con al menos un factor ambiental adverso", "GEIH 2025 rural. Indicador aproximado (proxy)."),
        card("servicios", "Cobertura de servicios públicos", "Porcentaje de hogares rurales que cuentan con cada servicio.",
             "Fuente: GEIH 2025, módulo Vivienda y hogares, P4030S1–S5. Ponderado."),
        card("ambiental", "Factores ambientales adversos del hogar", "Porcentaje de hogares rurales con cada condición "
             "(un hogar puede tener varias).", "Fuente: GEIH 2025 rural, P5080, P5040 y P5020."),
        card("fiesexp", "Experiencias de inseguridad alimentaria", "Porcentaje de hogares rurales que reporta cada situación.",
             "Fuente: DANE, anexo FIES 2025, Cuadro 1, total nacional rural."),
        card("ipmcomp", "Privaciones del IPM en la zona rural", "Porcentaje de personas con cada privación. Los componentes no se suman.",
             "Fuente: TerriData, IPM 2025 en centros poblados y rural disperso (promedio simple de departamentos)."),
        card("ingreso", "Ingreso laboral mensual", "Distribución entre hogares con al menos una persona ocupada. La caja va del "
             "percentil 25 al 75, la línea es la mediana y los bigotes llegan a los percentiles 5 y 95.",
             "Fuente: GEIH 2025 rural. Ingreso por persona = ingreso laboral del hogar ÷ personas del hogar."),
        card("ocupacion", "Proporción de personas ocupadas en el hogar", "Porcentaje de hogares según la parte de sus integrantes que está ocupada.",
             "Fuente: GEIH 2025 rural, módulos Ocupados (personas por ORDEN) y Vivienda (P6008)."),
        card("dptofies", "Inseguridad alimentaria por departamento", "Porcentaje de hogares rurales con inseguridad moderada o grave.",
             "Fuente: DANE, anexo FIES 2025, Cuadro 2. Unión por código DPTO.", tall=True),
        card("dptoacu", "Cobertura de acueducto por departamento", "Porcentaje de hogares rurales con acueducto. "
             "Los departamentos sin muestra GEIH rural no aparecen.", "Fuente: GEIH 2025 rural.", tall=True),
        card("dptoing", "Ingreso laboral por persona según departamento", "Promedio ponderado del ingreso laboral del hogar ÷ personas, "
             "en hogares con al menos una persona ocupada.", "Fuente: GEIH 2025 rural.", tall=True),
        card("dptoamb", "Factores ambientales adversos por departamento", "Porcentaje de hogares rurales con al menos una condición adversa.",
             "Fuente: GEIH 2025 rural.", tall=True),
    ]) + "</section>" + variables(CALIDAD)
    script = r"""DIBUJAR=()=>{const q=DATA.q,R=q.por_dpto,avg=k=>{const a=R.map(r=>r[k]).filter(x=>x!=null&&isFinite(x));return a.length?a.reduce((s,x)=>s+x,0)/a.length:null};
 txt('hog',f0(q.hogares_muestra));txt('fies',pct(q.fies_rural_nacional!=null?q.fies_rural_nacional:avg('inseguridad_alimentaria')));txt('ipm',pct(avg('ipm')));txt('amb',pct(q.contaminacion_pct));
 const S=[...q.servicios].sort((a,b)=>b.pct-a.pct);barras('servicios',S.map(s=>s.servicio),S.map(s=>s.pct),{rango:[0,110]});tabla('servicios_t',['Servicio','% de hogares'],S.map(s=>[s.servicio,pct(s.pct)]));
 const AM=Object.entries(q.contaminacion_componentes||{}).sort((a,b)=>b[1]-a[1]);
 if(AM.length){barras('ambiental',AM.map(a=>a[0]),AM.map(a=>a[1]),{rango:[0,105]});tabla('ambiental_t',['Condición','% de hogares'],AM.map(a=>[a[0],pct(a[1])]))}
 const F=q.fies_experiencias;barras('fiesexp',F.map(x=>x.indicador),F.map(x=>x.pct),{rango:[0,100]});tabla('fiesexp_t',['Experiencia','% de hogares'],F.map(x=>[x.indicador,pct(x.pct)]));
 const C=Object.entries(q.ipm_rural_componentes).sort((a,b)=>b[1]-a[1]);barras('ipmcomp',C.map(c=>c[0].replace(/^./,m=>m.toUpperCase())),C.map(c=>c[1]),{rango:[0,110]});tabla('ipmcomp_t',['Privación','%'],C.map(c=>[c[0],pct(c[1])]));
 const I=q.ingreso,box=(k,n)=>({type:'box',orientation:'h',name:n,y:[n],q1:[I[k].q1],median:[I[k].mediana],q3:[I[k].q3],lowerfence:[I[k].p5],upperfence:[I[k].p95],mean:[I[k].media],
  marker:{color:css('--serie')},line:{color:css('--serie')},fillcolor:'rgba(57,135,229,.25)',hovertemplate:'%{y}<extra></extra>'});
 plot('ingreso',[box('hogar','Hogar'),box('persona','Por persona')],{showlegend:false,xaxis:{title:{text:'Pesos colombianos (COP) al mes'},tickformat:',.0f'},margin:{l:10,r:20,t:10,b:50}});
 tabla('ingreso_t',['Medida','Hogar','Por persona'],[['Percentil 5','p5'],['Percentil 25','q1'],['Mediana','mediana'],['Percentil 75','q3'],['Percentil 95','p95'],['Media','media'],['Hogares','n']].map(([l,k])=>[l,k==='n'?f0(I.hogar[k]):cop(I.hogar[k]),k==='n'?f0(I.persona[k]):cop(I.persona[k])]));
 if(q.ocupacion_hogar){const O=q.ocupacion_hogar;barras('ocupacion',O.map(o=>o.grupo),O.map(o=>o.pct),{rango:[0,100]});tabla('ocupacion_t',['Personas ocupadas','% de hogares'],O.map(o=>[o.grupo,pct(o.pct)]))}
 else document.getElementById('ocupacion').outerHTML='<div class="pendiente">Pendiente de re-ejecución con microdatos GEIH.</div>';
 const dep=(id,k,fmt=pct,rango=[0,105],titulo='Porcentaje (%)')=>{const D=R.filter(r=>r[k]!=null).sort((a,b)=>b[k]-a[k]);barras(id,D.map(d=>d.departamento),D.map(d=>d[k]),{rango,fmt,titulo});tabla(id+'_t',['Departamento','Valor'],D.map(d=>[d.departamento,fmt(d[k])]))};
 dep('dptofies','inseguridad_alimentaria');dep('dptoacu','cobertura_acueducto');dep('dptoamb','contaminacion_proxy_pct');
 dep('dptoing','ingreso_persona_media',copM,null,'Pesos al mes por persona');};"""
    pagina("calidad_vida_dashboard.html", "Calidad de vida rural por departamento",
           "Servicios públicos, ingresos, inseguridad alimentaria y pobreza multidimensional en centros poblados y rural disperso.",
           cuerpo, {"q": q}, script)


def tablero_departamentos(dep: dict, cr: dict) -> None:
    fg = cr["finagro"]["por_dpto"]
    for d in dep["por_dpto"]:
        c = fg.get(d["DPTO"], {})
        m, h, o = c.get("Mujeres", 0), c.get("Hombres", 0), c.get("Sin dato / persona jurídica", 0)
        d.update(creditos_mujeres=m, creditos_hombres=h, creditos_otros=o, creditos_total=m + h + o,
                 pct_creditos_mujeres=100 * m / (m + h) if m + h else None)
    cuerpo = aviso(dep.get("pendientes", [])) + "<section class='grid'>" + "".join([
        kpi("nd", "Departamentos", "Incluye Bogotá D.C."),
        kpi("nr", "Municipios y áreas no municipalizadas rurales", "Categorías de ruralidad DNP: Rural + Rural disperso."),
        kpi("nc", "Créditos Finagro en municipios rurales", "Finagro 2025 (jjvv-55ck)."),
        kpi("pm", "Créditos rurales otorgados a mujeres", "% sobre créditos con sexo conocido."),
        card("map_rural", "Nivel de ruralidad", "Porcentaje de municipios de cada departamento clasificados como Rural o Rural disperso.",
             "Fuente: DNP, categorías de ruralidad."),
        card("map_ipm", "Pobreza multidimensional (IPM)", "Porcentaje de personas en pobreza multidimensional, 2025.", "Fuente: TerriData."),
        card("map_fies", "Inseguridad alimentaria rural", "Porcentaje de hogares rurales con inseguridad moderada o grave.",
             "Fuente: DANE, anexo FIES 2025."),
        card("map_mujeres", "Participación de las mujeres en el crédito rural", "Créditos Finagro a mujeres ÷ créditos a personas con sexo conocido.",
             "Fuente: Finagro 2025, municipios rurales."),
        card("map_incl", "Inclusión financiera tradicional", "Hogares rurales con al menos un producto financiero tradicional "
             "(cuentas, CDT, créditos o tarjeta).", "Fuente: GEIH 2025 rural. Sin muestra en Amazonía y Orinoquía."),
        card("map_movil", "Inclusión financiera con plataformas móviles", "Igual que el anterior, contando también Nequi, Daviplata y similares.",
             "Fuente: GEIH 2025 rural, P5222S11."),
        card("cred_dpto", "Créditos Finagro rurales por departamento", "Número de créditos 2025 por sexo. Ordenados de mayor a menor.",
             "Fuente: Finagro, jjvv-55ck. Un crédito no equivale a una persona única.", wide=True, tall=True),
    ]) + "<article class='card wide'><h3>Tabla departamental</h3><div id='tabla_dptos' class='tabla'></div></article></section>" + variables(COMUNES_GEIH + VAR_DEPARTAMENTOS)
    script = r"""
const GJ=DATA.geo;
function mapa(id,R,k,unidad){const el=document.getElementById(id);
 const V=R.filter(r=>r[k]!=null&&isFinite(r[k]));
 plot(id,[{type:'choropleth',geojson:GJ,featureidkey:'properties.divipola_dep',locations:V.map(r=>r.DPTO),z:V.map(r=>r[k]),text:V.map(r=>r.departamento),
  colorscale:[[0,css('--seq0')],[.25,css('--seq1')],[.5,css('--seq2')],[.75,css('--seq3')],[1,css('--seq4')]],reversescale:false,
  marker:{line:{color:css('--surface'),width:1}},colorbar:{title:{text:unidad,font:{color:css('--ink2')}},tickfont:{color:css('--ink2')},thickness:12,len:.8,outlinewidth:0},
  hovertemplate:'%{text}: %{z:.1f} '+unidad+'<extra></extra>'}],
  {height:460,margin:{l:0,r:0,t:10,b:0},geo:{fitbounds:'locations',visible:false,bgcolor:css('--surface')}});
 const sub=el.parentElement.querySelector('.sub');if(sub&&!sub.dataset.ok){sub.dataset.ok=1;sub.innerHTML+=' <b>Más oscuro = valor más alto.</b> Vacío = sin dato.'}}
DIBUJAR=()=>{const R=DATA.d.por_dpto,sum=k=>R.reduce((s,r)=>s+(r[k]||0),0);
 txt('nd',f0(R.length));txt('nr',f0(sum('municipios_rurales'))+' de '+f0(sum('municipios_total')));txt('nc',f0(sum('creditos_total')));
 txt('pm',pct(100*sum('creditos_mujeres')/(sum('creditos_mujeres')+sum('creditos_hombres'))));
 const C=[...R].filter(r=>r.creditos_total>0).sort((a,b)=>b.creditos_total-a.creditos_total),y=C.map(r=>r.departamento);
 plot('cred_dpto',[['Mujeres','creditos_mujeres'],['Hombres','creditos_hombres'],['Sin dato / persona jurídica','creditos_otros']].map(([n,k])=>({type:'bar',orientation:'h',name:n,y,x:C.map(r=>r[k]),
  marker:{color:colorSexo(n),cornerradius:2,line:{color:css('--surface'),width:2}},hovertemplate:'%{y}<br>'+n+': %{x:,.0f}<extra></extra>'})),
  {barmode:'stack',height:Math.max(520,C.length*24+90),yaxis:{autorange:'reversed'},xaxis:{title:{text:'Número de créditos'},tickformat:',.0f'},margin:{l:10,r:20,t:30,b:50}});
 tabla('cred_dpto_t',['Departamento','Mujeres','Hombres','Sin dato / jurídica','% mujeres'],C.map(r=>[r.departamento,f0(r.creditos_mujeres),f0(r.creditos_hombres),f0(r.creditos_otros),pct(r.pct_creditos_mujeres)]));
 document.getElementById('tabla_dptos').innerHTML='<table><thead><tr><th>Departamento</th><th>Municipios rurales</th><th>Ruralidad</th><th>IPM</th><th>Inseg. alimentaria</th><th>Inclusión tradicional</th><th>Inclusión con móvil</th><th>Créditos Finagro</th><th>% mujeres</th></tr></thead><tbody>'+
  R.map(r=>'<tr><td>'+r.departamento+'</td><td class="n">'+f0(r.municipios_rurales)+' / '+f0(r.municipios_total)+'</td><td class="n">'+pct(r.ruralidad_pct)+'</td><td class="n">'+pct(r.ipm)+'</td><td class="n">'+pct(r.inseguridad_alimentaria)+'</td><td class="n">'+pct(r.inclusion_financiera_pct)+'</td><td class="n">'+pct(r.inclusion_con_movil_pct)+'</td><td class="n">'+f0(r.creditos_total)+'</td><td class="n">'+pct(r.pct_creditos_mujeres)+'</td></tr>').join('')+'</tbody></table>';
 mapa('map_rural',R,'ruralidad_pct','%');mapa('map_ipm',R,'ipm','%');mapa('map_fies',R,'inseguridad_alimentaria','%');mapa('map_incl',R,'inclusion_financiera_pct','%');
 mapa('map_movil',R,'inclusion_con_movil_pct','%');mapa('map_mujeres',R,'pct_creditos_mujeres','%');};"""
    pagina("departamentos_dashboard.html", "El territorio: departamentos",
           "Cómo cambian la ruralidad, la pobreza, la alimentación, la inclusión financiera y el crédito rural entre departamentos.",
           cuerpo, {"d": dep, "geo": json.loads((BASE / "referencias" / "departamentos_colombia.geojson").read_text(encoding="utf-8"))}, script)


def tablero_financiero(cr: dict, inc: dict) -> None:
    cuerpo = aviso(inc.get("pendientes", [])) + "<section class='grid'>" + "".join([
        kpi("fg_n", "Créditos Finagro rurales", "Finagro 2025, municipios rurales.", par=True),
        kpi("fg_monto", "Monto promedio por crédito (Finagro)", "Σ valor_credito ÷ número de créditos.", par=True),
        kpi("fg_med", "Monto mediano por crédito (Finagro)", "La mitad de los créditos está por debajo de este valor.", par=True),
        kpi("fg_plazo", "Plazo promedio (Finagro)", "Meses pactados.", par=True),
        kpi("fg_ibr", "Margen sobre la IBR (Finagro)", "Puntos adicionales promedio en créditos indexados a la IBR.", par=True),
        kpi("fg_fag", "Créditos con garantía FAG (Finagro)", "Fondo Agropecuario de Garantías.", par=True),
        kpi("sf_n", "Créditos Superfinanciera rurales (CIIU 01)", "Σ numero_de_creditos.", par=True),
        kpi("sf_monto", "Monto promedio por crédito (Superfinanciera)", "Σ montos ÷ Σ créditos.", par=True),
        kpi("sf_tasa", "Tasa efectiva anual promedio (Superfinanciera)", "Ponderada por monto; sin filas con tasa 0.", par=True),
        kpi("inc_t", "Hogares rurales con productos financieros tradicionales", "GEIH 2025 rural, P5222S1–S7."),
        kpi("inc_m", "Hogares rurales con productos tradicionales o plataforma móvil", "GEIH 2025 rural, + P5222S11."),
        kpi("inc_j", "Inclusión tradicional según el sexo de la jefatura", "GEIH 2025 rural.", par=True),
        card("n_fuente", "Número de créditos rurales por sexo y fuente", "Créditos desembolsados en 2025 en municipios Rural o Rural disperso.",
             "Fuentes: Finagro (jjvv-55ck) y Superfinanciera (w9zh-vetq, CIIU 01). Sin datos de sexo ni de personas jurídicas."),
        card("monto_fuente", "Monto promedio por crédito, por sexo y fuente", "Millones de pesos por crédito.",
             "Finagro: valor_credito. Superfinanciera: montos_desembolsados ÷ numero_de_creditos."),
        card("tasa_tipo", "Tasa efectiva anual según el tipo de crédito", "Superfinanciera: tasa ponderada por monto en cada modalidad "
             "(solo modalidades con al menos 100 créditos por sexo).", "Fuente: Superfinanciera 2025, CIIU 01, municipios rurales."),
        card("monto_tipo", "Monto promedio según el tipo de crédito", "Superfinanciera: millones de pesos por crédito en cada modalidad.",
             "Fuente: Superfinanciera 2025, CIIU 01, municipios rurales."),
        card("linea", "Línea de crédito Finagro", "Distribución de los créditos de cada sexo por línea.", "Fuente: Finagro 2025, municipios rurales."),
        card("linea_monto", "Monto promedio según la línea Finagro", "Millones de pesos por crédito en cada línea.", "Fuente: Finagro 2025, municipios rurales."),
        card("productor", "Tipo de productor Finagro", "Distribución de los créditos de cada sexo por tamaño del productor.", "Fuente: Finagro 2025, municipios rurales."),
        card("tipo_sf", "Tipo de crédito Superfinanciera", "Distribución de los créditos de cada sexo por modalidad.",
             "Fuente: Superfinanciera 2025, CIIU 01, municipios rurales."),
        card("productos", "Productos financieros de los hogares rurales", "Porcentaje de hogares que usa cada producto (respuesta múltiple).",
             "Fuente: GEIH 2025 rural, P5222S1–S11, expandido con FEX_C18 ÷ 12.", wide=True),
        card("incl_sexo", "Inclusión financiera según el sexo de la jefatura", "Hogares con al menos un producto: solo tradicionales "
             "y contando también las plataformas móviles.", "Fuente: GEIH 2025 rural.", wide=True),
        card("educacion", "Inclusión financiera según el nivel educativo de la jefatura", "Porcentaje de hogares con al menos un producto financiero tradicional.",
             "Fuente: GEIH 2025 rural. Unidad: hogar; nivel educativo y sexo de la persona jefe de hogar.", wide=True),
        card("tamano", "Inclusión financiera según el tamaño del hogar", "Porcentaje de hogares con al menos un producto financiero tradicional, por número de personas.",
             "Fuente: GEIH 2025 rural.", wide=True),
    ]) + "</section>" + variables(COMUNES_GEIH + FINANCIERO)
    script = r"""DIBUJAR=()=>{const F=DATA.c.finagro.por_sexo,S=DATA.c.superfinanciera.por_sexo,I=DATA.i;
 const par=(id,obj,k,fmt)=>SEXOS.forEach(s=>txt(id+'_'+s.toLowerCase(),fmt((obj[s]||{})[k])));
 par('fg_n',F,'creditos',f0);par('fg_monto',F,'monto_promedio',copM);par('fg_med',F,'monto_mediana',copM);par('fg_plazo',F,'plazo_promedio_meses',x=>f1(x)+' meses');
 par('fg_ibr',F,'margen_ibr_puntos',x=>f1(x)+' pts');par('fg_fag',F,'pct_con_garantia_fag',pct);
 par('sf_n',S,'creditos',f0);par('sf_monto',S,'monto_promedio',copM);par('sf_tasa',S,'tasa_ponderada_ea',x=>f1(x)+' % E.A.');
 const N=I.inclusion_nacional||{};txt('inc_t',pct(N.tradicional));txt('inc_m',pct(N.con_movil));
 SEXOS.forEach(s=>txt('inc_j_'+s.toLowerCase(),pct((I.inclusion_por_sexo_jefatura||{})[s])));
 const fuentes=['Finagro','Superfinanciera'];
 barrasSexo('n_fuente',fuentes,Object.fromEntries(SEXOS.map(s=>[s,[F[s].creditos,S[s].creditos]])),{fmt:f0,titulo:'Número de créditos'});
 tabla('n_fuente_t',['Fuente','Mujeres','Hombres','% mujeres'],fuentes.map((n,i)=>{const o=[F,S][i];return [n,f0(o.Mujeres.creditos),f0(o.Hombres.creditos),pct(100*o.Mujeres.creditos/(o.Mujeres.creditos+o.Hombres.creditos))]}));
 barrasSexo('monto_fuente',fuentes,Object.fromEntries(SEXOS.map(s=>[s,[F[s].monto_promedio/1e6,S[s].monto_promedio/1e6]])),{fmt:x=>'$'+f1(x)+' M',titulo:'Millones de pesos por crédito'});
 tabla('monto_fuente_t',['Fuente','Mujeres','Hombres'],fuentes.map((n,i)=>{const o=[F,S][i];return [n,cop(o.Mujeres.monto_promedio),cop(o.Hombres.monto_promedio)]}));
 const TC=DATA.c.superfinanciera.tipo_credito_condiciones||{},tipos=Object.keys(TC.Mujeres||{}).filter(t=>SEXOS.every(s=>((TC[s]||{})[t]||{}).creditos>=100))
  .sort((a,b)=>TC.Hombres[b].creditos+TC.Mujeres[b].creditos-TC.Hombres[a].creditos-TC.Mujeres[a].creditos);
 barrasSexo('tasa_tipo',tipos,Object.fromEntries(SEXOS.map(s=>[s,tipos.map(t=>TC[s][t].tasa_ponderada_ea)])),{fmt:x=>f1(x)+' %',titulo:'Tasa efectiva anual (%)'});
 tabla('tasa_tipo_t',['Tipo de crédito','Mujeres','Hombres','Créditos mujeres','Créditos hombres'],tipos.map(t=>[t,f1(TC.Mujeres[t].tasa_ponderada_ea)+' %',f1(TC.Hombres[t].tasa_ponderada_ea)+' %',f0(TC.Mujeres[t].creditos),f0(TC.Hombres[t].creditos)]));
 barrasSexo('monto_tipo',tipos,Object.fromEntries(SEXOS.map(s=>[s,tipos.map(t=>TC[s][t].monto_promedio/1e6)])),{fmt:x=>'$'+f1(x)+' M',titulo:'Millones de pesos por crédito'});
 tabla('monto_tipo_t',['Tipo de crédito','Mujeres','Hombres'],tipos.map(t=>[t,cop(TC.Mujeres[t].monto_promedio),cop(TC.Hombres[t].monto_promedio)]));
 const LM=DATA.c.finagro.linea_monto_promedio||{},lineas=Object.keys(LM.Mujeres||{});
 barrasSexo('linea_monto',lineas,Object.fromEntries(SEXOS.map(s=>[s,lineas.map(l=>(LM[s]||{})[l]/1e6)])),{fmt:x=>'$'+f1(x)+' M',titulo:'Millones de pesos por crédito'});
 tabla('linea_monto_t',['Línea','Mujeres','Hombres'],lineas.map(l=>[l,cop(LM.Mujeres[l]),cop((LM.Hombres||{})[l])]));
 const dist=(id,obj,top=8)=>{const tot=Object.fromEntries(SEXOS.map(s=>[s,Object.values(obj[s]||{}).reduce((a,b)=>a+b,0)]));
  const cats=[...new Set(SEXOS.flatMap(s=>Object.keys(obj[s]||{})))].sort((a,b)=>((obj.Mujeres||{})[b]||0)+((obj.Hombres||{})[b]||0)-((obj.Mujeres||{})[a]||0)-((obj.Hombres||{})[a]||0)).slice(0,top);
  const ser=Object.fromEntries(SEXOS.map(s=>[s,cats.map(c=>100*((obj[s]||{})[c]||0)/tot[s])]));barrasSexo(id,cats,ser,{rango:[0,100]});
  tabla(id+'_t',['Categoría','Mujeres','Hombres'],cats.map((c,i)=>[c,pct(ser.Mujeres[i]),pct(ser.Hombres[i])]))};
 dist('linea',DATA.c.finagro.linea_credito);dist('productor',DATA.c.finagro.tipo_productor);dist('tipo_sf',DATA.c.superfinanciera.tipo_credito,4);
 if(I.productos_pct){const P=I.productos_pct;barras('productos',P.map(p=>p.producto),P.map(p=>p.pct),{rango:[0,100]});tabla('productos_t',['Producto','% de hogares'],P.map(p=>[p.producto,pct(p.pct)]))}
 else document.getElementById('productos').outerHTML='<div class="pendiente">Pendiente de re-ejecución con microdatos GEIH.</div>';
 const IS=I.inclusion_por_sexo_jefatura||{},IM=I.inclusion_movil_por_sexo_jefatura||{},ci=['Solo productos tradicionales','Con plataforma móvil'];
 barrasSexo('incl_sexo',ci,Object.fromEntries(SEXOS.map(s=>[s,[IS[s],IM[s]]])),{rango:[0,100]});
 tabla('incl_sexo_t',['Medida','Jefatura mujer','Jefatura hombre'],ci.map((c,i)=>[c,pct([IS.Mujeres,IM.Mujeres][i]),pct([IS.Hombres,IM.Hombres][i])]));
 const grupo=(id,arr,k)=>{const cats=[...new Set(arr.map(x=>x[k]))],ser=Object.fromEntries(SEXOS.map(s=>[s,cats.map(c=>(arr.find(x=>x[k]===c&&x.sexo===s)||{}).pct??null)]));
  barrasSexo(id,cats.map(c=>String(c).replace(/^\d\.\s/,'')),ser,{rango:[0,100]});tabla(id+'_t',['Grupo','Jefatura mujer','Jefatura hombre'],cats.map((c,i)=>[c,pct(ser.Mujeres[i]),pct(ser.Hombres[i])]))};
 grupo('educacion',I.inclusion_por_educacion,'nivel');grupo('tamano',I.inclusion_por_tamano.map(x=>({...x,tamano:x.tamano+(x.tamano==='1'?' persona':' personas')})),'tamano');};"""
    pagina("financiero_dashboard.html", "Crédito rural e inclusión financiera",
           "Acceso y condiciones del crédito formal para mujeres y hombres en municipios rurales, y uso de productos financieros en los hogares.",
           cuerpo, {"c": cr, "i": inc}, script)


# ───────────────────────────── Portal ─────────────────────────────

ER_SVG = """<svg viewBox="0 0 1180 640" role="img" aria-labelledby="er-t er-d" xmlns="http://www.w3.org/2000/svg">
<title id="er-t">Modelo entidad-relación del estudio</title>
<desc id="er-d">El departamento (DPTO) es el grano común. Municipio pertenece a departamento. Hogar GEIH tiene personas GEIH. Finagro y Superfinanciera se filtran por municipio rural. FIES, TerriData y GEIH se agregan a departamento. ENUT solo se compara por sexo.</desc>
<defs><marker id="m1" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse"><path d="M0,6 L11,6 M11,0 L11,12" fill="none" stroke="var(--ink2)" stroke-width="1.5"/></marker>
<marker id="mn" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="14" markerHeight="14" orient="auto-start-reverse"><path d="M13,7 L1,1 M13,7 L1,13 M13,7 L1,7" fill="none" stroke="var(--ink2)" stroke-width="1.5"/></marker></defs>
<style>.e rect{fill:var(--surface);stroke:var(--axis);stroke-width:1.5}.e .h{fill:var(--accent)}.e .ht{fill:#fff;font-weight:700;font-size:14px}
.e .k{font-size:12px;fill:var(--ink)}.e .a{font-size:12px;fill:var(--ink2)}.l{stroke:var(--ink2);stroke-width:1.5;fill:none}.lt{font-size:11px;fill:var(--muted)}
.dash{stroke-dasharray:6 5}</style>
<g class="e"><rect x="470" y="250" width="240" height="96" rx="10"/><rect class="h" x="470" y="250" width="240" height="30" rx="10"/><rect class="h" x="470" y="268" width="240" height="12"/>
<text class="ht" x="590" y="270" text-anchor="middle">DEPARTAMENTO</text><text class="k" x="484" y="302">🔑 DPTO (2 dígitos)</text><text class="a" x="484" y="322">nombre · grano común de integración</text></g>
<g class="e"><rect x="470" y="470" width="240" height="104" rx="10"/><rect class="h" x="470" y="470" width="240" height="30" rx="10"/><rect class="h" x="470" y="488" width="240" height="12"/>
<text class="ht" x="590" y="490" text-anchor="middle">MUNICIPIO (ruralidad DNP)</text><text class="k" x="484" y="522">🔑 DIVIPOLA (5 dígitos)</text><text class="a" x="484" y="542">FK DPTO = DIVIPOLA[1:2]</text><text class="a" x="484" y="560">categoría: Rural / Rural disperso / …</text></g>
<g class="e"><rect x="30" y="30" width="270" height="124" rx="10"/><rect class="h" x="30" y="30" width="270" height="30" rx="10"/><rect class="h" x="30" y="48" width="270" height="12"/>
<text class="ht" x="165" y="50" text-anchor="middle">GEIH · HOGAR</text><text class="k" x="44" y="82">🔑 mes + DIRECTORIO + HOGAR</text><text class="a" x="44" y="102">FK DPTO · CLASE 2/3 · FEX_C18</text><text class="a" x="44" y="120">servicios, productos financieros,</text><text class="a" x="44" y="138">combustible, basura, sanitario</text></g>
<g class="e"><rect x="30" y="250" width="270" height="124" rx="10"/><rect class="h" x="30" y="250" width="270" height="30" rx="10"/><rect class="h" x="30" y="268" width="270" height="12"/>
<text class="ht" x="165" y="270" text-anchor="middle">GEIH · PERSONA</text><text class="k" x="44" y="302">🔑 mes + DIRECTORIO + HOGAR + ORDEN</text><text class="a" x="44" y="322">sexo P3271 · parentesco · educación</text><text class="a" x="44" y="340">módulos: generales, fuerza de trabajo,</text><text class="a" x="44" y="358">ocupados (ingreso, rama), otras formas</text></g>
<g class="e"><rect x="30" y="470" width="270" height="104" rx="10"/><rect class="h" x="30" y="470" width="270" height="30" rx="10"/><rect class="h" x="30" y="488" width="270" height="12"/>
<text class="ht" x="165" y="490" text-anchor="middle">ENUT · PERSONA</text><text class="k" x="44" y="522">🔑 DIRECTORIO + SECUENCIA_P + ORDEN</text><text class="a" x="44" y="542">sexo P6020 · tiempos P11xx · FEX_C</text><text class="a" x="44" y="560">sin municipio: solo se compara por sexo</text></g>
<g class="e"><rect x="470" y="30" width="240" height="104" rx="10"/><rect class="h" x="470" y="30" width="240" height="30" rx="10"/><rect class="h" x="470" y="48" width="240" height="12"/>
<text class="ht" x="590" y="50" text-anchor="middle">FIES · DEPARTAMENTO</text><text class="k" x="484" y="82">🔑 DPTO (desde el nombre)</text><text class="a" x="484" y="102">área rural · inseguridad %</text><text class="a" x="484" y="120">8 experiencias</text></g>
<g class="e"><rect x="880" y="30" width="270" height="104" rx="10"/><rect class="h" x="880" y="30" width="270" height="30" rx="10"/><rect class="h" x="880" y="48" width="270" height="12"/>
<text class="ht" x="1015" y="50" text-anchor="middle">TERRIDATA · INDICADOR</text><text class="k" x="894" y="82">🔑 DIVIPOLA + indicador + año</text><text class="a" x="894" y="102">IPM 2025 (filas «xx000» = depto)</text><text class="a" x="894" y="120">componentes del IPM rural</text></g>
<g class="e"><rect x="880" y="380" width="270" height="104" rx="10"/><rect class="h" x="880" y="380" width="270" height="30" rx="10"/><rect class="h" x="880" y="398" width="270" height="12"/>
<text class="ht" x="1015" y="400" text-anchor="middle">FINAGRO · CRÉDITO</text><text class="k" x="894" y="432">🔑 id_credito</text><text class="a" x="894" y="452">FK cod_municipio → DIVIPOLA</text><text class="a" x="894" y="470">sexo · valor · plazo · línea · IBR</text></g>
<g class="e"><rect x="880" y="520" width="270" height="104" rx="10"/><rect class="h" x="880" y="520" width="270" height="30" rx="10"/><rect class="h" x="880" y="538" width="270" height="12"/>
<text class="ht" x="1015" y="540" text-anchor="middle">SUPERFINANCIERA · GRUPO</text><text class="k" x="894" y="572">entidad×semana×producto×sexo</text><text class="a" x="894" y="592">FK codigo_municipio → DIVIPOLA</text><text class="a" x="894" y="610">numero_de_creditos · monto · tasa</text></g>
<path class="l" d="M165,154 V250" marker-start="url(#m1)" marker-end="url(#mn)"/><text class="lt" x="172" y="206">1 : N · mes+DIRECTORIO+HOGAR</text>
<path class="l" d="M300,92 C390,92 390,280 470,280" marker-end="url(#m1)"/><text class="lt" x="318" y="84">N : 1 · DPTO (agregado)</text>
<path class="l dash" d="M165,470 V374"/><text class="lt" x="172" y="428">sin unión: muestras distintas</text>
<path class="l" d="M590,134 V250" marker-start="url(#m1)" marker-end="url(#m1)"/><text class="lt" x="598" y="196">1 : 1 · DPTO</text>
<path class="l" d="M880,92 C790,92 790,290 710,290" marker-end="url(#m1)"/><text class="lt" x="800" y="84">N : 1 · DPTO</text>
<path class="l" d="M590,470 V346" marker-start="url(#mn)" marker-end="url(#m1)"/><text class="lt" x="598" y="412">N : 1 · DIVIPOLA[1:2]</text>
<path class="l" d="M880,432 C800,432 790,510 710,510" marker-start="url(#mn)" marker-end="url(#m1)"/><text class="lt" x="735" y="452">N : 1 · DIVIPOLA (filtro rural)</text>
<path class="l" d="M880,572 C800,572 790,540 710,540" marker-start="url(#mn)" marker-end="url(#m1)"/><text class="lt" x="735" y="600">N : 1 · DIVIPOLA (filtro rural)</text>
</svg>"""


def portal(cr: dict, q: dict, dep: dict, g: dict) -> None:
    fg, sf = cr["finagro"], cr["superfinanciera"]
    n_mun = sum(d["municipios_total"] for d in dep["por_dpto"])
    n_rur = sum(d["municipios_rurales"] for d in dep["por_dpto"])
    con_fies = sum(1 for d in dep["por_dpto"] if d["inseguridad_alimentaria"] is not None)
    con_ipm = sum(1 for d in dep["por_dpto"] if d["ipm"] is not None)
    muestra = g.get("muestra") or {}
    nd = "Se informa al re-ejecutar"
    bases = [
        ("GEIH 2025 · Vivienda y hogares", "DANE", "Ene–dic 2025 · CLASE 2/3", "1 hogar en 1 mes",
         f"{q['hogares_muestra']:,} hogares rurales en 24 departamentos".replace(",", "."),
         "servicios P4030S1–S5, combustible P5080, basura P5040, sanitario P5020, productos financieros P5222S1–S11, total de personas P6008, DPTO, FEX_C18"),
        ("GEIH 2025 · Personas (generales, fuerza de trabajo, ocupados, otras formas de trabajo)", "DANE", "Ene–dic 2025 · CLASE 2/3", "1 persona en 1 mes",
         f"{muestra['personas']:,}".replace(",", ".") + " personas" if muestra.get("personas") else nd,
         "sexo P3271, parentesco P6050, nivel educativo P3042, actividad principal P6240, rama RAMA2D_R4, ingreso INGLABO, labores del hogar P3076–P3094"),
        ("ENUT 2024-2025", "DANE", "Sep 2024 – ago 2025 · CLASE 2/3 · 10 años o más", "1 persona",
         f"{muestra['enut_personas']:,}".replace(",", ".") + " personas" if muestra.get("enut_personas") else nd,
         "sexo P6020, edad P6040, tiempos de trabajo doméstico (I2–I6), cuidado (I11–I17) y autoconsumo (I8) en horas + minutos, FEX_C. No es año calendario 2025."),
        ("FIES · ECV 2025 (anexo)", "DANE", "2025 · Centros poblados y rural disperso", "1 departamento (Cuadro 2) / 1 departamento × experiencia (Cuadro 1)",
         f"{con_fies} departamentos con dato · 8 experiencias", "inseguridad alimentaria moderada o grave y grave (%), 8 experiencias FIES"),
        ("TerriData", "DNP", "Indicador 2025", "1 entidad territorial × indicador × año",
         f"IPM en {con_ipm} departamentos", "IPM, componentes del IPM en centros poblados y rural disperso"),
        ("Categorías de ruralidad", "DNP (Misión para la Transformación del Campo)", "Vigente", "1 municipio o área no municipalizada",
         f"{n_mun:,} entidades · {n_rur} Rural o Rural disperso".replace(",", "."), "DIVIPOLA, categoría de ruralidad. Es el filtro rural de las fuentes de crédito"),
        ("Finagro · Desembolsos de crédito de fomento agropecuario (jjvv-55ck)", "Finagro / datos.gov.co", "fecha_credito en 2025", "1 crédito desembolsado",
         f"{fg['registros_2025_todos_los_municipios']:,} en 2025 → {fg['registros_2025_rurales']:,} en municipios rurales".replace(",", "."),
         "sexo, cod_municipio, valor_credito, plazo, linea_credito, tipo_productor, tasa_indexacion, puntos_adicionales, garantia_fag"),
        ("Superfinanciera · Tasas de interés activas por tipo de crédito (w9zh-vetq)", "SFC / datos.gov.co", "fecha_corte en 2025 · CIIU 01", "1 grupo de créditos (entidad × semana × producto × municipio × sexo)",
         f"{sf['filas_2025_ciiu01_todos_los_municipios']:,} filas → {sf['filas_2025_ciiu01_rurales']:,} filas rurales = {sf['creditos_2025_ciiu01_rurales']:,} créditos".replace(",", "."),
         "sexo, codigo_municipio, codigo_ciiu, tipo_de_cr_dito, numero_de_creditos, montos_desembolsados, tasa_efectiva_promedio"),
    ]
    filas = "".join(f"<tr><td><b>{a}</b><br><span class='src'>{b}</span></td><td>{c}</td><td>{d}</td><td>{e}</td><td>{f}</td></tr>"
                    for a, b, c, d, e, f in bases)
    uniones = [
        ("GEIH hogar → GEIH persona", "mes + DIRECTORIO + HOGAR (+ ORDEN para personas)", "1 : N", "Correcta. Se agregó el mes para no mezclar viviendas de meses distintos."),
        ("GEIH, FIES, TerriData → Departamento", "DPTO", "N : 1 tras agregar", "Correcta: cada fuente se agrega primero a departamento y después se une 1 : 1."),
        ("FIES → Departamento", "nombre → código DPTO", "1 : 1", "Corregida: antes se unía por nombre y se perdían Valle del Cauca, San Andrés y Bogotá."),
        ("Municipio → Departamento", "DIVIPOLA[1:2] = DPTO", "N : 1", "Correcta."),
        ("Finagro / Superfinanciera → Municipio rural", "cod_municipio / codigo_municipio = DIVIPOLA", "N : 1", "Nueva: es el filtro de ruralidad del crédito."),
        ("GEIH ↔ ENUT", "—", "Sin unión", "Eliminada la unión anterior por DIVIPOLA + Sexo: son muestras distintas y ninguna trae municipio. Se comparan solo por sexo."),
    ]
    tabla_u = "".join(f"<tr><td>{a}</td><td><code>{b}</code></td><td>{c}</td><td>{d}</td></tr>" for a, b, c, d in uniones)
    tiles = "".join(f"<a class='tile' href='{a}'><b>{t} →</b><span>{d}</span></a>" for a, t, d in TABLEROS)
    cuerpo = f"""
<h2 id="bases">1. Bases de datos</h2><p class="lead">Qué fuentes usa el estudio, qué representa una fila, cuántos registros quedan
después de aplicar los filtros (rural y 2025) y qué variables se analizan.</p>
<div class="card wide tabla"><table><thead><tr><th>Base</th><th>Periodo y filtro</th><th>1 fila =</th><th>Registros usados</th><th>Variables analizadas</th></tr></thead>
<tbody>{filas}</tbody></table></div>
<h2 id="er">2. Modelo entidad-relación</h2><p class="lead">El departamento (DPTO) es el grano común. Las encuestas se agregan a
departamento antes de unirse; las fuentes de crédito se filtran con la lista de municipios rurales y luego se agregan.</p>
<div class="card wide er">{ER_SVG}</div>
<div class="card wide tabla" style="margin-top:16px"><table><thead><tr><th>Unión</th><th>Llave</th><th>Cardinalidad</th><th>Evaluación</th></tr></thead><tbody>{tabla_u}</tbody></table></div>
<h2 id="tableros">3. Tableros</h2><div class="tiles">{tiles}</div>"""
    pagina("index.html", "Crédito formal y género en la ruralidad colombiana, 2025",
           "Portal del estudio: fuentes de datos, modelo de integración y acceso a los tableros corregidos.", cuerpo, {}, "")


def main() -> None:
    cr = cargar("credito_rural_2025.json")
    g = cargar("genero_rural_2025.json")
    q = cargar("calidad_vida_rural_2025.json")
    dep = cargar("departamentos_rural_2025.json")
    inc = cargar("inclusion_financiera_rural_2025.json")
    portal(cr, q, dep, g)
    tablero_genero(g, cr)
    tablero_calidad(q, dep)
    tablero_departamentos(dep, cr)
    tablero_financiero(cr, inc)


if __name__ == "__main__":
    main()
