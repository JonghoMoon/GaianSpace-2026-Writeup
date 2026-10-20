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

## Hints

Two hints were released during the event:

1. **Two faces** — An elongated rock shows you its broad side twice every turn. The two views are not quite the same.
2. **Slow fall** — The lander is not moving at the speed the spring gave it for most of the way down. And the rock keeps turning while it falls.

## Solution

### Steps

The lander release time must be chosen for the **rotation phase at contact**, not at release. `descent_card.md` supplies GM, radii, spring speeds, contact speed limit, and the 540 release slots. The photometry constrains the asteroid's light-curve phase.

The revised solver first scans rotation periods from **2,000 to 12,000 seconds** at 5-second intervals, then refines the lowest four-harmonic least-squares error. It finds a coarse period of 5,850 s and a refined period of **5,848.911 s**. This avoids embedding a narrow range chosen around the already-known result. Harmonic aliases are possible with sparse photometry, but the best candidate's error is the lowest in the scanned range.

Energy conservation gives the radial contact speed for each spring:

$$
v_{contact}=\sqrt{v_{initial}^{2}+2GM\left(\frac{1}{r_{contact}}-\frac{1}{r_{start}}\right)}.
$$

| Spring | Initial speed | Contact speed | Limit 0.110 m/s |
|---|---:|---:|---|
| A | 0.020 m/s | 0.089682 m/s | PASS |
| B | 0.080 m/s | 0.118502 m/s | FAIL |

Spring A is the only viable choice. Integrating the radial descent equation gives a flight time of **13,690.834 s**. For each release slot, the solver adds this flight time, evaluates the fitted light curve at contact, and selects the brightest contact phase (smaller astronomical magnitude means brighter). The best release is **slot 0242**, giving `GAIANSPACE{A-0242}`.

### Reproduction

Run the original solver from the challenge's working directory, with the input files alongside the script as in the supplied ZIP.

```bash
python3 113.py
```

Expected relevant output:

```text
Spring A: contact speed=0.089682 m/s (PASS)
Spring B: contact speed=0.118502 m/s (FAIL)
Coarse period:   5850.000 s
Rotation period: 5848.911 s
Fall time:       13690.834 s
Contact speed:   0.089682 m/s
Best slot:       0242
FLAG: GAIANSPACE{A-0242}
```

### Solver Code

{% raw %}
```python
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
```
{% endraw %}

## Flag

```text
GAIANSPACE{A-0242}
```
