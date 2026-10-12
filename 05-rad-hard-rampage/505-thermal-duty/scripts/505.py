
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

