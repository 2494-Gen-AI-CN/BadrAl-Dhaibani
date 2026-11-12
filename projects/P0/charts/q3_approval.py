import logging
from pathlib import Path
from google.cloud import bigquery
from hmda.config import load_config

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

# Matplotlib warns once per text for each missing font in font.family, even when a later
# one is used. DejaVu Sans ships with Matplotlib, so a font is always found.
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]

bq = load_config(ROOT / 'config.yaml').bigquery
client = bigquery.Client(project=bq['project'], location=bq['location'])

sql = (ROOT / 'sql' / '03_approval.sql').read_text()
df = client.query(sql).to_dataframe(create_bqstorage_client=False)

df.to_csv(ROOT / 'charts' / 'data' / 'q3_approval.csv', index=False)

# USDA is about 1% of applications in each state, too small for its own bars;
# the footnote says so.
df = df[df.loan_type_label != 'USDA']

# The VA rows carry the headline, so their two differences go on the chart as callouts.
va = df[df.loan_type_label == 'VA'].set_index('state')
va_ratio = va.apps['NC'] / va.apps['OH']                                # NC's VA applications / Ohio's
va_gap = va.denial_rate_pct['OH'] - va.denial_rate_pct['NC']            # points lower in NC
conv = df[df.loan_type_label == 'Conventional'].set_index('state')

# The text says: Ohio denies conventional less often; NC has about twice Ohio's VA
# applications and fewer VA denials; DTI leads every product. Stop if the data disagrees.
assert conv.denial_rate_pct['OH'] < conv.denial_rate_pct['NC']
assert round(va_ratio) == 2 and va_gap > 0
assert (df.top_denial_reason == 'Debt-to-income ratio').all()


# ---- styling ------------------------------------------------------------------

# Same palette and look as charts/q1_demand.py and charts/q2_competition.py.
SURFACE, INK, INK_2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
# One colour per state (checked for colour-blind contrast). Ohio keeps the deck's blue.
STATES = [('OH', 'Ohio', '#1e5aa8'), ('NC', 'North Carolina', '#eb6834')]
PRODUCTS = ['Conventional', 'FHA', 'VA']    # top to bottom

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
    'ytick.labelsize': 13,
    'xtick.major.size': 0,
    'ytick.major.size': 0,
    'grid.color': GRID,
    'legend.frameon': False,
    'legend.fontsize': 12,
})

BAR = 0.36    # thickness of each bar
GAP = 0.2     # Ohio sits GAP above the product's centre line, North Carolina GAP below


# ---- chart --------------------------------------------------------------------

# Takeaway for the Ohio vs North Carolina decision; the numbers and the asserts above
# come from charts/data/q3_approval.csv.
title = (f"Conventional is {conv.product_share_pct['OH']:.0f}% of Ohio's demand, "
         f"and Ohio denies it less often")
subtitle = ("VA is North Carolina's one edge: twice Ohio's applications and fewer denials.\n"
            "Debt-to-income is the leading denial reason for every product.")

fig = plt.figure(figsize=(13.33, 7.5))
fig.text(0.045, 0.945, title, size=21, weight='bold', color=INK, va='top')
fig.text(0.045, 0.875, subtitle, size=13, color=INK_2, va='top', linespacing=1.4)
fig.text(0.045, 0.03, 'Source: FFIEC HMDA public data, home-purchase applications on site-built homes, '
         '2023-2025 combined. Denial rate = denied / (approved + denied). '
         'USDA loans (about 1% of applications) not shown.', size=10, color=MUTED, va='bottom')

# Two panels with the same rows: how much demand each product carries, and how often it is denied.
panels = [
    ('product_share_pct', 'Share of the state\'s applications', 80,
     f'{va_ratio:.0f}× Ohio\'s VA applications ({va.apps["NC"] / 1000:.1f}k vs {va.apps["OH"] / 1000:.0f}k)'),
    ('denial_rate_pct', 'Denial rate', 16, f'{va_gap:.1f} pts lower than Ohio'),
]
y_centre = {product: -i for i, product in enumerate(PRODUCTS)}    # 0, -1, -2: Conventional on top

for i, (column, heading, xmax, callout) in enumerate(panels):
    ax = fig.add_axes([0.14 + i * 0.44, 0.11, 0.38, 0.58])   # 0.58 tall: room for the legend under a two-line subtitle

    for (state, _, color), offset in zip(STATES, [GAP, -GAP]):
        rows = df[df.state == state]
        for row in rows.itertuples():
            y = y_centre[row.loan_type_label] + offset
            value = getattr(row, column)
            ax.barh(y, value, height=BAR, color=color)
            # Value just past the bar end; the offset is in points so the gap
            # looks the same on both panels' scales.
            ax.annotate(f'{value:.1f}%', xy=(value, y), xytext=(5, 0), textcoords='offset points',
                        va='center', size=12, color=INK, weight='bold')
            # Callout after North Carolina's VA value: the headline difference.
            if row.loan_type_label == 'VA' and state == 'NC':
                ax.annotate(f'← {callout}', xy=(value, y), xytext=(58, 0), textcoords='offset points',
                            va='center', size=12, color=INK)

    ax.set_title(heading, loc='left', size=14, weight='bold', color=INK, pad=10)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-2.6, 0.6)
    ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.grid(axis='x')
    ax.set_axisbelow(True)    # gridlines behind the bars
    # Product names only on the left panel; the right panel shares its rows.
    ax.set_yticks(list(y_centre.values()), list(y_centre) if i == 0 else [], weight='bold')

fig.legend(handles=[Patch(color=color, label=name) for _, name, color in STATES],
           loc='upper left', bbox_to_anchor=(0.04, 0.805), ncol=2)   # below the two-line subtitle

fig.savefig(ROOT / 'charts' / 'q3_approval.png', dpi=200)

plt.close(fig)
