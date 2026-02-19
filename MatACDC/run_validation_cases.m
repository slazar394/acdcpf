%% run_validation_cases.m
% Run all MatACDC test cases and export results for Python validation.
%
% This script runs each AC/DC case pair through runacdcpf and saves
% the results to JSON files that can be compared against acdcpf results.
%
% Usage:
%   cd MatACDC
%   run_validation_cases
%
% Output:
%   Creates 'validation_results/' folder with JSON files for each case.

clear; clc;

%% Setup paths
addpath(genpath(pwd));

%% Create output directory
outdir = 'validation_results';
if ~exist(outdir, 'dir')
    mkdir(outdir);
end

%% Define test cases
% Each row: {case_name, ac_case, dc_case}
test_cases = {
    'case5_stagg_hvdc_ptp',    'case5_stagg', 'case5_stagg_HVDCptp';
    'case5_stagg_mtdc_slack',  'case5_stagg', 'case5_stagg_MTDCslack';
    'case5_stagg_mtdc_droop',  'case5_stagg', 'case5_stagg_MTDCdroop';
    'case24_ieee_rts_mtdc',    'case24_ieee_rts1996_3zones', 'case24_ieee_rts1996_MTDC';
};

%% Define indices (from MatACDC idx_ functions)
% Bus indices
BUS_I = 1; BUS_TYPE = 2; PD = 3; QD = 4; GS = 5; BS = 6;
BUS_AREA = 7; VM = 8; VA = 9; BASE_KV = 10; ZONE = 11; VMAX = 12; VMIN = 13;

% Generator indices
GEN_BUS = 1; PG = 2; QG = 3; QMAX = 4; QMIN = 5; VG = 6;

% Branch indices
F_BUS = 1; T_BUS = 2; BR_R = 3; BR_X = 4; BR_B = 5;
PF = 14; QF = 15; PT = 16; QT = 17;

% DC bus indices
BUSDC_I = 1; BUSAC_I = 2; GRIDDC = 3; PDC = 4; VDC = 5; BASE_KVDC = 6;

% Converter indices
CONV_BUS = 1; CONVTYPE_DC = 2; CONVTYPE_AC = 3;
PCONV = 4; QCONV = 5; VCONV = 6;
VMC = 30; VAC = 31; PCCONV = 32; QCCONV = 33; PCLOSS = 34;

% DC branch indices
F_BUSDC = 1; T_BUSDC = 2; BRDC_R = 3;
PFDC = 10; PTDC = 11;

%% Run each test case
fprintf('=%.0s', 1:70); fprintf('\n');
fprintf('MatACDC Validation Results Export\n');
fprintf('=%.0s', 1:70); fprintf('\n\n');

results_summary = {};

