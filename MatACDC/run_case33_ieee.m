function run_case33_ieee()
%RUN_CASE33_IEEE  Run AC/DC power flow for case33_ieee network.
%
%   This script runs the sequential AC/DC power flow using MatACDC
%   for the case33_ieee network and exports voltage results for
%   comparison with the Python acdcpf tool.
%
%   Outputs:
%       - case33_ieee_results.mat: MATLAB workspace with all results
%       - results/res_ac_bus.csv: AC bus voltage results
%       - results/res_dc_bus.csv: DC bus voltage results
%       - results/res_vsc.csv: VSC converter results
%       - results/res_dc_line.csv: DC line flow results

%% Setup paths
% Add MatACDC directories to path
matacdc_dir = fileparts(mfilename('fullpath'));
addpath(matacdc_dir);
addpath(fullfile(matacdc_dir, 'Cases', 'PowerflowAC'));
addpath(fullfile(matacdc_dir, 'Cases', 'PowerflowDC'));

% Add the case files directory
case_dir = fullfile(fileparts(matacdc_dir), 'acdcpf', 'networks');
addpath(case_dir);

%% Define options
mdopt = macdcoption;
mdopt(1) = 1e-8;    % tolerance ac/dc power flow
mdopt(2) = 30;      % maximum iterations ac/dc power flow
mdopt(3) = 1e-8;    % tolerance dc power flow
mdopt(4) = 30;      % maximum iterations dc power flow
mdopt(13) = 1;      % print output

%% Run AC/DC power flow
fprintf('\n========================================\n');
fprintf('Running AC/DC Power Flow: case33_ieee\n');
fprintf('========================================\n\n');

try
    [resultsac, resultsdc, converged, timecalc] = runacdcpf(...
        'case33_ieee_AC', 'case33_ieee_DC', mdopt);
catch ME
    fprintf('Error running power flow: %s\n', ME.message);
    fprintf('Stack trace:\n');
    for k = 1:length(ME.stack)
        fprintf('  In %s at line %d\n', ME.stack(k).name, ME.stack(k).line);
    end
    return;
end

%% Display convergence status
fprintf('\n========================================\n');
if converged
    fprintf('Power flow CONVERGED in %.4f seconds\n', timecalc);
else
    fprintf('Power flow DID NOT CONVERGE\n');
end
fprintf('========================================\n\n');

%% Extract results
baseMVA = resultsac.baseMVA;
bus = resultsac.bus;
gen = resultsac.gen;
branch = resultsac.branch;

pol = resultsdc.pol;
busdc = resultsdc.busdc;
convdc = resultsdc.convdc;
branchdc = resultsdc.branchdc;

%% Define column indices for MATPOWER bus matrix
BUS_I = 1;      % bus number
BUS_TYPE = 2;   % bus type
PD = 3;         % real power demand (MW)
QD = 4;         % reactive power demand (MVAr)
GS = 5;         % shunt conductance (MW at V = 1.0 p.u.)
BS = 6;         % shunt susceptance (MVAr at V = 1.0 p.u.)
BUS_AREA = 7;   % area number
VM = 8;         % voltage magnitude (p.u.)
VA = 9;         % voltage angle (degrees)
BASE_KV = 10;   % base voltage (kV)
ZONE = 11;      % loss zone
VMAX = 12;      % maximum voltage magnitude (p.u.)
VMIN = 13;      % minimum voltage magnitude (p.u.)

%% Define column indices for DC bus matrix
BUSDC_I = 1;    % DC bus number
BUSAC_I = 2;    % AC bus number (0 if no AC connection)
GRIDDC = 3;     % DC grid number
PDC = 4;        % DC power (MW)
VDC = 5;        % DC voltage (p.u.)
BASE_KVDC = 6;  % DC base voltage (kV)
VDCMAX = 7;     % max DC voltage (p.u.)
VDCMIN = 8;     % min DC voltage (p.u.)

