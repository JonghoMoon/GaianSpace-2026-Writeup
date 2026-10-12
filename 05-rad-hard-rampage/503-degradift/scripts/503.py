
#!/usr/bin/env python3
import csv
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CSV_FILE = Path("sensor_log.csv")


def drift(n: int) -> int:
    value = Decimal("1.7") * Decimal(n)
    value += Decimal("0.013") * Decimal(n * n)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def main() -> None:
    readings = []

    with CSV_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n = int(row["sample_n"])
            measured = int(row["co2_ppm"])
            readings.append((n, measured - drift(n)))

    readings.sort(key=lambda item: item[0])

    for baseline in range(320, 351):
        codes = [value - baseline for _, value in readings]

        if not all(32 <= code <= 126 for code in codes):
            continue

        message = "".join(chr(code) for code in codes)

        if re.fullmatch(r"GAIANSPACE\{[^}]+\}", message):
            print(f"Baseline: {baseline} ppm")
            print(f"Samples: {len(readings)}")
            print(f"FLAG: {message}")
            return

    raise RuntimeError("No valid flag found")


if __name__ == "__main__":
    main()

