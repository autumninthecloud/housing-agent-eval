"""
Single-agent pipeline — Phase 1 (housing-agent-eval)

Loads data/static/ as-is, cleans it, ranks zip codes by Class C violation
concentration, and produces the four required outputs into
outputs/single_agent/:
  1. top10_zip_table.csv / .md
  2. stacked_bar_by_class.png
  3. trend_class_c_top_zips.png
  4. narrative_summary.md

Also writes data_notes.md documenting every row dropped, so the final
counts are explainable rather than a silent filter.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

SRC = "data/static/Housing_Maintenance_Code_Violations_20260821_vf.csv"
OUT = "outputs/single_agent"

# ---- palette (dataviz skill reference palette) ----
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# Class A/B/C is ordinal severity (C = most hazardous) -> single-hue sequential
# ramp, light to dark, per dataviz skill "ordinal ramp" rule (min step 250 on
# light surface).
CLASS_COLORS = {"A": "#86b6ef", "B": "#3987e5", "C": "#184f95"}

# Categorical slots 1,2,3,4,6,7 (skipping the low-contrast-on-light slots 5/8
# isn't required here since these are line labels with a legend, but slot
# order is kept fixed per the palette's CVD-safe ordering).
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

TREND_TOP_N = 6  # subset of the top-10 table, kept small for line legibility

# ---------------------------------------------------------------------------
# 1. Load + clean
# ---------------------------------------------------------------------------
df = pd.read_csv(SRC, dtype={"Postcode": "float64"})
notes = []
notes.append(f"Rows loaded from source file: {len(df)}")

df["NOVIssuedDate"] = pd.to_datetime(df["NOVIssuedDate"], format="%m/%d/%Y")
notes.append(f"Date range in source: {df['NOVIssuedDate'].min().date()} to {df['NOVIssuedDate'].max().date()}")

before = len(df)
df = df[df["NOVIssuedDate"] >= "2025-01-01"].copy()
notes.append(f"Dropped for NOVIssuedDate < 2025-01-01: {before - len(df)} rows (of {before})")

before = len(df)
null_zip = df["Postcode"].isnull().sum()
df = df.dropna(subset=["Postcode"]).copy()
notes.append(f"Dropped for missing Postcode: {null_zip} rows")

# Malformed postcodes: valid NYC ZIPs are 5-digit codes in the 10001-11697
# range. A handful of records carry corrupted values (e.g. 2018, 3366, 418, 0)
# that are not valid ZIPs at all -- drop them rather than let them distort a
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

# ---------------------------------------------------------------------------
# 2. Rank zip codes by Class C percentage
# ---------------------------------------------------------------------------
by_zip_class = df.groupby(["Postcode", "Class"]).size().unstack(fill_value=0)
for c in ["A", "B", "C"]:
    if c not in by_zip_class.columns:
        by_zip_class[c] = 0
by_zip_class["Total"] = by_zip_class[["A", "B", "C"]].sum(axis=1)
by_zip_class["ClassC_Pct"] = (by_zip_class["C"] / by_zip_class["Total"] * 100).round(1)

top10 = by_zip_class.sort_values("ClassC_Pct", ascending=False).head(10)
top10 = top10.reset_index()[["Postcode", "ClassC_Pct", "C", "Total", "A", "B"]]
top10.columns = ["Postcode", "ClassC_Pct", "ClassC_Count", "TotalViolations", "ClassA_Count", "ClassB_Count"]

top10.to_csv(f"{OUT}/top10_zip_table.csv", index=False)

with open(f"{OUT}/top10_zip_table.md", "w", encoding="utf-8") as f:
    f.write("# Top 10 Zip Codes by Class C Violation Percentage\n\n")
    f.write("Filtered to NOVIssuedDate >= 2025-01-01. Ranked by Class C violations as a percentage of each zip's total violations.\n\n")
    f.write("| Rank | Postcode | Class C % | Class C Count | Total Violations | Class A | Class B |\n")
    f.write("|---|---|---|---|---|---|---|\n")
    for i, row in top10.iterrows():
        f.write(f"| {i+1} | {row['Postcode']} | {row['ClassC_Pct']:.1f}% | {int(row['ClassC_Count'])} | {int(row['TotalViolations'])} | {int(row['ClassA_Count'])} | {int(row['ClassB_Count'])} |\n")

print("Top 10 table:")
print(top10.to_string(index=False))

# ---------------------------------------------------------------------------
# 3. Stacked bar chart — violation counts by class, per zip (top 10 zips)
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
ax.set_title("Violation Counts by Class — Top 10 Zip Codes by Class C %", color=INK_PRIMARY, fontsize=13, fontweight="bold", pad=14)

ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{int(v):,}"))
ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color(BASELINE)
ax.tick_params(colors=INK_MUTED)

legend = ax.legend(loc="upper right", frameon=False, fontsize=10, labelcolor=INK_SECONDARY)

fig.tight_layout()
fig.savefig(f"{OUT}/stacked_bar_by_class.png", dpi=160, facecolor=SURFACE)
plt.close(fig)

# ---------------------------------------------------------------------------
# 4. Trend line — Class C violations over time, top zip codes (monthly)
# ---------------------------------------------------------------------------
trend_zips = top10["Postcode"].head(TREND_TOP_N).tolist()
trend_df = df[(df["Class"] == "C") & (df["Postcode"].isin(trend_zips))].copy()
trend_df["Month"] = trend_df["NOVIssuedDate"].dt.to_period("M").dt.to_timestamp()

monthly = trend_df.groupby(["Month", "Postcode"]).size().unstack(fill_value=0)
monthly = monthly.reindex(columns=trend_zips)  # preserve top10 rank order for color assignment
full_months = pd.period_range(df["NOVIssuedDate"].min().to_period("M"), df["NOVIssuedDate"].max().to_period("M"), freq="M").to_timestamp()
monthly = monthly.reindex(full_months, fill_value=0)

fig2, ax2 = plt.subplots(figsize=(11, 6.5), facecolor=SURFACE)
ax2.set_facecolor(SURFACE)

for i, z in enumerate(trend_zips):
    ax2.plot(monthly.index, monthly[z], color=CATEGORICAL[i % len(CATEGORICAL)], linewidth=2, marker="o", markersize=4, label=z)

ax2.set_xlabel("Month (NOVIssuedDate)", color=INK_SECONDARY, fontsize=11)
ax2.set_ylabel("Class C Violation Count", color=INK_SECONDARY, fontsize=11)
ax2.set_title(f"Class C Violation Trend — Top {TREND_TOP_N} Zip Codes (by Class C %)", color=INK_PRIMARY, fontsize=13, fontweight="bold", pad=14)

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

# ---------------------------------------------------------------------------
# 5. Data notes (explain row counts / cleaning decisions)
# ---------------------------------------------------------------------------
with open(f"{OUT}/data_notes.md", "w", encoding="utf-8") as f:
    f.write("# Data Handling Notes - Single-Agent Pipeline\n\n")
    f.write(f"Source: `{SRC}`\n\n")
    for n in notes:
        f.write(f"- {n}\n")
    f.write(f"\nTrend line and narrative use the top {TREND_TOP_N} of the 10 ranked zip codes "
            f"(kept to {TREND_TOP_N} lines for chart legibility, per the dataviz skill's "
            f"categorical-color guidance); the stacked bar chart and table cover all 10.\n")

print("\nDone. Wrote outputs to", OUT)
print("Trend zips used:", trend_zips)
