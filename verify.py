"""
Quick sanity check — runs all three attack scenarios and prints results.
Not a formal test suite, just verify things work before the notebook.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from qkd import BB84
from attacks import InterceptResend, PartialIntercept, PNS
from analysis import sweep_partial_intercept, sweep_mu, detection_analysis

print("=" * 55)
print("BB84 ATTACK ANALYSIS - SANITY CHECK")
print("=" * 55)

N = 3000

# --- 1. No Eve ---
print("\n[1] Clean channel (no Eve, noise=2%)")
result = BB84(n_photons=N, noise=0.02).run()
print(result.summary())
assert result.qber < 0.08, f"QBER too high without Eve: {result.qber}"

# --- 2. Full intercept-resend ---
print("\n[2] Full intercept-resend (Eve intercepts everything)")
result = BB84(n_photons=N, noise=0.0).run(eve=InterceptResend())
print(result.summary())
print(f"  Expected QBER ~25%, got {result.qber:.1%}")
assert 0.20 < result.qber < 0.30, f"QBER should be ~25%: {result.qber}"

# --- 3. Partial intercept sweep (just 3 points) ---
print("\n[3] Partial intercept sweep (eta = 0, 0.5, 1.0)")
for eta in [0.0, 0.5, 1.0]:
    eve    = PartialIntercept(rate=eta)
    result = BB84(n_photons=N, noise=0.02).run(eve=eve)
    theory = eve.theoretical_qber + 0.02
    print(f"  eta={eta:.1f}  QBER={result.qber:.3f}  theory={theory:.3f}  "
          f"I(A:E)={result.eve_information:.3f}")

# --- 4. PNS on weak coherent pulse ---
print("\n[4] PNS attack (mu=0.1, realistic QKD hardware)")
result = BB84(n_photons=N, noise=0.01, use_wcp=True, mu=0.1).run(eve=PNS(mu=0.1))
print(result.summary())
print(f"  Theoretical I(A:E) from multi-photon pulses: "
      f"{PNS.information_per_key_bit(0.1):.4f} bits/bit")
print("  Note: QBER unchanged - PNS introduces zero detectable errors")

# --- 5. Detection threshold analysis ---
print("\n[5] Detection threshold analysis")
analysis = detection_analysis(noise=0.02, threshold=0.05)
print(f"  {analysis['interpretation']}")

print("\n" + "=" * 55)
print("ALL CHECKS PASSED")
print("=" * 55)
