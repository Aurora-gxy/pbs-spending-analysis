-- 10a_baseline.sql
-- Query optimisation, step 1: timings BEFORE any primary key or index exists.
-- Run 3 times and take the median "Execution Time":
--   for i in 1 2 3; do psql pbs -f sql/10a_baseline.sql | grep "Execution Time"; done

-- Query A: single-drug drill-down (selective: reads a small share of the rows)
EXPLAIN (ANALYZE, BUFFERS)
SELECT m.month_start, SUM(f.prescriptions) AS scripts, SUM(f.govt_contrib) AS govt_cost
FROM fact_supply f
JOIN dim_month m USING (month_key)
WHERE f.item_code IN (SELECT item_code FROM dim_item WHERE drug_name = 'ATORVASTATIN')
GROUP BY m.month_start
ORDER BY m.month_start;

-- Query B: full-table aggregate (reads almost every row)
EXPLAIN (ANALYZE, BUFFERS)
SELECT m.fin_year, i.atc1_code, SUM(f.total_cost) AS total_cost
FROM fact_supply f
JOIN dim_month m USING (month_key)
JOIN dim_item  i USING (item_code)
GROUP BY m.fin_year, i.atc1_code;
