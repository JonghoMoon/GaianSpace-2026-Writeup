#!/usr/bin/env python3
# Dependencies: pip install numpy pandas scipy

import numpy as np
import pandas as pd
from scipy.integrate import quad
from scipy.optimize import minimize_scalar

MU = 0.2123
R_START = 500.0
R_CONTACT = 50.0
SPRINGS = {"A": 0.020, "B": 0.080}
MAX_SPEED = 0.110
SLOT_INTERVAL = 10.0
SLOT_COUNT = 540

ORIGIN = pd.Timestamp("2041-11-02T00:00:00Z")
SLOT_ZERO = pd.Timestamp("2041-11-04T16:00:00Z")

df = pd.read_csv("hover_photometry.csv")
timestamps = pd.to_datetime(df["utc"], utc=True)

t = (timestamps - ORIGIN).dt.total_seconds().to_numpy()
magnitudes = df["rel_mag"].to_numpy(dtype=float)


def fit_period(period: float) -> tuple[float, np.ndarray]:
    omega = 2.0 * np.pi / period

    columns = [np.ones(len(t))]

    # Fit the fundamental and four harmonics.
    for harmonic in range(1, 5):
        columns.append(np.cos(harmonic * omega * t))
        columns.append(np.sin(harmonic * omega * t))

    matrix = np.column_stack(columns)
    coeffs = np.linalg.lstsq(matrix, magnitudes, rcond=None)[0]
    residual = matrix @ coeffs - magnitudes

    return float(np.mean(residual ** 2)), coeffs


# Coarse-search a broad period range, then refine its best minimum.
period_grid = np.arange(2000.0, 12000.1, 5.0, dtype=float)
coarse_errors = [fit_period(float(candidate))[0] for candidate in period_grid]
coarse_period = float(period_grid[int(np.argmin(coarse_errors))])
fit = minimize_scalar(
    lambda candidate: fit_period(float(candidate))[0],
    bounds=(coarse_period - 5.0, coarse_period + 5.0),
    method="bounded",
)
period = float(fit.x)
_, coeffs = fit_period(period)

# Assess each spring instead of assuming Spring A.
valid_springs: list[tuple[str, float, float]] = []
for name, initial in SPRINGS.items():
    impact = float(np.sqrt(
        initial ** 2 + 2.0 * MU * (1.0 / R_CONTACT - 1.0 / R_START)
    ))
    accepted = impact <= MAX_SPEED
    print(f"Spring {name}: contact speed={impact:.6f} m/s "
          f"({'PASS' if accepted else 'FAIL'})")
    if accepted:
        valid_springs.append((name, initial, impact))
if len(valid_springs) != 1:
    raise RuntimeError(f"Ambiguous viable spring choices: {valid_springs}")
spring, initial_speed, speed = valid_springs[0]

# Integrate time of flight under point-mass gravity.
fall_time, _ = quad(
    lambda r: 1.0 / np.sqrt(
        initial_speed ** 2
        + 2.0 * MU * (1.0 / r - 1.0 / R_START)
    ),
    R_CONTACT,
    R_START,
)

slot_base = float((SLOT_ZERO - ORIGIN).total_seconds())
slots = np.arange(SLOT_COUNT, dtype=int)
contact_times = slot_base + slots * SLOT_INTERVAL + fall_time

# Predict the brightness at each touchdown time.
predicted = np.full(SLOT_COUNT, coeffs[0], dtype=float)

for harmonic in range(1, 5):
    angle = 2.0 * np.pi * harmonic * contact_times / period
    predicted += coeffs[2 * harmonic - 1] * np.cos(angle)
    predicted += coeffs[2 * harmonic] * np.sin(angle)

# Lower astronomical magnitude means greater brightness.
best_slot = int(np.argmin(predicted))

print(f"Coarse period:   {coarse_period:.3f} s")
print(f"Rotation period: {period:.3f} s")
print(f"Fall time:       {fall_time:.3f} s")
print(f"Contact speed:   {speed:.6f} m/s")
print(f"Best slot:       {best_slot:04d}")
print(f"FLAG: GAIANSPACE{{{spring}-{best_slot:04d}}}")
