"""
bb84.py — Core BB84 protocol

Alice sends photons. Bob measures. They sift by basis agreement.
Eve can be injected between Alice and Bob.

The protocol returns full statistics so the analysis layer
can compute QBER, mutual information, detection probability.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List
from qkd.photon import Bit, Basis, Photon, encode, measure, weak_coherent_pulse


@dataclass
class TransmissionRecord:
    """Full record of a single photon transmission."""
    # Alice
    alice_bit:    Bit
    alice_basis:  Basis

    # Eve (None if no eavesdropping)
    eve_basis:    Optional[Basis]  = None
    eve_result:   Optional[Bit]    = None
    eve_intercepted: bool          = False

    # Bob
    bob_basis:    Optional[Basis]  = None
    bob_result:   Optional[Bit]    = None

    # Sifting
    basis_match:  bool             = False   # Alice and Bob used same basis
    in_sifted_key: bool            = False   # kept after sifting
    is_error:     bool             = False   # Bob got wrong bit (in sifted key)

    # Photon
    photon_count: int              = 1       # for weak coherent pulse analysis


@dataclass
class BB84Result:
    """Aggregated results from a full BB84 run."""
    records: List[TransmissionRecord]

    # Key material
    sifted_key_alice: List[Bit] = field(default_factory=list)
    sifted_key_bob:   List[Bit] = field(default_factory=list)

    # Metrics
    n_photons:       int   = 0
    n_sifted:        int   = 0
    n_errors:        int   = 0
    qber:            float = 0.0     # quantum bit error rate
    sift_ratio:      float = 0.0     # fraction of photons kept after sifting

    # Eve metrics
    n_intercepted:   int   = 0
    eve_correct:     int   = 0       # times Eve got the right bit
    eve_information: float = 0.0     # mutual information estimate I(A:E)

    def summary(self) -> str:
        lines = [
            f"Photons sent:       {self.n_photons}",
            f"Sifted key length:  {self.n_sifted}",
            f"Sift ratio:         {self.sift_ratio:.1%}",
            f"QBER:               {self.qber:.3%}",
            f"Eve intercepted:    {self.n_intercepted} ({self.n_intercepted/max(self.n_photons,1):.1%})",
            f"Eve information:    {self.eve_information:.3f} bits/bit",
        ]
        return "\n".join(lines)


class BB84:
    """
    BB84 Quantum Key Distribution protocol simulator.

    Usage:
        protocol = BB84(n_photons=10000, noise=0.01)
        result   = protocol.run()                    # no Eve
        result   = protocol.run(eve=InterceptResend(rate=0.3))

    Parameters
    ----------
    n_photons : int
        Number of photons Alice sends
    noise : float
        Channel noise — baseline QBER without any eavesdropping
        Typical real systems: 0.01 to 0.05
    use_wcp : bool
        Use weak coherent pulse model (realistic) instead of perfect single photons
    mu : float
        Mean photon number per pulse (only used if use_wcp=True)
        Typical value: 0.1
    """

    def __init__(self,
                 n_photons: int  = 10000,
                 noise:     float = 0.01,
                 use_wcp:   bool  = False,
                 mu:        float = 0.1):
        self.n_photons = n_photons
        self.noise     = noise
        self.use_wcp   = use_wcp
        self.mu        = mu

    def run(self, eve=None) -> BB84Result:
        """
        Run the full BB84 protocol.
        
        Eve is any object with an .intercept(photon) -> photon method.
        If None, no eavesdropping.
        """
        records = []

        for _ in range(self.n_photons):
            # --- Alice ---
            alice_bit   = Bit(np.random.randint(0, 2))
            alice_basis = np.random.choice(list(Basis))

            if self.use_wcp:
                photon = weak_coherent_pulse(alice_bit, alice_basis, self.mu)
            else:
                photon = encode(alice_bit, alice_basis)

            rec = TransmissionRecord(
                alice_bit   = alice_bit,
                alice_basis = alice_basis,
                photon_count= photon.photon_count,
            )

            # --- Eve (optional) ---
            if eve is not None:
                photon, eve_meta = eve.intercept(photon)
                rec.eve_intercepted = eve_meta.get("intercepted", False)
                rec.eve_basis       = eve_meta.get("basis",       None)
                rec.eve_result      = eve_meta.get("result",      None)

            # --- Channel noise ---
            # Independently of Eve, channel noise can flip the photon state
            if np.random.random() < self.noise:
                # Simulate depolarizing noise — random re-encoding
                noise_basis = np.random.choice(list(Basis))
                noise_bit   = Bit(np.random.randint(0, 2))
                photon.state = encode(noise_bit, noise_basis).state

            # --- Bob ---
            bob_basis  = np.random.choice(list(Basis))
            bob_result = measure(photon, bob_basis)

            rec.bob_basis  = bob_basis
            rec.bob_result = bob_result

            # --- Sifting ---
            rec.basis_match = (alice_basis == bob_basis)
            if rec.basis_match:
                rec.in_sifted_key = True
                rec.is_error      = (bob_result != alice_bit)

            records.append(rec)

        return self._compute_results(records)

    def _compute_results(self, records: List[TransmissionRecord]) -> BB84Result:
        result = BB84Result(records=records)
        result.n_photons = len(records)

        sifted = [r for r in records if r.in_sifted_key]
        result.n_sifted   = len(sifted)
        result.sift_ratio = result.n_sifted / max(result.n_photons, 1)

        result.sifted_key_alice = [r.alice_bit  for r in sifted]
        result.sifted_key_bob   = [r.bob_result for r in sifted]

        result.n_errors = sum(r.is_error for r in sifted)
        result.qber     = result.n_errors / max(result.n_sifted, 1)

        # Eve statistics
        intercepted = [r for r in records if r.eve_intercepted]
        result.n_intercepted = len(intercepted)

        if intercepted:
            result.eve_correct = sum(
                r.eve_result == r.alice_bit
                for r in intercepted
                if r.eve_result is not None
            )
            # Mutual information estimate: I(A:E) = 1 - H(error_rate)
            eve_error_rate = 1 - result.eve_correct / max(result.n_intercepted, 1)
            result.eve_information = self._binary_entropy_complement(eve_error_rate)

        return result

    @staticmethod
    def _binary_entropy_complement(e: float) -> float:
        """1 - H(e) where H is binary entropy. Measures information gained."""
        e = np.clip(e, 1e-10, 1 - 1e-10)
        h = -e * np.log2(e) - (1 - e) * np.log2(1 - e)
        return max(0.0, 1 - h)
