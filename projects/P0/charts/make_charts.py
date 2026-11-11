"""Draw the P0 correlation (4) and approval gap (5) charts from the hmda_dw warehouse.

    PYTHONPATH=src python charts/make_charts.py             # query BigQuery, save CSVs and PNGs
    PYTHONPATH=src python charts/make_charts.py --from-csv  # redraw from the saved CSVs

The Q1, Q2, Q3 and Q7 charts each have their own script (charts/q*.py).

Each chart's data is saved as charts/data/<name>.csv, the table view of the
chart, and every title is written from the numbers, so a rebuild on new data
keeps the titles true. All charts count site-built homes only, like the
queries in sql/.
"""
import argparse
import logging
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

# Matplotlib warns once per text for each missing font in font.family, even when a later
# one is used. DejaVu Sans ships with Matplotlib, so a font is always found.
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
OUT = ROOT / "charts"
DATA = OUT / "data"

# ---- palette (validated: categorical slots 1-2) ----
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE = "#2a78d6", "#eb6834"
STATE_COLOR = {"Ohio": BLUE, "North Carolina": ORANGE}
STATE_ABBR = {"Ohio": "OH", "North Carolina": "NC"}

SOURCE = "Source: FFIEC HMDA public data, home-purchase applications on site-built homes."

plt.rcParams.update({
    # Liberation Sans has Arial's letter widths, so the layout holds where Arial is missing (Linux).
    "font.family": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "font.size": 12,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 1,
    "axes.labelcolor": INK_2,
    "axes.labelsize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": MUTED,
    "ytick.color": INK_2,
    "xtick.labelsize": 11,
    "ytick.labelsize": 12,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "legend.frameon": False,
    "legend.fontsize": 12,
})

FIGSIZE = (13.33, 7.5)          # 16:9 slide
DPI = 200

# ---- queries -----------------------------------------------------------------

# The county points behind sql/06_correlation.sql, which reports only r.
CORRELATION_POINTS_SQL = """
SELECT g.state_name AS state, g.county_name,
  APPROX_QUANTILES(f.loan_to_income, 2)[OFFSET(1)] AS median_lti,
  AVG(IF(f.is_denied, 1, 0)) AS denial_rate,
  COUNT(*) AS decided
FROM hmda_dw.fact_application f
JOIN hmda_dw.dim_geography g USING (geography_key)
JOIN hmda_dw.dim_product p   USING (product_key)
WHERE (f.is_approved OR f.is_denied) AND f.activity_year = 2025
  AND p.dwelling_label = 'Site-built home'
GROUP BY 1, 2
HAVING decided >= 300
ORDER BY 1, 2
"""

QUERIES = {
    "correlation_points": lambda: CORRELATION_POINTS_SQL,
    "risk": (SQL / "05_risk.sql").read_text,
}


def fetch(from_csv):
    """Run every query (or read the saved CSVs) and return {name: DataFrame}."""
    DATA.mkdir(parents=True, exist_ok=True)
    if from_csv:
        return {name: pd.read_csv(DATA / f"{name}.csv") for name in QUERIES}

    from google.cloud import bigquery

    from hmda.config import load_config

    bq = load_config(ROOT / "config.yaml").bigquery
    client = bigquery.Client(project=bq["project"], location=bq["location"])
    frames = {}
    for name, sql in QUERIES.items():
        df = client.query(sql()).to_dataframe(create_bqstorage_client=False)
        df.to_csv(DATA / f"{name}.csv", index=False)
        frames[name] = df
        print(f"{name:<20} {len(df):>5} rows")
    return frames


# ---- shared layout -----------------------------------------------------------

def new_figure(title, subtitle, footnote=SOURCE, top=0.76, bottom=0.11):
    fig = plt.figure(figsize=FIGSIZE)
    fig.text(0.045, 0.945, title, size=21, weight="bold", color=INK, va="top")
    fig.text(0.045, 0.875, textwrap.fill(subtitle, 135), size=13, color=INK_2, va="top",
             linespacing=1.4)
    fig.text(0.045, 0.03, footnote, size=10, color=MUTED, va="bottom")
    fig.subplots_adjust(left=0.045, right=0.97, top=top, bottom=bottom)
    return fig


def save(fig, name):
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"wrote {path.relative_to(ROOT)}")


def county_label(county_name, state):
    return f"{county_name.removesuffix(' County')}, {STATE_ABBR.get(state, state)}"


def num(value, digits=2):
    return f"{value:.{digits}f}".replace("-", "\u2212")


