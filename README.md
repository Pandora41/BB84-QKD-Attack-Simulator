# BB84 QKD Attack Simulator

**A Python simulator for quantum key distribution — from the hacker's perspective.**

---

## What is this?

This project simulates a quantum cryptography protocol called **BB84**. It shows how Alice and Bob can share a secret key using light, and — more interestingly — how an attacker named Eve can try to steal that key, and whether she gets caught.

Most QKD simulators only show the happy path ("look, it works!"). This one asks the harder question: **what can an attacker actually steal, and how much does it cost her to try?**

---

## The Big Idea (No Physics Degree Required)

### Step 1 — Why do we need a secret key?

Before Alice and Bob can send each other secret messages, they need to agree on a shared secret (a **key**). The problem: if Eve is listening on every wire and WiFi signal, how do they share a key without Eve learning it?

Normal cryptography (like HTTPS) uses hard math problems to protect the key. Quantum cryptography uses **physics** instead — specifically, the fact that measuring a quantum particle disturbs it.

### Step 2 — What is a photon?

A photon is a particle of light. You can think of it like a coin that is spinning in a specific direction. The direction encodes a 0 or a 1.

Alice owns a special laser that shoots one photon at a time toward Bob. Each photon carries one secret bit.

### Step 3 — What is a "basis"?

This is the tricky part. You can measure a spinning coin in two different ways:

| Basis name | In code | What it measures |
|---|---|---|
| Rectilinear `+` | `Basis.RECTILINEAR` | Is the photon horizontal (0) or vertical (1)? |
| Diagonal `x` | `Basis.DIAGONAL` | Is the photon tilted 45° (0) or 135° (1)? |

**The catch:** if Alice sends a photon in the `+` basis and Bob measures it in the `x` basis by accident, he gets a completely random answer — not Alice's original bit. The photon's state is also permanently scrambled.

This is not a bug. This is the security feature.

### Step 4 — The BB84 Protocol (How the key gets shared)

1. Alice picks a random bit (0 or 1) and a random basis (`+` or `x`), then encodes the photon and sends it.
2. Bob picks a random basis and measures the photon.
3. They repeat this ~10,000 times.
4. Alice and Bob call each other on a normal (public) phone and compare **which basis they each used** for each photon. They do NOT say the actual bits.
5. They throw away every photon where they used different bases. The ones where both used the same basis form the **sifted key** — roughly 50% of photons survive this step.
6. They check a small random sample of their sifted key over the phone. If the error rate is low, they know Eve was not watching. The rest becomes their secret key.

This sifting step is implemented in [qkd/bb84.py](qkd/bb84.py).

```
Alice:  bit=1, basis=+  →  sends  →  Bob: basis=+ → gets 1  ✓ (keep)
Alice:  bit=0, basis=x  →  sends  →  Bob: basis=+ → gets ?  ✗ (throw away)
Alice:  bit=1, basis=x  →  sends  →  Bob: basis=x → gets 1  ✓ (keep)
```

---

## The Attacks

### Attack 1 — Intercept-Resend (the obvious hack)

Eve sits in the middle of the fiber cable and tries to read every photon before passing it to Bob.

**How she does it:**
1. She intercepts Alice's photon.
2. She guesses a basis and measures it.
3. She re-encodes the bit she got and sends a fresh photon to Bob.

**Why she gets caught:**

Eve has to guess the basis. She guesses right 50% of the time. When she guesses wrong, her measurement scrambles the photon's state. When Bob then measures *that* scrambled photon, he gets the wrong bit 50% of those times.

Net result: **Eve causes a 25% error rate** (QBER = 25%) in the sifted key. Alice and Bob notice this when they compare their sample. Normal channel noise is maybe 1-3%. 25% is screaming.

The **QBER** (Quantum Bit Error Rate) is the percentage of bits in the sifted key where Alice and Bob disagree. This is the main detector.

This attack is in [attacks/intercept_resend.py](attacks/intercept_resend.py).

