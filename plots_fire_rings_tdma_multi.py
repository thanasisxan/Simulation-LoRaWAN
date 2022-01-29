import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.pyplot import figure

# fon/t = {'family': 'Open Sans',
#         'weight': 'regular',
#         'size': 15}

# plt.rc('font', **font)
# figure(num=None, figsize=(20, 12))
#
# prints the column names
# print(table.columns.tolist())

plt.style.use('seaborn-deep')
regular = [0.9024]

no_ring_groups_event = [0.5766]  # PDR
no_ring_groups_event1 = [0.5966]  # PDR
ring_groups_event_sf_only = [0.6525]  # PDR
ring_groups_event_sf_only1 = [0.6925]  # PDR
ring_groups_event_sf_channel = [0.73]  # PDR

height = [
    1650.85,
    1194.96,
    488.92,
    684.25,
    1051.93
]

x = np.arange(1, 6)

for i, v in enumerate(height):
    plt.bar(x[i], height[i])
    plt.text(x[i] - 0.25, v + 0.01, str(v))

# Set Plot Title
# plt.title("Market Value of Tech Companies in 2019")

# Set X-Axis values for 8 rows in CSV file
plt.xticks(np.arange(1, 6),
           ['LoRaWAN - no traffic','LoRaWAN','channel-sf (Fire Rings)','simple-TDMA (Fire Rings)','multi-TDMA (Fire Rings)'], rotation=60)

# Set X/Y-Axis labels
# plt.xlabel("Fire Ring protocols")
plt.ylabel("Average ToA (ms)")

# Show Plots
plt.grid(zorder=0, which='minor', axis='y', alpha=0.3)
plt.grid(zorder=0, which='major', axis='y', alpha=0.8)
plt.minorticks_on()

# plt.axis().set_yticks(ticks=np.arange(0, max(regular) + 1, 0.10))
# plt.axis().set_yticks(np.arange(0, max(regular) + 1, 0.010), minor=True)

# plt.yaxis.set_tick_params(labelsize=12)

plt.subplots_adjust(bottom=0.25)

plt.show()

# Save Figure
# plt.savefig('market analysis using python matplotlib.png', dpi=300)