# ---- 4. correlation ------------------------------------------------------------

def describe_r(r):
    if abs(r) < 0.3:
        return "How far buyers stretch barely predicts how often they are denied"
    if r > 0:
        return "Where buyers stretch further on income, more are turned down"
    return "Where buyers stretch further on income, fewer are turned down"


def chart_correlation(points):
    r_all = points.median_lti.corr(points.denial_rate)
    r_state = {s: g.median_lti.corr(g.denial_rate) for s, g in points.groupby("state")}
    title = f"{describe_r(r_all)} (r = {num(r_all)})"
    subtitle = (f"One dot per county: median loan-to-income against the share of decided "
                f"applications denied, 2025. Counties with 300+ decided applications "
                f"({len(points)}).")
    footnote = (f"{SOURCE} Not a cause: HMDA has no credit scores, and house prices and the "
                f"product mix differ by county.")
    fig = new_figure(title, subtitle, footnote)
    ax = fig.subplots()
    fig.subplots_adjust(left=0.08)
    for state, color in STATE_COLOR.items():
        g = points[points.state == state]
        ax.scatter(g.median_lti, g.denial_rate * 100, s=70, color=color, edgecolor=SURFACE,
                   linewidth=1.5, zorder=3,
                   label=f"{state} (r = {num(r_state[state])}, {len(g)} counties)")
    for _, row in points.nlargest(2, "denial_rate").iterrows():
        ax.annotate(county_label(row.county_name, row.state),
                    (row.median_lti, row.denial_rate * 100), xytext=(8, 0),
                    textcoords="offset points", va="center", size=11, color=INK_2)
    ax.set_xlabel("Median loan-to-income ratio (loan amount ÷ annual income)")
    ax.set_ylabel("Share of decided applications denied")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}×"))
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_ylim(0, None)
    ax.grid()
    ax.set_axisbelow(True)
    ax.legend(loc="lower right")
    save(fig, "04_correlation")


# ---- 5. approval gap -----------------------------------------------------------

GAP_THRESHOLD = 5      # percentage points
MAX_COUNTIES = 20


def chart_risk(risk):
    wide = risk[risk.approval_gap_pts >= GAP_THRESHOLD].sort_values("approval_gap_pts",
                                                                   ascending=False)
    by_state = wide.state.value_counts()
    rows = wide.head(MAX_COUNTIES).iloc[::-1].reset_index(drop=True)
    title = (f"In {len(wide)} counties, lower-income neighbourhoods trail by "
             f"{GAP_THRESHOLD}+ approval points")
    subtitle = (f"Approval rate of decided applications, 2025, in counties with 1,000+ decided "
                f"({by_state.get('North Carolina', 0)} in North Carolina, "
                f"{by_state.get('Ohio', 0)} in Ohio). Low/Moderate: tract income below 80% "
                f"of the metro median; Upper: 120% and above. A gap, not evidence of "
                f"discrimination.")
    fig = new_figure(title, subtitle, top=0.74)
    ax = fig.subplots()
    fig.subplots_adjust(left=0.13, right=0.9)
    labels = [county_label(c, s) for c, s in zip(rows.county_name, rows.state)]
    ax.hlines(range(len(rows)), rows.approval_low_mod_pct, rows.approval_upper_pct,
              color=AXIS, linewidth=2, zorder=1)
    ax.scatter(rows.approval_low_mod_pct, range(len(rows)), s=80, color=ORANGE,
               edgecolor=SURFACE, linewidth=1.5, zorder=3, label="Low/Moderate-income tracts")
    ax.scatter(rows.approval_upper_pct, range(len(rows)), s=80, color=BLUE,
               edgecolor=SURFACE, linewidth=1.5, zorder=3, label="Upper-income tracts")
    for y, row in rows.iterrows():
        ax.text(row.approval_upper_pct + 0.4, y, f"{row.approval_gap_pts:.1f} pts",
                va="center", size=11, color=INK_2)
    ax.set_yticks(range(len(rows)), labels)
    ax.set_xlabel("Share of decided applications approved")
    ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_xlim(rows.approval_low_mod_pct.min() - 2, 100)
    ax.grid(axis="x")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    save(fig, "05_approval_gap")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Draw the P0 charts.")
    parser.add_argument("--from-csv", action="store_true",
                        help="redraw from charts/data/*.csv instead of querying BigQuery")
    args = parser.parse_args(argv)
    d = fetch(args.from_csv)
    chart_correlation(d["correlation_points"])
    chart_risk(d["risk"])


if __name__ == "__main__":
    main()