%% Define column indices for converter matrix (convdc)
% See MatACDC/idx_convdc.m for the official column definitions
CONV_BUS = 1;   % DC bus number (busdc_i)
TYPE_DC = 2;    % DC control type (1=P, 2=Vdc_slack, 3=droop)
TYPE_AC = 3;    % AC control type (1=PQ, 2=PV)
PCONV = 4;      % AC side active power (MW) - setpoint and result
QCONV = 5;      % AC side reactive power (MVAr) - setpoint and result
VCONV = 6;      % converter voltage setpoint
RTF = 7;        % transformer resistance
XTF = 8;        % transformer reactance
% Result columns (populated after power flow, starting at col 25)
VMC = 25;       % converter voltage magnitude (p.u.)
VAC = 26;       % converter voltage angle (degrees)
PCCONV = 27;    % converter side active power (MW)
QCCONV = 28;    % converter side reactive power (MVAr)
PCLOSS = 29;    % converter losses (MW)

%% Define column indices for DC branch matrix
F_BUSDC = 1;    % from bus
T_BUSDC = 2;    % to bus
PFDC = 10;      % from bus power (MW)
PTDC = 11;      % to bus power (MW)

%% Create results directory
results_dir = fullfile(matacdc_dir, 'results');
if ~exist(results_dir, 'dir')
    mkdir(results_dir);
end

%% Export AC bus results
fprintf('Exporting AC bus results...\n');
n_ac_bus = size(bus, 1);
ac_bus_results = table(...
    bus(:, BUS_I), ...
    bus(:, VM), ...
    bus(:, VA), ...
    bus(:, PD), ...
    bus(:, QD), ...
    bus(:, BASE_KV), ...
    'VariableNames', {'bus_id', 'v_pu', 'v_angle_deg', 'p_load_mw', 'q_load_mvar', 'base_kv'});
writetable(ac_bus_results, fullfile(results_dir, 'res_ac_bus.csv'));
fprintf('  -> %d AC buses exported\n', n_ac_bus);

%% Export DC bus results
fprintf('Exporting DC bus results...\n');
n_dc_bus = size(busdc, 1);
v_dc_kv = busdc(:, VDC) .* busdc(:, BASE_KVDC);
dc_bus_results = table(...
    busdc(:, BUSDC_I), ...
    busdc(:, BUSAC_I), ...
    busdc(:, GRIDDC), ...
    busdc(:, VDC), ...
    v_dc_kv, ...
    busdc(:, PDC), ...
    'VariableNames', {'dc_bus_id', 'ac_bus_id', 'dc_grid', 'v_dc_pu', 'v_dc_kv', 'p_mw'});
writetable(dc_bus_results, fullfile(results_dir, 'res_dc_bus.csv'));
fprintf('  -> %d DC buses exported\n', n_dc_bus);

%% Export VSC converter results
fprintf('Exporting VSC converter results...\n');
n_vsc = size(convdc, 1);
if n_vsc > 0
    % Get AC bus voltages for each converter
    v_ac_pu = zeros(n_vsc, 1);
    v_dc_pu = zeros(n_vsc, 1);
    for i = 1:n_vsc
        % Find the DC bus row that matches this converter's DC bus number
        dc_bus_num = convdc(i, CONV_BUS);
        dc_bus_row = find(busdc(:, BUSDC_I) == dc_bus_num);

        if ~isempty(dc_bus_row)
            % Get AC bus ID from DC bus data
            ac_bus_id = busdc(dc_bus_row, BUSAC_I);

            % Get DC voltage
            v_dc_pu(i) = busdc(dc_bus_row, VDC);

            if ac_bus_id > 0
                ac_bus_idx = find(bus(:, BUS_I) == ac_bus_id);
                if ~isempty(ac_bus_idx)
                    v_ac_pu(i) = bus(ac_bus_idx, VM);
                end
            end
        end
    end

    % Calculate P_DC from P_AC - P_loss (for MatACDC, P_DC is calculated differently)
    p_dc_mw = convdc(:, PCCONV) + convdc(:, PCLOSS);  % P_dc = P_c + P_loss (sign convention)

    vsc_results = table(...
        convdc(:, CONV_BUS), ...
        convdc(:, PCONV), ...
        convdc(:, QCONV), ...
        p_dc_mw, ...
        convdc(:, PCLOSS), ...
        v_ac_pu, ...
        v_dc_pu, ...
        'VariableNames', {'dc_bus_id', 'p_ac_mw', 'q_ac_mvar', 'p_dc_mw', 'p_loss_mw', 'v_ac_pu', 'v_dc_pu'});
    writetable(vsc_results, fullfile(results_dir, 'res_vsc.csv'));
    fprintf('  -> %d VSC converters exported\n', n_vsc);
