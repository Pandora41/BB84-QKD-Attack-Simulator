"""
attacks/pns.py — Photon Number Splitting (PNS) Attack

This is the attack that breaks practical QKD systems.

The gap between theory and reality:
  Theory:   Alice sends exactly 1 photon per pulse → BB84 is provably secure
  Reality:  Alice uses an attenuated laser (weak coherent pulse)
            Photon count follows Poisson distribution with mean μ ≈ 0.1
            Some pulses contain 2 or more photons

What Eve does with multi-photon pulses:
  1. She sits on the channel with a quantum non-demolition (QND) measurement
  2. She measures the photon NUMBER without disturbing the quantum state
  3. For n=1 pulses: she must let them through (blocking reveals her presence)
  4. For n≥2 pulses: she splits off one photon, stores it in quantum memory
                     forwards n-1 photons to Bob (he notices nothing)
  5. After Alice and Bob publicly announce bases during sifting,
     Eve measures her stored copies in the correct basis
  6. Eve gets perfect information on every multi-photon pulse — silently

Why this is devastating:
  At μ=0.1, roughly 0.5% of pulses have n≥2 (from Poisson distribution)
  That's a small fraction but Eve gets PERFECT information on those bits
  with ZERO error introduction
  
  Compare to intercept-resend: Eve gets imperfect info with 25% error cost
  PNS: Eve gets perfect info for free on the multi-photon pulses

The fix in real systems: decoy state protocol (adds random μ variation
to let Alice and Bob detect channel statistics manipulation)
"""

import numpy as np
from typing import Tuple, Dict, Any
from scipy.stats import poisson
from qkd.photon import Photon, Basis, Bit, measure, encode


class PNS:
    """
    Photon Number Splitting attack on weak coherent pulse BB84.

    Requires BB84 to be initialized with use_wcp=True and mu set.
    Single-photon pulses are passed through untouched.
    Multi-photon pulses: Eve splits, stores, and will measure after sifting.

    Parameters
    ----------
    mu : float
        Mean photon number of Alice's source (should match BB84's mu)
    block_single_photons : bool
        If True, Eve blocks single-photon pulses entirely.
        This is a more aggressive strategy — detectable via lower key rate
        but Eve gets better information. Default False (passive attack).
    """

    def __init__(self, mu: float = 0.1, block_single_photons: bool = False):
        self.mu                    = mu
        self.block_single_photons  = block_single_photons
        self._stored: list         = []   # Eve's quantum memory

    def intercept(self, photon: Photon) -> Tuple[Photon, Dict[str, Any]]:
        n = photon.photon_count

        if n == 0:
            # Vacuum pulse — nothing to intercept, Bob gets nothing
            return photon, {"intercepted": False, "basis": None, "result": None,
                            "pns_split": False, "n_photons": 0}

        if n == 1:
            if self.block_single_photons:
                # Eve blocks it — Bob's sift rate drops, detectable
                # We simulate by randomizing the photon state
                dummy_basis = np.random.choice(list(Basis))
                dummy_bit   = Bit(np.random.randint(0, 2))
                blocked     = encode(dummy_bit, dummy_basis)
                return blocked, {"intercepted": True, "basis": None,
                                 "result": None, "pns_split": False,
                                 "n_photons": 1, "blocked": True}
            else:
                # Pass through — Eve learns nothing about this photon
                return photon, {"intercepted": False, "basis": None,
                                "result": None, "pns_split": False,
                                "n_photons": 1}

        # n >= 2: Eve splits one photon off
        # The photon state is identical across all copies (same quantum state)
        # Eve stores her copy — will measure later when basis is announced
        # Forward n-1 photons to Bob (Bob notices nothing unusual)

        stored_photon = Photon(
            state        = photon.state.copy(),
            basis        = photon.basis,   # Eve doesn't know this yet
            bit          = photon.bit,     # Eve doesn't know this yet
            photon_count = 1
        )
        self._stored.append(stored_photon)

        # Forward the rest — Bob gets n-1 photons, protocol continues normally
        photon.photon_count = n - 1

        return photon, {
            "intercepted": True,
            "basis":       None,    # Eve hasn't measured yet
            "result":      None,    # will measure after basis announcement
            "pns_split":   True,
            "n_photons":   n,
        }

    def measure_stored(self, announced_bases: list) -> list:
        """
        After Alice publicly announces her bases during sifting,
        Eve measures all her stored photons in the correct basis.
        
        This is what makes PNS so powerful — Eve measures with perfect
        basis information, so she never makes a wrong-basis error.
        
        Returns list of (bit, basis) tuples — Eve's recovered key bits.
        """
        results = []
        for photon, basis in zip(self._stored, announced_bases):
            result = measure(photon, basis)
            results.append((result, basis))
        return results

    @staticmethod
    def multi_photon_probability(mu: float) -> float:
        """
        Probability that a pulse contains 2 or more photons.
        P(n >= 2) = 1 - P(0) - P(1) = 1 - e^-μ - μe^-μ
        
        At μ=0.1: ~0.467% of pulses are vulnerable
        At μ=0.5: ~9.02% of pulses are vulnerable
        """
        p0 = poisson.pmf(0, mu)
        p1 = poisson.pmf(1, mu)
        return 1 - p0 - p1

    @staticmethod
    def photon_number_distribution(mu: float, max_n: int = 5) -> Dict[int, float]:
        """Return P(n) for n in 0..max_n given mean photon number mu."""
        return {n: float(poisson.pmf(n, mu)) for n in range(max_n + 1)}

    @staticmethod
    def information_per_key_bit(mu: float) -> float:
        """
        Fraction of sifted key bits that Eve knows perfectly via PNS.
        
        Roughly: P(n>=2) / P(n>=1) — the fraction of non-vacuum pulses
        that were multi-photon.
        
        This is a lower bound on Eve's information in the passive attack.
        """
        p_multi  = PNS.multi_photon_probability(mu)
        p_single = poisson.pmf(1, mu)
        p_useful = p_single + p_multi
        if p_useful == 0:
            return 0.0
        return p_multi / p_useful
