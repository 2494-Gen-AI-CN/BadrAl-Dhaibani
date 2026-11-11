"""Q7 Geography: 2025 home-purchase applications per county, Ohio and North Carolina side by side.

County shapes: Census cartographic boundary file cb_2023_us_county_20m.zip in data/raw/
(scripts/download.sh fetches it). GeoPandas reads the zip directly.
"""
import logging
from pathlib import Path
from google.cloud import bigquery
from hmda.config import load_config

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, to_hex
from matplotlib.patches import Patch

# Matplotlib warns once per text for each missing font in font.family, even when a later
# one is used. DejaVu Sans ships with Matplotlib, so a font is always found.
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]

# Same palette and look as q1_demand.py, so the deck matches.
SURFACE, INK, INK_2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
AXIS = '#c3c2b7'

plt.rcParams.update({
    # Liberation Sans has Arial's letter widths, so the layout holds where Arial is missing (Linux).
    'font.family': ['Arial', 'Liberation Sans', 'DejaVu Sans'],
    'font.size': 12,
    'figure.facecolor': SURFACE,
    'axes.facecolor': SURFACE,
    'savefig.facecolor': SURFACE,
    'legend.frameon': False,
    'legend.fontsize': 11,
})

# What the map shades. Change these three to map another county measure.
VALUE = 'apps_2025'
BINS = [0, 500, 1000, 2500, 5000, float('inf')]          # class edges: [low, high)
BIN_LABELS = ['Under 500', '500–1k', '1k–2.5k', '2.5k–5k', '5k+']

# Each state keeps its deck colour: a light-to-dark ramp through it, one step per class.
STATES = [('39', 'Ohio', '#1e5aa8'), ('37', 'North Carolina', '#eb6834')]
N_LABELS = 5   # name each state's five largest counties on the map
# Move a label by (x, y) points, with a thin leader line back to its county, when it would
# collide with a neighbour or sit on a dark fill (text on the darkest class is hard to read).
# Others are labelled in place.
LABEL_OFFSETS = {
    'Ohio': {'Cuyahoga': (-20, 42), 'Summit': (80, 30),
             'Hamilton': (20, -48), 'Montgomery': (-62, 34), 'Franklin': (-50, 42)},
    'North Carolina': {'Forsyth': (-40, 55), 'Guilford': (25, 70), 'Wake': (50, 75),
                       'Johnston': (60, -40), 'Mecklenburg': (-30, -48)},
}


def ramp(base, n):
    """n colours, light to dark, from a pale tint of base up to base, then one darker step.
    The deck colour sits on the second-largest class, so big counties read as that state."""
    cmap = LinearSegmentedColormap.from_list('', [(0, '#f3f1ec'), (0.8, base),
                                                  (1, to_hex([c * 0.62 for c in matplotlib.colors.to_rgb(base)]))])
    return [to_hex(cmap(x)) for x in [0.16, 0.38, 0.6, 0.8, 1.0][:n]]


bq = load_config(ROOT / 'config.yaml').bigquery
client = bigquery.Client(project=bq['project'], location=bq['location'])

sql = (ROOT / 'sql' / '07_demand_map.sql').read_text()
df = client.query(sql).to_dataframe(create_bqstorage_client=False)
df.to_csv(ROOT / 'charts' / 'data' / 'q7_demand_map.csv', index=False)

# County shapes for the two states, in an equal-area projection (Albers, EPSG:5070),
# so both states keep their true shape and relative size.
shapes = gpd.read_file(ROOT / 'data' / 'raw' / 'cb_2023_us_county_20m.zip')
shapes = shapes[shapes.STATEFP.isin([fips for fips, _, _ in STATES])].to_crs(5070)

# Left join: every county shape stays; a county with no applications counts as 0.
counties = shapes.merge(df, left_on='GEOID', right_on='county_code', how='left')
print('counties with no data:', counties[VALUE].isna().sum(),
      '| data rows with no shape:', (~df.county_code.isin(shapes.GEOID)).sum())
counties[VALUE] = counties[VALUE].fillna(0)
counties['bin'] = pd.cut(counties[VALUE], BINS, right=False, labels=False)

