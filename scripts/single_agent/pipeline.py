"""
Single-agent pipeline -- Phase 1 (housing-agent-eval)

Loads data/static/ as-is, cleans it, ranks zip codes by Class C violation
concentration, and produces the four required outputs into
outputs/single_agent/:
  1. top10_zip_table.csv / .md
  2. stacked_bar_by_class.png
  3. trend_class_c_top_zips.png
  4. narrative_summary.md

Also writes data_notes.md documenting every row dropped and every
analytical judgment call, so the final counts and ranking are auditable
rather than a silent filter.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

SRC = "data/static/Housing_Maintenance_Code_Violations_20260821_vf.csv"
OUT = "outputs/single_agent"

MIN_TOTAL_FOR_RANKING = 50  # see data_notes.md for rationale
TREND_TOP_N = 6             # subset of the top-10 table, kept small for line legibility

# ---- palette (dataviz skill reference palette, light-surface) ----
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# Class A/B/C is ordinal severity (C = most hazardous) -> single-hue
# sequential ramp, light to dark.
CLASS_COLORS = {"A": "#86b6ef", "B": "#3987e5", "C": "#184f95"}

# Categorical palette slots, CVD-safe ordering, for the per-zip trend lines.
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

notes = []

# ---------------------------------------------------------------------------
# 1. Load + clean
# ---------------------------------------------------------------------------
df = pd.read_csv(SRC, dtype={"Postcode": "float64"})
notes.append(f"Rows loaded from source file: {len(df)}")

df["NOVIssuedDate"] = pd.to_datetime(df["NOVIssuedDate"], format="%m/%d/%Y")
notes.append(f"Date range in source: {df['NOVIssuedDate'].min().date()} to {df['NOVIssuedDate'].max().date()}")

before = len(df)
df = df[df["NOVIssuedDate"] >= "2025-01-01"].copy()
notes.append(f"Dropped for NOVIssuedDate < 2025-01-01: {before - len(df)} rows (of {before})")

before = len(df)
null_zip = int(df["Postcode"].isnull().sum())
df = df.dropna(subset=["Postcode"]).copy()
notes.append(f"Dropped for missing Postcode: {null_zip} rows")

# Malformed postcodes: valid NYC ZIPs fall in 10001-11697. A handful of
# records carry corrupted values (e.g. 2018, 3366, 418, 0) that are not
# valid ZIPs at all -- drop them rather than let them distort a
# percentage-based ranking (a 1-record zip can hit 100% Class C).
before = len(df)
df["Postcode"] = df["Postcode"].astype(int)
bad_zip_mask = (df["Postcode"] < 10001) | (df["Postcode"] > 11697)
bad_zips = sorted(df.loc[bad_zip_mask, "Postcode"].unique().tolist())
df = df[~bad_zip_mask].copy()
notes.append(f"Dropped for invalid/malformed Postcode (outside 10001-11697): {before - len(df)} rows; values seen: {bad_zips}")

df["Postcode"] = df["Postcode"].astype(str)
notes.append(f"Final cleaned row count: {len(df)}")

assert set(df["Class"].unique()) <= {"A", "B", "C"}, "Unexpected Class values present"
assert df["ViolationID"].duplicated().sum() == 0, "Duplicate ViolationID present"

# ---------------------------------------------------------------------------
# 2. Rank zip codes by Class C percentage
# ---------------------------------------------------------------------------
by_zip_class = df.groupby(["Postcode", "Class"]).size().unstack(fill_value=0)
for c in ["A", "B", "C"]:
    if c not in by_zip_class.columns:
        by_zip_class[c] = 0
by_zip_class["Total"] = by_zip_class[["A", "B", "C"]].sum(axis=1)
by_zip_class["ClassC_Pct"] = (by_zip_class["C"] / by_zip_class["Total"] * 100).round(1)

n_zips_total = len(by_zip_class)
low_volume = by_zip_class[by_zip_class["Total"] < MIN_TOTAL_FOR_RANKING]
notes.append(
    f"Zip codes represented in cleaned data: {n_zips_total}. "
    f"{len(low_volume)} of these have fewer than {MIN_TOTAL_FOR_RANKING} total "
    f"violations (min {int(by_zip_class['Total'].min())}) and were excluded from "
    f"the ranking only -- at that low a volume, a single violation shifts the "
    f"Class C percentage by several points, so ranking on percentage alone would "
    f"surface small-sample noise ahead of zips with a real, well-supported "
    f"concentration. Excluded zips: {sorted(low_volume.index.astype(int).tolist())}."
)

ranked = by_zip_class[by_zip_class["Total"] >= MIN_TOTAL_FOR_RANKING]
top10 = ranked.sort_values("ClassC_Pct", ascending=False).head(10)
top10 = top10.reset_index()[["Postcode", "ClassC_Pct", "C", "Total", "A", "B"]]
top10.columns = ["Postcode", "ClassC_Pct", "ClassC_Count", "TotalViolations", "ClassA_Count", "ClassB_Count"]

top10.to_csv(f"{OUT}/top10_zip_table.csv", index=False)

with open(f"{OUT}/top10_zip_table.md", "w", encoding="utf-8") as f:
    f.write("# Top 10 Zip Codes by Class C Violation Percentage\n\n")
    f.write(
        f"Filtered to NOVIssuedDate >= 2025-01-01. Ranked by Class C violations as a "
        f"percentage of each zip's total violations, among zips with at least "
        f"{MIN_TOTAL_FOR_RANKING} total violations (see data_notes.md).\n\n"
    )
    f.write("| Rank | Postcode | Class C % | Class C Count | Total Violations | Class A | Class B |\n")
    f.write("|---|---|---|---|---|---|---|\n")
    for i, row in top10.iterrows():
        f.write(f"| {i+1} | {row['Postcode']} | {row['ClassC_Pct']:.1f}% | {int(row['ClassC_Count'])} | {int(row['TotalViolations'])} | {int(row['ClassA_Count'])} | {int(row['ClassB_Count'])} |\n")

print("Top 10 table:")
print(top10.to_string(index=False))

# ---------------------------------------------------------------------------
# 3. Stacked bar chart -- violation counts by class, per zip (top 10 zips)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 6.5), facecolor=SURFACE)
ax.set_facecolor(SURFACE)

zips = top10["Postcode"].tolist()
a_vals = top10["ClassA_Count"].values
b_vals = top10["ClassB_Count"].values
c_vals = top10["ClassC_Count"].values

x = range(len(zips))
bar_width = 0.62

ax.bar(x, a_vals, bar_width, label="Class A", color=CLASS_COLORS["A"], edgecolor=SURFACE, linewidth=2)
ax.bar(x, b_vals, bar_width, bottom=a_vals, label="Class B", color=CLASS_COLORS["B"], edgecolor=SURFACE, linewidth=2)
ax.bar(x, c_vals, bar_width, bottom=[a + b for a, b in zip(a_vals, b_vals)], label="Class C", color=CLASS_COLORS["C"], edgecolor=SURFACE, linewidth=2)

ax.set_xticks(list(x))
ax.set_xticklabels(zips, rotation=0, color=INK_SECONDARY, fontsize=10)
ax.set_xlabel("Zip Code (Postcode)", color=INK_SECONDARY, fontsize=11)
ax.set_ylabel("Violation Count", color=INK_SECONDARY, fontsize=11)
ax.set_title("Violation Counts by Class -- Top 10 Zip Codes by Class C %", color=INK_PRIMARY, fontsize=13, fontweight="bold", pad=14)

ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{int(v):,}"))
ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color(BASELINE)
ax.tick_params(colors=INK_MUTED)

ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=INK_SECONDARY)

fig.tight_layout()
fig.savefig(f"{OUT}/stacked_bar_by_class.png", dpi=160, facecolor=SURFACE)
plt.close(fig)

# ---------------------------------------------------------------------------
# 4. Trend line -- Class C violations over time, top zip codes (monthly)
# ---------------------------------------------------------------------------
trend_zips = top10["Postcode"].head(TREND_TOP_N).tolist()
trend_df = df[(df["Class"] == "C") & (df["Postcode"].isin(trend_zips))].copy()
trend_df["Month"] = trend_df["NOVIssuedDate"].dt.to_period("M").dt.to_timestamp()

monthly = trend_df.groupby(["Month", "Postcode"]).size().unstack(fill_value=0)
monthly = monthly.reindex(columns=trend_zips)  # preserve top10 rank order for color assignment
full_months = pd.period_range(df["NOVIssuedDate"].min().to_period("M"), df["NOVIssuedDate"].max().to_period("M"), freq="M").to_timestamp()
monthly = monthly.reindex(full_months, fill_value=0)

# Drop the final partial month from the trend so a low mid-month count
# doesn't read as a fabricated "drop" -- note it instead.
last_full_month = (pd.Timestamp.today().normalize().replace(day=1) - pd.Timedelta(days=1)).to_period("M").to_timestamp()
partial_month_dropped = None
if monthly.index.max() > last_full_month:
    partial_month_dropped = monthly.index.max()
    monthly = monthly[monthly.index <= last_full_month]

fig2, ax2 = plt.subplots(figsize=(11, 6.5), facecolor=SURFACE)
ax2.set_facecolor(SURFACE)

for i, z in enumerate(trend_zips):
    ax2.plot(monthly.index, monthly[z], color=CATEGORICAL[i % len(CATEGORICAL)], linewidth=2, marker="o", markersize=4, label=z)

ax2.set_xlabel("Month (NOVIssuedDate)", color=INK_SECONDARY, fontsize=11)
ax2.set_ylabel("Class C Violation Count", color=INK_SECONDARY, fontsize=11)
ax2.set_title(f"Class C Violation Trend -- Top {TREND_TOP_N} Zip Codes (by Class C %)", color=INK_PRIMARY, fontsize=13, fontweight="bold", pad=14)

ax2.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
ax2.set_axisbelow(True)
for spine in ["top", "right"]:
    ax2.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax2.spines[spine].set_color(BASELINE)
ax2.tick_params(colors=INK_MUTED)
fig2.autofmt_xdate(rotation=45)

ax2.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=INK_SECONDARY, ncol=2, title="Postcode", title_fontsize=10)

fig2.tight_layout()
fig2.savefig(f"{OUT}/trend_class_c_top_zips.png", dpi=160, facecolor=SURFACE)
plt.close(fig2)

if partial_month_dropped is not None:
    notes.append(
        f"Trend chart excludes {partial_month_dropped.strftime('%Y-%m')} as a partial "
        f"month (source data cuts off mid-month at {df['NOVIssuedDate'].max().date()}); "
        f"including it would show a misleading drop that's really just an incomplete month."
    )

# ---------------------------------------------------------------------------
# 5. Trend direction, computed on a data-quality-adjusted window
# ---------------------------------------------------------------------------
# Citywide monthly totals (all zips, all classes) show Feb-May 2025 running at
# roughly 10-30% of every other month's volume, then a sharp June 2025 spike --
# a strong signature of an incomplete-data / backlog-catchup gap, not a real
# drop in violation activity. If left in, a naive first-half-vs-second-half
# split would read almost every zip as "trending up" simply because the
# artificially low Feb-May 2025 months anchor the first half -- an artifact of
# data completeness, not a real trend. The chart below still plots the full
# series (so this pattern is visible and auditable), but the up/down call used
# in the narrative is computed only over the stable window from 2025-08
# onward, split at its own midpoint.
STABLE_WINDOW_START = pd.Timestamp("2025-08-01")
stable = monthly[monthly.index >= STABLE_WINDOW_START]
notes.append(
    f"Citywide monthly violation totals for Feb-May 2025 run at roughly "
    f"10-30% of every other month's volume, followed by a sharp June 2025 "
    f"spike -- consistent with an incomplete-data/backlog-catchup gap rather "
    f"than a real activity drop. The trend chart still plots the full series "
    f"for transparency, but the up/down call in the narrative is computed only "
    f"over the stable window from {STABLE_WINDOW_START.strftime('%Y-%m')} onward, "
    f"to avoid that gap mechanically inflating an 'increasing' conclusion."
)

midpoint = stable.index[len(stable.index) // 2]
first_half = stable[stable.index < midpoint].sum()
second_half = stable[stable.index >= midpoint].sum()
direction = {}
for z in trend_zips:
    if second_half[z] > first_half[z]:
        direction[z] = "up"
    elif second_half[z] < first_half[z]:
        direction[z] = "down"
    else:
        direction[z] = "flat"
n_up = sum(1 for d in direction.values() if d == "up")
n_down = sum(1 for d in direction.values() if d == "down")

# 10006 has very low overall volume (90 total violations across the full
# period), so its monthly Class C counts are mostly 0-2 with one 48-count
# month (2026-05) that single-handedly decides its direction call -- flag
# this rather than presenting it with the same confidence as the
# higher-volume zips.
if by_zip_class.loc["10006", "Total"] < 200 and "10006" in direction:
    notes.append(
        "10006's trend direction call is driven almost entirely by a single "
        "high-count month (2026-05) against an otherwise near-zero monthly "
        "baseline (90 total violations across the full period) -- treat its "
        "trend direction as low-confidence relative to the other top-6 zips."
    )

# ---------------------------------------------------------------------------
# 6. Data notes (explain row counts / cleaning + analytical decisions)
# ---------------------------------------------------------------------------
with open(f"{OUT}/data_notes.md", "w", encoding="utf-8") as f:
    f.write("# Data Handling Notes -- Single-Agent Pipeline\n\n")
    f.write(f"Source: `{SRC}`\n\n")
    for n in notes:
        f.write(f"- {n}\n")
    f.write(
        f"\nTrend line and narrative use the top {TREND_TOP_N} of the 10 ranked zip codes "
        f"(kept small for chart legibility); the stacked bar chart and table cover all 10.\n"
    )
    f.write(
        f"\nNote on row count: the source file has exactly 1,048,575 data rows, "
        f"which coincides with Excel's per-sheet row limit (1,048,576 including "
        f"header). This raises the possibility the export was silently truncated "
        f"at some point upstream. The date range present (2025-01-03 to "
        f"{df['NOVIssuedDate'].max().date()}) does not show an obvious cutoff "
        f"consistent with truncation (rows are not date-sorted), but this "
        f"pipeline cannot rule out missing records and treats the file as-is per "
        f"project instructions. Flagging for awareness, not treated as a defect "
        f"to fix in this run.\n"
    )

# ---------------------------------------------------------------------------
# 7. Narrative summary
# ---------------------------------------------------------------------------
top_row = top10.iloc[0]
second_row = top10.iloc[1]
third_row = top10.iloc[2]
up_zips = [z for z, d in direction.items() if d == "up"]
down_zips = [z for z, d in direction.items() if d == "down"]

with open(f"{OUT}/narrative_summary.md", "w", encoding="utf-8") as f:
    f.write("# Narrative Summary -- Class C Violation Concentration by Zip Code\n\n")
    f.write(
        f"Among NYC zip codes with at least {MIN_TOTAL_FOR_RANKING} Housing "
        f"Maintenance Code violations issued since 2025-01-01, **{top_row['Postcode']}** "
        f"has the highest concentration of hazardous Class C violations, at "
        f"**{top_row['ClassC_Pct']:.1f}%** of its {int(top_row['TotalViolations']):,} "
        f"total violations ({int(top_row['ClassC_Count']):,} Class C). "
        f"**{second_row['Postcode']}** ({second_row['ClassC_Pct']:.1f}%) and "
        f"**{third_row['Postcode']}** ({third_row['ClassC_Pct']:.1f}%) follow. "
        f"The remaining seven zips in the top 10 cluster closely together, in the "
        f"{top10['ClassC_Pct'].iloc[3:].min():.1f}%-{top10['ClassC_Pct'].iloc[3:].max():.1f}% range -- "
        f"a much smaller spread than the gap separating the top two from the rest.\n\n"
    )
    f.write(
        f"Looking at Class C counts over time for the top {TREND_TOP_N} zips, using the "
        f"stable {STABLE_WINDOW_START.strftime('%b %Y')}-onward window (see caveat below): "
        f"**{n_up} of {TREND_TOP_N} are trending up** ({', '.join(up_zips) if up_zips else 'none'}) "
        f"and **{n_down} are trending down** ({', '.join(down_zips) if down_zips else 'none'}). "
        f"This is a mixed picture rather than a uniform citywide increase or decrease -- "
        f"concentration and trend direction should be read as two separate signals, not "
        f"assumed to move together.\n\n"
    )
    f.write(
        f"**Caveats:**\n"
        f"- The ranking above excludes {len(low_volume)} zip codes with fewer than "
        f"{MIN_TOTAL_FOR_RANKING} total violations, since a percentage computed on a handful "
        f"of records is not a reliable concentration estimate.\n"
        f"- Citywide violation counts for Feb-May 2025 run far below every other month, "
        f"then spike in June 2025 -- most likely an incomplete-data/backlog-catchup gap "
        f"rather than a real drop in violations. The trend chart plots the full series "
        f"(the dip is visible), but the up/down calls above use only the "
        f"{STABLE_WINDOW_START.strftime('%b %Y')}-onward window so that gap doesn't "
        f"mechanically read as an increase.\n"
        f"- 10006's trend call is low-confidence: it has only 90 total violations "
        f"over the full period, and its 'up' direction is driven almost entirely by a "
        f"single high-count month rather than a sustained pattern.\n\n"
        f"Full detail behind every number here is in `top10_zip_table.csv`.\n"
    )

print("\nDone. Wrote outputs to", OUT)
print("Trend zips used:", trend_zips)
print("Trend direction (first half vs second half):", direction)
