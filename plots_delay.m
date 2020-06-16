clear

Lamda = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1];
%G_BEB = [1.226, 11.366, 20, 28.1, 35.62, 43.25, 51.055, 58.8 ];
%G_BEB=[0.99, 2.04, 3.08, 4.13, 5.22, 6.4, 7.5, 8.67, 9.79, 11.08];
%S_BEB = [0.99, 0.72, 0.3, 0.1253, 0.05, 0.023, 0.01, 0.0044, 0.0026, 0.002];
%D_BEB = [2.103, 39.02, 49.806, 52.943, 53.84, 52.789, 55.4, 59.3, 48.25, 46.38]; % avg delay per succesful packet

S_BEB=[0.03,0.06,0.10,0.13,0.17,0.19,0.23,0.26,0.28,0.30];
D_BEB=[2.17,2.36,2.59,2.757,3.29,3.94,4.83,6.96,9.33,12.19];

figure('Name', 'Slotted LoRaWAN - Backoff strategies');
plot(S_BEB,D_BEB)
%plot(D_BEB,S_BEB)
%plot(G_BEB,D_BEB)

hold off
grid on
grid minor
xlabel('S - throughput (succesfull packets/slot)');
%xlabel('G - traffic load');
ylabel('Media Access Delay');
title('Slotted LoRaWAN - Backoff strategies');
legend('BEB')