---

### Attack 2 — Partial Intercept (the smarter hack)

What if Eve only intercepts *some* photons, not all of them?

If she intercepts a fraction **eta** of photons:
- QBER goes up by `eta / 4` (not the full 25%)
- If the channel is already noisy (say 2%), Alice and Bob can't tell the difference until QBER exceeds their abort threshold (say 5%)

So Eve has a window: `eta_max = 4 × (threshold - channel_noise)`

With 2% channel noise and a 5% abort threshold: **Eve can intercept up to 12% of photons without being detected.**

But she only gets information on those 12%, and her information per intercepted bit is also imperfect (she still guesses wrong basis 50% of the time). It is a real tradeoff.

The analysis sweeps eta from 0% to 100% and plots exactly this tradeoff. That's Figure 1 in the notebook.

---

### Attack 3 — Photon Number Splitting, PNS (the sneaky hack)

This is the attack that breaks real-world QKD hardware.

**The problem with real lasers:**

Theoretically Alice sends exactly 1 photon per pulse. In reality, she uses an attenuated laser. The number of photons per pulse follows a statistical distribution called a **Poisson distribution**. Most pulses have 0 or 1 photon, but occasionally a pulse has 2 or 3.

At a typical setting of `mu = 0.1` (mean photons per pulse):
- ~90.5% of pulses: 0 photons (vacuum, useless)
- ~9.0% of pulses: 1 photon (normal, secure)
- ~0.5% of pulses: 2+ photons (vulnerable!)

**What Eve does with multi-photon pulses:**

1. She taps the fiber and uses a special measurement that counts photons WITHOUT disturbing their quantum state (quantum non-demolition measurement).
2. For single-photon pulses: she does nothing. She can't read them without disturbing them.
3. For 2-photon pulses: she quietly splits off one copy, stores it in quantum memory, and forwards the other photon to Bob. Bob notices nothing — he still got a photon.
4. Later, when Alice publicly announces which basis she used for each photon (during sifting), Eve measures her stored copies in the correct basis. **She gets perfect information — no wrong-basis errors.**

**Why this is devastating:**

- Intercept-resend: Eve gets partial info, costs 25% QBER — she gets caught.
- PNS: Eve gets **perfect** info on the multi-photon pulses, costs **zero** QBER — she's invisible.

The attack is silent. Alice and Bob see a completely normal error rate. They have no idea.

This attack is in [attacks/pns.py](attacks/pns.py).

---

### The Fix: Decoy States

Real QKD systems defend against PNS using the **decoy state protocol** (Lo, Ma & Chen, 2005). Alice randomly varies the intensity of her laser pulses. Eve can't apply PNS without distorting the statistics across intensity levels, which Alice and Bob can detect.

This simulator does not implement decoy states — it shows why you need them.

---

### Why This Matters for Hardware

The PNS vulnerability exists in the first place because real lasers cannot produce exactly one photon on demand. An attenuated laser gives you a Poisson distribution — most pulses have zero or one photon, but some leak two or three, and those are Eve's target.

**True single-photon sources** would eliminate this attack class entirely. If Alice's source is physically incapable of emitting two photons at once, there is nothing for Eve to split. No multi-photon pulses means no PNS attack, full stop — not a workaround, an architectural fix.

This is why **quantum dots** are one of the most active areas in quantum hardware research. A quantum dot is a nanoscale trap that holds a single electron. When you excite it, it emits exactly one photon — a **Fock state** (n=1) rather than a Poisson distribution. That single photon carries the same quantum state properties BB84 relies on, but without the statistical tail that PNS exploits.

**Graphene quantum dots** are a particularly interesting direction: graphene's 2D structure and tunable bandgap make it a candidate for room-temperature single-photon emission, which most solid-state emitters cannot achieve. If that works at scale, it removes a fundamental hardware assumption this entire threat model is built on.

This simulator models the vulnerability. The hardware research is building the fix.

---

