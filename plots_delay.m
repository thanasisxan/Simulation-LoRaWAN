clear

Lamda = [1/3000, 2/3000, 3/3000, 4/3000, 5/3000, 6/3000, 7/3000, 8/3000, 9/3000, 10/3000];

%N=300 nodes Q=5
S_BEB=[0.1,0.192,0.286,0.3401,0.34486,0.3251,0.3,0.295,0.27,0.26];
G_BEB=[0.11,0.28,0.55,1.02,1.33,1.53,1.7,1.85,1.95,2.07];
D_BEB=[2.1,3.66,93.5,890.21,1602.6,2237.44,2690.69,2974.53,3258.26,3489.55];

figure('Name', 'Slotted LoRaWAN - Backoff strategies (N=300) (Q=5)');

% plot(S_BEB,D_BEB,'-o')
% xlabel('S - throughput (succesfull packets/slot)');
% ylabel('Media Access Delay');

% plot(Lamda,D_BEB,'-o')
% xlabel('ë - Poisson arrival rate');
% ylabel('Media Access Delay');

plot(G_BEB,S_BEB,'-o')
xlabel('G - channel traffic load (trx attempts/slot)');
ylabel('S - throughput (succesfull packets/slot)');

hold off
grid on
grid minor

title('Slotted LoRaWAN - Backoff strategies (N=300) (Q=5)');
legend('BEB')