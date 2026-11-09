from pathlib import Path
from google.cloud import bigquery
from hmda.config import load_config

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

bq = load_config(ROOT / 'config.yaml').bigquery
client = bigquery.Client(project=bq['project'], location=bq['location'])

sql = (ROOT / 'sql' / '01_demand.sql').read_text()
df = client.query(sql).to_dataframe(create_bqstorage_client=False)
df.to_csv(ROOT / 'charts' / 'data' / 'q1_demand.csv', index=False)

top = df[df.rank_in_state <= 10]

fig, axes = plt.subplots(1, 2, figsize=(16,8), sharex=True)

for ax, (state, group) in zip(axes, top.groupby('state_name')):
    group = group.iloc[::-1]
    y = np.arange(len(group))
    ax.barh(y + 0.27, group.apps_2023, height=0.27, color='lightgray', label='2023')
    ax.set_yticks(y, group.county_name.str.removesuffix(' County'))
    ax.set_title(state)

fig.savefig(ROOT / 'charts' / 'q1_demand.png')

plt.close(fig)