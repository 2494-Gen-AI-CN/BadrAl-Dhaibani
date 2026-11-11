"""Q4 Pricing: median rate spread per county, one row per state (a dot strip).

Each dot is a county with 300+ conventional originations on site-built homes in 2025.
No county labels, to keep it uncluttered: the five recommended Ohio counties are drawn darker.
"""
import logging
from pathlib import Path
from google.cloud import bigquery
from hmda.config import load_config

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Matplotlib warns once per text for each missing font in font.family, even when a later
# one is used. DejaVu Sans ships with Matplotlib, so a font is always found.
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]

bq = load_config(ROOT / 'config.yaml').bigquery
client = bigquery.Client(project=bq['project'], location=bq['location'])

sql = (ROOT / 'sql' / '04_pricing.sql').read_text()
df = client.query(sql).to_dataframe(create_bqstorage_client=False)
df.to_csv(ROOT / 'charts' / 'data' / 'q4_pricing.csv', index=False)


# ---- styling ------------------------------------------------------------------

# Same palette and look as charts/q3_approval.py: each state's deck colour, and a pale
# version for every other county, so the eye goes to the five recommended ones.
SURFACE, INK, INK_2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
STATES = [('Ohio', 'OH', '#1e5aa8', '#c8d9ef', 1),          # name, abbreviation, colour, pale, row
          ('North Carolina', 'NC', '#eb6834', '#f7cdb9', 0)]

# The five recommended counties, drawn in the full state colour.
HIGHLIGHT = {('Ohio', f'{name} County') for name in
             ['Franklin', 'Hamilton', 'Montgomery', 'Butler', 'Warren']}

BIN = 0.01      # counties within the same 0.01-point bin stack vertically
STEP = 0.075    # vertical distance between stacked dots, in rows

plt.rcParams.update({
    # Liberation Sans has Arial's letter widths, so the layout holds where Arial is missing (Linux).
    'font.family': ['Arial', 'Liberation Sans', 'DejaVu Sans'],
    'font.size': 12,
    'figure.facecolor': SURFACE,
    'axes.facecolor': SURFACE,
    'savefig.facecolor': SURFACE,
    'axes.edgecolor': AXIS,
    'axes.labelcolor': INK_2,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.spines.left': False,
    'xtick.color': MUTED,
    'ytick.color': INK,
    'xtick.labelsize': 11,
    'ytick.labelsize': 14,
    'xtick.major.size': 0,
    'ytick.major.size': 0,
    'grid.color': GRID,
    'legend.frameon': False,
})


def pts(value):
    """+0.23 / −0.06, with a real minus sign."""
    return f'{value:+.2f}'.replace('-', '−')


# ---- numbers for the text -----------------------------------------------------

median = df.groupby('state').state_median_spread.first()
nc_max = df.loc[df.state == 'North Carolina', 'median_rate_spread'].max()
above_nc = (df.loc[df.state == 'Ohio', 'median_rate_spread'] > nc_max).sum()

# Title is the takeaway; subtitle numbers come from the data.
title = "Ohio borrowers pay more over the benchmark rate than North Carolina's"
subtitle = (f'Each dot is one county\'s median rate spread on 2025 conventional loans. '
            f'Ohio\'s median is {median["Ohio"]:.2f} points, North Carolina\'s {median["North Carolina"]:.2f}.\n'
            f'All {above_nc} counties above North Carolina\'s highest are in Ohio. '
            f'Dark dots: the five counties we recommend.')


# ---- chart --------------------------------------------------------------------

fig = plt.figure(figsize=(13.33, 7.5))
fig.text(0.045, 0.945, title, size=21, weight='bold', color=INK, va='top')
fig.text(0.045, 0.875, subtitle, size=13, color=INK_2, va='top', linespacing=1.4)
fig.text(0.045, 0.03, 'Source: FFIEC HMDA public data, conventional loans on site-built homes originated in 2025, '
         'counties with 300+ loans. Rate spread = the loan\'s APR minus the average prime offer rate\n'
         'for a comparable loan; each dot and each state line is a median. '
         'A higher spread can also mean riskier borrowers, not only weaker competition.',
         size=10, color=MUTED, va='bottom', linespacing=1.4)

ax = fig.add_axes([0.13, 0.17, 0.83, 0.56])

for state, _, color, pale, row in STATES:
    counties = df[df.state == state].sort_values('median_rate_spread')
    # Stack counties that land in the same bin, centred on the row, so no dot hides another.
    counties['bin'] = (counties.median_rate_spread / BIN).round()
    counties['k'] = counties.groupby('bin').cumcount()
    counties['n'] = counties.groupby('bin').bin.transform('size')
    counties['y'] = row + (counties.k - (counties.n - 1) / 2) * STEP

    for c in counties.itertuples():
        dark = (state, c.county_name) in HIGHLIGHT
        ax.scatter(c.median_rate_spread, c.y, s=90 if dark else 70, zorder=3,
                   color=color if dark else pale, edgecolor=SURFACE, linewidth=1)

    # The state's median over all its loans: a short dark bar across the row, labelled
    # on the side facing the gap between the rows.
    m = median[state]
    ax.plot([m, m], [row - 0.28, row + 0.28], color=INK, linewidth=2.2, zorder=4)
    ax.annotate(f'{state} median {m:.2f}', xy=(m, row - 0.28 if row else row + 0.28),
                xytext=(0, -12 if row else 12), textcoords='offset points',
                ha='center', va='top' if row else 'bottom', size=12, color=INK, weight='bold')

# Zero: the benchmark rate itself.
ax.axvline(0, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
ax.annotate('Benchmark rate', xy=(0, 1.42), xytext=(-6, 0), textcoords='offset points',
            ha='right', va='center', size=11, color=MUTED)

ax.set_yticks([row for *_, row in STATES], [state for state, *_ in STATES])
ax.set_ylim(-0.5, 1.5)
ax.set_xlim(-0.1, 0.5)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: pts(v) if v else '0'))
ax.set_xlabel('Median rate spread, percentage points above the benchmark rate')
ax.grid(axis='x')
ax.set_axisbelow(True)

fig.savefig(ROOT / 'charts' / 'q4_pricing.png', dpi=200)

plt.close(fig)
