-- Referencia: query origen de base_epicentros_marketplace.csv
-- Mes de análisis configurable en params.mes_analisis

WITH
-- ============================================================
-- 1. PARÁMETROS DE TIEMPO
-- ============================================================
params AS (
    SELECT
        '202605' AS mes_analisis, -- 📍 Mes base para la foto (Mes 0)
        DATE_FORMAT(ADD_MONTHS(TO_DATE('202605', 'yyyyMM'), -2), 'yyyyMM') AS mes_inicio_l3m, -- Últimos 3 meses (Mes 0, -1, -2)
        DATE_FORMAT(ADD_MONTHS(TO_DATE('202605', 'yyyyMM'), -5), 'yyyyMM') AS mes_inicio_l6m  -- Últimos 6 meses para segmentación
),

-- ============================================================
-- 2. TABLA DE EXCLUSIONES (Blacklist)
-- ============================================================
clientes_excluidos AS (
    SELECT DISTINCT CAST(customer_ID AS STRING) AS cliente_id_excluido
    FROM brewdat_uc_mazana_dev.slv_maz_dataexperience_peru_adb.marketplace_maestro_exclusiones
),

-- ============================================================
-- 3. MAESTRO ÚNICO DE SKUS MARKETPLACE (Para optimizar el flag de venta)
-- ============================================================
maestro_skus_mp AS (
    SELECT DISTINCT CAST(material_id AS STRING) AS material_id_mp
    FROM brewdat_uc_mazana_dev.slv_maz_dataexperience_peru_adb.marketplace_maestro_sku
),

-- ============================================================
-- 4. FILTRO TEMPRANO Y CÁLCULO DE BILLETERAS GENERALES (L3M)
-- ============================================================
clientes_activos_base AS (
    SELECT 
        CAST(v.cliente_id AS STRING) AS cliente_id, 
        SUM(v.total) AS total_soles_backus_l3m,
        SUM(CASE WHEN m.material_id_mp IS NOT NULL THEN v.total ELSE 0 END) AS total_soles_marketplace_l3m
    FROM brewdat_uc_mazana_dev.slv_maz_dataexperience_peru_dm.dm_venta v
    CROSS JOIN params p
    LEFT JOIN clientes_excluidos e 
        ON CAST(v.cliente_id AS STRING) = e.cliente_id_excluido
    LEFT JOIN maestro_skus_mp m 
        ON CAST(v.material_id AS STRING) = m.material_id_mp
    WHERE v.mes BETWEEN p.mes_inicio_l3m AND p.mes_analisis
      AND v.estado_venta = 1
      AND LENGTH(CAST(v.cliente_id AS STRING)) = 8 
      AND e.cliente_id_excluido IS NULL 
    GROUP BY CAST(v.cliente_id AS STRING)
    HAVING SUM(v.total) > 10
),

-- ============================================================
-- 5. MAESTRO CLIENTE GEOLOCALIZADO
-- ============================================================
clientes_geo AS (
    SELECT 
        CAST(cliente_id AS STRING) AS cliente_id, 
        nombre, direccion, gerencia, canal, subcanal, cant_eeff, zona_peligrosa,
        CAST(x AS DOUBLE) AS longitud,  
        CAST(y AS DOUBLE) AS latitud 
    FROM (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY cliente_id ORDER BY mes DESC) as rn
        FROM brewdat_uc_mazana_dev.slv_maz_dataexperience_peru_dm.dm_cliente
        WHERE CAST(x AS DOUBLE) IS NOT NULL 
          AND CAST(y AS DOUBLE) IS NOT NULL 
          AND LENGTH(CAST(cliente_id AS STRING)) = 8
    ) WHERE rn = 1
),

