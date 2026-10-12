# 503-degradift

| | |
|---|---|
| **Category** | 05 — Rad Hard Rampage |
| **Points** | 144 |

## Description

The Foundation One CO2 sensor did not fail in a day. Displacement damage builds up: the lattice takes hit after hit, the readings creep, and by the end of the run the numbers have wandered far from the truth. We logged the whole decline. The characterization team worked out exactly how fast it drifts.

Here is the sensor diary and the drift model that fits it. Pull the drift back out of each reading and you are left with what the sensor was really seeing. The on-call will tell you the recovered numbers are just cleaner CO2 readings. Look at them again. They are not CO2.

Recover the as-flown readings and read what they spell.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `sensor_log.csv` — sample index and the degraded reading
- `ddd_characterization.md` — the measured drift model

## Solution

### Steps

1. Read each sample index and degraded CO2 measurement.
2. Compute the modeled displacement-damage drift, rounding half up.
3. Subtract the drift from each reading.
4. Try plausible baseline concentrations and interpret residuals as ASCII codes.
5. Select the valid flag string.

### Reproduction

Run the provided solver with the challenge input files in the locations expected by the script.

```bash
python3 503.py
```

Expected relevant output:

```text
Baseline: 333 ppm
Samples: 30
FLAG: GAIANSPACE{displ4cement_drift}
```

### Exploit Code

```python

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
```

## Flag

```text
GAIANSPACE{displ4cement_drift}
```
