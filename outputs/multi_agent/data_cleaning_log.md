# Data Cleaning Log - Phase 1 Multi-Agent (data-cleaner)

Source file: `data/static/Housing_Maintenance_Code_Violations_20260821_vf.csv`
Schema confirmed: `ViolationID, Borough, Postcode, Class, NOVIssuedDate` (exact match, no mismatch)

## Row-count summary

| Stage | Row count |
|---|---|
| Raw rows loaded | 1048575 |
| After dropping rows with missing/unparseable required fields (Postcode, Class, NOVIssuedDate) | 1048539 |
| After date filter (NOVIssuedDate >= 2025-01-01) | 1048539 |
| After validity filter (Class normalized to A/B/C; Postcode normalized to 5-digit) | 1048539 |
| **Final rows written to cleaned_violations.csv** | **1048539** |

## Dropped-row breakdown (fully explains raw_count -> final_count)

| Reason | Count |
|---|---|
| Missing/blank Postcode | 36 |
| Missing/blank Class (and Postcode present) | 0 |
| Missing/unparseable NOVIssuedDate (and Postcode, Class present) | 0 |
| Subtotal: required-field missing/unparseable | 36 |
| NOVIssuedDate present/valid but before 2025-01-01 | 0 |
| Postcode present but could not normalize to 5 digits | 0 |
| Class present but not A/B/C after normalization (and Postcode valid) | 0 |
| **Total dropped** | **36** |

Arithmetic check: 1048575 (raw) - 36 (total dropped) = 1048539 = 1048539 (final rows written). Confirmed match.

## Normalization notes

- `Postcode`: cast to string, stripped of any trailing `.0` float artifacts and non-digit characters, then zero-padded to 5 digits. Values that yielded zero digits or more than 5 digits after stripping (none observed beyond truncation-safe cases) were treated per the logic above; any that still didn't resolve to exactly 5 digits were dropped as invalid.
- `Class`: stripped, uppercased, and required to be exactly one of `A`, `B`, `C`. Anything else (blank, multi-character, other letters/codes) was dropped and counted above.
- `NOVIssuedDate`: parsed strictly as `M/D/YYYY` (matching the raw file's observed format), with a generic-parse fallback for any value that didn't match; values that still failed to parse were dropped and counted above. Output dates are written as ISO `YYYY-MM-DD`. `CurrentStatusDate` or any other date-like column was not present/used - only `NOVIssuedDate` was referenced per spec.

## Scope notes

- No ranking, percentage, or aggregation math performed here (reserved for the analyst subagent).
- No chart logic referenced here (reserved for the visualizer subagent).
- Source file was loaded as-is and not modified, re-fetched, or re-derived.
