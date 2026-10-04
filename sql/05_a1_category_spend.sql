-- 05_a1_category_spend.sql
-- Analysis 1: which drug categories cost the most, and which grow fastest?
-- Spending by financial year and ATC level 1, with share of the year, year-on-year growth and rank.
WITH yearly AS (
    SELECT m.fin_year,
           a.atc1_code,
           a.atc1_name,
           SUM(f.total_cost)    AS total_cost,
           SUM(f.govt_contrib)  AS govt_cost,
           SUM(f.prescriptions) AS scripts
    FROM fact_supply f
    JOIN dim_month m USING (month_key)
    JOIN dim_item  i USING (item_code)
    JOIN dim_atc1  a USING (atc1_code)
    WHERE m.fin_year IN (SELECT fin_year FROM v_full_fin_years)
    GROUP BY m.fin_year, a.atc1_code, a.atc1_name
)
SELECT fin_year,
       atc1_code,
       atc1_name,
       ROUND(total_cost / 1e6, 1)                                             AS total_cost_m,
       ROUND(govt_cost / 1e6, 1)                                              AS govt_cost_m,
       ROUND(scripts / 1e6, 2)                                                AS scripts_m,
       ROUND(100.0 * total_cost / SUM(total_cost) OVER (PARTITION BY fin_year), 1) AS share_pct,
       ROUND(100.0 * (total_cost / NULLIF(LAG(total_cost) OVER w, 0) - 1), 1) AS yoy_pct,
       RANK() OVER (PARTITION BY fin_year ORDER BY total_cost DESC)           AS rank_in_year
FROM yearly
WINDOW w AS (PARTITION BY atc1_code ORDER BY fin_year)
ORDER BY fin_year, total_cost DESC;
