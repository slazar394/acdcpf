# Changelog

All notable changes to acdcpf are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Sign error in the converter filter term (results change for stations with
  a filter).** `_calculate_converter_equations` and `_backward_converter_solve`
  computed the power continuing from the filter bus towards the phase reactor
  as `S_cf = S_sf + jQ_f` with `Q_f = −B_f·U_f²`, i.e. they treated the
  capacitive filter as an inductor. MatACDC writes that relation in its
  injection convention; in acdcpf's load convention it is `S_cf = S_sf − jQ_f`.
  The error changed the converter current, losses and the active power of
  slack/droop converters whenever `b_filter_pu > 0` (0.01–0.24 MW on the
  MatACDC reference cases). With the fix, all four MatACDC reference cases are
  reproduced to solver precision (≈1e-7 MW), and the tolerances in
  `tests/test_matacdc_validation.py` were tightened from 0.1–0.3 MW to 1e-4 MW
  so that an error of this size can no longer pass. Stations without a filter
  (e.g. the hybrid IEEE 33-bus cases) are unaffected.
- **DC loads and generators at droop-controlled DC buses were dropped from the
  DC power balance.** In `calc_dc_power_mismatch` the droop-bus mismatch
  compared the converter's droop power alone with the bus's total net
  injection, so constant-power DC loads and DC generators connected to a droop
  bus were ignored and the DC solution did not conserve power (while still
  reporting convergence). The droop mismatch now includes the bus's
  non-converter injection. `tests/test_dc_droop_local_injection.py` locks DC
  power conservation, the droop-bus balance and the droop characteristic.
- **Droop constants of `create_case5_stagg_mtdc_droop` were 345× too stiff.**
  The MatACDC `DROOP` column is a per-unit voltage change per MW
  (`PVdroop = DROOP·baseMVA`), whereas `droop_kv_per_mw` is in kV/MW; the two
  are related by `k[kV/MW] = DROOP · basekVdc`. The case entered the MatACDC
  values unconverted (0.005/0.007 instead of 1.725/2.415 kV/MW). Corrected; the
  case now matches its MatACDC reference to solver precision.
- **`loading_percent` and `i_c_loading_percent` now coincide.** The entry below
  attributed their disagreement to MatACDC's power-plane current circle not
  coinciding with the physical current. That was a consequence of the filter
  sign error: the circle is exact for the phase-reactor current, and with the
  corrected station equations both columns agree to solver precision.
