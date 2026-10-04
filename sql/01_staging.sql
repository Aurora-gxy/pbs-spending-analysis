-- 01_staging.sql
-- Staging tables: every column is text so the load never fails on a stray value.
-- Type conversion and checks happen in the next steps.
-- Run from the project folder:  psql pbs -f sql/01_staging.sql

DROP TABLE IF EXISTS stg_pbs_dos;
CREATE TABLE stg_pbs_dos (
    month_of_supply     text,
    item_code           text,
    atc5_code           text,
    drug_name           text,
    patient_cat         text,
    drg_typ_ctgry       text,
    script_type         text,
    prescriptions       text,
    patient_contrib     text,
    govt_contrib        text,
    retail_markup       text,
    total_cost          text,
    patient_net_contrib text
);

DROP TABLE IF EXISTS stg_item_map;
CREATE TABLE stg_item_map (
    item_code     text,
    drug_name     text,
    form_strength text,
    atc5_code     text
);

\copy stg_pbs_dos  FROM 'data/pbs_dos.csv'               WITH (FORMAT csv, HEADER true)
\copy stg_item_map FROM 'data/item_map.csv'  WITH (FORMAT csv, HEADER true)

SELECT 'stg_pbs_dos' AS table_name, COUNT(*) AS n_rows FROM stg_pbs_dos
UNION ALL
SELECT 'stg_item_map', COUNT(*) FROM stg_item_map;
