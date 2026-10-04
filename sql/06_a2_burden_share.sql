-- 06_a2_burden_share.sql
-- Analysis 2: how is the cost split between government and patients, and how does it change?

-- 2a: monthly patient share, share of scripts priced under the co-payment,
--     and a 12-month rolling patient share that removes the seasonal pattern.
WITH monthly AS (
    SELECT m.month_start,
           SUM(f.total_cost)      AS total_cost,
           SUM(f.patient_contrib) AS patient,
           SUM(f.prescriptions)   AS scripts,
           SUM(f.prescriptions) FILTER (WHERE f.script_type = 'UNDER CO-PAYMENT') AS under_scripts
    FROM fact_supply f
    JOIN dim_month m USING (month_key)
    GROUP BY m.month_start
)
SELECT month_start,
       ROUND(100.0 * patient / NULLIF(total_cost, 0), 2)    AS patient_share_pct,
       ROUND(100.0 * under_scripts / NULLIF(scripts, 0), 2) AS under_copay_script_pct,
       ROUND(100.0 * SUM(patient) OVER w12
             / NULLIF(SUM(total_cost) OVER w12, 0), 2)      AS patient_share_12m_pct,
       COUNT(*) OVER w12                                    AS months_in_window
FROM monthly
WINDOW w12 AS (ORDER BY month_start ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
ORDER BY month_start;

-- 2b: by calendar year and patient group. Calendar year, because co-payments and
--     safety-net thresholds reset on 1 January. Years with months_covered < 12 are partial.
SELECT m.cal_year,
       p.scheme_group,
       COUNT(DISTINCT m.month_key)                                        AS months_covered,
       ROUND(SUM(f.prescriptions) / 1e6, 2)                               AS scripts_m,
       ROUND(SUM(f.patient_contrib) / NULLIF(SUM(f.prescriptions), 0), 2) AS patient_cost_per_script,
       ROUND(100.0 * SUM(f.prescriptions) FILTER (WHERE p.on_safety_net)
             / NULLIF(SUM(f.prescriptions), 0), 1)                        AS safety_net_script_pct,
       ROUND(100.0 * SUM(f.prescriptions) FILTER (WHERE f.script_type = 'UNDER CO-PAYMENT')
             / NULLIF(SUM(f.prescriptions), 0), 1)                        AS under_copay_script_pct
FROM fact_supply f
JOIN dim_month       m USING (month_key)
JOIN dim_patient_cat p USING (patient_cat)
WHERE p.scheme_group IN ('General', 'Concessional')
GROUP BY m.cal_year, p.scheme_group
ORDER BY p.scheme_group, m.cal_year;
