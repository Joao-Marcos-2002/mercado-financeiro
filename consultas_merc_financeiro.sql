-- =====================================================================
-- Consultas do projeto: relacao entre indicadores macro e titulos publicos
-- Banco: merc_financeiro (MySQL 8+)
-- Tabelas: serie_def, serie_macro, titulo_tesouro
-- Series: 432 Selic meta | 433 IPCA mensal | 24363 IBC-Br | 24369 Desocupacao
-- =====================================================================

USE merc_financeiro;

-- ---------------------------------------------------------------------
-- 0. CONFERENCIA DA CARGA
-- ---------------------------------------------------------------------
SELECT d.codigo_serie, d.nome, COUNT(*) AS linhas,
       MIN(m.data) AS primeira, MAX(m.data) AS ultima
FROM serie_macro m JOIN serie_def d USING (codigo_serie)
GROUP BY d.codigo_serie, d.nome;

SELECT tipo_titulo, COUNT(*) AS linhas, MIN(data_base) AS primeira,
       MAX(data_base) AS ultima, COUNT(DISTINCT vencimento) AS vencimentos
FROM titulo_tesouro
GROUP BY tipo_titulo;

-- ---------------------------------------------------------------------
-- 1. VIEW: INDICADORES MACRO CONSOLIDADOS POR MES
--    (Selic e diaria -> usa media do mes e valor do fim do mes)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_macro_mensal AS
SELECT
    DATE_FORMAT(data, '%Y-%m-01') AS mes,
    AVG(CASE WHEN codigo_serie = 432   THEN valor END) AS selic_media,
    MAX(CASE WHEN codigo_serie = 433   THEN valor END) AS ipca_mensal,
    MAX(CASE WHEN codigo_serie = 24363 THEN valor END) AS ibc_br,
    MAX(CASE WHEN codigo_serie = 24369 THEN valor END) AS desocupacao
FROM serie_macro
GROUP BY DATE_FORMAT(data, '%Y-%m-01');

SELECT * FROM v_macro_mensal ORDER BY mes;

-- IPCA acumulado em 12 meses e variacoes mes a mes
SELECT mes, selic_media, ipca_mensal,
       ROUND((EXP(SUM(LN(1 + ipca_mensal/100)) OVER (ORDER BY mes
             ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)) - 1) * 100, 2) AS ipca_acum_12m,
       ibc_br - LAG(ibc_br) OVER (ORDER BY mes)               AS var_ibc_br,
       desocupacao - LAG(desocupacao) OVER (ORDER BY mes)     AS var_desocupacao
FROM v_macro_mensal
ORDER BY mes;

-- ---------------------------------------------------------------------
-- 2. CICLO DA SELIC: datas em que a meta mudou (base do estudo de caso)
-- ---------------------------------------------------------------------
SELECT data, valor AS selic_nova,
       LAG(valor) OVER (ORDER BY data) AS selic_anterior,
       valor - LAG(valor) OVER (ORDER BY data) AS variacao_pp
FROM serie_macro
WHERE codigo_serie = 432
ORDER BY data;
-- (use: SELECT * FROM (...) t WHERE variacao_pp <> 0 para ver so as mudancas)

-- ---------------------------------------------------------------------
-- 3. TITULOS DO TESOURO
-- ---------------------------------------------------------------------
-- 3.1 Quais titulos existem na janela e quantos dias de dados cada um tem
SELECT tipo_titulo, vencimento, COUNT(*) AS dias,
       MIN(data_base) AS inicio, MAX(data_base) AS fim
FROM titulo_tesouro
WHERE data_base >= '2025-01-01'
GROUP BY tipo_titulo, vencimento
HAVING dias > 200
ORDER BY tipo_titulo, vencimento;

-- 3.2 VIEW mensal por titulo: taxa media, PU medio e PU do ultimo dia do mes
CREATE OR REPLACE VIEW v_titulo_mensal AS
SELECT t.tipo_titulo, t.vencimento,
       DATE_FORMAT(t.data_base, '%Y-%m-01') AS mes,
       AVG(t.taxa_venda) AS taxa_media,
       AVG(t.pu_venda)   AS pu_medio,
       SUBSTRING_INDEX(GROUP_CONCAT(t.pu_venda   ORDER BY t.data_base DESC), ',', 1) + 0 AS pu_fim_mes,
       SUBSTRING_INDEX(GROUP_CONCAT(t.taxa_venda ORDER BY t.data_base DESC), ',', 1) + 0 AS taxa_fim_mes
FROM titulo_tesouro t
GROUP BY t.tipo_titulo, t.vencimento, DATE_FORMAT(t.data_base, '%Y-%m-01');

