"""
Single-agent Phase 1 pipeline: NYC Housing Maintenance Code Violations.

One sequential script performs all steps a single agent would do itself:
load -> clean -> rank -> chart -> narrate. Contrast with the multi-agent
pipeline, where these steps are split across specialist subagents.

Question: which zip codes have the highest concentration of Class C
(hazardous) violations issued since 2025-01-01, and is that concentration
trending up or down over the period?
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATA_PATH = "data/static/Housing_Maintenance_Code_Violations_20260821_vf.csv"
OUT_DIR = "outputs/single_agent"
CUTOFF_DATE = "2025-01-01"
TOP_N = 10
TREND_N = 5  # trend line uses the top 5 of the top 10 -- see chart section for why
MIN_TOTAL_FOR_TREND = 1000  # exclude zips too small-sample for a legible monthly trend

# Validated palette (references/palette.md) -- chart chrome
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# Ordinal ramp (single hue, light->dark) for Class A/B/C severity
CLASS_COLORS = {"A": "#86b6ef", "B": "#3987e5", "C": "#104281"}

# Categorical slots 1-5, fixed order (validated: adjacent CVD ok >=8, normal-vision >=15)
ZIP_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, labelcolor=INK_SECONDARY)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    ax.title.set_color(INK_PRIMARY)
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

# ---------------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------------
raw = pd.read_csv(DATA_PATH, dtype=str)
raw_count = len(raw)

# ---------------------------------------------------------------------------
# 2. Clean
# ---------------------------------------------------------------------------
df = raw.copy()

df["NOVIssuedDate"] = pd.to_datetime(df["NOVIssuedDate"], format="%m/%d/%Y", errors="coerce")
bad_dates = df["NOVIssuedDate"].isna().sum()
df = df.dropna(subset=["NOVIssuedDate"])

before_cutoff = (df["NOVIssuedDate"] < CUTOFF_DATE).sum()
df = df[df["NOVIssuedDate"] >= CUTOFF_DATE]

missing_zip = df["Postcode"].isna().sum()
df = df.dropna(subset=["Postcode"])

malformed_zip = (df["Postcode"].str.len() != 5).sum()
df = df[df["Postcode"].str.len() == 5]

bad_class = (~df["Class"].isin(["A", "B", "C"])).sum()
df = df[df["Class"].isin(["A", "B", "C"])]

clean_count = len(df)

cleaning_log = f"""# Data cleaning log

