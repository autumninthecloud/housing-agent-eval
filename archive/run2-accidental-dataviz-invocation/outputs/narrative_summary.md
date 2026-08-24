# Narrative Summary — Class C Violation Concentration by Zip Code

**Question:** Which NYC zip codes have the highest concentration of Class C (hazardous) violations issued since 2025-01-01, and is that concentration increasing or decreasing?

## Findings

Of 1,048,526 violations issued since 2025-01-01 across 182 zip codes, zip code **10006** has the highest concentration of Class C violations at **60.0%** (54 of 90 total violations in that zip). The next two highest are 10038 (44.34%) and 10475 (39.72%).

Across all 10 top-ranked zip codes, Class C concentration ranges from 35.25% to 60.0%, compared to a citywide Class C share of 30.32% — meaning these zip codes carry a disproportionately hazardous violation mix relative to the city as a whole.

## Trend

The trend line covers the top 5 of these 10 zip codes by Class C %, restricted to zips with at least 1,000 total violations over the period so the monthly counts are not dominated by small-sample noise (this excludes 10006, 10038, 10005 — each under 1,000 total violations across 20 months). The full 10 are in the table and bar chart above. Combined Class C violation counts across the 5 trended zip codes rose from 2025-01 through a peak of 907 in 2026-02, then eased off toward 2026-08 (average of the first 3 months: 208/month vs. the last 3 months: 340/month, a net +63.5% change over the full period). So the net direction over the whole window is **up**, but the most recent months are trending down from that peak rather than continuing to climb. Note the final month (2026-08) is partial, since data collection cuts off mid-month. See `classC_trend_line.png` for the month-by-month breakdown per zip code.

## Sources

- Top-10 table: `top10_zip_classC.csv`
- Stacked bar chart: `stacked_bar_by_zip.png`
- Trend line: `classC_trend_line.png`
- Data cleaning log: `data_cleaning_log.md`
