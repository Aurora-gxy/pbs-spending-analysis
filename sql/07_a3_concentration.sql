-- 07_a3_concentration.sql
-- Analysis 3: how concentrated is government spending? (Pareto analysis)
-- Latest full financial year, by generic drug name (one drug can have many item codes).

-- 3a: top 20 drugs with cumulative share
WITH drug AS (
    SELECT i.drug_name,
           SUM(f.govt_contrib)  AS govt_cost,
           SUM(f.prescriptions) AS scripts
    FROM fact_supply f
    JOIN dim_month m USING (month_key)
    JOIN dim_item  i USING (item_code)
    WHERE m.fin_year = (SELECT MAX(fin_year) FROM v_full_fin_years)
    GROUP BY i.drug_name
),
ranked AS (
    SELECT drug_name,
           govt_cost,
           scripts,
           ROW_NUMBER() OVER (ORDER BY govt_cost DESC, drug_name)                 AS rn,
           SUM(govt_cost) OVER (ORDER BY govt_cost DESC, drug_name
                                ROWS UNBOUNDED PRECEDING) / SUM(govt_cost) OVER () AS cum_share
    FROM drug
)
SELECT rn,
       drug_name,
       ROUND(govt_cost / 1e6, 1)                AS govt_cost_m,
       ROUND(scripts / 1e6, 3)                  AS scripts_m,
       ROUND(govt_cost / NULLIF(scripts, 0), 2) AS govt_cost_per_script,
       ROUND(100.0 * cum_share, 1)              AS cum_share_pct
FROM ranked
ORDER BY rn
LIMIT 20;

-- 3b: how many drugs make up 50% / 80% / 90% of government spending
WITH drug AS (
    SELECT i.drug_name, SUM(f.govt_contrib) AS govt_cost
    FROM fact_supply f
    JOIN dim_month m USING (month_key)
    JOIN dim_item  i USING (item_code)
    WHERE m.fin_year = (SELECT MAX(fin_year) FROM v_full_fin_years)
    GROUP BY i.drug_name
),
ranked AS (
    SELECT ROW_NUMBER() OVER (ORDER BY govt_cost DESC, drug_name)                 AS rn,
           SUM(govt_cost) OVER (ORDER BY govt_cost DESC, drug_name
                                ROWS UNBOUNDED PRECEDING) / SUM(govt_cost) OVER () AS cum_share
    FROM drug
)
SELECT COUNT(*)                                AS n_drugs,
       MIN(rn) FILTER (WHERE cum_share >= 0.5) AS drugs_for_50pct,
       MIN(rn) FILTER (WHERE cum_share >= 0.8) AS drugs_for_80pct,
       MIN(rn) FILTER (WHERE cum_share >= 0.9) AS drugs_for_90pct
FROM ranked;
