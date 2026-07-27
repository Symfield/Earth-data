#!/usr/bin/env python3
"""
Symfield Earth benchmark — measured, not expected.
Runs the paper's benchmark protocol over the archived daily snapshots:

  1. FCI pre-⧖ vs post-⧖
     FCI(t) = mean( mu(t) / (|g(t) - gbar_T(t)| + eps) ), gbar = trailing 30-day mean
     pre-⧖ : mu ≡ 1 (collapse: no confidence weighting)
     post-⧖: mu = stored fuzzy weights (the ⧖-update's memory)

  2. Bias–IERS correlation
     Underlying motion = 15-day centered mean of the normalized pole vector.
     collapse estimator: raw daily normalized pole (point estimate)
     ⧖ estimator      : stored bias vector (0.9/0.1 exponential memory update)
     Report Pearson r of each estimator against the underlying motion (x and y).

Honest caveats printed with results. Requires only numpy.
"""
import json, glob, math, datetime
import numpy as np

files = sorted(glob.glob("earth_data_2*.json"))
rows = []
for f in files:
    try:
        d = json.load(open(f))
    except Exception:
        continue
    ax = d.get("semi_axes") or d.get("metric_tensor") or {}
    bias = d.get("bias_vector") or {}
    if isinstance(bias, list):
        bias = {"x": bias[0], "y": bias[1], "z": bias[2] if len(bias) > 2 else 0}
    iers = d.get("iers_data") or {}
    mu = d.get("fuzzy_weights") or []
    if not (ax and mu):
        continue
    rows.append({
        "date": f[11:19],
        "g": np.array([float(ax["a"]), float(ax["b"]), float(ax["c"])]),
        "mu": np.array([float(m) for m in mu]),
        "bias": np.array([float(bias.get("x", 0)), float(bias.get("y", 0))]),
        "pole": (np.array([float(iers["x_pole_mas"]), float(iers["y_pole_mas"])])
                 if "x_pole_mas" in iers else None),
        "fci_reported": float(d.get("fci") or d.get("field_coherence_index") or 0),
    })

# keep the continuous block(s); flag gaps
dates = [datetime.date(int(r["date"][:4]), int(r["date"][4:6]), int(r["date"][6:8])) for r in rows]
gaps = [(dates[i - 1], dates[i]) for i in range(1, len(dates))
        if (dates[i] - dates[i - 1]).days > 3]

n = len(rows)
G = np.stack([r["g"] for r in rows])            # (n,3)
MU = np.stack([r["mu"] for r in rows])          # (n,5)
eps = 1e-6

# --- 1 · FCI pre vs post ------------------------------------------------
W = 30
fci_pre, fci_post = [], []
for t in range(n):
    lo = max(0, t - W + 1)
    gbar = G[lo:t + 1].mean(axis=0)
    dev = np.abs(G[t] - gbar) + eps
    fci_pre.append(np.mean(1.0 / dev))
    fci_post.append(np.mean(MU[t].mean() / dev))
fci_pre = np.array(fci_pre[W // 2:])            # skip warm-up
fci_post = np.array(fci_post[W // 2:])

def norm01(a):                                   # scale-free comparison
    return (a - a.min()) / (a.max() - a.min() + eps)

# stability of the coherence signal (lower CV = steadier field reading)
cv_pre = fci_pre.std() / (fci_pre.mean() + eps)
cv_post = fci_post.std() / (fci_post.mean() + eps)

# --- 2 · Bias–IERS correlation -----------------------------------------
P = [r["pole"] for r in rows]
have = [i for i, p in enumerate(P) if p is not None]
r_raw = r_tau = None
if len(have) >= 10:
    idx = np.array(have)
    pole = np.stack([P[i] for i in idx])
    pole_u = pole / (np.linalg.norm(pole, axis=1, keepdims=True) + eps)
    bias = np.stack([rows[i]["bias"] for i in idx])
    # underlying motion: 15-day centered mean of unit pole vector
    K = 15
    under = np.stack([pole_u[max(0, j - K // 2): j + K // 2 + 1].mean(axis=0)
                      for j in range(len(idx))])
    def pearson(a, b):
        a = a - a.mean(); b = b - b.mean()
        return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + eps))
    r_raw = tuple(pearson(pole_u[:, k], under[:, k]) for k in (0, 1))
    r_tau = tuple(pearson(bias[:, k], under[:, k]) for k in (0, 1))

# --- report -------------------------------------------------------------
print("SYMFIELD EARTH BENCHMARK — measured on archived snapshots")
print(f"snapshots: {n}  ({rows[0]['date']} → {rows[-1]['date']})")
for a, b in gaps:
    print(f"  data gap: {a} → {b}  ({(b - a).days} days)")
print()
print("1 · FIELD COHERENCE (paper proxy, 30-day trailing mean, warm-up skipped)")
print(f"    pre-⧖  (mu=1)     mean FCI {fci_pre.mean():10.3f}   CV {cv_pre:.3f}")
print(f"    post-⧖ (mu live)  mean FCI {fci_post.mean():10.3f}   CV {cv_post:.3f}")
print(f"    coherence-signal steadiness gain (CV_pre / CV_post): "
      f"{cv_pre / (cv_post + eps):.2f}×")
print()
print("2 · BIAS VECTOR vs UNDERLYING POLAR MOTION (15-day centered mean)")
if r_raw:
    print(f"    collapse estimator (raw daily pole)   r_x {r_raw[0]:+.3f}   r_y {r_raw[1]:+.3f}")
    print(f"    ⧖ estimator (memory-weighted bias)    r_x {r_tau[0]:+.3f}   r_y {r_tau[1]:+.3f}")
else:
    print("    not enough snapshots carrying IERS pole data yet — rerun as archive grows")
print()
print("CAVEATS: short continuous window (Nov 10–Dec 15, 2025) plus post-restore")
print("points; backend bias is the simplified 0.9/0.1 estimator, not the full")
print("eigenanalysis; FCI here is the paper's ratio proxy on 3-component g.")
print("Rerun monthly as the restored pipeline accumulates data.")
