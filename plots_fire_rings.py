import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

#
# Generated Delivered - Time
#
Up = 6.4

fig1, ax1 = plt.subplots()
ax1.grid(zorder=0)

df = pd.read_csv('generated_delivered_v=' + str(Up) + 'ms_n=13741.csv', ';')

time = df['time' + str(Up)].to_list()
pkts_gen = df['#pkts_gen' + str(Up)].to_list()
pkts_sent = df['#pkts_sent' + str(Up)].to_list()

color = 'orange'

plt.plot(time, pkts_gen, c=color, linestyle='solid', label='Generated v=' + str(Up) + 'm/s', zorder=3)
plt.plot(time, pkts_sent, c=color, linestyle='dashed', label='Delivered v=' + str(Up) + 'm/s', zorder=3)

plt.legend(loc='upper left', edgecolor='black', prop={'size': 9}).get_frame().set_alpha(None)

ax1.set_xlabel('Time (s)')
ax1.set_ylabel('Number of packets')

# plt.savefig('generated_delivered_fire_rings_700km2.svg', bbox_inches='tight', pad_inches=0.05)
# plt.savefig('generated_delivered_fire_rings_700km2.pdf', bbox_inches='tight', pad_inches=0.05)


#
# Node densities - Packet delivery ratio (PDR)
#
# nodes = [700, 1500, 2300]
nodes = [700]

# regular = [0.9024, 0.8318, 0.7286]
regular = [0.9024]

no_ring_groups_event = [0.5766]  # PDR
ring_groups_event_sf_only = [0.6525]  # PDR
ring_groups_event_sf_channel = [0.73]  # PDR

# x = np.arange(len(nodes))  # the label locations
x = 1  # the label locations
width = 0.02  # the width of the bars

fig2, ax2 = plt.subplots()
ax2.grid(zorder=0,which='both',axis='y')
ax2.set_yticks(np.arange(0, max(regular)+1, 0.10))
# ax2.set_yticklabels()

rects1 = ax2.bar(x - 3 / 2 * width - 0.02, regular, width, label='Regular traffic', zorder=3)
rects2 = ax2.bar(x - 1 / 2 * width - 0.01, ring_groups_event_sf_channel, width,
                 label='$V_{p}$ = 6.4 m/s (ring groups - sf & channel)', zorder=3)
rects3 = ax2.bar(x + 1 / 2 * width + 0.01, ring_groups_event_sf_only, width,
                 label='$V_{p}$ = 6.4 m/s (ring groups - sf only)', zorder=3)
rects4 = ax2.bar(x + 3 / 2 * width + 0.02, no_ring_groups_event, width,
                 label='$V_{p}$ = 6.4 m/s (no ring groups - LoRaWAN)', zorder=3)

# Add some text for labels, title and custom x-axis tick labels, etc.
# ax2.set_xlabel('Node density (per sq. km.)')
ax2.set_ylabel('Packet delivery rate (PDR)')
# ax2.set_xticklabels(nodes)
ax2.set_xticklabels(' ')
ax2.legend()

fig2.tight_layout()

# plt.savefig('pdr-node_den.svg', bbox_inches='tight', pad_inches=0.05)
# plt.savefig('pdr-node_den.pdf', bbox_inches='tight', pad_inches=0.05)
