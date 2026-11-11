from pathlib import Path
from google.cloud import bigquery
from hmda.config import load_config

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

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


# ---- styling ------------------------------------------------------------------

# Same palette and look as charts/q1_demand.py and charts/q2_competition.py.
SURFACE, INK, INK_2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
# One colour per state (checked for colour-blind contrast). Ohio keeps the deck's blue.
# The pale version of each colour is for the context rows, so the eye goes to VA first.
STATES = [('OH', 'Ohio', '#1e5aa8', '#c8d9ef'), ('NC', 'North Carolina', '#eb6834', '#f7cdb9')]
PRODUCTS = ['Conventional', 'FHA', 'VA']    # top to bottom
HIGHLIGHT = 'VA'

plt.rcParams.update({
    'font.family': ['Arial', 'DejaVu Sans'],
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

# Hand-written takeaway for the Ohio vs North Carolina decision. Numbers checked against
# charts/data/q3_approval.csv; re-check them if the data changes.
title = 'VA lending is twice as large in North Carolina, with fewer denials'
subtitle = ('Conventional and FHA denial rates are close in both states; '
            'debt-to-income is the leading denial reason for every product.')

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
    ax = fig.add_axes([0.14 + i * 0.44, 0.11, 0.38, 0.6])

    for (state, _, color, pale), offset in zip(STATES, [GAP, -GAP]):
        rows = df[df.state == state]
        for row in rows.itertuples():
            y = y_centre[row.loan_type_label] + offset
            value = getattr(row, column)
            is_va = row.loan_type_label == HIGHLIGHT
            ax.barh(y, value, height=BAR, color=color if is_va else pale)
            # Value just past the bar end; the offset is in points so the gap
            # looks the same on both panels' scales.
            ax.annotate(f'{value:.1f}%', xy=(value, y), xytext=(5, 0), textcoords='offset points',
                        va='center', size=12, color=INK if is_va else MUTED,
                        weight='bold' if is_va else 'normal')
            # Callout after North Carolina's VA value: the headline difference.
            if is_va and state == 'NC':
                ax.annotate(f'← {callout}', xy=(value, y), xytext=(58, 0), textcoords='offset points',
                            va='center', size=12, color=INK)

    ax.set_title(heading, loc='left', size=14, weight='bold', color=INK, pad=10)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-2.6, 0.6)
    ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.grid(axis='x')
    ax.set_axisbelow(True)    # gridlines behind the bars
    # Product names only on the left panel; the right panel shares its rows.
    ax.set_yticks(list(y_centre.values()), list(y_centre) if i == 0 else [])
    for label in ax.get_yticklabels():
        label.set_color(INK if label.get_text() == HIGHLIGHT else MUTED)
        label.set_weight('bold' if label.get_text() == HIGHLIGHT else 'normal')

fig.legend(handles=[Patch(color=color, label=name) for _, name, color, _ in STATES],
           loc='upper left', bbox_to_anchor=(0.04, 0.835), ncol=2)

fig.savefig(ROOT / 'charts' / 'q3_approval.png', dpi=200)

plt.close(fig)
