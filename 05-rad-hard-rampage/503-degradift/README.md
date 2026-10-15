# 503-degradift

| | |
|---|---|
| **Category** | 05 — Rad Hard Rampage |
| **Points** | 100 |

## Description

The Foundation One CO2 sensor did not fail in a day. Displacement damage builds up: the lattice takes hit after hit, the readings creep, and by the end of the run the numbers have wandered far from the truth. We logged the whole decline. The characterization team worked out exactly how fast it drifts.

Here is the sensor diary and the drift model that fits it. Pull the drift back out of each reading and you are left with what the sensor was really seeing. The on-call will tell you the recovered numbers are just cleaner CO2 readings. Look at them again. They are not CO2.

Recover the as-flown readings and read what they spell.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `sensor_log.csv` — sample index and the degraded reading
- `ddd_characterization.md` — the measured drift model

## Solution

### Analysis

`ddd_characterization.md` specifies the cumulative displacement-damage bias in
parts per million. For sample index `n`:

$$
D(n)=\operatorname{round}_{\text{half-up}}(1.7n+0.013n^2).
$$

The measured reading includes both the original signal and this bias:

$$
M(n)=B+\operatorname{ASCII}(c_n)+D(n),
$$

where `B` is an unknown fixed CO2 baseline. Subtracting the modeled drift
recovers the baseline plus the encoded character:

$$
R(n)=M(n)-D(n)=B+\operatorname{ASCII}(c_n).
$$

The challenge provides the flag format `GAIANSPACE{...}`, so the first character
must be `G` (`ASCII 71`). The first CSV row gives `sample_n = 0` and
`co2_ppm = 404`, and `D(0) = 0`. This determines the baseline **directly**:

$$
B=404-0-71=\boxed{333\text{ ppm}}.
$$

No baseline sweep and no hardcoded value `333` are needed. For every row, the
solver applies **decimal round-half-up** (rather than Python's default
round-to-even behavior), subtracts both `D(n)` and the derived baseline, and
converts the result to ASCII. The recovered prefix is checked against the
known flag format, and the full message is validated.

### Steps

1. Load and sort the logged sample indices and readings.
2. Calculate the specified drift using decimal half-up rounding.
3. Derive the baseline from sample zero and the known initial `G`.
4. Subtract the drift and baseline from every reading to obtain ASCII codes.
5. Verify the prefix, printable character values, and final flag format.

### Reproduction

Place the solver and this challenge's input files in the same directory and run:

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
```

## Flag

```text
GAIANSPACE{displ4cement_drift}
```
