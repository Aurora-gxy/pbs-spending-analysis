-- 10b_indexes.sql
-- Query optimisation, step 2: primary key, indexes and a pre-aggregated materialised view.
-- Run once:  psql pbs -f sql/10b_indexes.sql

-- Primary key on the grain (safe because quality check 5 found no duplicates).
ALTER TABLE fact_supply
    ADD PRIMARY KEY (month_key, item_code, patient_cat, drug_type_cat, script_type);

-- Supports drill-down by item, then by month.
CREATE INDEX idx_fact_item_month ON fact_supply (item_code, month_key);

-- Supports looking up item codes by drug name.
CREATE INDEX idx_item_drug_name ON dim_item (drug_name);

-- Full-table aggregates read almost every row, so an index cannot help them.
-- For those, pre-aggregate once: month x drug x ATC level 1 x patient group.
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_drug;
CREATE MATERIALIZED VIEW mv_monthly_drug AS
SELECT f.month_key,
       i.drug_name,
       i.atc1_code,
       p.scheme_group,
       SUM(f.prescriptions)   AS scripts,
       SUM(f.total_cost)      AS total_cost,
       SUM(f.govt_contrib)    AS govt_cost,
       SUM(f.patient_contrib) AS patient_cost
FROM fact_supply f
JOIN dim_item        i USING (item_code)
JOIN dim_patient_cat p USING (patient_cat)
GROUP BY f.month_key, i.drug_name, i.atc1_code, p.scheme_group;

CREATE INDEX idx_mv_drug  ON mv_monthly_drug (drug_name, month_key);
CREATE INDEX idx_mv_month ON mv_monthly_drug (month_key);

ANALYZE fact_supply;
ANALYZE dim_item;
ANALYZE mv_monthly_drug;

SELECT (SELECT COUNT(*) FROM fact_supply)     AS fact_rows,
       (SELECT COUNT(*) FROM mv_monthly_drug) AS mv_rows;
