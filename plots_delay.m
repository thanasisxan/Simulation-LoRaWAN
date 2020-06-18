clear

Lamda = [1/3000, 2/3000, 3/3000, 4/3000, 5/3000, 6/3000, 7/3000, 8/3000, 9/3000, 10/3000];

%N=300 nodes Q=5
G_BEB=[0.11,0.298,0.558,1.442,2.821,3.772,4.489,5.188,5.893,6.453];
S_BEB=[0.099,0.2,0.2947,0.333,0.172,0.09,0.054,0.034,0.019,0.013];
D_BEB=[2.277,7.166,14.43,81.377,236.646,294.799,326.913,344.015,333.57,344.493];

figure('Name', 'Slotted LoRaWAN - Backoff strategies (N=300) (Q=5)');

% plot(S_BEB,D_BEB,'-o')
% xlabel('S - throughput (succesfull packets/slot)');
% ylabel('Media Access Delay');

plot(Lamda,D_BEB,'-o')
xlabel('ë - Poisson arrival rate');
ylabel('Media Access Delay');

% plot(G_BEB,D_BEB,'-o')
% xlabel('G - channel traffic load (trx attempts/slot)');
% ylabel('Media Access Delay');

% plot(G_BEB,S_BEB,'-o')
% xlabel('G - channel traffic load (trx attempts/slot)');
% ylabel('S - throughput (succesfull packets/slot)');

hold off
grid on
grid minor

title('Slotted LoRaWAN - Backoff strategies (N=300) (Q=5)');
legend('BEB')