from pathlib import Path
from google.cloud import bigquery
from hmda.config import load_config

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parents[1]

# Same palette and look as Tristan's charts/make_charts.py, so the deck matches.
SURFACE, INK, INK_2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
# One colour per year, light to dark, so the latest year stands out.
YEAR_COLOR = {2023: '#a5c4ea', 2024: '#5d97dd', 2025: '#1e5aa8'}

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
    'ytick.color': INK_2,
    'xtick.labelsize': 11,
    'ytick.labelsize': 12,
    'xtick.major.size': 0,
    'ytick.major.size': 0,
    'grid.color': GRID,
    'legend.frameon': False,
    'legend.fontsize': 12,
})

BAR = 0.22    # thickness of each bar
GAP = 0.25    # distance between a county's bars: 2023 at y + GAP, 2024 at y, 2025 at y - GAP


def signed(value):
    """+9.1 / −12.1, with a real minus sign."""
    return f'{value:+.1f}'.replace('-', '−')


bq = load_config(ROOT / 'config.yaml').bigquery
client = bigquery.Client(project=bq['project'], location=bq['location'])

sql = (ROOT / 'sql' / '01_demand.sql').read_text()
df = client.query(sql).to_dataframe(create_bqstorage_client=False)
df.to_csv(ROOT / 'charts' / 'data' / 'q1_demand.csv', index=False)

top = df[df.rank_in_state <= 10]

# Title and subtitle are written from the numbers, so they stay true if the data changes.
big = top.sort_values('apps_2025', ascending=False).iloc[0]
fast = top.sort_values('growth_pct', ascending=False).iloc[0]
if big.apps_2024 < big.apps_2023 and big.apps_2025 < big.apps_2024:
    trend = 'shrank two years running'
elif big.apps_2024 > big.apps_2023 and big.apps_2025 > big.apps_2024:
    trend = 'grew two years running'
else:
    trend = 'changed direction in 2025'
title = f'{big.county_name}, the biggest market, {trend} ({signed(big.growth_pct)}% since 2023)'
subtitle = (f'Home-purchase applications, ten largest counties per state in 2025, '
            f'with 2023 and 2024 for comparison.\nAmong these twenty, '
            f'{fast.county_name}, {fast.state_name} grew fastest ({signed(fast.growth_pct)}% since 2023).')

fig = plt.figure(figsize=(13.33, 7.5))
fig.text(0.045, 0.945, title, size=21, weight='bold', color=INK, va='top')
fig.text(0.045, 0.875, subtitle, size=13, color=INK_2, va='top', linespacing=1.4)
fig.text(0.045, 0.03, 'Source: FFIEC HMDA public data, home-purchase applications on site-built homes.',
         size=10, color=MUTED, va='bottom')
axes = fig.subplots(1, 2, sharex=True)
fig.subplots_adjust(left=0.12, right=0.97, top=0.68, bottom=0.11, wspace=0.32)

for ax, state in zip(axes, ['Ohio', 'North Carolina']):
    group = top[top.state_name == state].iloc[::-1]   # reversed so the biggest county is on top
    y = np.arange(len(group))

    for offset, year in [(GAP, 2023), (0, 2024), (-GAP, 2025)]:
        ax.barh(y + offset, group[f'apps_{year}'], height=BAR, color=YEAR_COLOR[year])

    # Growth % just past each county's longest bar. The offset is in points,
    # so the gap looks the same whatever the axis scale.
    longest = group[['apps_2023', 'apps_2024', 'apps_2025']].max(axis=1)
    for pos, end, pct in zip(y, longest, group.growth_pct):
        ax.annotate(f'{signed(pct)}%', (end, pos), xytext=(6, 0),
                    textcoords='offset points', va='center', size=11, color=INK_2)

    ax.set_yticks(y, group.county_name.str.removesuffix(' County'))
    ax.set_title(state, loc='left', size=14, weight='bold', color=INK, pad=10)
    ax.grid(axis='x')
    ax.set_axisbelow(True)    # gridlines behind the bars
    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.set_xlabel('Applications')

axes[0].set_xlim(0, top[['apps_2023', 'apps_2024', 'apps_2025']].max().max() * 1.25)

fig.legend(handles=[Patch(color=color, label=str(year)) for year, color in YEAR_COLOR.items()],
           loc='upper left', bbox_to_anchor=(0.04, 0.795), ncol=3)

fig.savefig(ROOT / 'charts' / 'q1_demand.png', dpi=200)

plt.close(fig)
