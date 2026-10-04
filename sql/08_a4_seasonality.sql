-- 08_a4_seasonality.sql
-- Analysis 4: which drug groups are seasonal, and when do they peak?
-- Seasonal index = average scripts in a calendar month / average over all months.
-- 1.20 means that month runs 20% above the group's average. Not de-trended.
WITH monthly AS (
    SELECT i.atc2_code,
           m.month_start,
           m.cal_month,
           SUM(f.prescriptions) AS scripts
    FROM fact_supply f
    JOIN dim_month m USING (month_key)
    JOIN dim_item  i USING (item_code)
    WHERE m.fin_year IN (SELECT fin_year FROM v_full_fin_years)
      AND i.atc2_code IS NOT NULL
    GROUP BY i.atc2_code, m.month_start, m.cal_month
),
idx AS (
    SELECT atc2_code,
           cal_month,
           AVG(scripts) / NULLIF(AVG(AVG(scripts)) OVER (PARTITION BY atc2_code), 0) AS seasonal_index,
           SUM(SUM(scripts)) OVER (PARTITION BY atc2_code)                           AS total_scripts
    FROM monthly
    GROUP BY atc2_code, cal_month
)
SELECT atc2_code,
       ROUND(MAX(total_scripts) / 1e6, 2)                     AS total_scripts_m,
       ROUND(MAX(seasonal_index), 2)                          AS peak_index,
       ROUND(MIN(seasonal_index), 2)                          AS trough_index,
       (ARRAY_AGG(cal_month ORDER BY seasonal_index DESC))[1] AS peak_month,
       (ARRAY_AGG(cal_month ORDER BY seasonal_index ASC))[1]  AS trough_month
FROM idx
GROUP BY atc2_code
HAVING MAX(total_scripts) >= 1000000
ORDER BY MAX(seasonal_index) - MIN(seasonal_index) DESC
LIMIT 15;

-- 4b: the full month-by-month index for the 15 largest groups (feeds the heatmap)
WITH monthly AS (
    SELECT i.atc2_code,
           m.month_start,
           m.cal_month,
           SUM(f.prescriptions) AS scripts
    FROM fact_supply f
    JOIN dim_month m USING (month_key)
    JOIN dim_item  i USING (item_code)
    WHERE m.fin_year IN (SELECT fin_year FROM v_full_fin_years)
      AND i.atc2_code IS NOT NULL
    GROUP BY i.atc2_code, m.month_start, m.cal_month
),
idx AS (
    SELECT atc2_code,
           cal_month,
           AVG(scripts) / NULLIF(AVG(AVG(scripts)) OVER (PARTITION BY atc2_code), 0) AS seasonal_index,
           SUM(SUM(scripts)) OVER (PARTITION BY atc2_code)                           AS total_scripts
    FROM monthly
    GROUP BY atc2_code, cal_month
),
top15 AS (
    SELECT atc2_code
    FROM idx
    GROUP BY atc2_code
    ORDER BY MAX(total_scripts) DESC
    LIMIT 15
)
SELECT atc2_code,
       cal_month,
       ROUND(seasonal_index, 3)       AS seasonal_index,
       ROUND(total_scripts / 1e6, 2)  AS total_scripts_m
FROM idx
WHERE atc2_code IN (SELECT atc2_code FROM top15)
ORDER BY total_scripts DESC, atc2_code, cal_month;
