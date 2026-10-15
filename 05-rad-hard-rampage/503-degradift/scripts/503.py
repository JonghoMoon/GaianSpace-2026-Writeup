#!/usr/bin/env python3
import csv
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CSV_FILE = Path("sensor_log.csv")
KNOWN_PREFIX = "GAIANSPACE{"


def drift(n: int) -> int:
    value = Decimal("1.7") * Decimal(n)
    value += Decimal("0.013") * Decimal(n * n)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def main() -> None:
    readings: list[tuple[int, int]] = []

    with CSV_FILE.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            n = int(row["sample_n"])
            measured = int(row["co2_ppm"])
            readings.append((n, measured - drift(n)))

    readings.sort(key=lambda item: item[0])

    if len(readings) < len(KNOWN_PREFIX):
        raise ValueError("Not enough samples for the known flag prefix")

    indices = [index for index, _ in readings]
    if indices != list(range(len(readings))):
        raise ValueError("Expected consecutive sample indices starting at zero")

    # At n=0, drift is zero and the first plaintext character is 'G'.
    # The recovered reading equals baseline + ASCII character code.
    baseline = readings[0][1] - ord(KNOWN_PREFIX[0])

    codes = [adjusted - baseline for _, adjusted in readings]
    if not all(32 <= code <= 126 for code in codes):
        raise ValueError("Non-printable value after removing the baseline")

    message = "".join(chr(code) for code in codes)
    if not message.startswith(KNOWN_PREFIX):
        raise ValueError("The recovered prefix does not match GAIANSPACE{")
    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", message) is None:
        raise ValueError("Recovered data is not a valid flag")

    print(f"Baseline: {baseline} ppm")
    print(f"Samples: {len(readings)}")
    print(f"FLAG: {message}")


if __name__ == "__main__":
    main()
