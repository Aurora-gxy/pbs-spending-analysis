-- 02_schema.sql
-- Star schema: 1 fact table (fact_supply) + 4 dimension tables.
-- Run:  psql pbs -f sql/02_schema.sql

DROP TABLE IF EXISTS fact_supply;
DROP TABLE IF EXISTS dim_item;
DROP TABLE IF EXISTS dim_atc1;
DROP TABLE IF EXISTS dim_patient_cat;
DROP TABLE IF EXISTS dim_month CASCADE;

-- 1) Month dimension.
--    Australian financial year runs July-June; FY is named by its ending year,
--    so 2023-07 .. 2024-06 is fin_year 2024 (month + 6 months, then take the year).
CREATE TABLE dim_month AS
SELECT month_key,
       month_start,
       EXTRACT(YEAR  FROM month_start)::int                       AS cal_year,
       EXTRACT(MONTH FROM month_start)::int                       AS cal_month,
       EXTRACT(YEAR  FROM month_start + INTERVAL '6 months')::int AS fin_year
FROM (
    SELECT DISTINCT
           month_of_supply::int AS month_key,
           make_date(month_of_supply::int / 100, month_of_supply::int % 100, 1) AS month_start
    FROM stg_pbs_dos
) m;
ALTER TABLE dim_month ADD PRIMARY KEY (month_key);

-- 2) ATC level 1: the 14 WHO anatomical main groups, plus X for codes that cannot be classified
--    (the data uses 'Z' and '99999Z' for missing / unlisted items).
CREATE TABLE dim_atc1 (
    atc1_code    text PRIMARY KEY,
    atc1_name    text NOT NULL,
    atc1_name_cn text NOT NULL
);
INSERT INTO dim_atc1 VALUES
 ('A', 'Alimentary tract and metabolism',                     '消化道与代谢'),
 ('B', 'Blood and blood forming organs',                      '血液与造血器官'),
 ('C', 'Cardiovascular system',                               '心血管系统'),
 ('D', 'Dermatologicals',                                     '皮肤科用药'),
 ('G', 'Genito-urinary system and sex hormones',              '泌尿生殖系统与性激素'),
 ('H', 'Systemic hormonal preparations',                      '全身用激素制剂'),
 ('J', 'Antiinfectives for systemic use',                     '全身用抗感染药'),
 ('L', 'Antineoplastic and immunomodulating agents',          '抗肿瘤药与免疫调节剂'),
 ('M', 'Musculo-skeletal system',                             '肌肉骨骼系统'),
 ('N', 'Nervous system',                                      '神经系统'),
 ('P', 'Antiparasitic products, insecticides and repellents', '抗寄生虫药'),
 ('R', 'Respiratory system',                                  '呼吸系统'),
 ('S', 'Sensory organs',                                      '感觉器官'),
 ('V', 'Various',                                             '其他'),
 ('X', 'Unclassified',                                        '无法分类');

-- 3) Item dimension: one row per PBS item code.
--    Name and ATC code come from the latest month the item appears in;
--    form/strength comes from the PBS item map file.
--    ATC codes in the data have different lengths (1, 4, 5 or 7 characters),
--    so level 2 is only filled when the code is at least 3 characters long.
CREATE TABLE dim_item AS
SELECT s.item_code,
       s.drug_name,
       mp.form_strength,
       s.atc5_code,
       CASE WHEN a.atc1_code IS NOT NULL AND LENGTH(s.atc5_code) >= 3
            THEN LEFT(s.atc5_code, 3) END  AS atc2_code,
       COALESCE(a.atc1_code, 'X')          AS atc1_code
FROM (
    SELECT DISTINCT ON (item_code) item_code, drug_name, atc5_code
    FROM stg_pbs_dos
    ORDER BY item_code, month_of_supply DESC
) s
LEFT JOIN dim_atc1     a  ON a.atc1_code = LEFT(s.atc5_code, 1) AND a.atc1_code <> 'X'
LEFT JOIN stg_item_map mp ON mp.item_code = s.item_code;
ALTER TABLE dim_item ADD PRIMARY KEY (item_code);
ALTER TABLE dim_item ADD FOREIGN KEY (atc1_code) REFERENCES dim_atc1 (atc1_code);

-- 4) Patient category dimension (codes from the PBS explanatory notes).
CREATE TABLE dim_patient_cat (
    patient_cat   text PRIMARY KEY,
    description   text NOT NULL,
    scheme_group  text NOT NULL,   -- General / Concessional / RPBS / Other
    on_safety_net boolean          -- NULL = not applicable
);
INSERT INTO dim_patient_cat VALUES
 ('G2', 'General non-safety net',      'General',      false),
 ('G1', 'General safety net',          'General',      true),
 ('C1', 'Concessional non-safety net', 'Concessional', false),
 ('C0', 'Concessional safety net',     'Concessional', true),
 ('R1', 'RPBS non-safety net',         'RPBS',         false),
 ('R0', 'RPBS safety net',             'RPBS',         true),
 ('DB', 'Prescriber Bag',              'Other',        NULL),
 ('UK', 'Undetermined',                'Other',        NULL);

-- 5) Fact table. Grain: month x item x patient category x program x script type.
--    Money is numeric, not float, so sums are exact.
--    No primary key or index yet: the baseline timings in 10_optimisation.sql come first.
CREATE TABLE fact_supply (
    month_key           int    NOT NULL REFERENCES dim_month (month_key),
    item_code           text   NOT NULL REFERENCES dim_item (item_code),
    patient_cat         text   NOT NULL REFERENCES dim_patient_cat (patient_cat),
    drug_type_cat       text   NOT NULL,
    script_type         text   NOT NULL,
    prescriptions       bigint NOT NULL,
    patient_contrib     numeric(14,2) NOT NULL,
    govt_contrib        numeric(14,2) NOT NULL,
    total_cost          numeric(14,2) NOT NULL,
    retail_markup       numeric(14,2),
    patient_net_contrib numeric(14,2)
);

INSERT INTO fact_supply
SELECT month_of_supply::int,
       item_code,
       patient_cat,
       drg_typ_ctgry,
       script_type,
       prescriptions::bigint,
       patient_contrib::numeric,
       govt_contrib::numeric,
       total_cost::numeric,
       NULLIF(retail_markup, '')::numeric,
       NULLIF(patient_net_contrib, '')::numeric
FROM stg_pbs_dos;

ANALYZE;

SELECT 'fact_supply' AS table_name, COUNT(*) AS n_rows FROM fact_supply
UNION ALL SELECT 'dim_month', COUNT(*) FROM dim_month
UNION ALL SELECT 'dim_item', COUNT(*) FROM dim_item
UNION ALL SELECT 'dim_atc1', COUNT(*) FROM dim_atc1
UNION ALL SELECT 'dim_patient_cat', COUNT(*) FROM dim_patient_cat;
