-- 09_a5_price_volume.sql
-- Analysis 5: is the change in spending driven by script volume or by cost per script?
-- Q = scripts, P = cost per script, 0 = first full FY, 1 = last full FY.
--   C1 - C0 = (Q1 - Q0) * P0  [volume effect]  +  (P1 - P0) * Q1  [price effect]
-- The two effects add up exactly to the total change (self-check: volume + price = change).
WITH fy AS (
    SELECT MIN(fin_year) AS y0, MAX(fin_year) AS y1 FROM v_full_fin_years
),
agg AS (
    SELECT a.atc1_code,
           a.atc1_name,
           SUM(f.total_cost)    FILTER (WHERE m.fin_year = fy.y0) AS c0,
           SUM(f.prescriptions) FILTER (WHERE m.fin_year = fy.y0) AS q0,
           SUM(f.total_cost)    FILTER (WHERE m.fin_year = fy.y1) AS c1,
           SUM(f.prescriptions) FILTER (WHERE m.fin_year = fy.y1) AS q1
    FROM fact_supply f
    JOIN dim_month m USING (month_key)
    JOIN dim_item  i USING (item_code)
    JOIN dim_atc1  a USING (atc1_code)
    CROSS JOIN fy
    WHERE m.fin_year IN (fy.y0, fy.y1)
    GROUP BY a.atc1_code, a.atc1_name
)
SELECT atc1_code,
       atc1_name,
       ROUND(c0 / q0, 2)                        AS cost_per_script_y0,
       ROUND(c1 / q1, 2)                        AS cost_per_script_y1,
       ROUND(100.0 * (q1 - q0) / q0, 1)         AS script_growth_pct,
       ROUND((c1 - c0) / 1e6, 1)                AS change_m,
       ROUND((q1 - q0) * (c0 / q0) / 1e6, 1)    AS volume_effect_m,
       ROUND((c1 / q1 - c0 / q0) * q1 / 1e6, 1) AS price_effect_m
FROM agg
WHERE q0 > 0 AND q1 > 0
ORDER BY ABS(c1 - c0) DESC;

-- Same decomposition for the whole scheme (one row)
WITH fy AS (
    SELECT MIN(fin_year) AS y0, MAX(fin_year) AS y1 FROM v_full_fin_years
),
agg AS (
    SELECT SUM(f.total_cost)    FILTER (WHERE m.fin_year = fy.y0) AS c0,
           SUM(f.prescriptions) FILTER (WHERE m.fin_year = fy.y0) AS q0,
           SUM(f.total_cost)    FILTER (WHERE m.fin_year = fy.y1) AS c1,
           SUM(f.prescriptions) FILTER (WHERE m.fin_year = fy.y1) AS q1
    FROM fact_supply f
    JOIN dim_month m USING (month_key)
    CROSS JOIN fy
    WHERE m.fin_year IN (fy.y0, fy.y1)
)
SELECT ROUND(c0 / 1e6, 1)                       AS cost_y0_m,
       ROUND(c1 / 1e6, 1)                       AS cost_y1_m,
       ROUND(100.0 * (c1 - c0) / c0, 1)         AS cost_growth_pct,
       ROUND(100.0 * (q1 - q0) / q0, 1)         AS script_growth_pct,
       ROUND(c0 / q0, 2)                        AS cost_per_script_y0,
       ROUND(c1 / q1, 2)                        AS cost_per_script_y1,
       ROUND((q1 - q0) * (c0 / q0) / 1e6, 1)    AS volume_effect_m,
       ROUND((c1 / q1 - c0 / q0) * q1 / 1e6, 1) AS price_effect_m
FROM agg;