else
    fprintf('  -> No VSC converters found\n');
end

%% Export DC line results
fprintf('Exporting DC line results...\n');
n_dc_line = size(branchdc, 1);
if n_dc_line > 0
    p_loss_mw = branchdc(:, PFDC) + branchdc(:, PTDC);
    dc_line_results = table(...
        branchdc(:, F_BUSDC), ...
        branchdc(:, T_BUSDC), ...
        branchdc(:, PFDC), ...
        branchdc(:, PTDC), ...
        p_loss_mw, ...
        'VariableNames', {'from_bus', 'to_bus', 'p_from_mw', 'p_to_mw', 'p_loss_mw'});
    writetable(dc_line_results, fullfile(results_dir, 'res_dc_line.csv'));
    fprintf('  -> %d DC lines exported\n', n_dc_line);
else
    fprintf('  -> No DC lines found\n');
end

%% Save all results to MAT file
fprintf('Saving MATLAB workspace...\n');
save(fullfile(results_dir, 'case33_ieee_results.mat'), ...
    'resultsac', 'resultsdc', 'converged', 'timecalc', ...
    'baseMVA', 'bus', 'gen', 'branch', ...
    'pol', 'busdc', 'convdc', 'branchdc');
fprintf('  -> Saved to case33_ieee_results.mat\n');

%% Print summary
fprintf('\n========================================\n');
fprintf('RESULTS SUMMARY\n');
fprintf('========================================\n');
fprintf('AC System:\n');
fprintf('  Base MVA: %.1f\n', baseMVA);
fprintf('  Number of AC buses: %d\n', n_ac_bus);
fprintf('  Voltage range: %.4f - %.4f p.u.\n', min(bus(:, VM)), max(bus(:, VM)));
fprintf('  Angle range: %.2f - %.2f deg\n', min(bus(:, VA)), max(bus(:, VA)));

fprintf('\nDC System:\n');
fprintf('  Number of poles: %d\n', pol);
fprintf('  Number of DC buses: %d\n', n_dc_bus);
fprintf('  Number of DC grids: %d\n', max(busdc(:, GRIDDC)));
fprintf('  DC voltage range: %.4f - %.4f p.u.\n', min(busdc(:, VDC)), max(busdc(:, VDC)));

fprintf('\nConverters:\n');
fprintf('  Number of VSC converters: %d\n', n_vsc);
if n_vsc > 0
    fprintf('  Total P_AC injection: %.2f MW\n', sum(convdc(:, PCONV)));
    fprintf('  Total Q_AC injection: %.2f MVAr\n', sum(convdc(:, QCONV)));
    fprintf('  Total converter losses: %.2f MW\n', sum(convdc(:, PCLOSS)));
end

fprintf('\nDC Lines:\n');
fprintf('  Number of DC lines: %d\n', n_dc_line);
if n_dc_line > 0
    fprintf('  Total DC line losses: %.4f MW\n', sum(branchdc(:, PFDC) + branchdc(:, PTDC)));
end

fprintf('\nResults exported to: %s\n', results_dir);
fprintf('========================================\n\n');

end