-- ============================================================
-- 6. VENTAS DETALLADAS DE LOS 5 PARTNERS ESPECÍFICOS
-- ============================================================
ventas_partners AS (
    SELECT
        CAST(a.cliente_id AS STRING) AS cliente_id,
        a.mes,
        UPPER(d.partner) AS partner_limpio,
        SUM(a.cantidad_venta) AS cajas,
        SUM(a.total) AS nr 
    FROM brewdat_uc_mazana_dev.slv_maz_dataexperience_peru_dm.dm_venta a
    CROSS JOIN params p
    INNER JOIN clientes_activos_base cb 
        ON CAST(a.cliente_id AS STRING) = cb.cliente_id 
    INNER JOIN brewdat_uc_mazana_dev.slv_maz_dataexperience_peru_adb.marketplace_maestro_sku d
        ON CAST(a.material_id AS STRING) = CAST(d.material_id AS STRING) 
    WHERE a.mes BETWEEN p.mes_inicio_l6m AND p.mes_analisis
      AND a.estado_venta = 1
      AND UPPER(d.partner) IN ('RED BULL', 'BAT', 'QUEIROLO', 'PISCANO', 'PERNOD')
      AND a.agrupador IN ('Venta', 'Rewards')
    GROUP BY CAST(a.cliente_id AS STRING), a.mes, UPPER(d.partner)
),

-- ============================================================
-- 7. MATRIZ DE COMPORTAMIENTO L6M (Filas a Columnas)
-- ============================================================
comportamiento_partner AS (
    SELECT 
        v.cliente_id,
        v.partner_limpio,
        SUM(CASE WHEN v.mes >= p.mes_inicio_l3m THEN v.cajas ELSE 0 END) AS cajas_l3m,
        SUM(CASE WHEN v.mes >= p.mes_inicio_l3m THEN v.nr ELSE 0 END) AS nr_l3m,
        MAX(CASE WHEN v.mes = p.mes_analisis THEN 1 ELSE 0 END) AS compra_m0,
        MAX(CASE WHEN v.mes = DATE_FORMAT(ADD_MONTHS(TO_DATE(p.mes_analisis, 'yyyyMM'), -1), 'yyyyMM') THEN 1 ELSE 0 END) AS compra_m1,
        MAX(CASE WHEN v.mes = DATE_FORMAT(ADD_MONTHS(TO_DATE(p.mes_analisis, 'yyyyMM'), -2), 'yyyyMM') THEN 1 ELSE 0 END) AS compra_m2,
        MAX(CASE WHEN v.mes = DATE_FORMAT(ADD_MONTHS(TO_DATE(p.mes_analisis, 'yyyyMM'), -3), 'yyyyMM') THEN 1 ELSE 0 END) AS compra_m3,
        MAX(CASE WHEN v.mes = DATE_FORMAT(ADD_MONTHS(TO_DATE(p.mes_analisis, 'yyyyMM'), -4), 'yyyyMM') THEN 1 ELSE 0 END) AS compra_m4,
        MAX(CASE WHEN v.mes = DATE_FORMAT(ADD_MONTHS(TO_DATE(p.mes_analisis, 'yyyyMM'), -5), 'yyyyMM') THEN 1 ELSE 0 END) AS compra_m5
    FROM ventas_partners v
    CROSS JOIN params p
    GROUP BY v.cliente_id, v.partner_limpio
),

-- ============================================================
-- 8. CÁLCULO DE SEGMENTACIONES Y PROMEDIOS L3M POR PARTNER
-- ============================================================
segmentacion_partner AS (
    SELECT 
        cliente_id,
        partner_limpio,
        cajas_l3m,
        nr_l3m,
        ROUND(nr_l3m / 3.0, 2) AS nr_prom_l3m, 
        CASE 
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3 + compra_m4 + compra_m5) = 0 THEN 'Perdido/No Comprador'
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3) BETWEEN 3 AND 4 AND compra_m0 = 1 AND compra_m1 = 1 AND compra_m2 = 1 THEN 'Super Estable'
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3) BETWEEN 3 AND 4 THEN 'Estable'
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3) BETWEEN 1 AND 2 THEN 'Inestable'
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3) = 0 AND (compra_m4 + compra_m5) > 0 THEN 'En Riesgo / Perdido Reciente'
            ELSE 'Sin Clasificar' 
        END AS segmento,
        CASE 
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3 + compra_m4 + compra_m5) = 0 THEN 'No Comprador'
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3) BETWEEN 3 AND 4 THEN 'Estable' 
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3) BETWEEN 1 AND 2 THEN 'Inestable'
            WHEN (compra_m0 + compra_m1 + compra_m2 + compra_m3) = 0 AND (compra_m4 + compra_m5) > 0 THEN 'Inestable' 
            ELSE 'No Comprador' 
        END AS segmento_resumen
    FROM comportamiento_partner
),

