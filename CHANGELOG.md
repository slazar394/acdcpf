# Changelog

All notable changes to acdcpf are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

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
