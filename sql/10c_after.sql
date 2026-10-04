-- 10c_after.sql
-- Query optimisation, step 3: the same queries AFTER the indexes, plus Query B on the materialised view.
--   for i in 1 2 3; do psql pbs -f sql/10c_after.sql | grep "Execution Time"; done
-- Prints 3 lines per run: Query A, Query B, Query B on the materialised view.

-- Query A: single-drug drill-down
EXPLAIN (ANALYZE, BUFFERS)
SELECT m.month_start, SUM(f.prescriptions) AS scripts, SUM(f.govt_contrib) AS govt_cost
FROM fact_supply f
JOIN dim_month m USING (month_key)
WHERE f.item_code IN (SELECT item_code FROM dim_item WHERE drug_name = 'ATORVASTATIN')
GROUP BY m.month_start
ORDER BY m.month_start;

-- Query B: full-table aggregate on the fact table
EXPLAIN (ANALYZE, BUFFERS)
SELECT m.fin_year, i.atc1_code, SUM(f.total_cost) AS total_cost
FROM fact_supply f
JOIN dim_month m USING (month_key)
JOIN dim_item  i USING (item_code)
GROUP BY m.fin_year, i.atc1_code;

-- Query B on the materialised view: same answer from a much smaller table
EXPLAIN (ANALYZE, BUFFERS)
SELECT m.fin_year, v.atc1_code, SUM(v.total_cost) AS total_cost
FROM mv_monthly_drug v
JOIN dim_month m USING (month_key)
GROUP BY m.fin_year, v.atc1_code;
