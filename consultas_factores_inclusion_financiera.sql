-- Consultas DuckDB para factores de inclusión financiera rural.
-- GEIH: CLASE 2 = centros poblados; CLASE 3 = rural disperso.

CREATE OR REPLACE TEMP VIEW geih_hogares AS
SELECT
  CAST(DIRECTORIO AS VARCHAR) AS DIRECTORIO,
  CAST(HOGAR AS VARCHAR) AS HOGAR,
  LPAD(CAST(DPTO AS VARCHAR), 2, '0') AS DPTO,
  -- Esta tabla es de hogar: el tamaño oficial ya viene en esta variable.
  -- No se usa SECUENCIA_P como identificador de persona.
  MAX(TRY_CAST(total_de_personas_en_el_hogar AS DOUBLE)) AS personas_hogar,
  MAX(TRY_CAST(FEX_C18 AS DOUBLE)) AS factor_hogar,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza AS INTEGER)=1 THEN 1 ELSE 0 END) AS cuenta_corriente,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_2 AS INTEGER)=1 THEN 1 ELSE 0 END) AS cuenta_ahorros,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_3 AS INTEGER)=1 THEN 1 ELSE 0 END) AS cdt,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_4 AS INTEGER)=1 THEN 1 ELSE 0 END) AS credito_vivienda,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_5 AS INTEGER)=1 THEN 1 ELSE 0 END) AS credito_vehiculo,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_6 AS INTEGER)=1 THEN 1 ELSE 0 END) AS credito_libre_inversion,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_7 AS INTEGER)=1 THEN 1 ELSE 0 END) AS tarjeta_credito,
  MAX(CASE WHEN TRY_CAST(cuales_de_los_siguientes_productos_financieros_utiliza_9 AS INTEGER)=1 THEN 1 ELSE 0 END) AS ningun_producto
FROM read_parquet('plata/geih_2025_decodificada/*__datos_del_hogar_y_la_vivienda.parquet')
WHERE CAST(CLASE AS VARCHAR) IN ('2','3')
  GROUP BY 1,2,3;

-- Productos financieros utilizados en hogares rurales.
SELECT producto, SUM(hogares_estimados) AS hogares_estimados
FROM (
  SELECT 'Cuenta corriente' producto, SUM(cuenta_corriente * factor_hogar) hogares_estimados FROM geih_hogares
  UNION ALL SELECT 'Cuenta de ahorros', SUM(cuenta_ahorros * factor_hogar) FROM geih_hogares
  UNION ALL SELECT 'CDT', SUM(cdt * factor_hogar) FROM geih_hogares
  UNION ALL SELECT 'Crédito de vivienda', SUM(credito_vivienda * factor_hogar) FROM geih_hogares
  UNION ALL SELECT 'Crédito de vehículo', SUM(credito_vehiculo * factor_hogar) FROM geih_hogares
  UNION ALL SELECT 'Crédito de libre inversión', SUM(credito_libre_inversion * factor_hogar) FROM geih_hogares
  UNION ALL SELECT 'Tarjeta de crédito', SUM(tarjeta_credito * factor_hogar) FROM geih_hogares
  UNION ALL SELECT 'Ningún producto', SUM(ningun_producto * factor_hogar) FROM geih_hogares
) x GROUP BY producto ORDER BY hogares_estimados DESC;

-- Nota: el sexo de la jefatura no está en la tabla de vivienda.
-- Para ese cruce se debe construir otra vista con la tabla de personas,
-- usando DIRECTORIO + HOGAR y el parentesco/sexo del jefe.

-- Tamaño promedio de los hogares rurales, sin atribuirlo a un sexo.
SELECT AVG(personas_hogar) AS promedio_personas_hogar,
       COUNT(*) AS hogares_observados
FROM geih_hogares;

-- Créditos agrarios, montos y tasas por sexo.
SELECT
  CASE WHEN LOWER(CAST(Sexo AS VARCHAR)) IN ('f','2','femenino','mujer') THEN 'Mujeres'
       WHEN LOWER(CAST(Sexo AS VARCHAR)) IN ('m','1','masculino','hombre') THEN 'Hombres'
       ELSE 'Sin dato' END AS sexo,
  COUNT(*) AS creditos,
  AVG(TRY_CAST(monto AS DOUBLE)) AS monto_promedio,
  MEDIAN(TRY_CAST(monto AS DOUBLE)) AS monto_mediano,
  AVG(TRY_CAST(tasa AS DOUBLE)) AS tasa_promedio
FROM read_parquet('plata/finagro_2025_limpia.parquet')
GROUP BY 1;

-- Productos y créditos por departamento.
SELECT
  LPAD(SUBSTR(CAST(DIVIPOLA AS VARCHAR),1,2),2,'0') AS DPTO,
  CASE WHEN LOWER(CAST(Sexo AS VARCHAR)) IN ('f','2','femenino','mujer') THEN 'Mujeres'
       WHEN LOWER(CAST(Sexo AS VARCHAR)) IN ('m','1','masculino','hombre') THEN 'Hombres'
       ELSE 'Sin dato' END AS sexo,
  COUNT(*) AS creditos,
  AVG(TRY_CAST(monto AS DOUBLE)) AS monto_promedio,
  AVG(TRY_CAST(tasa AS DOUBLE)) AS tasa_promedio
FROM read_parquet('plata/finagro_2025_limpia.parquet')
GROUP BY 1,2;

-- Cobertura bancaria territorial.
SELECT
  LPAD(SUBSTR(CAST(DIVIPOLA AS VARCHAR),1,2),2,'0') AS DPTO,
  AVG(TRY_CAST(densidad_bancaria AS DOUBLE)) AS densidad_bancaria
FROM read_parquet('plata/contexto_municipal_2025.parquet')
GROUP BY 1;

-- Importante: el plazo en meses y las sucursales físicas no se consultan
-- porque no existen en las bases actuales verificadas.
