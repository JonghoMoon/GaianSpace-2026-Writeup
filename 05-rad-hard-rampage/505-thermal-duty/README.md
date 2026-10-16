# 505-thermal-duty

| | |
|---|---|
| **Category** | 05 — Rad Hard Rampage |
| **Points** | 75 |

## Description

Foundation One's radio has no business running flat out — deep space is cold, but a transmitter with nowhere to dump its heat cooks itself. The flight software duty-cycles the power amplifier to stay under the limit. During one pass the housekeeping logged the PA case temperature the whole time. The thermal team wants to know exactly how hard the amplifier was being driven, moment to moment.

The temperature log is all you have; the drive signal itself was never recorded. The thermal behaviour of the case is a plain first-order model, but the sheet with its fitted constants walked out the door with the last thermal lead. Put the constants back, run the temperature curve through the model, and the drive it was fed falls out, one step at a time. The on-call swears the drive was a steady hum. It was not steady.

Recover the drive sequence the amplifier was given.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `thermal_log.csv` — time and PA case temperature
- `thermal_model.md` — the first-order thermal model, without its constants

## Hints

Two hints were released during the event:

1. **Driven, not drifting** — The temperature does not wander on its own; something pushes it each step. You already know what the first few pushes spelled, so you know the drive for the first few steps.
2. **Counts, then characters** — Solve the model for the drive at each step. The recovered counts are small whole numbers, and they read as text.

## Solution

### Analysis

The attached `thermal_model.md` specifies a first-order lumped model sampled
once per second:

$$
T_{n+1}=T_n+\Delta t\left(KP_n-\frac{T_n-T_{amb}}{\tau}\right),
\qquad \Delta t=1\text{ s}.
$$

Here `T` is PA case temperature, `P` the unknown integer drive count, `K` the
heating coefficient, `T_amb` the sink temperature, and `tau` the thermal time
constant. Rearranging for the observed one-second temperature difference gives:

$$
\Delta T_n=T_{n+1}-T_n=KP_n-\frac{1}{\tau}T_n
+\frac{T_{amb}}{\tau}.
$$

Define `A = 1/tau` and `B = T_amb/tau`. The equation becomes **linear in the
reparameterized unknowns** `K`, `A`, and `B`:

$$
\Delta T_n=KP_n-AT_n+B.
$$

The flag format provides a known prefix, `GAIANSPACE{`, so its 11 ASCII values
supply the first 11 drive counts. For those steps, the solver builds a matrix
with row `[P_n, -T_n, 1]` and fits the coefficients `[K, A, B]` by least
squares against the measured `Delta T_n`. The temperature samples are stored
with finite decimal precision, so least squares is preferable to solving only
three equations exactly.

The fitted values are approximately:

```text
K    = 0.02000001
A    = 1 / 40
B    = 20 / 40

tau  = 1 / A = 40 s
Tamb = B / A = 20 C
```

Having recovered the model, invert the equation for **every** sample step:

$$
P_n=\frac{\Delta T_n+AT_n-B}{K}.
$$

The values are almost integers; rounding yields the ASCII sequence for the
complete flag. The solver checks the maximum deviation from the nearest
integer, verifies the ASCII range, and confirms the required flag syntax.

### Steps

1. Read temperatures and verify that successive timestamps differ by 1 second.
2. Fit `K`, `A`, and `B` using the known 11-byte flag prefix.
3. Recover `tau = 1/A` and `T_amb = B/A`.
4. Invert the thermal equation to estimate every drive count.
5. Round to ASCII integers, check residuals, and verify the flag.

### Reproduction

Place the solver and this challenge's input files in the same directory and run:

```bash
python3 505.py
```

Expected relevant output:

```text
K: 0.02000001
tau: 40.00000351 s
Tamb: 19.99997964 C
Maximum integer residual: 0.00005205
Drive sequence: [71, 65, 73, 65, 78, 83, 80, 65, 67, 69, 123, 116, 104, 101, 114, 109, 52, 108, 95, 100, 117, 116, 121, 95, 99, 121, 99, 108, 101, 125]
Decoded message: GAIANSPACE{therm4l_duty_cycle}
FLAG: GAIANSPACE{therm4l_duty_cycle}
```

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies: numpy (least-squares model fitting)
# Install: python3 -m pip install numpy

import csv
import re
from pathlib import Path

import numpy as np

CSV_FILE = Path("thermal_log.csv")
KNOWN_PREFIX = b"GAIANSPACE{"


def main() -> None:
    with CSV_FILE.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    times = np.array([float(row["t_s"]) for row in rows], dtype=float)
    temps = np.array([float(row["temp_c"]) for row in rows], dtype=float)

    if len(rows) < len(KNOWN_PREFIX) + 1:
        raise ValueError("Insufficient samples for fitting the known prefix")

    dt = np.diff(times)
    if not np.allclose(dt, 1.0):
        raise ValueError("Expected one sample per second")

    delta = np.diff(temps)
    count = len(KNOWN_PREFIX)

    if delta.size < count:
        raise ValueError("Insufficient samples")

    # Fit delta_T = K * P - A * T + B using known ASCII prefix.
    matrix = np.column_stack((
        np.frombuffer(KNOWN_PREFIX, dtype=np.uint8).astype(float),
        -temps[:count],
        np.ones(count),
    ))

    coefficients, _, _, _ = np.linalg.lstsq(
        matrix, delta[:count], rcond=None
    )

    k = float(coefficients[0])
    a = float(coefficients[1])
    b = float(coefficients[2])

    if not np.all(np.isfinite(coefficients)) or k <= 0.0 or a <= 0.0:
        raise ValueError("Non-physical or non-finite thermal model parameters")

    tau = 1.0 / a
    ambient = b / a

    # Recover the drive counts from the thermal model.
    drive_float = (delta + a * temps[:-1] - b) / k
    drive = np.rint(drive_float).astype(int)

    residual = np.max(np.abs(drive_float - drive))

    if residual > 0.001:
        raise ValueError(f"Drive values are not integers: {residual}")

    if np.any((drive < 0) | (drive > 127)):
        raise ValueError("Recovered drive contains invalid ASCII values")

    message = bytes(int(value) for value in drive).decode("ascii")
    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", message) is None:
        raise ValueError("Recovered drive does not form a valid flag")

    print(f"K: {k:.8f}")
    print(f"tau: {tau:.8f} s")
    print(f"Tamb: {ambient:.8f} C")
    print(f"Maximum integer residual: {residual:.8f}")
    print(f"Drive sequence: {drive.tolist()}")
    print(f"Decoded message: {message}")
    print(f"FLAG: {message}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{therm4l_duty_cycle}
```
