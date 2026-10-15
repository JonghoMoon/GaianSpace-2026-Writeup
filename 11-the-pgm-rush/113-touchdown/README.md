# 113-touchdown

| | |
|---|---|
| **Category** | 11 — The PGM Rush |
| **Points** | 250 |

## Description

AO-111 is holding station 500 m above `2041 QM23`. The lander has one spring, one shot, and no radio that can hear Earth.

The rock is light-minutes away, so nobody gets to steer. Everything the lander needs has to be on the order before it lets go: which spring, and which release slot. After that it falls, slowly, onto a spinning metal rock in almost no gravity. If it comes in too fast it bounces back into space. If it comes in at the wrong moment it lands on plain rock and the trip was for nothing.

The hover camera has watched the rock turn for two days. Kaito says the period is obvious. Sunniva wants the order checked twice.

Write the order.

**Flag format:** `GAIANSPACE{<spring>-<slot as four digits>}` — for example `GAIANSPACE{B-0042}`.

### Files

- `hover_photometry.csv` — the hover camera's brightness record of the rock, UTC
- `descent_card.md` — the rock, the hover station, the lander, and the release slots

*The PGM Rush is inspired by AstroForge, whose unusually open mission updates show how cheap, autonomous deep-space spacecraft could open the solar system not only to asteroid mining but to faster, cheaper science for everyone.*

## Solution

### Steps

Fit a four-harmonic Fourier model to the brightness series to recover the rotational period, accounting for the double-peaked light curve of an elongated body. The fitted period is 5848.911 s. From the descent card, use the asteroid's gravitational parameter `GM = 0.2123 m³/s²`, release radius 500 m, contact radius 50 m, and spring A speed 0.020 m/s. Conservation of energy gives a contact speed of 0.089682 m/s, below the 0.110 m/s limit. Integrate radial fall time (13690.834 s). For each release slot, calculate the **contact** time and use the Fourier model to predict which face is directed toward the lander then. The brightest contact configuration selects slot `0242`. Spring B would exceed the contact-speed limit.

### Reproduction

Run the original solver from the challenge's working directory, with the input files alongside the script as in the supplied ZIP.

```bash
python3 113.py
```

Expected relevant output:

```text
Rotation period: 5848.911 s
Fall time:       13690.834 s
Contact speed:   0.089682 m/s
Best slot:       0242
FLAG: GAIANSPACE{A-0242}
```

### Exploit Code

```python
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
```

## Flag

```text
GAIANSPACE{A-0242}
```