for i = 1:size(test_cases, 1)
    case_name = test_cases{i, 1};
    ac_case = test_cases{i, 2};
    dc_case = test_cases{i, 3};

    fprintf('Running: %s\n', case_name);
    fprintf('  AC case: %s\n', ac_case);
    fprintf('  DC case: %s\n', dc_case);

    try
        %% Run power flow
        % Suppress output during run
        macdcopt = macdcoption;
        macdcopt(13) = 0;  % Disable output
        mpopt = mpoption('verbose', 0, 'out.all', 0);

        [resultsac, resultsdc, converged, timecalc] = runacdcpf(ac_case, dc_case, macdcopt, mpopt);

        %% Extract results
        results = struct();
        results.case_name = case_name;
        results.ac_case = ac_case;
        results.dc_case = dc_case;
        results.converged = converged;
        results.time_seconds = timecalc;

        % AC bus results
        bus = resultsac.bus;
        results.ac_bus = struct();
        results.ac_bus.bus_i = bus(:, BUS_I)';
        results.ac_bus.vm_pu = bus(:, VM)';
        results.ac_bus.va_deg = bus(:, VA)';
        results.ac_bus.pd_mw = bus(:, PD)';
        results.ac_bus.qd_mvar = bus(:, QD)';
        results.ac_bus.base_kv = bus(:, BASE_KV)';

        % AC generator results
        gen = resultsac.gen;
        results.ac_gen = struct();
        results.ac_gen.bus = gen(:, GEN_BUS)';
        results.ac_gen.pg_mw = gen(:, PG)';
        results.ac_gen.qg_mvar = gen(:, QG)';

        % AC branch results
        branch = resultsac.branch;
        results.ac_branch = struct();
        results.ac_branch.from_bus = branch(:, F_BUS)';
        results.ac_branch.to_bus = branch(:, T_BUS)';
        if size(branch, 2) >= QT
            results.ac_branch.pf_mw = branch(:, PF)';
            results.ac_branch.qf_mvar = branch(:, QF)';
            results.ac_branch.pt_mw = branch(:, PT)';
            results.ac_branch.qt_mvar = branch(:, QT)';
        end

        % DC bus results
        busdc = resultsdc.busdc;
        results.dc_bus = struct();
        results.dc_bus.busdc_i = busdc(:, BUSDC_I)';
        results.dc_bus.busac_i = busdc(:, BUSAC_I)';
        results.dc_bus.grid = busdc(:, GRIDDC)';
        results.dc_bus.pdc_mw = busdc(:, PDC)';
        results.dc_bus.vdc_pu = busdc(:, VDC)';
        results.dc_bus.base_kv = busdc(:, BASE_KVDC)';

        % Converter results
        convdc = resultsdc.convdc;
        results.converter = struct();
        results.converter.busdc_i = convdc(:, CONV_BUS)';
        results.converter.type_dc = convdc(:, CONVTYPE_DC)';
        results.converter.type_ac = convdc(:, CONVTYPE_AC)';
        results.converter.ps_mw = convdc(:, PCONV)';      % Grid-side P
        results.converter.qs_mvar = convdc(:, QCONV)';    % Grid-side Q
        if size(convdc, 2) >= PCLOSS
            results.converter.vm_conv_pu = convdc(:, VMC)';
            results.converter.va_conv_deg = convdc(:, VAC)';
            results.converter.pc_mw = convdc(:, PCCONV)';     % Converter-side P
            results.converter.qc_mvar = convdc(:, QCCONV)';   % Converter-side Q
            results.converter.ploss_mw = convdc(:, PCLOSS)';  % Losses
        end

        % DC branch results
        branchdc = resultsdc.branchdc;
        results.dc_branch = struct();
        results.dc_branch.from_bus = branchdc(:, F_BUSDC)';
        results.dc_branch.to_bus = branchdc(:, T_BUSDC)';
        results.dc_branch.r_pu = branchdc(:, BRDC_R)';
        if size(branchdc, 2) >= PTDC
            results.dc_branch.pf_mw = branchdc(:, PFDC)';
            results.dc_branch.pt_mw = branchdc(:, PTDC)';
        end

        % System info
        results.baseMVA = resultsac.baseMVA;
        results.pol = resultsdc.pol;

        %% Save to JSON
        json_file = fullfile(outdir, [case_name, '.json']);
        save_json(json_file, results);

        fprintf('  Status: CONVERGED = %d\n', converged);
        fprintf('  Time: %.3f seconds\n', timecalc);
        fprintf('  Saved: %s\n\n', json_file);

        results_summary{end+1} = struct('name', case_name, 'converged', converged, 'time', timecalc);

    catch ME
        fprintf('  ERROR: %s\n\n', ME.message);
        results_summary{end+1} = struct('name', case_name, 'converged', -1, 'error', ME.message);
    end
end

%% Print summary
fprintf('=%.0s', 1:70); fprintf('\n');
fprintf('Summary\n');
fprintf('=%.0s', 1:70); fprintf('\n');
for i = 1:length(results_summary)
    r = results_summary{i};
    if r.converged == 1
        fprintf('  %-30s PASS (%.3fs)\n', r.name, r.time);
    elseif r.converged == 0
        fprintf('  %-30s FAIL (did not converge)\n', r.name);
    else
        fprintf('  %-30s ERROR\n', r.name);
    end
end
fprintf('=%.0s', 1:70); fprintf('\n');
fprintf('Results saved to: %s/\n', outdir);


%% Helper function to save struct as JSON
function save_json(filename, data)
    % Convert struct to JSON and save
    json_str = jsonencode(data);

    % Pretty print (basic formatting)
    json_str = strrep(json_str, ',"', sprintf(',\n  "'));
    json_str = strrep(json_str, '{', sprintf('{\n  '));
    json_str = strrep(json_str, '}', sprintf('\n}'));

    fid = fopen(filename, 'w');
    fprintf(fid, '%s', json_str);
    fclose(fid);
end