- **Documentation error on the DC base voltage convention.** `create_dc_bus`
  and two places in the user manual stated that `v_base` is the pole-to-pole
  voltage when `pol = 2`. It is the pole-to-ground (per-pole) voltage for every
  value of `pol`, and `r_ohm_per_km` on a DC line is the resistance of a single
  conductor. This is a docs-only correction, reported by Victor Tibanlombo
  (Tool #7). No solver behaviour changed, and no result changes.
  The code has always solved MatACDC Eq. (14),
  `P_dc,i = p · U_dc,i · Σ_j Y_dc,ij · (U_dc,i − U_dc,j)`, which is written in
  per-pole voltages and per-conductor resistances, so the `pol` factor is what
  accounts for the second conductor. The rest of the manual already documented
  the correct convention (`v_base` "per pole"), so the two wrong statements
  contradicted it. `tests/test_dc_pole_convention.py` (17 tests) now locks the
  three observable consequences on minimal two-bus DC cases with no AC side and
  no converters: the reported triple satisfies `P = pol · U · I`, `i_ka` is the
  current in one conductor and does not scale with `pol`, and line losses are
  `pol · I² · R`.
- **Converter `loading_percent` now reflects the enforced quantity.** When the
  full capability limit set is defined (`i_max_pu`, `vc_max_pu`, `vc_min_pu`),
  loading is reported as the utilisation of the MatACDC current-limit circle,
  `100 · |s_inj − mpl1| / r_l1` with `s_inj = −(P_s + jQ_s)` — the exact
  boundary the limiter (`_convlim`) enforces in the `(P_s, Q_s)` power plane.
  This agrees with the limiter's verdict by construction: a converged point it
  deems feasible (`viol == 0`) reports ≤ 100 %, so no spurious overload warning
  fires on a converter it considers legal. Neither the grid-side apparent power
  `|S_s| / s_mva` (double-counts transformer/filter reactive consumption) nor
  the physical phase-reactor current ratio `|I_c| / i_max_pu` (a current-plane
  quantity that does not coincide with MatACDC's power-plane circle, so it can
  read > 100 % at a feasible point) matches that boundary. `|S_s| / s_mva`
  remains the fallback when only a rating `s_mva` is known.
- **New `i_c_loading_percent` column on `net.res_vsc`.** Retains the physical
  phase-reactor current ratio `|I_c| / i_max_pu` (%) as a diagnostic, alongside
  the enforced `loading_percent`; `NaN` when the full limit set is absent.
- CHANGELOG: converter losses are computed in `_calculate_converter_equations`
  (and stored on the network), not in `process_converter_results`, which only
  reads them.

### Added

- **Opt-in Vdc-slack reactive limiting.** `run_pf` gained a standalone
  `enforce_slack_q_limits` flag (default `False`). When on, a Vdc-slack
  converter that also holds AC voltage (`vdc_vac`) has its reactive power
  bounded onto the capability region — dropping AC-voltage control and holding
  the clamped Q — while its slack active power (set by the DC balance) is never
  curtailed. Off by default preserves the current behaviour, matching MatACDC,
  which exempts slack converters from its capability check entirely.
- `run_pf` now warns when an in-service DC line joins buses carrying different
  `dc_grid` labels. `dc_grid` is user-supplied and not derived from DC-line
  connectivity; per-grid slack power sharing and the per-grid converter-limit
  correction both assume it matches the topology, and were previously silently
  wrong on a mismatch.

## [0.2.0] - 2026-09-15

### Changed

- **BREAKING (behaviour): converter limit enforcement is now on by default.**
  `run_pf` gained an `enforce_limits` parameter (default `True`) that applies
  the MatACDC PQ-capability-diagram limiter (`_convlim`) to non-slack VSCs and
  switches control modes on violation. Pass `enforce_limits=False` to reproduce
  the previous unconstrained behaviour (MatACDC `limac = 0`).
- **`from_matacdc`: ICMAX is now read consistently as per-unit.** The converter
  apparent-power rating is now `s_mva = Imax_pu * baseMVA`, matching the
  per-unit value used by the capability-diagram limiter and the adjacent
  per-unit VCMAX/VCMIN fields. Previously the rating was computed as
  `sqrt(3) * basekVac * Imax` (treating ICMAX as kA), which disagreed with the
  limit actually enforced. A warning is emitted for ICMAX outside the plausible
  per-unit range `[0.1, 5.0]`.

### Added

- Convergence flag now requires the AC and DC subproblems to have actually
  converged (`converged = max|dP_s| < tol AND ac_conv AND dc_conv`).
- VCMAX / VCMIN / ICMAX converter limits are imported from MatACDC `convdc`
  data and stored on the VSC (`i_max_pu`, `vc_max_pu`, `vc_min_pu`).
- `net.res_vsc` gains a `loading_percent` column (apparent power against the
  converter rating), so overloads are visible even for Vdc-slack converters
  that the limiter cannot curtail.
- Post-solve warnings are emitted for converters whose control mode was
  switched on a limit violation and for any converter (slack included) left
  loaded above its rating.

### Fixed

- `run_ac_pf` now reports the number of AC island solves performed instead of
  always returning `0`.
- Removed the unreachable `_calculate_converter_losses` helper (converter
  losses are computed in `_calculate_converter_equations` and stored on the
  network; `process_converter_results` only reads them).
- Dummy generators added for VSC AC-voltage control now carry the converter's
  physical reactive-power bound (`±s_mva`) instead of a magic `±9999`.

## [0.1.0]

- Initial release: sequential AC/DC power flow (Beerten Ch. 13), VSC and DC-DC
  converters, DC loads/generators, MatACDC import, CIGRE B4 test system.
