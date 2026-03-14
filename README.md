# ACDCPF

**Hybrid AC/DC Power Flow Library**

A Python library for steady-state power flow analysis in hybrid AC/DC networks, implementing the sequential AC/DC power flow method based on [Beerten et al. (2012)](#references).

## Features

- Multi-terminal VSC-HVDC systems with six converter control modes (P-Q, P-Vac, Vdc-Q, Vdc-Vac, Droop-Q, Droop-Vac)
- DC-DC converters for interconnecting DC grids at different voltage levels
- Multiple independent DC grids with proper voltage control coordination
- DC loads and generators
- Newton-Raphson solvers for both AC and DC sub-problems
- Built-in test networks (CIGRE B4, IEEE 33-bus, IEEE 24-bus RTS, 5-bus Stagg)

## Installation

```bash
git clone https://github.com/your-username/acdcpf.git
cd acdcpf
pip install -e .
```

Or install dependencies only:

```bash
pip install numpy scipy pandas pypower
```

## Quick Start

```python
import acdcpf as pf

# Load a built-in test network
net = pf.create_cigre_b4_dc_test_system()

# Run power flow
converged = pf.run_pf(net, verbose=True)

# Access results
print(net.res_ac_bus)   # AC bus voltages and power injections
print(net.res_dc_bus)   # DC bus voltages
print(net.res_vsc)      # VSC converter results
```

### Build a Network from Scratch

```python
import acdcpf as pf

net = pf.create_empty_network(name="My HVDC", s_base=100.0)

# AC side
b0 = pf.create_ac_bus(net, vr_kv=380.0, name="AC-Slack")
b1 = pf.create_ac_bus(net, vr_kv=380.0, name="AC-Load")
pf.create_ac_line(net, b0, b1, length_km=100,
                  r_ohm_per_km=0.02, x_ohm_per_km=0.268)
pf.create_ac_gen(net, bus=b0, p_mw=0.0, v_pu=1.0)
pf.create_ac_load(net, bus=b1, p_mw=500.0, q_mvar=100.0)

# DC side
dc0 = pf.create_dc_bus(net, v_base=400.0, bus_type="vdc", v_dc_pu=1.0)
dc1 = pf.create_dc_bus(net, v_base=400.0, bus_type="p", v_dc_pu=1.0)
pf.create_dc_line(net, dc0, dc1, length_km=100, r_ohm_per_km=0.0114)

# VSC converters
pf.create_vsc(net, ac_bus=b0, dc_bus=dc0, s_mva=600,
              control_mode="vdc_q", v_dc_pu=1.0)
pf.create_vsc(net, ac_bus=b1, dc_bus=dc1, s_mva=600,
              control_mode="p_q", p_mw=500.0)

converged = pf.run_pf(net, verbose=True)
```

## Built-in Test Networks

| Function | Description |
|----------|-------------|
| `create_2terminal_hvdc()` | Simple point-to-point HVDC |
| `create_case5_stagg_hvdc_ptp()` | 5-bus Stagg with HVDC link |
| `create_case5_stagg_mtdc_slack()` | 5-bus Stagg with MTDC (slack control) |
| `create_case5_stagg_mtdc_droop()` | 5-bus Stagg with MTDC (droop control) |
| `create_case33_ieee()` | IEEE 33-bus distribution with MTDC |
| `create_case33_ieee_ext()` | IEEE 33-bus extended with DC-DC converters |
| `create_case24_ieee_rts_mtdc()` | IEEE 24-bus RTS (3 zones) with MTDC |
| `create_cigre_b4_dc_test_system()` | CIGRE B4 DC Grid Test System |

## Documentation

See [`docs/users_manual.mdx`](docs/users_manual.mdx) for the full user manual, including:

- Complete API reference for all element types
- VSC control mode descriptions and equations
- Algorithm details (sequential AC/DC method, backward converter solver)
- DC-DC converter modeling
- Worked examples with code

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

## Project Structure

```
acdcpf/
├── acdcpf/                 # Main package
│   ├── build/              # Bus-branch model construction
│   ├── create/             # Element creation API
│   ├── networks/           # Built-in test networks
│   ├── powerflow/          # AC, DC, and sequential solvers
│   └── results/            # Result processing and export
├── tests/                  # Test suite
├── examples/               # Usage examples and validation scripts
├── docs/                   # Documentation
├── pyproject.toml          # Package configuration
├── LICENSE                 # MIT License
└── README.md
```

## References

1. J. Beerten, S. Cole, R. Belmans, "Generalized Steady-State VSC MTDC Model for Sequential AC/DC Power Flow Algorithms", *IEEE Trans. Power Systems*, vol. 27, no. 1, pp. 428-436, 2012.
2. T.K. Vrana et al., "The CIGRE B4 DC Grid Test System", *ELECTRA* No. 270, October 2013.

## License

MIT License. See [LICENSE](LICENSE) for details.
