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

## Solution

### Steps

1. Read the PA temperature samples and verify the one-second sample interval.
2. Use the known `GAIANSPACE{` prefix to fit the first-order thermal equation by least squares.
3. Recover the gain `K`, thermal time constant `tau`, and ambient temperature.
4. Invert the model to estimate the drive sequence.
5. Round to integer ASCII values, check the residuals, and decode the message.

### Reproduction

Run the provided solver with the challenge input files in the locations expected by the script.

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
```

### Exploit Code

```python

#!/usr/bin/env python3
import csv
from pathlib import Path

import numpy as np

CSV_FILE = Path("thermal_log.csv")
KNOWN_PREFIX = b"GAIANSPACE{"


def main() -> None:
    with CSV_FILE.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    times = np.array([float(row["t_s"]) for row in rows], dtype=float)
    temps = np.array([float(row["temp_c"]) for row in rows], dtype=float)

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

    print(f"K: {k:.8f}")
    print(f"tau: {tau:.8f} s")
    print(f"Tamb: {ambient:.8f} C")
    print(f"Maximum integer residual: {residual:.8f}")
    print(f"Drive sequence: {drive.tolist()}")
    print(f"Decoded message: {message}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{therm4l_duty_cycle}
```
