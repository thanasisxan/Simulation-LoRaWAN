clear

Lamda = [1/3000, 2/3000, 3/3000, 4/3000, 5/3000, 6/3000, 7/3000, 8/3000, 9/3000, 10/3000];
%G_BEB = [1.226, 11.366, 20, 28.1, 35.62, 43.25, 51.055, 58.8 ];
%G_BEB=[0.99, 2.04, 3.08, 4.13, 5.22, 6.4, 7.5, 8.67, 9.79, 11.08];
%S_BEB = [0.99, 0.72, 0.3, 0.1253, 0.05, 0.023, 0.01, 0.0044, 0.0026, 0.002];
%D_BEB = [2.103, 39.02, 49.806, 52.943, 53.84, 52.789, 55.4, 59.3, 48.25, 46.38]; % avg delay per succesful packet

%100 nodes
%S_BEB=[0.03,0.06,0.10,0.13,0.17,0.19,0.23,0.26,0.28,0.30];
%G_BEB=[0.03,0.07,0.11,0.16,0.22,0.28,0.37,0.52,0.68,0.82];
%D_BEB=[2.17,2.36,2.59,2.757,3.29,3.94,4.83,6.96,9.33,12.19];

%300 nodes
S_BEB=[0.1,0.196,0.27,0.18,0.07,0.045,0.02395,0.015,0.0095,0.0054];
G_BEB=[0.1,0.295,0.3,0.37,0.44,0.5,0.56,0.62,0.68,0.73];
D_BEB=[2.477,4.41,10.99,31.39,49.63,54.44,59.48,61.02,57.102,62];

figure('Name', 'Slotted LoRaWAN - Backoff strategies (N=300)');
%plot(S_BEB,D_BEB,'-o')
%plot(D_BEB,S_BEB)
%plot(G_BEB,D_BEB)
plot(Lamda,D_BEB,'-o')
%plot(G_BEB,S_BEB,'-o')

hold off
grid on
grid minor

%xlabel('S - throughput (succesfull packets/slot)');
%xlabel('G - traffic load');
xlabel('ë - arrival rate');

ylabel('Media Access Delay');
%ylabel('S - throughput');
title('Slotted LoRaWAN - Backoff strategies (N=300)');
legend('BEB')