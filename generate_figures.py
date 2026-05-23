"""
generate_figures.py — Run this once to produce the PNG figures the notebook loads.

Usage:
    python generate_figures.py

Outputs:
    fig1_intercept_tradeoff.png  — η vs QBER vs I(A:E) tradeoff curves
    fig2_pns_analysis.png        — PNS photon distribution and info leak
    fig3_theory_vs_practice.png  — Attack comparison summary
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

from qkd.bb84 import BB84
from attacks.intercept_resend import PartialIntercept
from attacks.pns import PNS
from analysis.metrics import sweep_partial_intercept, sweep_mu, detection_analysis

plt.rcParams.update({
    "figure.dpi": 150,
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})

NOISE = 0.02
THRESHOLD = 0.05
N_PHOTONS = 6000


# ─────────────────────────────────────────────────────────────
# Figure 1: Intercept-resend tradeoff
# ─────────────────────────────────────────────────────────────

def fig1_intercept_tradeoff():
    print("Running intercept-resend sweep...")
    rates = np.linspace(0, 1, 25)
    points = sweep_partial_intercept(rates=rates, n_photons=N_PHOTONS, noise=NOISE)

    etas     = [p.parameter        for p in points]
    qber_obs = [p.qber             for p in points]
    qber_thy = [p.qber_theoretical for p in points]
    eve_info = [p.eve_information  for p in points]

    # Attack efficiency: info gained per unit QBER cost
    efficiency = [
        (i / max(q, 1e-6)) for i, q in zip(eve_info, qber_obs)
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Intercept-Resend Attack: The Detection Tradeoff", fontsize=14, fontweight="bold", y=1.01)

    # Left: QBER vs η
    ax1.fill_between([0, 1], 0, NOISE, color="lightgreen", alpha=0.25, label="Channel noise floor")
    ax1.fill_between([0, 1], THRESHOLD, 0.35, color="salmon", alpha=0.2, label=f"Detection zone (>{THRESHOLD:.0%} QBER)")
    ax1.fill_between([0, 1], NOISE, THRESHOLD, color="gold", alpha=0.2, label="Eve's operating window")

    ax1.plot(etas, qber_thy, "--", color="steelblue", linewidth=1.5, label=f"Theoretical: noise + η/4")
    ax1.plot(etas, qber_obs, "o-", color="steelblue", markersize=4, linewidth=2, label="Simulated QBER")
    ax1.axhline(THRESHOLD, color="firebrick", linewidth=1.2, linestyle=":", label=f"Abort threshold ({THRESHOLD:.0%})")
    ax1.axhline(NOISE,     color="seagreen",  linewidth=1.2, linestyle=":", label=f"Channel noise ({NOISE:.0%})")

    eta_max = PartialIntercept.detection_threshold_rate(NOISE, THRESHOLD)
    ax1.axvline(eta_max, color="darkorange", linewidth=1.5, linestyle="-.",
                label=f"Max safe η = {eta_max:.1%}")

    ax1.set_xlabel("Eve's interception rate η", fontsize=11)
    ax1.set_ylabel("QBER", fontsize=11)
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 0.32)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax1.legend(fontsize=8, loc="upper left")
    ax1.set_title("QBER rises linearly with interception rate", fontsize=10)

    # Right: I(A:E) and efficiency vs η
    color_info = "mediumpurple"
    color_eff  = "darkorange"

    ax2.plot(etas, eve_info, "s-", color=color_info, markersize=4, linewidth=2, label="I(A:E) — Eve's information")
    ax2.set_xlabel("Eve's interception rate η", fontsize=11)
    ax2.set_ylabel("I(A:E)  [bits/bit]", fontsize=11, color=color_info)
    ax2.tick_params(axis="y", labelcolor=color_info)
    ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1.05)

    ax2b = ax2.twinx()
    ax2b.spines["right"].set_visible(True)
    ax2b.plot(etas, efficiency, "^--", color=color_eff, markersize=4, linewidth=1.5, label="Attack efficiency\nI(A:E)/QBER")
    ax2b.set_ylabel("Attack efficiency  I(A:E)/QBER", fontsize=10, color=color_eff)
    ax2b.tick_params(axis="y", labelcolor=color_eff)

    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")
    ax2.set_title("Efficiency peaks at low η — intercepting everything is suboptimal", fontsize=10)

    fig.tight_layout()
    fig.savefig("fig1_intercept_tradeoff.png", bbox_inches="tight")
    plt.close(fig)
    print("  -> fig1_intercept_tradeoff.png")


# ─────────────────────────────────────────────────────────────
# Figure 2: PNS attack analysis
# ─────────────────────────────────────────────────────────────

def fig2_pns_analysis():
    print("Running PNS mu sweep...")
    mus    = np.linspace(0.01, 0.8, 30)
    points = sweep_mu(mus=mus, n_photons=N_PHOTONS, noise=0.01)

    mu_vals   = [p.parameter       for p in points]
    qbers     = [p.qber            for p in points]
    eve_infos = [p.eve_information for p in points]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Photon Number Splitting (PNS) Attack on Weak Coherent Pulse Sources",
                 fontsize=14, fontweight="bold", y=1.01)

    # Left: Photon number distribution for several μ
    mus_demo = [0.1, 0.3, 0.5, 0.8]
    colors   = ["steelblue", "seagreen", "darkorange", "firebrick"]
    x        = np.arange(6)
    width    = 0.18

    for i, (mu, col) in enumerate(zip(mus_demo, colors)):
        dist = PNS.photon_number_distribution(mu, max_n=5)
        vals = [dist[n] for n in range(6)]
        bars = ax1.bar(x + i * width, vals, width, label=f"μ={mu}", color=col, alpha=0.75)
        # Annotate the n≥2 portion
        multi = sum(vals[2:])
        ax1.annotate(
            f"{multi:.2%}",
            xy=(x[2] + i * width, vals[2]),
            xytext=(0, 4), textcoords="offset points",
            ha="center", fontsize=7, color=col,
        )

    ax1.set_xticks(x + width * 1.5)
    ax1.set_xticklabels([f"n={n}" for n in range(6)])
    ax1.set_ylabel("Probability P(n photons)", fontsize=11)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1%}"))
    ax1.legend(fontsize=9)
    ax1.set_title("Poisson photon distribution — % above bars = P(n≥2), Eve's target", fontsize=9)

    # Right: Eve's info and QBER vs μ
    ax2.plot(mu_vals, eve_infos, "o-", color="mediumpurple", markersize=4,
             linewidth=2, label="I(A:E) — Eve's information (no errors introduced)")
    ax2.plot(mu_vals, qbers, "s--", color="steelblue", markersize=4,
             linewidth=1.5, label="Observed QBER (should stay flat)")

    ax2.axvline(0.1, color="gray", linewidth=1, linestyle=":", label="μ=0.1 (practical systems)")
    ax2.fill_between(mu_vals, 0, [PNS.multi_photon_probability(m) for m in mu_vals],
                     alpha=0.12, color="firebrick", label="P(n≥2) — vulnerable pulse fraction")

    ax2.set_xlabel("Mean photon number per pulse  μ", fontsize=11)
    ax2.set_ylabel("Rate  [bits/bit  or  probability]", fontsize=11)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1%}"))
    ax2.legend(fontsize=8)
    ax2.set_title("QBER stays flat — PNS is completely silent, unlike intercept-resend", fontsize=9)

    fig.tight_layout()
    fig.savefig("fig2_pns_analysis.png", bbox_inches="tight")
    plt.close(fig)
    print("  -> fig2_pns_analysis.png")


# ─────────────────────────────────────────────────────────────
# Figure 3: Theory vs Practice summary
# ─────────────────────────────────────────────────────────────

def fig3_theory_vs_practice():
    print("Building theory vs practice summary figure...")

    fig = plt.figure(figsize=(13, 6.5))
    gs  = GridSpec(2, 3, figure=fig, hspace=0.55, wspace=0.4)

    fig.suptitle("BB84 Security: Theory vs Practice", fontsize=15, fontweight="bold")

    # ── Panel A: QBER cost of each attack ──
    ax_a = fig.add_subplot(gs[0, 0])
    attacks    = ["No Eve\n(noise only)", "Partial IR\nη=0.12", "Full IR\nη=1.0", "PNS\nWCP μ=0.1"]
    qbers_comp = [NOISE, NOISE + 0.12 * 0.25, 0.25, NOISE]
    colors_bar = ["steelblue", "gold", "firebrick", "mediumpurple"]
    bars = ax_a.bar(attacks, qbers_comp, color=colors_bar, alpha=0.8, width=0.5)
    ax_a.axhline(THRESHOLD, color="firebrick", linewidth=1.5, linestyle="--", label=f"Abort threshold {THRESHOLD:.0%}")
    ax_a.set_ylabel("QBER", fontsize=10)
    ax_a.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax_a.set_title("QBER cost of each attack", fontsize=10, fontweight="bold")
    ax_a.legend(fontsize=8)
    for bar, val in zip(bars, qbers_comp):
        ax_a.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                  f"{val:.1%}", ha="center", va="bottom", fontsize=8)

    # ── Panel B: Information gained ──
    ax_b = fig.add_subplot(gs[0, 1])
    info_comp = [0.0, 0.12 * 0.5, 0.5, PNS.information_per_key_bit(0.1)]
    bars_b = ax_b.bar(attacks, info_comp, color=colors_bar, alpha=0.8, width=0.5)
    ax_b.set_ylabel("I(A:E)  [bits/sifted bit]", fontsize=10)
    ax_b.set_title("Eve's information gained", fontsize=10, fontweight="bold")
    for bar, val in zip(bars_b, info_comp):
        ax_b.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                  f"{val:.3f}", ha="center", va="bottom", fontsize=8)

    # ── Panel C: Detectability rating (qualitative) ──
    ax_c = fig.add_subplot(gs[0, 2])
    detectability = [0.0, 0.35, 1.0, 0.02]
    det_colors    = ["steelblue", "gold", "firebrick", "mediumpurple"]
    bars_c = ax_c.barh(attacks, detectability, color=det_colors, alpha=0.8)
    ax_c.set_xlabel("Detectability  (0=silent, 1=obvious)", fontsize=9)
    ax_c.set_title("How detectable?", fontsize=10, fontweight="bold")
    ax_c.set_xlim(0, 1.1)
    for bar, val in zip(bars_c, detectability):
        label = {0.0: "Silent", 0.35: "Marginal", 1.0: "Always", 0.02: "Silent"}[val]
        ax_c.text(val + 0.02, bar.get_y() + bar.get_height() / 2,
                  label, va="center", fontsize=8)

    # ── Panel D: Safe interception window across noise levels ──
    ax_d = fig.add_subplot(gs[1, :2])
    noises     = np.linspace(0.005, 0.08, 50)
    thresholds = [0.05, 0.10, 0.15]
    t_colors   = ["firebrick", "darkorange", "seagreen"]
    for thresh, col in zip(thresholds, t_colors):
        eta_maxes = [PartialIntercept.detection_threshold_rate(n, thresh) * 100 for n in noises]
        ax_d.plot(noises * 100, eta_maxes, linewidth=2, color=col,
                  label=f"Abort threshold = {thresh:.0%}")
    ax_d.fill_between(noises * 100,
                      [PartialIntercept.detection_threshold_rate(n, 0.05) * 100 for n in noises],
                      [PartialIntercept.detection_threshold_rate(n, 0.15) * 100 for n in noises],
                      alpha=0.1, color="gray", label="Eve's viable range")
    ax_d.set_xlabel("Channel noise  (%)", fontsize=10)
    ax_d.set_ylabel("Max safe interception η  (%)", fontsize=10)
    ax_d.set_title("Eve's maximum undetected interception rate vs channel quality\n"
                   "(noisier channels give Eve more room to hide)", fontsize=10, fontweight="bold")
    ax_d.legend(fontsize=9)

    # ── Panel E: PNS info gain vs mu (small panel) ──
    ax_e = fig.add_subplot(gs[1, 2])
    mus_e    = np.linspace(0.01, 1.0, 60)
    info_pns = [PNS.information_per_key_bit(m) for m in mus_e]
    ax_e.plot(mus_e, info_pns, color="mediumpurple", linewidth=2)
    ax_e.axvline(0.1, color="gray", linewidth=1, linestyle=":", label="μ=0.1 practical")
    ax_e.axvline(0.5, color="gray", linewidth=1, linestyle="-.", label="μ=0.5 sloppy")
    ax_e.set_xlabel("Mean photon number μ", fontsize=10)
    ax_e.set_ylabel("PNS info fraction", fontsize=10)
    ax_e.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1%}"))
    ax_e.set_title("PNS leak grows with μ\n(zero QBER cost throughout)", fontsize=10, fontweight="bold")
    ax_e.legend(fontsize=8)

    fig.savefig("fig3_theory_vs_practice.png", bbox_inches="tight")
    plt.close(fig)
    print("  -> fig3_theory_vs_practice.png")


if __name__ == "__main__":
    fig1_intercept_tradeoff()
    fig2_pns_analysis()
    fig3_theory_vs_practice()
    print("\nDone. All figures written to the current directory.")
