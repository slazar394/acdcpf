# Changelog

All notable changes to acdcpf are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  losses are computed in `process_converter_results`).
- Dummy generators added for VSC AC-voltage control now carry the converter's
  physical reactive-power bound (`±s_mva`) instead of a magic `±9999`.

## [0.1.0]

- Initial release: sequential AC/DC power flow (Beerten Ch. 13), VSC and DC-DC
  converters, DC loads/generators, MatACDC import, CIGRE B4 test system.
