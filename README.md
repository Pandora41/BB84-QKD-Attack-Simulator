# 🔐 BB84 QKD Attack Simulator

> *"The best encryption in the world is useless if Eve can steal the key silently."*

I built this because most QKD simulators only show the happy path — "look, quantum crypto works!" But I wanted to know what an attacker can actually steal, and what it costs her.

So this simulates the full BB84 protocol. From Eve's chair.

![Status](https://img.shields.io/badge/status-ongoing-yellow)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🔬 What Even Is This?

BB84 is a quantum key distribution protocol. Alice and Bob want to share a secret key. Eve wants to steal it. Quantum physics makes that surprisingly hard — but not impossible.

Most implementations just simulate Alice and Bob agreeing on a key and call it done. This one asks the uncomfortable question: **what if Eve is smarter than the demo assumes?**

Three attacks are modeled, in order of scariness:

| Attack | Info Eve gains | QBER cost | Detectable? |
|---|---|---|---|
| Full intercept-resend | ~50% per bit | +25% | Always |
| Partial intercept (eta) | ~eta × 50% | +eta/4 | Depends |
| PNS on real hardware | Perfect, on some bits | Zero | Not without decoy states |

That last one is the frightening one.

---

## 🧠 The Big Idea (No Physics Degree Required)

### Why a secret key?

Before Alice and Bob can send encrypted messages, they need a shared secret. The problem: if Eve is watching every wire and WiFi signal, how do they share a key without her learning it?

Normal crypto (HTTPS, Signal) uses hard math. Quantum crypto uses **physics** instead — specifically that measuring a quantum particle disturbs it. If you look, you leave fingerprints.

### What's a photon?

A photon is a particle of light. Think of it like a coin spinning in a specific direction. The direction encodes a 0 or a 1. Alice shoots them toward Bob one at a time.

### What's a "basis"?

You can measure a photon in two different ways:

| Basis | In code | What it reads |
|---|---|---|
| Rectilinear `+` | `Basis.RECTILINEAR` | Horizontal (0) or vertical (1)? |
| Diagonal `x` | `Basis.DIAGONAL` | 45° (0) or 135° (1)? |

If Alice encodes in the `+` basis and Bob measures in the `x` basis by accident, he gets a **completely random answer**. And the photon's state is permanently scrambled. This isn't a bug — it's the entire security mechanism.

### How BB84 works

```
Alice picks bit + basis  →  encodes photon  →  sends
                                                  ↓
                                           [Eve might be here]
                                                  ↓
Bob picks a random basis  →  measures  →  records result

After ~10,000 photons:

Alice + Bob compare bases on a public call (NOT the bits themselves)
                              ↓
Throw away mismatched bases  →  ~50% survive  →  sifted key
                              ↓
Check a sample publicly  →  error rate okay? Eve wasn't watching. Done.
```

```
Alice:  bit=1, basis=+  →  Bob: basis=+ → gets 1  ✓ keep
Alice:  bit=0, basis=x  →  Bob: basis=+ → gets ?  ✗ throw away
Alice:  bit=1, basis=x  →  Bob: basis=x → gets 1  ✓ keep
```

Code: [qkd/bb84.py](qkd/bb84.py)

---

## ⚔️ The Attacks

### Attack 1 — Intercept-Resend (the obvious one)

Eve sits in the fiber, reads every photon, then re-sends a copy to Bob.

**The problem for Eve:** she has to guess Alice's basis. She's right 50% of the time. When she guesses wrong, her measurement scrambles the photon. When Bob then measures that scrambled photon (in the correct basis), he gets the wrong answer half those times.

Net result: **25% error rate.** Normal channels are 1-3%. 25% is screaming. Alice and Bob notice immediately.

Code: [attacks/intercept_resend.py](attacks/intercept_resend.py)

---

### Attack 2 — Partial Intercept (the smarter one)

What if Eve only intercepts *some* photons?

If she intercepts fraction **eta**:
- QBER goes up by `eta / 4`, not the full 25%
- With 2% channel noise and a 5% abort threshold, Eve's window is: `eta_max = 4 × (threshold − noise)`
- That gives her **up to 12% of photons undetected**

She still gets imperfect info on those (wrong-basis guesses still happen). But it's a real operating window. Figure 1 in the notebook shows the full tradeoff curve.

Code: [attacks/intercept_resend.py](attacks/intercept_resend.py) — `PartialIntercept` class

---

### Attack 3 — Photon Number Splitting (the scary one)

This is the attack that breaks *real* QKD hardware.

**The problem with real lasers:**

Theoretically Alice sends exactly 1 photon per pulse. In practice she uses an attenuated laser, and the photon count follows a Poisson distribution:

```
n=0 photons:  ~90.5%  (vacuum, useless to everyone)
n=1 photon:   ~9.0%   (normal, secure)
n=2+ photons: ~0.47%  (Eve's target)
```

**What Eve does with multi-photon pulses:**

```
Eve on the fiber
      ↓
QND measurement → counts photons WITHOUT disturbing their state
      ↓
n=1?  → pass through, do nothing (can't read safely)
n≥2?  → split off one copy, store in quantum memory
         forward n-1 photons to Bob (he notices nothing)
      ↓
Alice publicly announces bases during sifting
      ↓
Eve measures stored copies in the CORRECT basis
      ↓
Perfect information. Zero wrong-basis errors. Zero QBER increase.
```

**Why this is devastating:**
- Intercept-resend: partial info, costs 25% QBER → gets caught
- PNS: perfect info on multi-photon pulses, costs **zero** QBER → completely invisible

Alice and Bob see a totally normal error rate. They have no idea.

Code: [attacks/pns.py](attacks/pns.py)

---

### The fix: Decoy States

Alice randomly varies her laser intensity. Eve can't apply PNS without distorting the statistics across intensity levels, which Alice and Bob can detect. That's the Lo, Ma & Chen (2005) decoy state protocol.

This simulator doesn't implement decoy states. It's here to show you why you need them.

---

### 🔩 Why This Matters for Hardware

The PNS vulnerability exists because real lasers can't produce exactly one photon on demand. They give you a Poisson distribution — and that statistical tail is all Eve needs.

**True single-photon sources would fix this entirely.** If Alice's hardware physically can't emit two photons at once, there's nothing for Eve to split. No multi-photon pulses, no attack. Not a workaround — an architectural fix.

This is why **quantum dots** are such an active research area. A quantum dot is a nanoscale trap that holds a single electron. Excite it, it emits exactly one photon — a Fock state (n=1) instead of a Poisson distribution. No tail. No vulnerability.

**Graphene quantum dots** are a particularly interesting direction: graphene's 2D structure and tunable bandgap make it a candidate for room-temperature single-photon emission, which most solid-state emitters can't do. If that works at scale, the entire threat model this simulator is built on becomes irrelevant.

This simulator models the problem. The hardware research is building the fix.

---

## 📓 What the Notebook Shows

Open [bb84_adversarial_analysis.ipynb](bb84_adversarial_analysis.ipynb) in Jupyter:

| Section | What it does |
|---|---|
| 1 — Quick Demo | All three scenarios side by side |
| 2 — Intercept tradeoff | Figure 1: QBER vs eta, Eve's info, attack efficiency curve |
| 3 — Detection threshold | Table: max safe eta for each noise + threshold combo |
| 4 — PNS Analysis | Figure 2: photon distribution, info leak vs mu |
| 5 — Theory vs Practice | Figure 3: full attack comparison |
| 6 — Conclusions | Written summary + real-world implications |

---

## 📁 Project Structure

```
BB84/
├── qkd/
│   ├── photon.py          ← quantum physics layer: Photon, Basis, encode(), measure()
│   └── bb84.py            ← BB84 protocol: Alice → Eve → Bob → sifting
│
├── attacks/
│   ├── intercept_resend.py  ← InterceptResend, PartialIntercept
│   └── pns.py               ← PNS on weak coherent pulse sources
│
├── analysis/
│   └── metrics.py           ← sweep functions, detection_analysis()
│
├── generate_figures.py      ← run once to generate the PNGs the notebook loads
├── verify.py                ← sanity check: should print ALL CHECKS PASSED
├── bb84_adversarial_analysis.ipynb
└── requirements.txt
```

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
python verify.py              # ALL CHECKS PASSED
python generate_figures.py    # ~30 seconds, writes the 3 figure PNGs
jupyter notebook              # open bb84_adversarial_analysis.ipynb
```

### Use the library directly

```python
from qkd import BB84
from attacks import InterceptResend, PartialIntercept, PNS

# No Eve
result = BB84(n_photons=10000, noise=0.02).run()
print(result.summary())

# Full intercept-resend → QBER should be ~25%
result = BB84(n_photons=10000).run(eve=InterceptResend())
print(f"QBER: {result.qber:.1%}")

# Partial — Eve intercepts 20% of photons
result = BB84(n_photons=10000, noise=0.02).run(eve=PartialIntercept(rate=0.2))
print(f"QBER: {result.qber:.1%}")   # ~7% (2% noise + 20%/4)

# PNS — completely silent
result = BB84(n_photons=10000, noise=0.01, use_wcp=True, mu=0.1).run(eve=PNS(mu=0.1))
print(f"QBER: {result.qber:.1%}")              # still ~1%
print(f"Eve's info: {result.eve_information:.4f} bits/bit")
```

---

## ⚠️ Limitations (Being Honest)

- **PNS requires hardware Eve doesn't have yet.** Quantum non-demolition measurement and long-lived quantum memory are active research areas. The attack is theoretically valid — not something you build today with off-the-shelf parts.

- **No privacy amplification or error correction.** Real QKD compresses the sifted key to squeeze out Eve's partial information. This simulator stops at the sifted key — numbers are pre-compression.

- **Simplified channel model.** Noise is modeled as random depolarizing, which is a reasonable approximation but not a full physical channel.

- **PNS information is slightly underestimated.** The simulator tracks which photons Eve split but doesn't fully simulate the post-sifting measurement step. Use `PNS.information_per_key_bit(mu)` for the accurate theoretical number.

---

## 🔭 Future Work

- [ ] Decoy state protocol — show that it actually catches PNS statistically
- [ ] Privacy amplification — show how much the key shrinks after accounting for Eve
- [ ] Full security proof walkthrough — QBER to secret key rate, step by step
- [ ] Single-photon source simulation — model a Fock state source, compare to WCP
- [ ] Side-channel attacks — timing, detector efficiency mismatch
- [ ] Write up as a formal paper / arXiv submission

---

## 📄 References

- Bennett, C.H. & Brassard, G. (1984). *Quantum Cryptography: Public Key Distribution and Coin Tossing.*
- Huttner, B. et al. (1995). *Quantum Cryptography with Coherent States.* Physical Review A 51, 1863.
- Lo, H.-K., Ma, X. & Chen, K. (2005). *Decoy State Quantum Key Distribution.* Physical Review Letters 94, 230504.

---

## 🐱 About

Made by someone who got curious about why quantum crypto is "provably secure" but real-world systems keep getting broken.

Spoiler: the math is fine. The hardware isn't.

```
Alice ─────────────────────────────────────────► Bob
         ↑
       Eve? 👀
```
