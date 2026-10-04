-- 04_views.sql
-- Financial years with all 12 months present. Yearly comparisons use only these,
-- otherwise a partial year would look like a collapse in spending.
CREATE OR REPLACE VIEW v_full_fin_years AS
SELECT fin_year
FROM dim_month
GROUP BY fin_year
HAVING COUNT(*) = 12;

SELECT fin_year FROM v_full_fin_years ORDER BY fin_year;