# Hand-written takeaway. Numbers checked against charts/data/q7_demand_map.csv;
# re-check them if the data changes.
title = 'In both states, about a third of buyers are in five metro counties'
subtitle = ("Ohio's five largest counties drew 38% of its 2025 applications, spread across five cities.\n"
            "North Carolina's drew 34%, led by Wake (Raleigh) and Mecklenburg (Charlotte).")

fig = plt.figure(figsize=(13.33, 7.5))
fig.text(0.045, 0.945, title, size=21, weight='bold', color=INK, va='top')
fig.text(0.045, 0.875, subtitle, size=13, color=INK_2, va='top', linespacing=1.4)
fig.text(0.045, 0.03, 'Source: FFIEC HMDA public data, 2025 home-purchase applications on site-built homes. '
         'County boundaries: US Census Bureau.', size=10, color=MUTED, va='bottom')

# Place the two maps at the same scale (metres per inch), side by side, in the space
# between the subtitle and the source line.
LEFT, RIGHT, BOTTOM, TOP, GAP = 0.045, 0.975, 0.10, 0.70, 0.05    # figure fractions
LEGEND_TOP = 0.215                                                 # top of the legend block
W_IN, H_IN = fig.get_size_inches()
groups = [counties[counties.STATEFP == fips] for fips, _, _ in STATES]
bounds = [g.total_bounds for g in groups]                          # minx, miny, maxx, maxy
widths = [b[2] - b[0] for b in bounds]
heights = [b[3] - b[1] for b in bounds]
scale = min((RIGHT - LEFT - GAP) * W_IN / sum(widths),             # inches per metre
            (TOP - BOTTOM) * H_IN / max(heights))

x = LEFT
legend_colors = []
for group, (fips, state, base), b, w, h in zip(groups, STATES, bounds, widths, heights):
    ax_w, ax_h = w * scale / W_IN, h * scale / H_IN
    ax = fig.add_axes([x, TOP - ax_h, ax_w, ax_h])                 # top-aligned
    x += ax_w + GAP
    colors = ramp(base, len(BIN_LABELS))

    group.plot(ax=ax, color=[colors[i] for i in group['bin']],
               edgecolor=SURFACE, linewidth=0.6)
    group.dissolve().boundary.plot(ax=ax, color=AXIS, linewidth=0.8)   # state outline
    ax.set_xlim(b[0], b[2])
    ax.set_ylim(b[1], b[3])
    ax.set_axis_off()
    ax.set_title(state, loc='left', size=14, weight='bold', color=INK, pad=10)

    # Name the largest counties, with a halo so the text reads on dark fills.
    offsets = LABEL_OFFSETS.get(state, {})
    for _, row in group.nlargest(N_LABELS, VALUE).iterrows():
        point = row.geometry.representative_point()
        dx, dy = offsets.get(row.NAME, (0, 0))
        ax.annotate(f"{row.NAME}\n{row[VALUE]:,.0f}", (point.x, point.y),
                    xytext=(dx, dy), textcoords='offset points', ha='center', va='center',
                    size=10, color=INK, linespacing=1.1, annotation_clip=False,
                    path_effects=[pe.withStroke(linewidth=4, foreground=SURFACE)],
                    arrowprops=dict(arrowstyle='-', color=INK_2, linewidth=0.8, shrinkA=8, shrinkB=0)
                    if (dx, dy) != (0, 0) else None)

    legend_colors.append((state, colors))

# Legend in the empty space under North Carolina (the wider, shorter map): a heading,
# then one row of swatches per state, both rows on the same bins.
legend_x = ax.get_position().x0
fig.text(legend_x, LEGEND_TOP, 'Applications per county, 2025', size=12, weight='bold', color=INK, va='top')
for row, (state, colors) in enumerate(legend_colors):
    y = LEGEND_TOP - 0.04 - row * 0.05
    fig.text(legend_x, y, state, size=11, color=INK_2, va='center')
    fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(colors, BIN_LABELS)],
               loc='center left', bbox_to_anchor=(legend_x + 0.1, y), ncol=5,
               handlelength=1.2, columnspacing=1.0, labelcolor=INK_2, borderpad=0, borderaxespad=0)

fig.savefig(ROOT / 'charts' / 'q7_demand_map.png', dpi=200)

plt.close(fig)
