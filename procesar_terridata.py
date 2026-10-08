#!/usr/bin/env python3
"""Normaliza la descarga TerriData para cruces limpios con DuckDB."""
from pathlib import Path
import re
import unicodedata
import pandas as pd

BASE = Path(__file__).resolve().parent
ENTRADAS = sorted((BASE / 'Terridata1').glob('TerriData_Dim*.xlsx'))
SALIDA = BASE / 'plata/terridata_dim1_limpia.parquet'
SALIDA_ANCHA = BASE / 'plata/terridata_indicadores_2025.parquet'

def slug(text):
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii','ignore').decode()
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text.lower()).strip('_')
    return text or 'indicador'

def main():
    if not ENTRADAS:
        raise FileNotFoundError('No existen archivos Terridata1/TerriData_Dim*.xlsx')
    df = pd.concat([pd.read_excel(p, sheet_name=0) for p in ENTRADAS], ignore_index=True)
    df.columns = [str(c).strip() for c in df.columns]
    required = {'Código Entidad','Código Departamento','Indicador','Dato Numérico','Año'}
    missing = required - set(df.columns)
    if missing: raise ValueError(f'Faltan columnas TerriData: {sorted(missing)}')
    df['DIVIPOLA'] = df['Código Entidad'].astype('string').str.extract(r'(\d+)', expand=False).str.zfill(5)
    df['DPTO'] = df['Código Departamento'].astype('string').str.extract(r'(\d+)', expand=False).str.zfill(2)
    df['Año'] = pd.to_numeric(df['Año'], errors='coerce')
    # Se conserva 2025 por indicador; si no existe, se usa el último año
    # disponible para ese indicador (por ejemplo, ruralidad histórica 2000).
    latest_by_indicator = df.groupby('Indicador')['Año'].transform(lambda s: 2025 if (s == 2025).any() else s.max())
    df = df[df['Año'].eq(latest_by_indicator)].copy()
    target = 2025 if (df['Año'] == 2025).any() else int(df['Año'].dropna().max())
    df['indicador_nombre'] = df['Indicador'].map(slug)
    # Homologa las dos variantes de escritura del IPM que entrega TerriData.
    df.loc[df['indicador_nombre'].str.contains('indice_de_pobreza_multidimensional_ipm', na=False), 'indicador_nombre'] = 'ipm'
    # TerriData puede entregar números con formato colombiano: 24.517,00.
    raw_num = df['Dato Numérico'].astype('string').str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    df['dato_numerico'] = pd.to_numeric(raw_num, errors='coerce')
    # Evita colisiones: el indicador queda como fila larga y también se conserva el nombre limpio.
    keep = ['DIVIPOLA','DPTO','Departamento','Entidad','indicador_nombre','dato_numerico','Dato Cualitativo','Año','Mes','Fuente','Unidad de Medida']
    keep = [c for c in keep if c in df.columns]
    out = df[keep].drop_duplicates()
    SALIDA.parent.mkdir(exist_ok=True)
    out.to_parquet(SALIDA, index=False)
    # Tabla ancha para cruces directos: cada indicador se convierte en columna.
    wide = (out.pivot_table(index=['DIVIPOLA','DPTO','Departamento','Entidad','Año'],
                            columns='indicador_nombre', values='dato_numerico', aggfunc='first')
              .reset_index())
    wide.columns.name = None
    wide.to_parquet(SALIDA_ANCHA, index=False)
    print(f'OK: {len(out):,} filas -> {SALIDA}')
    print(f'OK: {len(wide):,} entidades -> {SALIDA_ANCHA}')
    print(f'Periodo seleccionado: {target}')
    print('Indicadores disponibles:')
    print('\n'.join(f"- {x}" for x in sorted(out['indicador_nombre'].dropna().unique())))

if __name__ == '__main__':
    main()
