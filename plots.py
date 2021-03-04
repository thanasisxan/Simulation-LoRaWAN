import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

#
# Generated Delivered - Time
#
Up = [500, 1000, 4000]
df = {500: None, 1000: None, 4000: None}
time = {500: None, 1000: None, 4000: None}
pkts_gen = {500: None, 1000: None, 4000: None}
pkts_sent = {500: None, 1000: None, 4000: None}

fig1, ax1 = plt.subplots()
ax1.grid(zorder=0)
for v in Up:
    df[v] = pd.read_csv('generated_delivered_v=' + str(v) + 'ms_n=700.csv', ';')
    time[v] = df[v]['time' + str(v)].to_list()
    pkts_gen[v] = df[v]['#pkts_gen' + str(v)].to_list()
    pkts_sent[v] = df[v]['#pkts_sent' + str(v)].to_list()
    plt.plot(time[v], pkts_gen[v], linestyle='solid', label='Generated v=' + str(v) + 'm/s', zorder=3)
    plt.plot(time[v], pkts_sent[v], linestyle='dashed', label='Delivered v=' + str(v) + 'm/s', zorder=3)

plt.legend(loc='upper left', edgecolor='black', prop={'size': 9}).get_frame().set_alpha(None)

ax1.set_xlabel('Time (s)')
ax1.set_ylabel('Number of packets')

plt.savefig('generated_delivered_n=700.svg', bbox_inches='tight', pad_inches=0.05)
plt.savefig('generated_delivered_n=700.pdf', bbox_inches='tight', pad_inches=0.05)

#
# Node densities - Packet delivery ratio (PDR)
#
nodes = [700, 1500, 2300]
regular = [1, 0.9988207547169812, 0.9976538060479666]
v500 = [0.4232830044474799, 0.19393877047955296, 0.07012162945125668]
v1000 = [0.36581212188576784, 0.14296949655691032, 0.06746098682920824]
v4000 = [0.2689184571038008, 0.12764685398636047, 0.08109809215837412]

x = np.arange(len(nodes))  # the label locations
width = 0.15  # the width of the bars

fig2, ax2 = plt.subplots()
ax2.grid(zorder=0)
rects1 = ax2.bar(x - 3 / 2 * width - 0.02, regular, width, label='Regular traffic', zorder=3)
rects2 = ax2.bar(x - width / 2 - 0.01, v500, width, label='$V_{p}$ = 500m/s', zorder=3)
rects3 = ax2.bar(x + width / 2 + 0.01, v1000, width, label='$V_{p}$ = 1000m/s', zorder=3)
rects4 = ax2.bar(x + 3 / 2 * width + 0.02, v4000, width, label='$V_{p}$ = 4000m/s', zorder=3)

# Add some text for labels, title and custom x-axis tick labels, etc.
ax2.set_xlabel('Node density (per sq. km.)')
ax2.set_ylabel('Packet delivery rate (PDR)')
ax2.set_xticks(x)
ax2.set_xticklabels(nodes)
ax2.legend()

fig2.tight_layout()

plt.savefig('pdr-node_den.svg', bbox_inches='tight', pad_inches=0.05)
plt.savefig('pdr-node_den.pdf', bbox_inches='tight', pad_inches=0.05)
