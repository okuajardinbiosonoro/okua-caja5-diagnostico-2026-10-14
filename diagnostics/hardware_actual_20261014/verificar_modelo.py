"""Verificacion independiente del modelo ideal; no accede a nodos ni a Ableton."""
import cmath
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
kh = 1 + 100_000 / 2_200_000
kl = 1 + 10_000 / 2_000_000
rh1, rh2, ch1, ch2 = 47_000, 100_000, 4.7e-6, 4.7e-6
rl1, rl2, cl1, cl2 = 220, 220, 10e-6, 4.7e-6
ah = rh1 * (ch1 + ch2) + rh2 * ch2 * (1 - kh)
bh = rh1 * rh2 * ch1 * ch2
al = cl2 * (rl1 + rl2) + rl1 * cl1 * (1 - kl)
bl = rl1 * rl2 * cl1 * cl2
n = kh * kl * bh

def denominator(a, b, s):
    return 1 + a*s + b*s*s

def roots(a, b):
    delta = cmath.sqrt(a*a - 4*b)
    return [(-a + delta)/(2*b), (-a - delta)/(2*b)]

def amplitude(f):
    s = 2j * math.pi * f
    return abs(n*s*s / (denominator(ah, bh, s) * denominator(al, bl, s)))

def normalized(stage, f):
    s = 2j * math.pi * f
    if stage == "hp":
        return abs(bh*s*s / denominator(ah, bh, s))
    return abs(1 / denominator(al, bl, s))

def cutoff(stage, lo, hi):
    target = 1 / math.sqrt(2)
    for _ in range(80):
        mid = (lo + hi) / 2
        below = normalized(stage, mid) < target
        if (stage == "hp" and below) or (stage == "lp" and not below):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

residues = []
for a, b, other_a, other_b in [(ah, bh, al, bl), (al, bl, ah, bh)]:
    for p in roots(a, b):
        residue = n*p / ((a + 2*b*p) * denominator(other_a, other_b, p))
        residues.append((p, residue))

def step(t):
    return sum(r * cmath.exp(p*t) for p, r in residues).real

def derivative(t):
    return sum(r*p * cmath.exp(p*t) for p, r in residues).real

extrema = []
previous = derivative(0)
for i in range(1, 100001):
    t = i * 0.0001
    current = derivative(t)
    if current * previous < 0:
        lo, hi = t - 0.0001, t
        for _ in range(50):
            mid = (lo + hi) / 2
            if derivative(lo) * derivative(mid) <= 0:
                hi = mid
            else:
                lo = mid
        tx = (lo + hi) / 2
        if tx > 1e-7:
            extrema.append({"seconds": tx, "volts_for_unit_step": step(tx)})
    previous = current

report = {
    "kind": "ideal_linear_filter_model_independent_calculation",
    "derived_from": "R/C values and visually inspected topology of node PDF pages 1-4",
    "not_a_physical_measurement": True,
    "hp_gain": kh, "lp_gain": kl,
    "transfer_numerator_s_squared": n,
    "hp_denominator_ascending": [1, ah, bh],
    "lp_denominator_ascending": [1, al, bl],
    "hp_natural_frequency_hz": 1/(2*math.pi*math.sqrt(bh)),
    "lp_natural_frequency_hz": 1/(2*math.pi*math.sqrt(bl)),
    "hp_minus3db_relative_passband_hz": cutoff("hp", 0.00001, 10),
    "lp_minus3db_relative_dc_gain_hz": cutoff("lp", 1, 10000),
    "amplitude_v_per_v": {str(f): amplitude(f) for f in [0.1, 10, 60, 100]},
    "unit_step_first_extrema": extrema[:8],
    "unit_step_max_v": max(x["volts_for_unit_step"] for x in extrema),
    "unit_step_min_v": min(x["volts_for_unit_step"] for x in extrema),
    "limitations": [
        "Ideal opamps and component values; no saturation, tolerance or loading model.",
        "No actual electrode impedance, physical waveforms, power rails or ADC calibration measured.",
        "Output may have both signs relative to GND; this model is not an ADC transfer function."
    ]
}
(ROOT / "modelo_ideal_verificado.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
