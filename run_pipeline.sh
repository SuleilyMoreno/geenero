#!/usr/bin/env bash
# Pipeline completo 2025 (ruralidad + año 2025). Requiere los microdatos locales:
#   GEIH_2025/, Diccionario_de_datos_GEIH_2025.xlsx, ENUT/, Diccionario_ENUT_2024_2025_1.xlsx,
#   FIES.xlsx, Terridata1/TerriData_Dim*.xlsx
# Sin microdatos: python3 ejecutar_pipeline_2025.py --sin-microdatos
# Opcional: export SODAPY_APP_TOKEN=... para evitar límites de la API de datos.gov.co
set -euo pipefail
python3 ejecutar_pipeline_2025.py "$@"
