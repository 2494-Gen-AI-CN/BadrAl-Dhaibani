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

sql = (ROOT / 'sql' / '02_competition.sql').read_text()
df = client.query(sql).to_dataframe(create_bqstorage_client=False)

df.to_csv(ROOT / 'charts' / 'data' / 'q2_competition.csv', index=False)

# One row per state and year: the leader's row also carries that state-year's
# top-10 share and lender count, so the three bar segments come from here.
split = df[df.rank_in_state == 1].copy()

split['next9_share'] = split.top10_share - split.leader_share

split['other_share'] = 100 - split.top10_share
split['other_lenders'] = split.lenders - 10


# ---- styling ------------------------------------------------------------------

# Same palette and look as charts/q1_demand.py, so the deck matches.
SURFACE, INK, INK_2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
# Dark to light: the leader, the next nine, then the long tail of small lenders.
SEGMENTS = [
    ('leader_share', 'Largest lender', '#1e5aa8', 'white'),
    ('next9_share', 'Next 9 lenders', '#5d97dd', 'white'),
    ('other_share', 'All other lenders', '#c8d9ef', INK),
]
STATE_NAME = {'OH': 'Ohio', 'NC': 'North Carolina'}

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
    'ytick.color': INK_2,
    'xtick.labelsize': 11,
    'ytick.labelsize': 12,
    'xtick.major.size': 0,
    'ytick.major.size': 0,
    'grid.color': GRID,
    'legend.frameon': False,
    'legend.fontsize': 12,
})

LEGAL_SUFFIXES = [', NATIONAL ASSOCIATION', ', L.L.C.', ', LLC', ', INC.', ', LTD.', ' INC.', ' LLC']
MIXED_CASE = {'CROSSCOUNTRY': 'CrossCountry', 'JPMORGAN': 'JPMorgan'}
# Filed names that are unclear on their own.
FULL_NAME = {"STATE EMPLOYEES'": "State Employees' Credit Union"}


def lender_label(name):
    """CROSSCOUNTRY MORTGAGE, INC. -> CrossCountry Mortgage (after Tristan's lender_label)."""
    if name in FULL_NAME:
        return FULL_NAME[name]
    for suffix in LEGAL_SUFFIXES:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return ' '.join(MIXED_CASE.get(word, word.capitalize()) for word in name.split())


# ---- chart --------------------------------------------------------------------

# Hand-written takeaway for the Ohio vs North Carolina decision. Numbers checked against
# charts/data/q2_competition.csv; re-check them if the data changes.
title = 'Lender concentration is low and comparable in both states'
subtitle = ('The ten largest lenders hold about 36% of applications in each state; '
            'more than 650 smaller lenders hold the remainder.')

fig = plt.figure(figsize=(13.33, 7.5))
fig.text(0.045, 0.945, title, size=21, weight='bold', color=INK, va='top')
fig.text(0.045, 0.875, subtitle, size=13, color=INK_2, va='top', linespacing=1.4)
fig.text(0.045, 0.03, 'Source: FFIEC HMDA public data, home-purchase applications on site-built homes. '
         'Segment labels are rounded, so a bar may sum to 99-101%.', size=10, color=MUTED, va='bottom')
ax = fig.add_axes([0.1, 0.11, 0.87, 0.64])

# Each state gets a header line, then one bar per year (2023 on top).
# y counts down from the top so the chart reads in the same order as the code.
yticks, ylabels = [], []
y = 8.0
for state in ['OH', 'NC']:
    rows = split[split.state == state].sort_values('activity_year')

    # State header, with the leader's name next to it (the same lender all three years).
    header = ax.text(0, y, STATE_NAME[state], size=14, weight='bold', color=INK,
                     va='center', ha='left')
    leader = lender_label(rows.lender_name.iloc[-1])
    ax.annotate(f'largest lender: {leader}', xy=(1, 0.5), xycoords=header,
                xytext=(10, 0), textcoords='offset points', va='center', size=12, color=INK_2)
    y -= 0.9

    for row in rows.itertuples():
        left = 0
        for column, _, color, text_color in SEGMENTS:
            width = getattr(row, column)
            ax.barh(y, width, left=left, height=0.62, color=color)
            label = f'{width:.0f}%'
            if column == 'other_share':
                label += f' · {row.other_lenders:,} other lenders'
            ax.text(left + width / 2, y, label, ha='center', va='center', size=11,
                    color=text_color, weight='bold' if text_color == 'white' else 'normal')
            left += width
        yticks.append(y)
        ylabels.append(str(row.activity_year))
        y -= 0.85
    y -= 0.5    # extra space before the next state

ax.set_yticks(yticks, ylabels)
ax.set_ylim(y + 0.6, 8.4)
ax.set_xlim(0, 100)
ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
ax.set_xlabel('Share of home-purchase applications')
ax.grid(axis='x')
ax.set_axisbelow(True)    # gridlines behind the bars

fig.legend(handles=[Patch(color=color, label=label) for _, label, color, _ in SEGMENTS],
           loc='upper left', bbox_to_anchor=(0.04, 0.835), ncol=3)

fig.savefig(ROOT / 'charts' / 'q2_competition.png', dpi=200)

plt.close(fig)
