clear

Lamda = [1/3000, 2/3000, 3/3000, 4/3000, 5/3000, 6/3000, 7/3000, 8/3000, 9/3000, 10/3000];

%N=300 nodes Q=5
S_BEB=[];
G_BEB=[];
D_BEB=[];

figure('Name', 'Slotted LoRaWAN - Backoff strategies (N=300) (Q=5)');

% plot(S_BEB,D_BEB,'-o')
% xlabel('S - throughput (succesfull packets/slot)');
% ylabel('Media Access Delay');

% plot(Lamda,D_BEB,'-o')
% xlabel('ë - Poisson arrival rate');
% ylabel('Media Access Delay');

% plot(G_BEB,S_BEB,'-o')
% xlabel('G - channel traffic load');
% ylabel('S - throughput (succesfull packets/slot)');

hold off
grid on
grid minor

title('Slotted LoRaWAN - Backoff strategies (N=300)');
legend('BEB')