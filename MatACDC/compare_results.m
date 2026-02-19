function compare_results(python_results_dir)
%COMPARE_RESULTS  Compare MatACDC results with Python acdcpf results.
%
%   COMPARE_RESULTS(PYTHON_RESULTS_DIR) compares the voltage results from
%   MatACDC (stored in ./results/) with Python acdcpf results.
%
%   Input:
%       python_results_dir - Path to directory containing Python CSV results
%                           (default: '../acdcpf/results')
%
%   The script compares:
%       - AC bus voltages (magnitude and angle)
%       - DC bus voltages
%       - VSC converter powers and losses

%% Setup paths
matacdc_dir = fileparts(mfilename('fullpath'));
matlab_results_dir = fullfile(matacdc_dir, 'results');

if nargin < 1 || isempty(python_results_dir)
    python_results_dir = fullfile(fileparts(matacdc_dir), 'acdcpf', 'results');
end

%% Check if directories exist
if ~exist(matlab_results_dir, 'dir')
    error('MATLAB results directory not found: %s\nRun run_case33_ieee.m first.', matlab_results_dir);
end

if ~exist(python_results_dir, 'dir')
    fprintf('Python results directory not found: %s\n', python_results_dir);
    fprintf('To compare results, run the Python power flow first and export results.\n');
    fprintf('\nDisplaying MATLAB results only:\n\n');
    display_matlab_results(matlab_results_dir);
    return;
end

%% Load MATLAB results
fprintf('\n========================================\n');
fprintf('COMPARING RESULTS: MatACDC vs acdcpf\n');
fprintf('========================================\n\n');

fprintf('MATLAB results: %s\n', matlab_results_dir);
fprintf('Python results: %s\n\n', python_results_dir);

%% Compare AC bus results
fprintf('--- AC BUS VOLTAGES ---\n');
matlab_ac = readtable(fullfile(matlab_results_dir, 'res_ac_bus.csv'));
python_ac_file = fullfile(python_results_dir, 'res_ac_bus.csv');

if exist(python_ac_file, 'file')
    python_ac = readtable(python_ac_file);

    % Find common buses
    common_buses = intersect(matlab_ac.bus_id, python_ac.Properties.RowNames);
    if isempty(common_buses) && ismember('bus_id', python_ac.Properties.VariableNames)
        common_buses = intersect(matlab_ac.bus_id, python_ac.bus_id);
    end

    fprintf('MATLAB buses: %d, Python buses: %d, Common: %d\n', ...
        height(matlab_ac), height(python_ac), length(common_buses));

    % If we can match buses, compare values
    if ~isempty(common_buses)
        fprintf('\nBus\t| MATLAB Vm\t| Python Vm\t| Diff\t\t| MATLAB Va\t| Python Va\t| Diff\n');
        fprintf('----\t|-----------\t|-----------\t|-------\t|-----------\t|-----------\t|-------\n');

        max_vm_diff = 0;
        max_va_diff = 0;

        for i = 1:min(10, length(common_buses))  % Show first 10 buses
            bus_id = common_buses(i);
            m_idx = find(matlab_ac.bus_id == bus_id);

            % Try to find Python data
            if isnumeric(python_ac.Properties.RowNames{1}(1))
                p_idx = find(str2double(python_ac.Properties.RowNames) == bus_id);
            else
                p_idx = find(python_ac.bus_id == bus_id);
            end

            if ~isempty(m_idx) && ~isempty(p_idx)
                m_vm = matlab_ac.v_pu(m_idx);
                p_vm = python_ac.v_pu(p_idx);
                vm_diff = abs(m_vm - p_vm);
                max_vm_diff = max(max_vm_diff, vm_diff);

                m_va = matlab_ac.v_angle_deg(m_idx);
                p_va = python_ac.v_angle_deg(p_idx);
                va_diff = abs(m_va - p_va);
                max_va_diff = max(max_va_diff, va_diff);

                fprintf('%d\t| %.6f\t| %.6f\t| %.2e\t| %.4f\t\t| %.4f\t\t| %.2e\n', ...
                    bus_id, m_vm, p_vm, vm_diff, m_va, p_va, va_diff);
            end
        end

        if length(common_buses) > 10
            fprintf('... (%d more buses)\n', length(common_buses) - 10);
        end

        fprintf('\nMax voltage magnitude difference: %.2e p.u.\n', max_vm_diff);
        fprintf('Max voltage angle difference: %.2e deg\n', max_va_diff);
    end
else
    fprintf('Python AC bus results not found.\n');
    fprintf('MATLAB AC bus voltage range: %.4f - %.4f p.u.\n', ...
        min(matlab_ac.v_pu), max(matlab_ac.v_pu));
end

%% Compare DC bus results
fprintf('\n--- DC BUS VOLTAGES ---\n');
matlab_dc = readtable(fullfile(matlab_results_dir, 'res_dc_bus.csv'));
python_dc_file = fullfile(python_results_dir, 'res_dc_bus.csv');

