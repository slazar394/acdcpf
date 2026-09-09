% Regenerate convlim_golden.csv: reference outputs of MatACDC's convlim.m
% used by tests/test_convlim.py to validate the Python _convlim port.
%
% Run from the repository root in MATLAB/Octave:
%   run('tests/convlim_reference_data/generate_golden.m')
%
% Values are in MatACDC generator/injection convention (S_inj); the Python
% test negates to acdcpf's load convention. Keep the station parameters and
% limits below in sync with the Z_TF/Z_C/B_F/I_MAX/VC_MAX/VC_MIN constants in
% tests/test_convlim.py.

addpath(fullfile(fileparts(mfilename('fullpath')), '..', '..', 'MatACDC'));

Ztf = 0.0015 + 0.1121i; Zc = 0.0001 + 0.16428i; Bf = 0.0887;
Icmax = 1.1; Vcmax = 1.2; Vcmin = 0.85; epslim = 1e-4;

outf = fullfile(fileparts(mfilename('fullpath')), 'convlim_golden.csv');
fid = fopen(outf, 'w');
fprintf(fid, '# MatACDC convlim.m reference outputs (injection convention)\n');
fprintf(fid, '# Ztf=%.4f%+.4fi Zc=%.4f%+.4fi Bf=%.4f Icmax=%.2f Vcmax=%.2f Vcmin=%.2f epslim=%g\n', ...
    real(Ztf), imag(Ztf), real(Zc), imag(Zc), Bf, Icmax, Vcmax, Vcmin, epslim);
fprintf(fid, 'vsm,p_inj,q_inj,viol,p_new_inj,q_new_inj\n');

VSM = [0.95 1.0 1.05];
P = [-1.0 -0.5 0.0 0.3 0.5 0.8];
Q = [-1.2 -0.5 0.0 0.6 1.2 1.6];
for vi = 1:length(VSM)
  Vs = VSM(vi) + 0i;
  for ip = 1:length(P)
    for iq = 1:length(Q)
      Ss = P(ip) + 1i*Q(iq);
      [viol, SsNew, ~] = convlim(Ss, Vs, Vs, Ztf, Bf, Zc, Icmax, Vcmax, Vcmin, 1, epslim, 0);
      fprintf(fid, '%.10g,%.10g,%.10g,%d,%.10g,%.10g\n', ...
          VSM(vi), P(ip), Q(iq), viol, real(SsNew), imag(SsNew));
    end
  end
end
fclose(fid);
disp('convlim_golden.csv regenerated');
