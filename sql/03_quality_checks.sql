-- 03_quality_checks.sql
-- Nine data-quality checks. Record each result in the README.
-- Run:  psql pbs -f sql/03_quality_checks.sql

\echo '--- Check 1: row counts (staging must equal the converter output; fact must equal staging)'
SELECT (SELECT COUNT(*) FROM stg_pbs_dos) AS staging_rows,
       (SELECT COUNT(*) FROM fact_supply) AS fact_rows;

\echo '--- Check 2: non-numeric values in numeric columns (expect 0)'
SELECT COUNT(*) FILTER (WHERE prescriptions   !~ '^-?[0-9]+$')             AS bad_prescriptions,
       COUNT(*) FILTER (WHERE total_cost      !~ '^-?[0-9]+(\.[0-9]+)?$')  AS bad_total_cost,
       COUNT(*) FILTER (WHERE govt_contrib    !~ '^-?[0-9]+(\.[0-9]+)?$')  AS bad_govt,
       COUNT(*) FILTER (WHERE patient_contrib !~ '^-?[0-9]+(\.[0-9]+)?$')  AS bad_patient
FROM stg_pbs_dos;

\echo '--- Check 3: missing values in key columns (expect 0)'
SELECT COUNT(*) FILTER (WHERE month_of_supply IS NULL OR month_of_supply = '') AS null_month,
       COUNT(*) FILTER (WHERE item_code   IS NULL OR item_code   = '')         AS null_item,
       COUNT(*) FILTER (WHERE atc5_code   IS NULL OR atc5_code   = '')         AS null_atc,
       COUNT(*) FILTER (WHERE patient_cat IS NULL OR patient_cat = '')         AS null_patient_cat
FROM stg_pbs_dos;

\echo '--- Check 4: category values (compare with the explanatory notes)'
SELECT 'patient_cat' AS col, patient_cat AS val, COUNT(*) AS n_rows FROM stg_pbs_dos GROUP BY 2
UNION ALL
SELECT 'drg_typ_ctgry', drg_typ_ctgry, COUNT(*) FROM stg_pbs_dos GROUP BY 2
UNION ALL
SELECT 'script_type', script_type, COUNT(*) FROM stg_pbs_dos GROUP BY 2
ORDER BY 1, 3 DESC;

\echo '--- Check 5: grain uniqueness of the fact table (expect 0 duplicate groups)'
SELECT COUNT(*) AS duplicate_groups
FROM (
    SELECT 1
    FROM fact_supply
    GROUP BY month_key, item_code, patient_cat, drug_type_cat, script_type
    HAVING COUNT(*) > 1
) d;

\echo '--- Check 6: item codes mapped to more than one drug name or ATC code (expect 0)'
SELECT COUNT(*) AS items_with_conflicts
FROM (
    SELECT item_code
    FROM stg_pbs_dos
    GROUP BY item_code
    HAVING COUNT(DISTINCT drug_name) > 1 OR COUNT(DISTINCT atc5_code) > 1
) c;

\echo '--- Check 6b: items in the data that are missing from the PBS item map, and unclassified ATC codes'
SELECT COUNT(*)                                        AS n_items,
       COUNT(*) FILTER (WHERE form_strength IS NULL)   AS not_in_item_map,
       COUNT(*) FILTER (WHERE atc1_code = 'X')         AS unclassified_atc,
       COUNT(*) FILTER (WHERE atc2_code IS NULL)       AS no_atc_level2
FROM dim_item;

\echo '--- Check 7: month continuity (expect 0 missing months)'
SELECT COUNT(*) AS missing_months
FROM generate_series(
         (SELECT MIN(month_start) FROM dim_month)::timestamp,
         (SELECT MAX(month_start) FROM dim_month)::timestamp,
         INTERVAL '1 month') AS g(m)
LEFT JOIN dim_month d ON d.month_start = g.m::date
WHERE d.month_key IS NULL;

\echo '--- Check 8: total cost = patient contribution + government contribution'
SELECT COUNT(*)                                                                        AS n_rows,
       COUNT(*) FILTER (WHERE ABS(total_cost - patient_contrib - govt_contrib) > 0.01) AS n_mismatch,
       SUM(total_cost - patient_contrib - govt_contrib)                                AS total_diff
FROM fact_supply;

\echo '--- Check 9: business rules and anomalies (expect 0)'
SELECT COUNT(*) FILTER (WHERE script_type = 'UNDER CO-PAYMENT' AND govt_contrib <> 0) AS under_copay_with_govt,
       COUNT(*) FILTER (WHERE prescriptions < 0)                                      AS negative_scripts,
       COUNT(*) FILTER (WHERE total_cost < 0)                                         AS negative_cost,
       COUNT(*) FILTER (WHERE prescriptions = 0 AND total_cost <> 0)                  AS zero_scripts_with_cost
FROM fact_supply;

\echo '--- Completeness: the latest 6 months (a sharp drop in the newest month means incomplete data)'
SELECT m.month_start, SUM(f.prescriptions) AS scripts, ROUND(SUM(f.total_cost) / 1e6, 1) AS total_cost_m
FROM fact_supply f
JOIN dim_month m USING (month_key)
GROUP BY m.month_start
ORDER BY m.month_start DESC
LIMIT 6;