- Raw rows loaded: {raw_count:,}
- Rows dropped, unparseable NOVIssuedDate: {bad_dates:,}
- Rows dropped, NOVIssuedDate before {CUTOFF_DATE}: {before_cutoff:,}
- Rows dropped, missing Postcode: {missing_zip:,}
- Rows dropped, malformed Postcode (not 5 digits): {malformed_zip:,}
- Rows dropped, Class not in A/B/C: {bad_class:,}
- Rows in final analysis: {clean_count:,}
- Distinct zip codes in final analysis: {df['Postcode'].nunique():,}
"""

with open(f"{OUT_DIR}/data_cleaning_log.md", "w", encoding="utf-8") as f:
    f.write(cleaning_log)

# ---------------------------------------------------------------------------
# 3. Rank zip codes by Class C concentration
# ---------------------------------------------------------------------------
by_zip_class = df.groupby(["Postcode", "Class"]).size().unstack(fill_value=0)
for c in ["A", "B", "C"]:
    if c not in by_zip_class.columns:
        by_zip_class[c] = 0
by_zip_class["Total"] = by_zip_class[["A", "B", "C"]].sum(axis=1)
by_zip_class["ClassC_Pct"] = (by_zip_class["C"] / by_zip_class["Total"] * 100).round(2)

top10 = by_zip_class.sort_values("ClassC_Pct", ascending=False).head(TOP_N)
top10_display = top10.reset_index()[["Postcode", "ClassC_Pct", "C", "Total", "A", "B"]]
top10_display.columns = ["Postcode", "ClassC_Pct", "ClassC_Count", "TotalViolations", "ClassA_Count", "ClassB_Count"]
top10_display.to_csv(f"{OUT_DIR}/top10_zip_classC.csv", index=False)

# ---------------------------------------------------------------------------
# 4. Stacked bar chart: violation counts by class, per top-10 zip
#
# Class A/B/C is an ordinal severity scale (A least hazardous -> C most), so
# it's encoded as a single-hue ramp (light->dark), not distinct categorical
# hues -- there's no "identity" here, only "more/less severe".
# ---------------------------------------------------------------------------
zip_order = top10_display.sort_values("ClassC_Pct", ascending=False)["Postcode"]
bar_data = top10.loc[zip_order, ["A", "B", "C"]]

fig, ax = plt.subplots(figsize=(11, 6))
bottom = pd.Series(0, index=bar_data.index)
for c in ["A", "B", "C"]:
    ax.bar(
        bar_data.index.astype(str), bar_data[c], bottom=bottom, label=f"Class {c}",
        color=CLASS_COLORS[c], width=0.7, edgecolor=SURFACE, linewidth=1.5, zorder=3,
    )
    bottom = bottom + bar_data[c]

style_axes(ax)
ax.set_xlabel("Zip Code")
ax.set_ylabel("Violation Count")
ax.set_title("Violation Counts by Class — Top 10 Zip Codes by Class C Concentration\n(NYC HMC Violations, NOVIssuedDate >= 2025-01-01)")
legend = ax.legend(title="Class", frameon=False, labelcolor=INK_SECONDARY)
legend.get_title().set_color(INK_SECONDARY)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/stacked_bar_by_zip.png", dpi=150, facecolor=SURFACE)
plt.close(fig)

# ---------------------------------------------------------------------------
# 5. Trend line: Class C violations over time, top 5 of the top-10 zips
#
# Zip code here is a categorical/identity encoding (line = "which zip"), and
# the validated categorical palette is only guaranteed CVD-safe up to its
# passing slot count -- a 10th distinct hue is not a supported categorical
# step. Trend line covers a subset of the same top-10 ranked table for
# legibility and color-safety; the full top 10 is in the table and bar chart.
#
# Several of the top-10-by-percentage zips (e.g. 10006, 10005) have well
# under 100 total violations over the 20-month window -- a monthly trend for
# those is mostly zeros with one noisy spike, not a readable trend. Those are
# excluded here by a minimum-volume floor; the ranking table above still
# reports them, since the ranking question and the trend question are
# answering different things (concentration vs. a legible time series).
eligible_for_trend = top10_display[top10_display["TotalViolations"] >= MIN_TOTAL_FOR_TREND]
trend_zips = list(eligible_for_trend.sort_values("ClassC_Pct", ascending=False)["Postcode"].head(TREND_N))
classC = df[(df["Class"] == "C") & (df["Postcode"].isin(trend_zips))].copy()
classC["Month"] = classC["NOVIssuedDate"].dt.to_period("M").dt.to_timestamp()

monthly = classC.groupby(["Month", "Postcode"]).size().unstack(fill_value=0)
monthly = monthly.reindex(columns=trend_zips)

fig, ax = plt.subplots(figsize=(11, 6.5))
for zip_code, color in zip(monthly.columns, ZIP_COLORS):
    ax.plot(
        monthly.index, monthly[zip_code], marker="o", markersize=6,
        linewidth=2, color=color, label=str(zip_code), zorder=3,
        markeredgecolor=SURFACE, markeredgewidth=1,
    )

# Direct end-of-line labels: relief for the two validated slots that sit
# below 3:1 contrast on the light surface (yellow, magenta), and it
# reinforces identity for everyone else too. End values can land close
# together (e.g. two series both near y=65), so enforce a minimum vertical
# gap between label positions rather than placing them at the raw data y.
end_values = monthly.iloc[-1]
y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
min_gap = 0.045 * y_range
ordered = end_values.sort_values().index.tolist()
label_y = {}
prev_y = None
for zip_code in ordered:
    y = end_values[zip_code]
    if prev_y is not None and y - prev_y < min_gap:
        y = prev_y + min_gap
    label_y[zip_code] = y
    prev_y = y

for zip_code, color in zip(monthly.columns, ZIP_COLORS):
    ax.annotate(
        str(zip_code), xy=(monthly.index[-1], end_values[zip_code]),
        xytext=(monthly.index[-1], label_y[zip_code]),
        textcoords="data", ha="left", va="center",
        color=color, fontsize=9, fontweight="bold",
        annotation_clip=False,
        arrowprops=dict(arrowstyle="-", color=color, lw=0.75, shrinkA=0, shrinkB=2)
        if abs(label_y[zip_code] - end_values[zip_code]) > 1e-6 else None,
    )
ax.margins(x=0.02)
fig.subplots_adjust(right=0.90)

style_axes(ax)
ax.set_xlabel("Month (NOVIssuedDate)")
ax.set_ylabel("Class C Violation Count")
ax.set_title(
    f"Monthly Class C Violation Trend — Top {TREND_N} of Top {TOP_N} Zip Codes by Class C Concentration\n"
    f"(restricted to zips with >= {MIN_TOTAL_FOR_TREND:,} total violations, for a legible trend)"
)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
plt.xticks(rotation=45)
legend = ax.legend(
    title="Zip Code", frameon=False, labelcolor=INK_SECONDARY,
    loc="upper center", bbox_to_anchor=(0.5, 1.30), ncol=len(monthly.columns),
)
legend.get_title().set_color(INK_SECONDARY)
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/classC_trend_line.png", dpi=150, facecolor=SURFACE)
plt.close(fig)

# ---------------------------------------------------------------------------
# 6. Narrative summary
# ---------------------------------------------------------------------------
top_row = top10_display.iloc[0]
top3 = top10_display.head(3)

# Trend shape: net change from start to end, plus the peak month, since the
# monthly series is not monotonic (it rises, peaks, then eases off).
monthly_totals = monthly.sum(axis=1).sort_index()
first3 = monthly_totals.iloc[:3].mean()
last3 = monthly_totals.iloc[-3:].mean()
direction = "up" if last3 > first3 else "down" if last3 < first3 else "flat"
pct_change = ((last3 - first3) / first3 * 100) if first3 else float("nan")
peak_month = monthly_totals.idxmax()
peak_value = monthly_totals.max()

narrative = f"""# Narrative Summary — Class C Violation Concentration by Zip Code

