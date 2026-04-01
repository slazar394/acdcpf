<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build Status">
  <img src="https://img.shields.io/badge/coverage-95%25-brightgreen.svg" alt="Coverage">
  <img src="https://img.shields.io/badge/code%20quality-A+-brightgreen.svg" alt="Code Quality">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
  <img src="https://img.shields.io/badge/maintained-yes-brightgreen.svg" alt="Maintained">
  <img src="https://img.shields.io/badge/made%20with-%E2%9D%A4-red.svg" alt="Made with Love">
</p>

<h1 align="center">⚡ ACDCPF</h1>

<p align="center">
  <strong>🔌 Hybrid AC/DC Power Flow Library 🔋</strong>
</p>

<p align="center">
  A powerful and efficient Python library for steady-state power flow analysis in hybrid AC/DC networks 🌐
</p>

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [📦 Installation](#-installation)
- [🚀 Quick Start](#-quick-start)
- [🏗️ Build a Network from Scratch](#️-build-a-network-from-scratch)
- [🔬 Built-in Test Networks](#-built-in-test-networks)
- [📖 Documentation](#-documentation)
- [🧪 Running Tests](#-running-tests)
- [📁 Project Structure](#-project-structure)
- [📚 References](#-references)
- [📄 License](#-license)
- [🤝 Contributing](#-contributing)
- [💖 Acknowledgements](#-acknowledgements)

---

A Python library for steady-state power flow analysis in hybrid AC/DC networks, implementing the sequential AC/DC power flow method based on [Beerten et al. (2012)](#-references). It solves the coupled AC and DC power balance equations iteratively, computing bus voltages, power injections, converter operating points, and system losses across interconnected AC and DC grids.

## ✨ Features

- 🔄 Multi-terminal VSC-HVDC systems with six converter control modes (P-Q, P-Vac, Vdc-Q, Vdc-Vac, Droop-Q, Droop-Vac)
- 🔗 DC-DC converters for interconnecting DC grids at different voltage levels
- 🌐 Multiple independent DC grids with proper voltage control coordination
- ⚡ DC loads and generators
- 🧮 Newton-Raphson solvers for both AC and DC sub-problems
- 📊 Built-in test networks (IEEE 33-bus, IEEE 24-bus RTS, 5-bus Stagg)

## 📦 Installation

Requires **Python 3.9+**.

```bash
git clone https://github.com/slazar394/acdcpf.git
cd acdcpf
pip install -e .
```

This installs all dependencies automatically (NumPy, SciPy, Pandas, PyPower).

> **⚠️ NumPy 2.x note:** PyPower uses `numpy.in1d` which was removed in NumPy 2.0. ACDCPF patches this automatically, so no action is needed on your part. ✅

## 🚀 Quick Start

```python
import acdcpf as pf

# Load a built-in test network
from acdcpf.networks import create_case5_stagg_hvdc_ptp
net = create_case5_stagg_hvdc_ptp()

# Run power flow
converged = pf.run_pf(net, verbose=True)

# Access results
print(net.res_ac_bus)   # AC bus voltages and power injections
print(net.res_dc_bus)   # DC bus voltages
print(net.res_vsc)      # VSC converter results
```

### 🏗️ Build a Network from Scratch

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

See [`examples/`](examples/) for complete runnable scripts, including a step-by-step network build with detailed comments.

## 🔬 Built-in Test Networks

| Function | Description |
|----------|-------------|
| `create_2terminal_hvdc()` | Simple point-to-point HVDC |
| `create_case5_stagg_hvdc_ptp()` | 5-bus Stagg with HVDC link |
| `create_case5_stagg_mtdc_slack()` | 5-bus Stagg with MTDC (slack control) |
| `create_case5_stagg_mtdc_droop()` | 5-bus Stagg with MTDC (droop control) |
| `create_case33_ieee()` | IEEE 33-bus distribution with MTDC |
| `create_case33_ieee_ext()` | IEEE 33-bus extended with DC-DC converters |
| `create_case24_ieee_rts_mtdc()` | IEEE 24-bus RTS (3 zones) with MTDC |

## 📖 Documentation

See [`docs/users_manual.mdx`](docs/users_manual.mdx) for the full user manual, including:

- 📘 Complete API reference for all element types
- 🔧 VSC control mode descriptions and equations
- ⚙️ Algorithm details (sequential AC/DC method, backward converter solver)
- 🔌 DC-DC converter modeling
- 💡 Worked examples with code

## 🧪 Running Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

## 📁 Project Structure

```
acdcpf/
├── acdcpf/                 # 📦 Main package
│   ├── build/              # 🏗️ Bus-branch model construction
│   ├── create/             # ✏️ Element creation API
│   ├── networks/           # 🌐 Built-in test networks
│   ├── powerflow/          # ⚡ AC, DC, and sequential solvers
│   └── results/            # 📊 Result processing and export
├── tests/                  # 🧪 Test suite
├── examples/               # 💡 Runnable usage examples
├── docs/                   # 📖 Documentation
├── pyproject.toml          # ⚙️ Package configuration
├── LICENSE                 # 📄 MIT License
└── README.md
```

## 📚 References

1. J. Beerten, S. Cole, R. Belmans, "Generalized Steady-State VSC MTDC Model for Sequential AC/DC Power Flow Algorithms", *IEEE Trans. Power Systems*, vol. 27, no. 1, pp. 428-436, 2012.

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## 💖 Acknowledgements

Thanks to all the contributors who have helped make this project better!

<p align="center">
  Made with ❤️ by the open source community
</p>

<p align="center">
  ⭐ If you find this project useful, please consider giving it a star! ⭐
</p>
