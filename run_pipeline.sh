export GEIH_VIVIENDAS="GEIH_2025_normalizada/datos_del_hogar_y_la_vivienda.csv"
export GEIH_PERSONAS="GEIH_2025_normalizada/ocupados.csv"

# Superfinanciera
export SUPER_DATASET_ID="w9zh-vetq"
export SUPER_ANIO_FIELD="date_extract_y(fecha_corte)"
export SUPER_CIIU_FIELD="codigo_ciiu"

# Finagro
export FINAGRO_DATASET_ID="w3uf-w9ey"
export FINAGRO_YEAR_COLUMN="a_o"

# Territoriales
export DIVIPOLA_CSV="divipola.csv"
export TERRIDATA_URL="http://httpbin.org/get?terri={codigo}"
export IGAC_URL="http://httpbin.org/get?igac={codigo}"

python3 ejecutar_pipeline_2025.py