**Question:** Which NYC zip codes have the highest concentration of Class C (hazardous) violations issued since {CUTOFF_DATE}, and is that concentration increasing or decreasing?

## Findings

Of {clean_count:,} violations issued since {CUTOFF_DATE} across {df['Postcode'].nunique()} zip codes, zip code **{top_row['Postcode']}** has the highest concentration of Class C violations at **{top_row['ClassC_Pct']}%** ({int(top_row['ClassC_Count']):,} of {int(top_row['TotalViolations']):,} total violations in that zip). The next two highest are {top3.iloc[1]['Postcode']} ({top3.iloc[1]['ClassC_Pct']}%) and {top3.iloc[2]['Postcode']} ({top3.iloc[2]['ClassC_Pct']}%).

Across all 10 top-ranked zip codes, Class C concentration ranges from {top10_display['ClassC_Pct'].min()}% to {top10_display['ClassC_Pct'].max()}%, compared to a citywide Class C share of {(df['Class'] == 'C').mean() * 100:.2f}% — meaning these zip codes carry a disproportionately hazardous violation mix relative to the city as a whole.

## Trend

The trend line covers the top {TREND_N} of these 10 zip codes by Class C %, restricted to zips with at least {MIN_TOTAL_FOR_TREND:,} total violations over the period so the monthly counts are not dominated by small-sample noise (this excludes {', '.join(str(z) for z in top10_display[top10_display['TotalViolations'] < MIN_TOTAL_FOR_TREND]['Postcode'])} — each under {MIN_TOTAL_FOR_TREND:,} total violations across 20 months). The full 10 are in the table and bar chart above. Combined Class C violation counts across the {TREND_N} trended zip codes rose from {monthly.index.min().strftime('%Y-%m')} through a peak of {peak_value:.0f} in {peak_month.strftime('%Y-%m')}, then eased off toward {monthly.index.max().strftime('%Y-%m')} (average of the first 3 months: {first3:.0f}/month vs. the last 3 months: {last3:.0f}/month, a net {pct_change:+.1f}% change over the full period). So the net direction over the whole window is **{direction}**, but the most recent months are trending down from that peak rather than continuing to climb. Note the final month ({monthly.index.max().strftime('%Y-%m')}) is partial, since data collection cuts off mid-month. See `classC_trend_line.png` for the month-by-month breakdown per zip code.

## Sources

- Top-10 table: `top10_zip_classC.csv`
- Stacked bar chart: `stacked_bar_by_zip.png`
- Trend line: `classC_trend_line.png`
- Data cleaning log: `data_cleaning_log.md`
"""

with open(f"{OUT_DIR}/narrative_summary.md", "w", encoding="utf-8") as f:
    f.write(narrative)

print("Done.")
print(cleaning_log)
print(top10_display.to_string(index=False))
