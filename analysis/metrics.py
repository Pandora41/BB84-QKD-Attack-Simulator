"""
analysis/metrics.py — Sweep attacks across parameters, compute tradeoff curves

The main research contribution lives here:
  sweep_partial_intercept() → the η vs QBER vs I(A:E) tradeoff curve
  sweep_mu()                → PNS vulnerability vs photon number mean
"""

import numpy as np
from dataclasses import dataclass
from typing import List
from qkd.bb84 import BB84
from attacks.intercept_resend import PartialIntercept
from attacks.pns import PNS


@dataclass
class SweepPoint:
    """Single point in a parameter sweep."""
    parameter:       float   # the thing being swept (η or μ)
    qber:            float   # observed QBER
    qber_theoretical:float   # expected QBER from math
    eve_information: float   # estimated mutual information I(A:E)
    sifted_key_len:  int     # key bits available
    n_intercepted:   int     # photons Eve touched


def sweep_partial_intercept(
    rates:     np.ndarray = np.linspace(0, 1, 21),
    n_photons: int        = 5000,
    noise:     float      = 0.02,
) -> List[SweepPoint]:
    """
    Sweep Eve's interception rate η from 0 to 1.
    
    At each η, run BB84 with PartialIntercept(rate=η) and record:
    - Observed QBER (what Alice and Bob see)
    - Theoretical QBER (η/4 + noise)
    - Eve's information gain

    This produces the core tradeoff curve:
    As η increases, QBER increases linearly.
    Eve's information also increases — but she becomes more detectable.
    """
    results = []
    protocol = BB84(n_photons=n_photons, noise=noise)

    for eta in rates:
        eve    = PartialIntercept(rate=float(eta))
        result = protocol.run(eve=eve)

        point = SweepPoint(
            parameter        = float(eta),
            qber             = result.qber,
            qber_theoretical = noise + eve.theoretical_qber,
            eve_information  = result.eve_information,
            sifted_key_len   = result.n_sifted,
            n_intercepted    = result.n_intercepted,
        )
        results.append(point)

    return results


def sweep_mu(
    mus:       np.ndarray = np.linspace(0.01, 1.0, 30),
    n_photons: int        = 5000,
    noise:     float      = 0.01,
) -> List[SweepPoint]:
    """
    Sweep mean photon number μ from near-zero to 1.
    
    Shows how PNS vulnerability grows with μ.
    At μ=0.1 (practical): small but nonzero fraction of pulses exposed
    At μ=0.5 (sloppy):    significant fraction exposed
    
    Eve's information here is the fraction of key bits she knows perfectly
    (no errors introduced, no QBER increase — that's what makes PNS dangerous)
    """
    results = []

    for mu in mus:
        protocol = BB84(n_photons=n_photons, noise=noise, use_wcp=True, mu=float(mu))
        eve      = PNS(mu=float(mu))
        result   = protocol.run(eve=eve)

        # Eve's information from PNS: fraction of bits she knows perfectly
        theoretical_eve_info = PNS.information_per_key_bit(float(mu))

        point = SweepPoint(
            parameter        = float(mu),
            qber             = result.qber,
            qber_theoretical = noise,    # PNS introduces no extra QBER
            eve_information  = theoretical_eve_info,
            sifted_key_len   = result.n_sifted,
            n_intercepted    = result.n_intercepted,
        )
        results.append(point)

    return results


def detection_analysis(
    noise:     float = 0.02,
    threshold: float = 0.05,
) -> dict:
    """
    Compute the maximum safe interception rate for given noise and threshold.
    
    If Alice and Bob's channel has `noise` baseline QBER,
    and they abort if QBER > `threshold`,
    what is the maximum η Eve can use without triggering abort?
    
    Also computes Eve's information at that maximum safe rate.
    """
    eta_max = PartialIntercept.detection_threshold_rate(noise, threshold)
    eve_info_at_max = eta_max * 0.5   # approx: each intercepted bit gives 0.5 bits info

    return {
        "channel_noise":          noise,
        "detection_threshold":    threshold,
        "max_safe_intercept_rate": eta_max,
        "eve_info_at_max_rate":   eve_info_at_max,
        "interpretation": (
            f"With {noise:.0%} channel noise and {threshold:.0%} detection threshold, "
            f"Eve can intercept up to {eta_max:.1%} of photons undetected, "
            f"gaining ~{eve_info_at_max:.3f} bits of information per sifted key bit."
        )
    }
