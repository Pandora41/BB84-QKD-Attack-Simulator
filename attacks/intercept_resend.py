"""
attacks/intercept_resend.py — Eve's intercept-resend attack strategies

InterceptResend:  Eve intercepts every photon
PartialIntercept: Eve intercepts fraction η of photons — the interesting case

The key insight: Eve faces a fundamental tradeoff.
Every photon she touches risks introducing a detectable error.
But every photon she ignores gives her zero information.

This module lets you sweep η from 0 to 1 and observe that tradeoff.
"""

import numpy as np
from typing import Tuple, Dict, Any
from qkd.photon import Photon, Basis, Bit, measure, encode


class InterceptResend:
    """
    Naive intercept-resend attack.

    Eve intercepts every photon, measures in a random basis,
    then re-encodes and forwards based on her measurement result.

    Why this is detectable:
    - Eve guesses wrong basis 50% of the time
    - Wrong basis measurement collapses the photon to a random state
    - When Bob measures these disturbed photons (in correct basis),
      he gets the wrong answer 50% of those times
    - Net QBER contribution: 0.5 × 0.5 = 0.25 (25%)

    Information Eve gains: ~0.5 bits per intercepted bit
    (she's right when she guesses the correct basis)
    """

    def intercept(self, photon: Photon) -> Tuple[Photon, Dict[str, Any]]:
        # Eve picks a random basis — she doesn't know Alice's
        eve_basis  = np.random.choice(list(Basis))
        eve_result = measure(photon, eve_basis)   # collapses the state

        # Eve re-encodes and forwards — she has no choice but to guess
        new_photon = encode(eve_result, eve_basis)
        new_photon.photon_count = photon.photon_count

        meta = {
            "intercepted": True,
            "basis":       eve_basis,
            "result":      eve_result,
        }
        return new_photon, meta


class PartialIntercept:
    """
    Partial intercept-resend attack.

    Eve intercepts a fraction η of photons, leaves the rest untouched.
    This is the strategically interesting attack.

    At η = 0:    Eve learns nothing, introduces no errors → undetected
    At η = 1:    Eve learns maximum, introduces 25% QBER → detected
    At η = 0.2:  Eve introduces ~5% extra QBER — below noise floor for noisy channels

    The question: what is the maximum η before Alice and Bob can detect her?
    Answer: depends on their noise threshold.
    If channel noise is 2% and they abort above 5% QBER,
    Eve can intercept up to ~12% of photons undetected.

    This is the core tradeoff the analysis notebook visualizes.

    Parameters
    ----------
    rate : float
        Fraction of photons Eve intercepts. 0 = none, 1 = all.
    """

    def __init__(self, rate: float = 0.5):
        assert 0.0 <= rate <= 1.0, "rate must be between 0 and 1"
        self.rate     = rate
        self._attacker = InterceptResend()

    def intercept(self, photon: Photon) -> Tuple[Photon, Dict[str, Any]]:
        if np.random.random() < self.rate:
            return self._attacker.intercept(photon)
        else:
            # Pass through untouched — Eve learns nothing about this photon
            return photon, {"intercepted": False, "basis": None, "result": None}

    @property
    def theoretical_qber(self) -> float:
        """
        Expected QBER contribution from this attack rate (ignoring channel noise).
        
        Derivation:
        - Eve intercepts fraction η
        - Of those, she guesses wrong basis 50% → introduces error 50% of those
        - QBER contribution = η × 0.5 × 0.5 = η/4
        """
        return self.rate * 0.25

    @staticmethod
    def detection_threshold_rate(noise: float, threshold: float) -> float:
        """
        Maximum interception rate before QBER exceeds detection threshold.
        
        total_QBER = noise + η/4
        threshold  = noise + η_max/4
        η_max      = 4 × (threshold - noise)

        Parameters
        ----------
        noise     : baseline channel noise (QBER without Eve)
        threshold : QBER level above which Alice and Bob abort
        """
        eta_max = 4 * (threshold - noise)
        return float(np.clip(eta_max, 0, 1))
