hold on

plot(time500,pkts_gen500,'.-')
plot(time500,pkts_sent500,'--')

plot(time1000,pkts_gen1000,'.-')
plot(time1000,pkts_sent1000,'--')

plot(time4000,pkts_gen4000,'.-')
plot(time4000,pkts_sent4000,'--')

legend('Generated v=500m/s','Delivered v=500m/s',...
        'Generated v=1000m/s','Delivered v=1000m/s',...
        'Generated v=4000m/s','Delivered v=4000m/s')

hold off