if exist(python_dc_file, 'file')
    python_dc = readtable(python_dc_file);

    fprintf('MATLAB DC buses: %d, Python DC buses: %d\n', ...
        height(matlab_dc), height(python_dc));

    fprintf('\nDC Bus\t| MATLAB Vdc\t| Python Vdc\t| Diff\n');
    fprintf('------\t|------------\t|------------\t|-------\n');

    max_vdc_diff = 0;
    n_compare = min(height(matlab_dc), height(python_dc));

    for i = 1:n_compare
        m_vdc = matlab_dc.v_dc_pu(i);

        % Try to get Python value
        if ismember('v_dc_pu', python_dc.Properties.VariableNames)
            p_vdc = python_dc.v_dc_pu(i);
        else
            p_vdc = NaN;
        end

        if ~isnan(p_vdc)
            vdc_diff = abs(m_vdc - p_vdc);
            max_vdc_diff = max(max_vdc_diff, vdc_diff);
            fprintf('%d\t| %.6f\t| %.6f\t| %.2e\n', ...
                matlab_dc.dc_bus_id(i), m_vdc, p_vdc, vdc_diff);
        else
            fprintf('%d\t| %.6f\t| N/A\t\t| N/A\n', ...
                matlab_dc.dc_bus_id(i), m_vdc);
        end
    end

    fprintf('\nMax DC voltage difference: %.2e p.u.\n', max_vdc_diff);
else
    fprintf('Python DC bus results not found.\n');
    fprintf('MATLAB DC bus voltage range: %.4f - %.4f p.u.\n', ...
        min(matlab_dc.v_dc_pu), max(matlab_dc.v_dc_pu));
end

%% Compare VSC results
fprintf('\n--- VSC CONVERTERS ---\n');
matlab_vsc = readtable(fullfile(matlab_results_dir, 'res_vsc.csv'));
python_vsc_file = fullfile(python_results_dir, 'res_vsc.csv');

if exist(python_vsc_file, 'file')
    python_vsc = readtable(python_vsc_file);

    fprintf('MATLAB VSCs: %d, Python VSCs: %d\n', ...
        height(matlab_vsc), height(python_vsc));

    fprintf('\nVSC\t| MATLAB P_ac\t| Python P_ac\t| MATLAB Q_ac\t| Python Q_ac\t| MATLAB P_loss\t| Python P_loss\n');
    fprintf('---\t|-------------\t|-------------\t|-------------\t|-------------\t|--------------\t|--------------\n');

    n_compare = min(height(matlab_vsc), height(python_vsc));
    for i = 1:n_compare
        m_pac = matlab_vsc.p_ac_mw(i);
        m_qac = matlab_vsc.q_ac_mvar(i);
        m_loss = matlab_vsc.p_loss_mw(i);

        if ismember('p_ac_mw', python_vsc.Properties.VariableNames)
            p_pac = python_vsc.p_ac_mw(i);
            p_qac = python_vsc.q_ac_mvar(i);
            p_loss = python_vsc.p_loss_mw(i);
        else
            p_pac = NaN; p_qac = NaN; p_loss = NaN;
        end

        fprintf('%d\t| %8.4f\t| %8.4f\t| %8.4f\t| %8.4f\t| %8.4f\t| %8.4f\n', ...
            i, m_pac, p_pac, m_qac, p_qac, m_loss, p_loss);
    end
else
    fprintf('Python VSC results not found.\n');
    fprintf('MATLAB VSC summary:\n');
    fprintf('  Total P_AC: %.4f MW\n', sum(matlab_vsc.p_ac_mw));
    fprintf('  Total Q_AC: %.4f MVAr\n', sum(matlab_vsc.q_ac_mvar));
    fprintf('  Total losses: %.4f MW\n', sum(matlab_vsc.p_loss_mw));
end

fprintf('\n========================================\n');
fprintf('Comparison complete.\n');
fprintf('========================================\n\n');

end


function display_matlab_results(results_dir)
%DISPLAY_MATLAB_RESULTS  Display MATLAB results when Python results unavailable.

fprintf('--- MATLAB RESULTS ---\n\n');

% AC bus results
fprintf('AC BUS VOLTAGES:\n');
ac = readtable(fullfile(results_dir, 'res_ac_bus.csv'));
fprintf('Bus\t| Vm (p.u.)\t| Va (deg)\n');
fprintf('----\t|----------\t|---------\n');
for i = 1:min(15, height(ac))
    fprintf('%d\t| %.6f\t| %.4f\n', ac.bus_id(i), ac.v_pu(i), ac.v_angle_deg(i));
end
if height(ac) > 15
    fprintf('... (%d more buses)\n', height(ac) - 15);
end

% DC bus results
fprintf('\nDC BUS VOLTAGES:\n');
dc = readtable(fullfile(results_dir, 'res_dc_bus.csv'));
fprintf('DC Bus\t| Vdc (p.u.)\t| Vdc (kV)\t| P (MW)\n');
fprintf('------\t|-----------\t|----------\t|--------\n');
for i = 1:height(dc)
    fprintf('%d\t| %.6f\t| %.4f\t| %.4f\n', ...
        dc.dc_bus_id(i), dc.v_dc_pu(i), dc.v_dc_kv(i), dc.p_mw(i));
end

% VSC results
fprintf('\nVSC CONVERTERS:\n');
vsc = readtable(fullfile(results_dir, 'res_vsc.csv'));
fprintf('DC Bus\t| P_ac (MW)\t| Q_ac (MVAr)\t| P_dc (MW)\t| P_loss (MW)\n');
fprintf('------\t|----------\t|------------\t|----------\t|------------\n');
for i = 1:height(vsc)
    fprintf('%d\t| %8.4f\t| %8.4f\t| %8.4f\t| %8.4f\n', ...
        vsc.dc_bus_id(i), vsc.p_ac_mw(i), vsc.q_ac_mvar(i), vsc.p_dc_mw(i), vsc.p_loss_mw(i));
end

end