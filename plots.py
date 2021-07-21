import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

#
# Generated Delivered - Time
#
Up = [500, 1000, 4000]
df = {500: None, 1000: None, 4000: None}
time = {500: None, 1000: None, 4000: None}
timeg = {500: None, 1000: None, 4000: None}
times = {500: None, 1000: None, 4000: None}
pkts_gen = {500: None, 1000: None, 4000: None}
pkts_sent = {500: None, 1000: None, 4000: None}

fig1, ax1 = plt.subplots()
ax1.grid(zorder=0)
for v in Up:
    df[v] = pd.read_csv('generated_delivered_v=' + str(v) + 'ms_n=13741.csv', ';')
    time[v] = df[v]['time' + str(v)].to_list()
    # timeg[v] = df[v]['timeg' + str(v)].to_list()
    # times[v] = df[v]['times' + str(v)].to_list()
    pkts_gen[v] = df[v]['#pkts_gen' + str(v)].to_list()
    pkts_sent[v] = df[v]['#pkts_sent' + str(v)].to_list()
    color = ''
    if v == 500:
        color = 'red'
    elif v == 1000:
        color = 'blue'
    elif v == 4000:
        color = 'green'
    # plt.plot(timeg[v], pkts_gen[v], c=color, linestyle='solid', label='Generated v=' + str(v) + 'm/s', zorder=3)
    # plt.plot(times[v], pkts_sent[v], c=color, linestyle='dashed', label='Delivered v=' + str(v) + 'm/s', zorder=3)
    plt.plot(time[v], pkts_gen[v], c=color, linestyle='solid', label='Generated v=' + str(v) + 'm/s', zorder=3)
    plt.plot(time[v], pkts_sent[v], c=color, linestyle='dashed', label='Delivered v=' + str(v) + 'm/s', zorder=3)

plt.legend(loc='upper left', edgecolor='black', prop={'size': 9}).get_frame().set_alpha(None)

ax1.set_xlabel('Time (s)')
ax1.set_ylabel('Number of packets')

plt.savefig('generated_delivered_700km2.svg', bbox_inches='tight', pad_inches=0.05)
plt.savefig('generated_delivered_700km2.pdf', bbox_inches='tight', pad_inches=0.05)

#
# Node densities - Packet delivery ratio (PDR)
#
nodes = [700, 1500, 2300]
# regular = [0.92625, 0.8903508771929824, 0.8294117647058824]
# v500 = [0.16071428571428573, 0.10619469026548672, 0.08536585365853659]
# v1000 = [0.16417910447761194, 0.08666666666666667, 0.07664233576642336]
# v4000 = [0.13, 0.09202453987730061, 0.04597701149425287]

# regular = [0.932708006, 0.867556988, 0.82443946]
# v500 = [0.162603904, 0.075452053, 0.052478169]
# v1000 = [0.151364703, 0.074869728, 0.042327153]
# v4000 = [0.125859027, 0.069214484, 0.040238516]

regular = [0.9024, 0.8318, 0.7286]
v500 = [0.109, 0.055, 0.0425]
v1000 = [0.09, 0.048, 0.035]
v4000 = [0.08, 0.044, 0.033]

x = np.arange(len(nodes))  # the label locations
width = 0.15  # the width of the bars

fig2, ax2 = plt.subplots()
ax2.grid(zorder=0)
rects1 = ax2.bar(x - 3 / 2 * width - 0.02, regular, width, label='Regular traffic', zorder=3)
rects2 = ax2.bar(x - width / 2 - 0.01, v500, width, label='$V_{p}$ = 500 m/s', zorder=3)
rects3 = ax2.bar(x + width / 2 + 0.01, v1000, width, label='$V_{p}$ = 1000 m/s', zorder=3)
rects4 = ax2.bar(x + 3 / 2 * width + 0.02, v4000, width, label='$V_{p}$ = 4000 m/s', zorder=3)

# Add some text for labels, title and custom x-axis tick labels, etc.
ax2.set_xlabel('Node density (per sq. km.)')
ax2.set_ylabel('Packet delivery rate (PDR)')
ax2.set_xticks(x)
ax2.set_xticklabels(nodes)
ax2.legend()

fig2.tight_layout()

plt.savefig('pdr-node_den.svg', bbox_inches='tight', pad_inches=0.05)
plt.savefig('pdr-node_den.pdf', bbox_inches='tight', pad_inches=0.05)
