-- Consultas DuckDB de referencia (corregidas) para inclusión financiera rural 2025.
-- Filtros: GEIH 2025 con CLASE 2/3 (centros poblados y rural disperso).
-- Los tableros usan las mismas reglas desde generar_tablero_financiero_nacional_2025.py.

-- Hogares rurales: llave mes + DIRECTORIO + HOGAR. El mes sale del nombre del archivo
-- (enero__..., febrero__...) para no mezclar viviendas de meses distintos.
CREATE OR REPLACE TEMP VIEW geih_hogares AS
WITH v AS (
  SELECT *, regexp_extract(filename, '([^/]+?)__[^/]*$', 1) AS mes_archivo
  FROM read_parquet('plata/geih_2025_decodificada/*__datos_del_hogar_y_la_vivienda.parquet', filename=true, union_by_name=true)
  WHERE CAST(CLASE AS VARCHAR) IN ('2','3')
), meses AS (SELECT COUNT(DISTINCT mes_archivo) n FROM v)
SELECT
  mes_archivo, CAST(DIRECTORIO AS VARCHAR) DIRECTORIO, CAST(HOGAR AS VARCHAR) HOGAR,
  LPAD(CAST(DPTO AS VARCHAR), 2, '0') AS DPTO,
  MAX(TRY_CAST(total_de_personas_en_el_hogar AS DOUBLE)) AS personas_hogar,
  -- Factor anual: FEX_C18 mensual / número de meses (si no, se cuenta 12 veces la población).
  MAX(TRY_CAST(FEX_C18 AS DOUBLE)) / ANY_VALUE((SELECT n FROM meses)) AS w,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza AS INTEGER)=1 THEN 1 ELSE 0 END) AS cuenta_corriente,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_2 AS INTEGER)=1 THEN 1 ELSE 0 END) AS cuenta_ahorros,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_3 AS INTEGER)=1 THEN 1 ELSE 0 END) AS cdt,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_4 AS INTEGER)=1 THEN 1 ELSE 0 END) AS credito_vivienda,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_5 AS INTEGER)=1 THEN 1 ELSE 0 END) AS credito_vehiculo,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_6 AS INTEGER)=1 THEN 1 ELSE 0 END) AS credito_libre_inversion,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_7 AS INTEGER)=1 THEN 1 ELSE 0 END) AS tarjeta_credito,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_9 AS INTEGER)=1 THEN 1 ELSE 0 END) AS ningun_producto
FROM v GROUP BY 1, 2, 3, 4;

-- Porcentaje de hogares rurales que usa cada producto (respuesta múltiple).
SELECT 'Cuenta de ahorros' producto, 100*SUM(cuenta_ahorros*w)/SUM(w) pct FROM geih_hogares
UNION ALL SELECT 'Cuenta corriente', 100*SUM(cuenta_corriente*w)/SUM(w) FROM geih_hogares
UNION ALL SELECT 'CDT', 100*SUM(cdt*w)/SUM(w) FROM geih_hogares
UNION ALL SELECT 'Crédito de vivienda', 100*SUM(credito_vivienda*w)/SUM(w) FROM geih_hogares
UNION ALL SELECT 'Crédito de vehículo', 100*SUM(credito_vehiculo*w)/SUM(w) FROM geih_hogares
UNION ALL SELECT 'Crédito de libre inversión', 100*SUM(credito_libre_inversion*w)/SUM(w) FROM geih_hogares
UNION ALL SELECT 'Tarjeta de crédito', 100*SUM(tarjeta_credito*w)/SUM(w) FROM geih_hogares
UNION ALL SELECT 'Ningún producto', 100*SUM(ningun_producto*w)/SUM(w) FROM geih_hogares
ORDER BY pct DESC;

-- Tamaño promedio del hogar rural (ponderado) y hogares de la muestra.
SELECT SUM(personas_hogar*w)/SUM(w) AS promedio_personas_hogar, COUNT(*) AS hogares_muestra FROM geih_hogares;

-- Crédito (Finagro y Superfinanciera): no se consulta aquí. Lo calcula
-- extraer_credito_rural_2025.py directamente en la API de datos.gov.co, con:
--   * año 2025 y municipio con categoría DNP Rural o Rural disperso;
--   * Superfinanciera: créditos = SUM(numero_de_creditos) (cada fila es un grupo),
--     monto promedio = SUM(montos) / SUM(numero_de_creditos),
--     tasa = SUM(tasa*monto)/SUM(monto) excluyendo tasa_efectiva_promedio = 0.
