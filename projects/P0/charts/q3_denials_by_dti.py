"""Q3 Approval, second chart: denial rate by debt-to-income band, one line per loan product.

Restored from the old charts/make_charts.py (chart 3), which the cleanup in bab5297 removed.
"""
import logging
from pathlib import Path
from google.cloud import bigquery
from hmda.config import load_config

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

# Matplotlib warns once per text for each missing font in font.family, even when a later
# one is used. DejaVu Sans ships with Matplotlib, so a font is always found.
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]

bq = load_config(ROOT / 'config.yaml').bigquery
client = bigquery.Client(project=bq['project'], location=bq['location'])

sql = (ROOT / 'sql' / '03b_approval_dti.sql').read_text()
df = client.query(sql).to_dataframe(create_bqstorage_client=False)
df.to_csv(ROOT / 'charts' / 'data' / 'q3_denials_by_dti.csv', index=False)


# ---- styling ------------------------------------------------------------------

# Same palette and look as the other charts. One colour per product, as on the slide
# this chart already sits on.
SURFACE, INK, INK_2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
LOAN_TYPES = [('Conventional', '#2a78d6'), ('FHA', '#eb6834'), ('VA', '#1baf7a')]
# "Not reported" is left out: it is not a debt level.
DTI_ORDER = ['<20%', '20%-<30%', '30%-<36%', '36%-<43%', '43%-<50%', '50%-60%', '>60%']

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
    'xtick.color': MUTED,
    'ytick.color': INK_2,
    'xtick.labelsize': 11,
    'ytick.labelsize': 12,
    'xtick.major.size': 0,
    'ytick.major.size': 0,
    'grid.color': GRID,
    'legend.frameon': False,
    'legend.fontsize': 12,
})


# ---- chart --------------------------------------------------------------------

rate = df.pivot(index='dti_band', columns='loan_type_label', values='denial_rate_pct')
conv_before, conv_after = rate.loc['43%-<50%', 'Conventional'], rate.loc['50%-60%', 'Conventional']
fha_at = rate.loc['50%-60%', 'FHA']
usda = int(df.loc[df.loan_type_label == 'USDA', 'decided'].sum())

# Title and subtitle are written from the numbers, so they stay true if the data changes.
title = (f'Conventional denials jump from {conv_before:.0f}% to {conv_after:.0f}% '
         f'once debt passes 50% of income')
subtitle = (f'Share of decided applications denied, 2023 to 2025. FHA denials stay at {fha_at:.0f}% '
            f'up to 60% of income; above 60%, every loan type is mostly\nturned down.')

fig = plt.figure(figsize=(13.33, 7.5))
fig.text(0.045, 0.945, title, size=21, weight='bold', color=INK, va='top')
fig.text(0.045, 0.875, subtitle, size=13, color=INK_2, va='top', linespacing=1.4)
fig.text(0.045, 0.03, 'Source: FFIEC HMDA public data, home-purchase applications on site-built homes. '
         f'Left out: USDA loans ({usda:,} decided; too few at high debt) and applications with '
         'no ratio reported.', size=10, color=MUTED, va='bottom')

ax = fig.add_axes([0.075, 0.11, 0.805, 0.65])
x = range(len(DTI_ORDER))
for loan_type, color in LOAN_TYPES:
    y = rate.loc[DTI_ORDER, loan_type]
    ax.plot(x, y, color=color, linewidth=2.2, marker='o', markersize=8,
            markeredgecolor=SURFACE, markeredgewidth=1.5, label=loan_type, zorder=3)
    # Name each line at its right end, so the chart doesn't depend on colour alone.
    ax.annotate(loan_type, (len(DTI_ORDER) - 1, y.iloc[-1]), xytext=(12, 0),
                textcoords='offset points', va='center', size=12, color=INK, weight='bold')

ax.set_xticks(list(x), [b.replace('-<', ' to <').replace('-', ' to ') for b in DTI_ORDER])
ax.set_xlabel('Debt-to-income ratio')
ax.set_ylabel('Share of decided applications denied')
ax.set_ylim(0, 100)
ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
ax.grid(axis='y')
ax.set_axisbelow(True)
ax.legend(loc='upper left')

fig.savefig(ROOT / 'charts' / 'q3_denials_by_dti.png', dpi=200)

plt.close(fig)
