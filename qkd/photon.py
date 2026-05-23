"""
photon.py — Quantum state primitives for BB84

Two models:
  - SinglePhoton: ideal, theoretically perfect source
  - WeakCoherentPulse: realistic laser source (Poisson distributed photon number)
                       this is what real QKD hardware uses, and what PNS attacks exploit
"""

import numpy as np
from dataclasses import dataclass
from enum import Enum


class Basis(Enum):
    RECTILINEAR = "+"   # |0> = horizontal, |1> = vertical
    DIAGONAL    = "x"   # |0> = 45deg, |1> = 135deg


class Bit(Enum):
    ZERO = 0
    ONE  = 1


# Basis vectors as numpy arrays
# Rectilinear basis
H = np.array([1, 0], dtype=complex)   # horizontal  → |0> in + basis
V = np.array([0, 1], dtype=complex)   # vertical    → |1> in + basis

# Diagonal basis
D = np.array([1,  1], dtype=complex) / np.sqrt(2)   # 45deg  → |0> in x basis
A = np.array([1, -1], dtype=complex) / np.sqrt(2)   # 135deg → |1> in x basis

# Map (basis, bit) → quantum state vector
STATE = {
    (Basis.RECTILINEAR, Bit.ZERO): H,
    (Basis.RECTILINEAR, Bit.ONE):  V,
    (Basis.DIAGONAL,    Bit.ZERO): D,
    (Basis.DIAGONAL,    Bit.ONE):  A,
}

# Measurement projectors: P = |ψ><ψ|
PROJECTORS = {basis: [np.outer(STATE[(basis, b)], STATE[(basis, b)].conj())
                      for b in Bit]
              for basis in Basis}


@dataclass
class Photon:
    """A single photon carrying a quantum state."""
    state: np.ndarray       # 2D complex vector
    basis: Basis            # encoding basis (known only to sender)
    bit: Bit                # encoded bit (known only to sender)
    photon_count: int = 1   # >1 means weak coherent pulse leaked extra photons


def encode(bit: Bit, basis: Basis) -> Photon:
    """Alice encodes a classical bit into a photon state."""
    return Photon(state=STATE[(basis, bit)].copy(), basis=basis, bit=bit)


def measure(photon: Photon, basis: Basis) -> Bit:
    """
    Measure a photon in the given basis.
    
    If basis matches encoding basis → correct bit, deterministic.
    If basis mismatches             → random result, 50/50.
    
    This is the Born rule: probability = |<ψ_measure|ψ_state>|²
    """
    projectors = PROJECTORS[basis]
    
    # Calculate probability of measuring |0> in this basis
    prob_zero = np.real(photon.state.conj() @ projectors[0] @ photon.state)
    prob_zero = np.clip(prob_zero, 0, 1)  # numerical safety
    
    outcome = Bit.ZERO if np.random.random() < prob_zero else Bit.ONE
    
    # Collapse the state (important for Eve — her measurement disturbs the photon)
    photon.state = STATE[(basis, outcome)].copy()
    
    return outcome


def weak_coherent_pulse(bit: Bit, basis: Basis, mu: float = 0.1) -> Photon:
    """
    Realistic photon source: laser attenuated to mean photon number mu.
    
    Photon count follows Poisson distribution.
    mu = 0.1 is typical for practical QKD systems.
    
    Pulses with n >= 2 photons are vulnerable to PNS attack:
    Eve can split off one photon and store it, forward the rest,
    then measure her copy after basis is publicly announced.
    """
    n = np.random.poisson(mu)
    photon = encode(bit, basis)
    photon.photon_count = n
    return photon
