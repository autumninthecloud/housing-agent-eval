# Narrative Summary — Class C Violation Concentration by Zip Code

**Question:** Which NYC zip codes have the highest concentration of hazardous
(Class C) violations issued since 2025-01-01, and are those concentrations
increasing or decreasing?

**Data:** 1,048,526 HMC violations issued 2025-01-03 through 2026-08-19
(source file is already scoped to NOVIssuedDate ≥ 2025-01-01; 36 rows with no
postcode and 13 rows with malformed postcodes — `2016`, `2018`, `3366`, `418`,
`0` — outside the valid 10001–11697 NYC ZIP range were excluded; see
`data_notes.md` for the full accounting).

## Highest concentration, at meaningful volume

Four zip codes combine a high Class C share **and** a large violation count,
making them the most robust findings: **10030 (35.5%, 9,808 violations)**,
**11210 (35.3%, 9,664)**, **10039 (35.5%, 8,527)**, and **10454 (35.3%,
9,080)**. Each has issued 8,500–9,800 total violations since Jan 2025, so
their ~35% Class C share is not a small-sample artifact.

- 10030, 11210, and 10039 are trending **up**: their average monthly Class C
  count rose roughly **26–29%** comparing 2025 (full year) to Jan–Aug 2026
  (e.g. 10030 went from ~161/mo in 2025 to ~203/mo in 2026).
- 10454 is essentially **flat** (~163/mo in 2025 vs ~162/mo in 2026).
- 10009 (35.5%, 4,231 violations) shows the same upward pattern (+28%
  monthly average) and the most visible volatility in the trend chart, with
  a sharp spike in Nov 2025 and again in Feb 2026.
- 10475 (39.7%, 1,080 violations) has the largest swing of all — its
  Class C rate more than quadrupled in 2026 — but nearly all of that
  increase is concentrated in a single month (Feb 2026, 210 Class C
  violations), so it reads as a spike, not a steady climb; worth flagging
  for follow-up rather than treating as a stable trend.

## Highest percentage, but low volume — treat with caution

Two zip codes rank at the very top of the table by percentage but on very
little data: **10006 (60.0%, only 90 total violations)** and **10005 (36.0%,
only 25 total violations)**. A handful of Class C notices in a low-traffic
zip can swing the percentage sharply (10006's rate is based on just 54 Class
C violations total, most issued in 2026), so these percentages are real but
statistically fragile compared to the high-volume zips above — they should
not be read as "the most dangerous zip codes" on the strength of the
percentage alone.

10038 (44.3%, 424 violations) sits in between: enough volume to be more
reliable than 10006/10005, but its Class C rate is actually **declining**
(-35% monthly average, 2025 to 2026).

## Bottom line

The most defensible answer to "where is Class C concentration highest and
rising": **10030, 11210, 10039, and 10009** — all ~35% Class C, each with
thousands of violations, and each trending upward roughly 26–29% year over
year. 10475 stands out for a sharp recent spike that warrants investigation
rather than a smooth "trend." The two highest-percentage zips overall
(10006, 10005) are driven by small sample sizes and should be weighted
accordingly.

*Figures above are drawn directly from `top10_zip_table.csv` and the two
chart files in this folder; see `data_notes.md` for cleaning and scope
details.*