-- 3.3 Variacao mensal da taxa e do preco (marcacao a mercado) de cada titulo
CREATE OR REPLACE VIEW v_titulo_variacao AS
SELECT tipo_titulo, vencimento, mes, taxa_fim_mes, pu_fim_mes,
       taxa_fim_mes - LAG(taxa_fim_mes) OVER w AS var_taxa_pp,
       (pu_fim_mes / LAG(pu_fim_mes) OVER w - 1) * 100 AS var_pu_pct
FROM v_titulo_mensal
WINDOW w AS (PARTITION BY tipo_titulo, vencimento ORDER BY mes);



/* View macro mensal*/

CREATE OR REPLACE VIEW v_macro_mensal AS
SELECT
    DATE_FORMAT(data, '%Y-%m-01') AS mes,
    AVG(CASE WHEN codigo_serie = 432   THEN valor END) AS selic_media,
    MAX(CASE WHEN codigo_serie = 433   THEN valor END) AS ipca_mensal,
    MAX(CASE WHEN codigo_serie = 24363 THEN valor END) AS ibc_br,
    MAX(CASE WHEN codigo_serie = 24369 THEN valor END) AS desocupacao
FROM serie_macro
GROUP BY DATE_FORMAT(data, '%Y-%m-01');


/* View mensal por título: */

CREATE OR REPLACE VIEW v_titulo_mensal AS
SELECT t.tipo_titulo, t.vencimento,
       DATE_FORMAT(t.data_base, '%Y-%m-01') AS mes,
       AVG(t.taxa_venda) AS taxa_media,
       AVG(t.pu_venda)   AS pu_medio,
       SUBSTRING_INDEX(GROUP_CONCAT(t.pu_venda   ORDER BY t.data_base DESC), ',', 1) + 0 AS pu_fim_mes,
       SUBSTRING_INDEX(GROUP_CONCAT(t.taxa_venda ORDER BY t.data_base DESC), ',', 1) + 0 AS taxa_fim_mes
FROM titulo_tesouro t
GROUP BY t.tipo_titulo, t.vencimento, DATE_FORMAT(t.data_base, '%Y-%m-01');



/* View de variação (a que faltou) */


CREATE OR REPLACE VIEW v_titulo_variacao AS
SELECT tipo_titulo, vencimento, mes, taxa_fim_mes, pu_fim_mes,
       taxa_fim_mes - LAG(taxa_fim_mes) OVER w AS var_taxa_pp,
       (pu_fim_mes / LAG(pu_fim_mes) OVER w - 1) * 100 AS var_pu_pct
FROM v_titulo_mensal
WINDOW w AS (PARTITION BY tipo_titulo, vencimento ORDER BY mes);



-- ---------------------------------------------------------------------
-- 4. CRUZAMENTO MACRO x TITULO  (troque tipo_titulo e vencimento)
--    Rode a consulta 3.1 para ver os nomes exatos disponiveis.
-- ---------------------------------------------------------------------
SELECT m.mes, m.selic_media, m.ipca_mensal, m.ibc_br, m.desocupacao,
       v.taxa_fim_mes, v.var_taxa_pp, v.var_pu_pct
FROM v_macro_mensal m
JOIN v_titulo_variacao v ON v.mes = m.mes
WHERE v.tipo_titulo = 'Tesouro Prefixado'
  AND v.vencimento  = '2029-01-01'
ORDER BY m.mes;

-- ---------------------------------------------------------------------
-- 5. CORRELACAO E DEFASAGENS (MySQL nao tem CORR, entao usamos a formula)
--    Correlacao de Pearson entre a variacao do preco do titulo e cada
--    indicador deslocado em 0, 1, 2 e 3 meses.
-- ---------------------------------------------------------------------
WITH base AS (
    SELECT m.mes,
           v.var_pu_pct AS y,
           m.selic_media,
           m.ipca_mensal,
           m.ibc_br - LAG(m.ibc_br) OVER (ORDER BY m.mes)           AS d_ibc,
           m.desocupacao - LAG(m.desocupacao) OVER (ORDER BY m.mes) AS d_desoc
    FROM v_macro_mensal m
    JOIN v_titulo_variacao v ON v.mes = m.mes
    WHERE v.tipo_titulo = 'Tesouro Prefixado' AND v.vencimento = '2029-01-01'
),
lags AS (
    SELECT mes, y,
           selic_media AS selic_l0, LAG(selic_media,1) OVER (ORDER BY mes) AS selic_l1,
           LAG(selic_media,2) OVER (ORDER BY mes) AS selic_l2, LAG(selic_media,3) OVER (ORDER BY mes) AS selic_l3,
           ipca_mensal AS ipca_l0, LAG(ipca_mensal,1) OVER (ORDER BY mes) AS ipca_l1,
           LAG(ipca_mensal,2) OVER (ORDER BY mes) AS ipca_l2, LAG(ipca_mensal,3) OVER (ORDER BY mes) AS ipca_l3,
           d_desoc AS desoc_l0, LAG(d_desoc,1) OVER (ORDER BY mes) AS desoc_l1,
           LAG(d_desoc,2) OVER (ORDER BY mes) AS desoc_l2, LAG(d_desoc,3) OVER (ORDER BY mes) AS desoc_l3
    FROM base
)
SELECT 'Selic' AS indicador, 0 AS defasagem_meses,
       (COUNT(*)*SUM(y*selic_l0)-SUM(y)*SUM(selic_l0)) /
       SQRT((COUNT(*)*SUM(y*y)-POW(SUM(y),2))*(COUNT(*)*SUM(selic_l0*selic_l0)-POW(SUM(selic_l0),2))) AS correlacao,
       COUNT(*) AS n
