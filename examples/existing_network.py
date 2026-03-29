"""
Example: Using a built-in test network

Loads the 5-bus Stagg system with a 3-terminal MTDC grid (slack control),
runs power flow, and prints the results.
"""
import acdcpf as pf
from acdcpf.networks import create_case5_stagg_mtdc_slack

# Load a built-in test network
net = create_case5_stagg_mtdc_slack()

# Run power flow
converged = pf.run_pf(net, verbose=True)

# Display results
print(f"\nConverged: {converged}")
print("\n=== AC Bus Results ===")
print(net.res_ac_bus)
print("\n=== DC Bus Results ===")
print(net.res_dc_bus)
print("\n=== VSC Converter Results ===")
print(net.res_vsc)
print("\n=== DC Line Results ===")
print(net.res_dc_line)
