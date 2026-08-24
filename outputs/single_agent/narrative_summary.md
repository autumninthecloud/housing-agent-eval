# Narrative Summary -- Class C Violation Concentration by Zip Code

Among NYC zip codes with at least 50 Housing Maintenance Code violations issued since 2025-01-01, **10006** has the highest concentration of hazardous Class C violations, at **60.0%** of its 90 total violations (54 Class C). **10038** (44.3%) and **10475** (39.7%) follow. The remaining seven zips in the top 10 cluster closely together, in the 35.0%-35.6% range -- a much smaller spread than the gap separating the top two from the rest.

Looking at Class C counts over time for the top 6 zips, using the stable Aug 2025-onward window (see caveat below): **3 of 6 are trending up** (10006, 10475, 10010) and **3 are trending down** (10038, 10009, 10039). This is a mixed picture rather than a uniform citywide increase or decrease -- concentration and trend direction should be read as two separate signals, not assumed to move together.

**Caveats:**
- The ranking above excludes 10 zip codes with fewer than 50 total violations, since a percentage computed on a handful of records is not a reliable concentration estimate.
- Citywide violation counts for Feb-May 2025 run far below every other month, then spike in June 2025 -- most likely an incomplete-data/backlog-catchup gap rather than a real drop in violations. The trend chart plots the full series (the dip is visible), but the up/down calls above use only the Aug 2025-onward window so that gap doesn't mechanically read as an increase.
- 10006's trend call is low-confidence: it has only 90 total violations over the full period, and its 'up' direction is driven almost entirely by a single high-count month rather than a sustained pattern.

Full detail behind every number here is in `top10_zip_table.csv`.