FROM lags WHERE y IS NOT NULL AND selic_l0 IS NOT NULL
UNION ALL
SELECT 'Selic', 1,
       (COUNT(*)*SUM(y*selic_l1)-SUM(y)*SUM(selic_l1)) /
       SQRT((COUNT(*)*SUM(y*y)-POW(SUM(y),2))*(COUNT(*)*SUM(selic_l1*selic_l1)-POW(SUM(selic_l1),2))),
       COUNT(*)
FROM lags WHERE y IS NOT NULL AND selic_l1 IS NOT NULL
UNION ALL
SELECT 'IPCA', 0,
       (COUNT(*)*SUM(y*ipca_l0)-SUM(y)*SUM(ipca_l0)) /
       SQRT((COUNT(*)*SUM(y*y)-POW(SUM(y),2))*(COUNT(*)*SUM(ipca_l0*ipca_l0)-POW(SUM(ipca_l0),2))),
       COUNT(*)
FROM lags WHERE y IS NOT NULL AND ipca_l0 IS NOT NULL
UNION ALL
SELECT 'IPCA', 1,
       (COUNT(*)*SUM(y*ipca_l1)-SUM(y)*SUM(ipca_l1)) /
       SQRT((COUNT(*)*SUM(y*y)-POW(SUM(y),2))*(COUNT(*)*SUM(ipca_l1*ipca_l1)-POW(SUM(ipca_l1),2))),
       COUNT(*)
FROM lags WHERE y IS NOT NULL AND ipca_l1 IS NOT NULL
UNION ALL
SELECT 'Desocupacao (var.)', 0,
       (COUNT(*)*SUM(y*desoc_l0)-SUM(y)*SUM(desoc_l0)) /
       SQRT((COUNT(*)*SUM(y*y)-POW(SUM(y),2))*(COUNT(*)*SUM(desoc_l0*desoc_l0)-POW(SUM(desoc_l0),2))),
       COUNT(*)
FROM lags WHERE y IS NOT NULL AND desoc_l0 IS NOT NULL
UNION ALL
SELECT 'Desocupacao (var.)', 1,
       (COUNT(*)*SUM(y*desoc_l1)-SUM(y)*SUM(desoc_l1)) /
       SQRT((COUNT(*)*SUM(y*y)-POW(SUM(y),2))*(COUNT(*)*SUM(desoc_l1*desoc_l1)-POW(SUM(desoc_l1),2))),
       COUNT(*)
FROM lags WHERE y IS NOT NULL AND desoc_l1 IS NOT NULL;
-- Para defasagens 2 e 3, copie um bloco e troque _l1 por _l2 / _l3.

-- ---------------------------------------------------------------------
-- 6. ESTUDO DE CASO: reacao dos titulos a cada mudanca da Selic
--    Compara a taxa media de cada titulo 15 dias antes e 15 dias depois
--    de cada decisao do Copom (datas em que a meta mudou).
-- ---------------------------------------------------------------------
WITH mudancas AS (
    SELECT data AS dt, valor AS selic_nova,
           valor - LAG(valor) OVER (ORDER BY data) AS var_pp
    FROM serie_macro WHERE codigo_serie = 432
)
SELECT c.dt AS data_decisao, c.var_pp AS mudanca_selic_pp,
       t.tipo_titulo, t.vencimento,
       AVG(CASE WHEN t.data_base BETWEEN c.dt - INTERVAL 15 DAY AND c.dt - INTERVAL 1 DAY
                THEN t.taxa_venda END) AS taxa_antes,
       AVG(CASE WHEN t.data_base BETWEEN c.dt AND c.dt + INTERVAL 15 DAY
                THEN t.taxa_venda END) AS taxa_depois
FROM mudancas c
JOIN titulo_tesouro t
  ON t.data_base BETWEEN c.dt - INTERVAL 15 DAY AND c.dt + INTERVAL 15 DAY
WHERE c.var_pp <> 0
GROUP BY c.dt, c.var_pp, t.tipo_titulo, t.vencimento
ORDER BY c.dt, t.tipo_titulo, t.vencimento;
