clear
% assuming your files are in present working directory
files = dir('**/*.txt');
deliminator = ' ';
A = cell(length(files), 1); 
% data storing to variables first
for ii = 1:length(files)
    filename = files(ii).name;
    A{ii} = dlmread(filename, deliminator);  % A data
end
names=cell(length(files),1);
figure('Name', 'Slotted LoRaWAN - Backoff strategies');
for ii = 1:length(files)
    names{ii}=strtok(files(ii).name,'.');
    plot ( smooth(A{ii}(:,1)),  smooth(A{ii}(:,2)));
    hold on
end
hold off
grid on
grid minor
xlabel('G - traffic load');
ylabel('S(G) - throughput');
title('Slotted LoRaWAN - Backoff strategies');
legend(names)
% legend(files(:).name);