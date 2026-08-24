# Data Handling Notes -- Single-Agent Pipeline

Source: `data/static/Housing_Maintenance_Code_Violations_20260821_vf.csv`

- Rows loaded from source file: 1048575
- Date range in source: 2025-01-03 to 2026-08-19
- Dropped for NOVIssuedDate < 2025-01-01: 0 rows (of 1048575)
- Dropped for missing Postcode: 36 rows
- Dropped for invalid/malformed Postcode (outside 10001-11697): 13 rows; values seen: [0, 418, 2016, 2018, 3366]
- Final cleaned row count: 1048526
- Zip codes represented in cleaned data: 182. 10 of these have fewer than 50 total violations (min 1) and were excluded from the ranking only -- at that low a volume, a single violation shifts the Class C percentage by several points, so ranking on percentage alone would surface small-sample noise ahead of zips with a real, well-supported concentration. Excluded zips: [10004, 10005, 10069, 10105, 10282, 11004, 11005, 11040, 11109, 11430].
- Trend chart excludes 2026-08 as a partial month (source data cuts off mid-month at 2026-08-19); including it would show a misleading drop that's really just an incomplete month.
- Citywide monthly violation totals for Feb-May 2025 run at roughly 10-30% of every other month's volume, followed by a sharp June 2025 spike -- consistent with an incomplete-data/backlog-catchup gap rather than a real activity drop. The trend chart still plots the full series for transparency, but the up/down call in the narrative is computed only over the stable window from 2025-08 onward, to avoid that gap mechanically inflating an 'increasing' conclusion.
- 10006's trend direction call is driven almost entirely by a single high-count month (2026-05) against an otherwise near-zero monthly baseline (90 total violations across the full period) -- treat its trend direction as low-confidence relative to the other top-6 zips.

Trend line and narrative use the top 6 of the 10 ranked zip codes (kept small for chart legibility); the stacked bar chart and table cover all 10.

Note on row count: the source file has exactly 1,048,575 data rows, which coincides with Excel's per-sheet row limit (1,048,576 including header). This raises the possibility the export was silently truncated at some point upstream. The date range present (2025-01-03 to 2026-08-19) does not show an obvious cutoff consistent with truncation (rows are not date-sorted), but this pipeline cannot rule out missing records and treats the file as-is per project instructions. Flagging for awareness, not treated as a defect to fix in this run.
