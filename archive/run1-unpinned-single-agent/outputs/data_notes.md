# Data Handling Notes - Single-Agent Pipeline

Source: `data/static/Housing_Maintenance_Code_Violations_20260821_vf.csv`

- Rows loaded from source file: 1048575
- Date range in source: 2025-01-03 to 2026-08-19
- Dropped for NOVIssuedDate < 2025-01-01: 0 rows (of 1048575)
- Dropped for missing Postcode: 36 rows
- Dropped for invalid/malformed Postcode (outside 10001-11697): 13 rows; values seen: [0, 418, 2016, 2018, 3366]
- Final cleaned row count: 1048526

Trend line and narrative use the top 6 of the 10 ranked zip codes (kept to 6 lines for chart legibility, per the dataviz skill's categorical-color guidance); the stacked bar chart and table cover all 10.