-- ============================================================
-- 9. PIVOT: APLANAR LA DATA A UNA FILA POR CLIENTE
-- ============================================================
clientes_pivoteados AS (
    SELECT 
        cliente_id,
        MAX(CASE WHEN partner_limpio = 'RED BULL' THEN cajas_l3m ELSE 0 END) AS rb_cajas_l3m,
        MAX(CASE WHEN partner_limpio = 'RED BULL' THEN nr_l3m ELSE 0 END) AS rb_nr_l3m,
        MAX(CASE WHEN partner_limpio = 'RED BULL' THEN nr_prom_l3m ELSE 0 END) AS rb_nr_prom_l3m,
        MAX(CASE WHEN partner_limpio = 'RED BULL' THEN segmento ELSE 'No Comprador' END) AS rb_segmento,
        MAX(CASE WHEN partner_limpio = 'RED BULL' THEN segmento_resumen ELSE 'No Comprador' END) AS rb_segmento_resumen,
        MAX(CASE WHEN partner_limpio = 'BAT' THEN cajas_l3m ELSE 0 END) AS bat_cajas_l3m,
        MAX(CASE WHEN partner_limpio = 'BAT' THEN nr_l3m ELSE 0 END) AS bat_nr_l3m,
        MAX(CASE WHEN partner_limpio = 'BAT' THEN nr_prom_l3m ELSE 0 END) AS bat_nr_prom_l3m,
        MAX(CASE WHEN partner_limpio = 'BAT' THEN segmento ELSE 'No Comprador' END) AS bat_segmento,
        MAX(CASE WHEN partner_limpio = 'BAT' THEN segmento_resumen ELSE 'No Comprador' END) AS bat_segmento_resumen,
        MAX(CASE WHEN partner_limpio = 'QUEIROLO' THEN cajas_l3m ELSE 0 END) AS queirolo_cajas_l3m,
        MAX(CASE WHEN partner_limpio = 'QUEIROLO' THEN nr_l3m ELSE 0 END) AS queirolo_nr_l3m,
        MAX(CASE WHEN partner_limpio = 'QUEIROLO' THEN nr_prom_l3m ELSE 0 END) AS queirolo_nr_prom_l3m,
        MAX(CASE WHEN partner_limpio = 'QUEIROLO' THEN segmento ELSE 'No Comprador' END) AS queirolo_segmento,
        MAX(CASE WHEN partner_limpio = 'QUEIROLO' THEN segmento_resumen ELSE 'No Comprador' END) AS queirolo_segmento_resumen,
        MAX(CASE WHEN partner_limpio = 'PISCANO' THEN cajas_l3m ELSE 0 END) AS piscano_cajas_l3m,
        MAX(CASE WHEN partner_limpio = 'PISCANO' THEN nr_l3m ELSE 0 END) AS piscano_nr_l3m,
        MAX(CASE WHEN partner_limpio = 'PISCANO' THEN nr_prom_l3m ELSE 0 END) AS piscano_nr_prom_l3m,
        MAX(CASE WHEN partner_limpio = 'PISCANO' THEN segmento ELSE 'No Comprador' END) AS piscano_segmento,
        MAX(CASE WHEN partner_limpio = 'PISCANO' THEN segmento_resumen ELSE 'No Comprador' END) AS piscano_segmento_resumen,
        MAX(CASE WHEN partner_limpio = 'PERNOD' THEN cajas_l3m ELSE 0 END) AS pernod_cajas_l3m,
        MAX(CASE WHEN partner_limpio = 'PERNOD' THEN nr_l3m ELSE 0 END) AS pernod_nr_l3m,
        MAX(CASE WHEN partner_limpio = 'PERNOD' THEN nr_prom_l3m ELSE 0 END) AS pernod_nr_prom_l3m,
        MAX(CASE WHEN partner_limpio = 'PERNOD' THEN segmento ELSE 'No Comprador' END) AS pernod_segmento,
        MAX(CASE WHEN partner_limpio = 'PERNOD' THEN segmento_resumen ELSE 'No Comprador' END) AS pernod_segmento_resumen
    FROM segmentacion_partner
    GROUP BY cliente_id
)

