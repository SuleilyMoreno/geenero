"""Configuración visual compartida por los cuatro dashboards."""

TITULO_PRINCIPAL = (
    "Identificación de los factores asociados a las diferencias en el acceso "
    "y las condiciones del crédito formal entre hombres y mujeres rurales en Colombia"
)

PLOTLY_LAYOUT = {
    "autosize": True,
    "margin": {"l": 20, "r": 20, "t": 30, "b": 20},
    "paper_bgcolor": "#F5F7FB",
    "plot_bgcolor": "#FFFFFF",
    "font": {"family": "Roboto, Helvetica, Arial, sans-serif", "color": "#172033"},
}

CSS_COMUN = """
.global-title{width:100%;margin:0 auto 24px;text-align:center;font-family:Roboto,Helvetica,Arial,sans-serif;font-size:clamp(24px,3vw,42px);line-height:1.15;font-weight:800;color:#123B66}
.dashboard-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:15px;width:100%;align-items:stretch}
.kpi-card,.chart-card{min-width:0;background:#fff;border:1px solid #E2E8F0;border-radius:16px;box-shadow:0 8px 24px rgba(15,23,42,.08)}
.kpi-card{grid-column:span 3;min-height:150px;padding:20px}.chart-card{grid-column:span 6;min-height:390px;padding:12px}.chart-card.wide{grid-column:span 12}
.plot-container{width:100%;min-height:320px}.source{margin-top:10px;color:#64748B;font-size:11px}
@media(max-width:1000px){.kpi-card{grid-column:span 6}.chart-card,.chart-card.wide{grid-column:span 12}}
@media(max-width:600px){.kpi-card,.chart-card,.chart-card.wide{grid-column:span 12}}
"""


def apply_common_style(html: str) -> str:
    """Añade título, estilo responsivo y marcadores visibles al HTML final."""
    style = f"<style>{CSS_COMUN}</style>"
    title = f"<h1 class='global-title'>{TITULO_PRINCIPAL}</h1>"
    if "global-title" not in html:
        html = html.replace("</head>", style + "</head>", 1)
        html = html.replace("<body>", "<body>" + title, 1)
    return html
