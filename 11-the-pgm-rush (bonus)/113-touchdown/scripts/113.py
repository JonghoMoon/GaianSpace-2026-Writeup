import numpy as np
import pandas as pd
from scipy.integrate import quad
from scipy.optimize import minimize_scalar

MU = 0.2123
R_START = 500.0
R_CONTACT = 50.0
V_INITIAL = 0.020
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


fit = minimize_scalar(
    lambda period: fit_period(period)[0],
    bounds=(5800.0, 5900.0),
    method="bounded",
)

period = float(fit.x)
_, coeffs = fit_period(period)

# Calculate contact speed using energy conservation.
speed = np.sqrt(
    V_INITIAL ** 2
    + 2.0 * MU * (1.0 / R_CONTACT - 1.0 / R_START)
)

if speed > MAX_SPEED:
    raise RuntimeError("Spring exceeds landing speed limit")

# Integrate time of flight under point-mass gravity.
fall_time, _ = quad(
    lambda r: 1.0 / np.sqrt(
        V_INITIAL ** 2
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

print(f"Rotation period: {period:.3f} s")
print(f"Fall time:       {fall_time:.3f} s")
print(f"Contact speed:   {speed:.6f} m/s")
print(f"Best slot:       {best_slot:04d}")
print(f"FLAG: GAIANSPACE{{A-{best_slot:04d}}}")