-- ============================================================
-- 10. TABLÓN FINAL PLANO DE EXPORTACIÓN
-- ============================================================
SELECT 
    cb.cliente_id,
    cg.latitud,
    cg.longitud,
    cg.direccion AS zona_direccion,
    cg.gerencia,
    cg.canal,
    cg.subcanal,
    cg.cant_eeff,
    cg.zona_peligrosa,
    1 AS flag_activo_l3m,
    cb.total_soles_backus_l3m,
    cb.total_soles_marketplace_l3m,
    COALESCE(cp.rb_cajas_l3m, 0) AS rb_cajas_l3m,
    COALESCE(cp.rb_nr_l3m, 0) AS rb_nr_l3m,
    COALESCE(cp.rb_nr_prom_l3m, 0) AS rb_nr_prom_l3m,
    COALESCE(cp.rb_segmento, 'No Comprador') AS rb_segmento,
    COALESCE(cp.rb_segmento_resumen, 'No Comprador') AS rb_segmento_resumen,
    COALESCE(cp.bat_cajas_l3m, 0) AS bat_cajas_l3m,
    COALESCE(cp.bat_nr_l3m, 0) AS bat_nr_l3m,
    COALESCE(cp.bat_nr_prom_l3m, 0) AS bat_nr_prom_l3m,
    COALESCE(cp.bat_segmento, 'No Comprador') AS bat_segmento,
    COALESCE(cp.bat_segmento_resumen, 'No Comprador') AS bat_segmento_resumen,
    COALESCE(cp.queirolo_cajas_l3m, 0) AS queirolo_cajas_l3m,
    COALESCE(cp.queirolo_nr_l3m, 0) AS queirolo_nr_l3m,
    COALESCE(cp.queirolo_nr_prom_l3m, 0) AS queirolo_nr_prom_l3m,
    COALESCE(cp.queirolo_segmento, 'No Comprador') AS queirolo_segmento,
    COALESCE(cp.queirolo_segmento_resumen, 'No Comprador') AS queirolo_segmento_resumen,
    COALESCE(cp.piscano_cajas_l3m, 0) AS piscano_cajas_l3m,
    COALESCE(cp.piscano_nr_l3m, 0) AS piscano_nr_l3m,
    COALESCE(cp.piscano_nr_prom_l3m, 0) AS piscano_nr_prom_l3m,
    COALESCE(cp.piscano_segmento, 'No Comprador') AS piscano_segmento,
    COALESCE(cp.piscano_segmento_resumen, 'No Comprador') AS piscano_segmento_resumen,
    COALESCE(cp.pernod_cajas_l3m, 0) AS pernod_cajas_l3m,
    COALESCE(cp.pernod_nr_l3m, 0) AS pernod_nr_l3m,
    COALESCE(cp.pernod_nr_prom_l3m, 0) AS pernod_nr_prom_l3m,
    COALESCE(cp.pernod_segmento, 'No Comprador') AS pernod_segmento,
    COALESCE(cp.pernod_segmento_resumen, 'No Comprador') AS pernod_segmento_resumen
FROM clientes_activos_base cb
LEFT JOIN clientes_geo cg ON cb.cliente_id = cg.cliente_id
LEFT JOIN clientes_pivoteados cp ON cb.cliente_id = cp.cliente_id;
