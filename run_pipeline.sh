#!/usr/bin/env bash
# Pipeline completo 2025 (ruralidad + año 2025). Insumos locales (no se versionan):
#   GEIH_2025/<Mes> 2025/*.CSV y Diccionario_de_datos_GEIH_2025.xlsx
#       https://microdatos.dane.gov.co/index.php/catalog/853 (12 ZIP mensuales + diccionario)
#   ENUT/ENUT_C1.csv, ENUT_C3.csv, ENUT_C8.csv y Diccionario_ENUT_2024_2025_1.xlsx
#       https://microdatos.dane.gov.co/index.php/catalog/910
#   FIES.xlsx  https://www.dane.gov.co/files/operaciones/FIES/anex-FIES-2025.xlsx
#   Terridata1/TerriData_Dim*.xlsx (opcional; descarga manual en terridata.dnp.gov.co)
# Sin microdatos: python3 ejecutar_pipeline_2025.py --sin-microdatos
# Opcional: export SODAPY_APP_TOKEN=... para evitar límites de la API de datos.gov.co
set -euo pipefail
python3 ejecutar_pipeline_2025.py "$@"
