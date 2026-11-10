"""Draw P0 charts 2 to 5 from the hmda_dw warehouse.

    PYTHONPATH=src python charts/make_charts.py             # query BigQuery, save CSVs and PNGs
    PYTHONPATH=src python charts/make_charts.py --from-csv  # redraw from the saved CSVs

The Q1 demand chart is drawn separately by charts/q1_demand.py.

Each chart's data is saved as charts/data/<name>.csv, the table view of the
chart, and every title is written from the numbers, so a rebuild on new data
keeps the titles true. All charts count site-built homes only, like the
queries in sql/.
"""
import argparse
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
OUT = ROOT / "charts"
DATA = OUT / "data"

# ---- palette (validated: categorical slots 1-3) ----
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
STATE_COLOR = {"Ohio": BLUE, "North Carolina": ORANGE}
STATE_ABBR = {"Ohio": "OH", "North Carolina": "NC"}

SOURCE = "Source: FFIEC HMDA public data, home-purchase applications on site-built homes."

plt.rcParams.update({
    "font.family": ["Liberation Sans", "DejaVu Sans"],
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

LENDER_NAMES_SQL = """
SELECT lei, lender_name, EXTRACT(YEAR FROM effective_from) AS from_year
FROM hmda_dw.dim_lender
WHERE name_in_filers
ORDER BY lei, from_year
"""

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
    "competition":(SQL / "02_competition.sql").read_text,
    "lender_names": lambda: LENDER_NAMES_SQL,
    "approval": (SQL / "03_approval.sql").read_text,
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


LEGAL_SUFFIXES = [", NATIONAL ASSOCIATION", ", L.L.C.", ", LLC", ", INC.", ", LTD.", " INC.",
                  " CORP.", " LLC"]
KEEP_UPPER = {"DHI", "NFM", "USAA", "PNC", "TD", "BMO", "MRC"}
MIXED_CASE = {"CROSSCOUNTRY": "CrossCountry", "JPMORGAN": "JPMorgan"}


def lender_label(name):
    """Readable lender name: legal suffix dropped, title case, known acronyms kept."""
    for suffix in LEGAL_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    words = []
    for word in name.split():
        if word in KEEP_UPPER:
            words.append(word)
        elif word in MIXED_CASE:
            words.append(MIXED_CASE[word])
        else:
            words.append(word.capitalize() if word != "OF" else "of")
    return " ".join(words)


FULL_SUFFIX_CASE = {"Llc": "LLC", "L.l.c.": "L.L.C.", "Llc.": "LLC."}


def full_name_label(name):
    """Name as filed, in title case, legal suffix kept."""
    words = []
    for word in name.split():
        bare = word.rstrip(",")
        tail = word[len(bare):]
        if bare in KEEP_UPPER:
            cased = bare
        elif bare in MIXED_CASE:
            cased = MIXED_CASE[bare]
        else:
            cased = FULL_SUFFIX_CASE.get(bare.capitalize(), bare.capitalize())
        words.append(cased + tail)
    return " ".join(words)


# ---- 2. competition ------------------------------------------------------------

def name_history(lender_names):
    """lei -> list of (from_year, name) when the lender filed under more than one name."""
    history = {}
    for lei, rows in lender_names.groupby("lei"):
        names = rows.drop_duplicates("lender_name")
        if len(names) > 1:
            history[lei] = list(zip(names.from_year, names.lender_name))
    return history


MARKERS = ["*", "\u2020", "\u2021"]


def chart_competition(competition, lender_names):
    year = int(competition.activity_year.max())
    latest = competition[competition.activity_year == year]
    history = name_history(lender_names)
    top5 = {s: latest[latest.state == s].nlargest(5, "apps").market_share_pct.sum()
            for s in STATE_COLOR}
    biggest = latest.market_share_pct.max()
    title = f"No lender holds more than {biggest:.0f}% of either state's market"
    subtitle = (f"Share of {year} home-purchase applications, ten largest lenders per state. "
                f"The five largest take {top5['Ohio']:.0f}% in Ohio and "
                f"{top5['North Carolina']:.0f}% in North Carolina. "
                f"Names are as each lender filed them that year.")
    # A lender shown under a different name than it used in an earlier year gets a
    # marker, explained in the footnote: the type 2 lender history at work.
    notes = {}
    for _, row in latest.iterrows():
        earlier = [(yr, n) for yr, n in history.get(row.lei, [])
                   if yr < year and lender_label(n) != lender_label(row.name_that_year)]
        if earlier and row.lei not in notes:
            yr, n = earlier[0]
            notes[row.lei] = (MARKERS[len(notes)],
                              f"filed as {full_name_label(n)} in {yr}; same lender (LEI)")
    footnote = SOURCE + "".join(f"  {m} {lender_label(latest.loc[latest.lei == lei].name_that_year.iloc[0])}: {text}."
                                for lei, (m, text) in notes.items())
    fig = new_figure(title, subtitle, footnote, top=0.72)
    axes = fig.subplots(1, 2, sharex=True)
    fig.subplots_adjust(wspace=0.62, left=0.2)
    for ax, state in zip(axes, ["Ohio", "North Carolina"]):
        rows = latest[latest.state == state].sort_values("apps").reset_index(drop=True)
        labels = [lender_label(n) + (f" {notes[lei][0]}" if lei in notes else "")
                  for n, lei in zip(rows.name_that_year, rows.lei)]
        ax.barh(labels, rows.market_share_pct, color=BLUE, height=0.68)
        for y, row in rows.iterrows():
            ax.text(row.market_share_pct, y, f"  {row.market_share_pct:.1f}%", va="center",
                    size=11, color=INK_2)
        ax.set_title(state, loc="left", size=14, weight="bold", color=INK, pad=10)
        ax.grid(axis="x")
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
        ax.set_xlabel(f"Share of {year} applications")
    axes[0].set_xlim(0, biggest * 1.25)
    save(fig, "02_competition")


# ---- 3. denials by debt-to-income ----------------------------------------------

DTI_ORDER = ["<20%", "20%-<30%", "30%-<36%", "36%-<43%", "43%-<50%", "50%-60%", ">60%"]
LOAN_TYPES = [("Conventional", BLUE), ("FHA", ORANGE), ("VA", AQUA)]


def chart_approval(approval):
    rate = approval.pivot(index="dti_band", columns="loan_type_label", values="denial_rate_pct")
    conv_before, conv_after = rate.loc["43%-<50%", "Conventional"], rate.loc["50%-60%", "Conventional"]
    fha_at = rate.loc["50%-60%", "FHA"]
    usda = int(approval.loc[approval.loan_type_label == "USDA", "decided"].sum())
    title = (f"Conventional denials jump from {conv_before:.0f}% to {conv_after:.0f}% "
             f"once debt passes 50% of income")
    subtitle = (f"Share of decided applications denied, 2023 to 2025. FHA denials stay at "
                f"{fha_at:.0f}% up to 60% of income; above 60%, every loan type is mostly "
                f"turned down.")
    footnote = (f"{SOURCE} Left out: USDA loans ({usda:,} decided; too few at high debt) and "
                f"applications with no ratio reported.")
    fig = new_figure(title, subtitle, footnote)
    ax = fig.subplots()
    fig.subplots_adjust(left=0.075, right=0.88)
    x = range(len(DTI_ORDER))
    for loan_type, color in LOAN_TYPES:
        y = rate.loc[DTI_ORDER, loan_type]
        ax.plot(x, y, color=color, linewidth=2.2, marker="o", markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=loan_type, zorder=3)
        ax.annotate(loan_type, (len(DTI_ORDER) - 1, y.iloc[-1]), xytext=(12, 0),
                    textcoords="offset points", va="center", size=12, color=INK, weight="bold")
    ax.set_xticks(list(x), [b.replace("-<", " to <").replace("-", " to ") for b in DTI_ORDER])
    ax.set_xlabel("Debt-to-income ratio")
    ax.set_ylabel("Share of decided applications denied")
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.legend(loc="upper left")
    save(fig, "03_denials_by_dti")


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
    chart_competition(d["competition"], d["lender_names"])
    chart_approval(d["approval"])
    chart_correlation(d["correlation_points"])
    chart_risk(d["risk"])


if __name__ == "__main__":
    main()