## What the Notebook Shows

Open [bb84_adversarial_analysis.ipynb](bb84_adversarial_analysis.ipynb) in Jupyter to see:

| Section | What it shows |
|---|---|
| 1 — Quick Demo | Run all three scenarios side by side and print the results |
| 2 — Intercept tradeoff | Figure 1: QBER vs eta, Eve's info vs eta, attack efficiency curve |
| 3 — Detection threshold | Table: for each noise level + abort threshold, what is Eve's maximum safe eta? |
| 4 — PNS Analysis | Figure 2: photon distribution per mu, Eve's info leak vs mu |
| 5 — Theory vs Practice | Figure 3: full comparison of all attacks across key metrics |
| 6 — Conclusions | Written summary of findings and real-world implications |

---

## Project Structure

```
BB84/
├── qkd/
│   ├── __init__.py
│   ├── photon.py          # Photon, Basis, encode(), measure() — the quantum physics layer
│   └── bb84.py            # BB84 protocol: Alice sends, Eve intercepts, Bob measures, sifting
│
├── attacks/
│   ├── __init__.py
│   ├── intercept_resend.py  # InterceptResend, PartialIntercept
│   └── pns.py               # PNS — photon number splitting on weak coherent pulse sources
│
├── analysis/
│   ├── __init__.py
│   └── metrics.py           # sweep_partial_intercept(), sweep_mu(), detection_analysis()
│
├── generate_figures.py      # Run this once to create the PNGs the notebook uses
├── verify.py                # Sanity check — run this to confirm everything works
├── bb84_adversarial_analysis.ipynb   # Main analysis notebook
└── requirements.txt
```

---

## How to Run It

**1. Install dependencies** (first time only):
```
pip install -r requirements.txt
```

**2. Verify everything works:**
```
python verify.py
```

You should see "ALL CHECKS PASSED" at the end.

**3. Generate the figures** (first time only, takes ~30 seconds):
```
python generate_figures.py
```

**4. Open the notebook:**
```
jupyter notebook bb84_adversarial_analysis.ipynb
```

Run all cells from top to bottom.

---

## How to Use the Library Directly

```python
from qkd import BB84
from attacks import InterceptResend, PartialIntercept, PNS

# Clean channel — no Eve
result = BB84(n_photons=10000, noise=0.02).run()
print(result.summary())

# Full intercept-resend — Eve intercepts everything
result = BB84(n_photons=10000, noise=0.0).run(eve=InterceptResend())
print(f"QBER: {result.qber:.1%}")   # should be ~25%

# Partial intercept — Eve intercepts 20% of photons
result = BB84(n_photons=10000, noise=0.02).run(eve=PartialIntercept(rate=0.2))
print(f"QBER: {result.qber:.1%}")   # should be ~7% (2% noise + 20%/4)

# PNS on a realistic laser source
result = BB84(n_photons=10000, noise=0.01, use_wcp=True, mu=0.1).run(eve=PNS(mu=0.1))
print(f"QBER: {result.qber:.1%}")   # still ~1% — PNS is silent
print(f"Eve's info: {result.eve_information:.4f} bits/bit")
```

---

## Key Numbers to Remember

| Fact | Number |
|---|---|
| Fraction of sifted key kept after basis sifting | ~50% |
| QBER from full intercept-resend | 25% |
| QBER from PNS attack | 0% (that's the whole problem) |
| Multi-photon pulse fraction at mu=0.1 | ~0.47% |
| Max safe Eve interception at 2% noise, 5% threshold | 12% |

---

## References

- Bennett, C.H. & Brassard, G. (1984). *Quantum Cryptography: Public Key Distribution and Coin Tossing.*
- Huttner, B. et al. (1995). *Quantum Cryptography with Coherent States.* Physical Review A 51, 1863.
- Lo, H.-K., Ma, X. & Chen, K. (2005). *Decoy State Quantum Key Distribution.* Physical Review Letters 94, 230504.
