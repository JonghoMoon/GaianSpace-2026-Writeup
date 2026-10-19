---
render_with_liquid: false
---

# 116 — Sealed Canister

| | |
|---|---|
| **Category** | 11 — The PGM Rush |
| **Points** | 300 |

## Description

The AO-111 sample canister was tested in a thermal-vacuum chamber before flight. The question is whether its seal opened during the thermal cycle, and if so, **which environmental record was the first one after the breach**.

**Attachments:**
- `cl3_0419_boot.txt` — logger boot log with the actual BME688 NVM register dump
- `cl3_0419_env.csv` — 1 Hz raw BME688 environmental ADC records
- `cl3_0419_co2.csv` — SCD-41 CO2 measurements at approximately 5-second intervals
- `cl3_datasheet.md` — CL-3 logger format and an example factory calibration table
- `tvac_report.md` — chamber profile, reference pressure, and operator notes

## Hints

Two hints were released during the event:

1. **Hint 1** — **One number.** A closed box of gas keeps one number fixed while it warms and cools. Find where it stops being fixed for good, not just for a moment.
2. **Hint 2** — **Shape or seal.** A box can change its shape without opening. After a step, ask whether the gas still obeys the same law.

## Solution

### Initial Investigation and Calibration Trap

The datasheet's factory calibration values belong to **CL3-0417**, while the actual instrument is **CL3-0419**. Using the table directly produces the wrong pressure. The boot log contains the correct sensor-specific NVM calibration in register regions `0x8A–0xA0`, `0xE1–0xEE`, and `0x00–0x02`.

Decode the Bosch BME68x temperature and pressure trims from the register bytes. The critical recovered values are `T1=26020` and `P1=37172`. The floating-point Bosch compensation formula produces **1018.668 hPa at record 0**, consistent with the test-house reference barometer of **1018.6 hPa**.

### Distinguishing Heating from a Leak

Pressure alone is misleading in a sealed cell undergoing heating and cooling. At fixed volume, a sealed gas obeys the ideal-gas relationship

$$
P/T_{K} \propto n
$$

where $T_{K}=T_{C}+273.15$. Therefore compare the *moles proxy* $P/T_{K}$, not just raw pressure.

The apparent pressure changes during the 45 °C hot soak are explained by temperature; they do not indicate loss of containment. The door-opening event at approximately record 3300 also does not produce a persistent decrease in the proxy.

### Finding the First Breach Record

The `tvac_report.md` setpoint table identifies the cooling phase (logger records **4200–6900**) independently of the breach timestamp. The supplied script parses the schedule, selects the longest decreasing-temperature segment, and uses the **first half** of that interval (4200–5550) as the normal-noise baseline. It calculates successive differences of `P/T_K`, estimates their center with a median and their robust noise scale with `σ = 1.4826 × MAD`, and flags a candidate below **−8σ** only if at least **three of the five differences starting at that candidate** are also below **−3σ**. The five-difference window includes the candidate's own change and the following four changes (`derivatives[index - 1:index + 4]`), not five additional changes after the candidate. The default script scans the cooling interval.

**The first sustained anomaly is record 6304 for all four tested baselines.** As an independent sensitivity check, the same compensated data and detection rule were evaluated with several reference intervals and search ranges:

| Baseline interval | Search range | Robust σ (`Δ(P/T_K)`) | First anomaly | z at rec 6304 |
|---|---|---:|---:|---:|
| 4200–5550 (early cooling) | Entire record | 1.00663 × 10⁻⁴ | **6304** | −9.59 |
| 6100–6290 (immediately before breach) | Cooling interval | 7.80014 × 10⁻⁵ | **6304** | −12.51 |
| 1–900 (before heating) | Entire record | 1.01481 × 10⁻⁴ | **6304** | −9.47 |
| 7000–8300 (low-temperature hold) | Entire record | 8.54423 × 10⁻⁵ | **6304** | −11.42 |

The two commonly cited scores, **−9.59** and **−12.51**, describe the *same* record 6304, not two different event detections. The shorter pre-event interval has a smaller estimated noise scale, hence a more negative standardized score. The 7000–8300 interval is a **retrospective robustness check**, not a baseline that would have been available for real-time detection. The table extends the default script's cooling-only search; it is not additional output printed by `116.py`.

The physical measurements support the same breakpoint:

- **Through record 6303:** during late cooling, `P/T_K` remains near **3.444**, with ordinary small fluctuations. At record 6303 it is **3.44392882**. The pre-breach fluctuations are not a strict ±1.2 × 10⁻⁴ bound on every difference.
- **Records 6304–6305:** the first differences suddenly fall to **−9.61 × 10⁻⁴** and **−1.48 × 10⁻³**, respectively. Record 6304 is the first sharp drop.
- **From approximately record 6500 onward:** pressure stays near **1007 hPa** while the cell temperature progresses from roughly **19 °C** down to **10 °C** and back toward **22 °C**, consistent with pressure equalizing to its surroundings after the seal opens. Earlier in the cycle, internal pressure changed substantially with temperature, reaching approximately **1097 hPa** during heating.

CO2 readings subsequently rise from near-zero values toward **418 ppm**, separately corroborating loss of containment. The SCD-41's sub-400 ppm readings are qualitative indications only, not reliable quantitative concentrations. The report's 950–1100 hPa acceptance range does not establish hermetic sealing because temperature-dependent pressure changes can mask gas loss.

### Reproduction

Run from the `116-sealed-canister/` directory with the original inputs in `challenges/` (`cl3_datasheet.md` is documentation, not a script input):

```bash
python3 scripts/116.py \
    --boot challenges/cl3_0419_boot.txt \
    --env challenges/cl3_0419_env.csv \
    --co2 challenges/cl3_0419_co2.csv \
    --report challenges/tvac_report.md
```

Expected relevant output:

```text
Logger calibration: T1=26020 P1=37172
Record 0: T=22.041 C, Bosch pressure=1018.668 hPa
Reference barometer: 1018.6 hPa
Cooling phase from test report: rec=4200..6900
Baseline interval: rec=4200..5550
Cooling baseline sigma: 0.00010066295
First sustained pressure anomaly: rec=6304 z=-9.59
Pre-event CO2 median: 0.0 ppm
Final CO2: 418 ppm
FLAG: GAIANSPACE{6304}
```

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
"""CL3-0419 seal-breach analysis from the original ADC and CO2 logs."""

import argparse
import csv
import math
import re
from pathlib import Path
from statistics import median


def signed(value: int, bits: int) -> int:
    """Interpret an unsigned register value as a signed integer."""
    limit = 1 << (bits - 1)
    return value - (1 << bits) if value >= limit else value


def load_registers(path: Path) -> dict[int, int]:
    """Parse address-indexed BME688 boot calibration bytes."""
    registers: dict[int, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"REG 0x([0-9a-fA-F]+) ((?:[0-9a-fA-F]{2}\s*)+)", line.strip())
        if match is None:
            continue
        address = int(match.group(1), 16)
        for offset, value in enumerate(match.group(2).split()):
            registers[address + offset] = int(value, 16)
    return registers


def calibration(reg: dict[int, int]) -> dict[str, int]:
    """Decode temperature and pressure trims using Bosch BME68x addresses."""
    def word(address: int) -> int:
        return reg[address] | (reg[address + 1] << 8)

    return {
        "T1": word(0xE9),
        "T2": signed(word(0x8A), 16),
        "T3": signed(reg[0x8C], 8),
        "P1": word(0x8E),
        "P2": signed(word(0x90), 16),
        "P3": signed(reg[0x92], 8),
        "P4": signed(word(0x94), 16),
        "P5": signed(word(0x96), 16),
        "P6": signed(reg[0x99], 8),
        "P7": signed(reg[0x98], 8),
        "P8": signed(word(0x9C), 16),
        "P9": signed(word(0x9E), 16),
        "P10": reg[0xA0],
    }


def compensate(temp_adc: int, press_adc: int, c: dict[str, int]) -> tuple[float, float]:
    """Bosch BME68x floating-point temperature and pressure compensation."""
    var1 = (temp_adc / 16384.0 - c["T1"] / 1024.0) * c["T2"]
    var2 = ((temp_adc / 131072.0 - c["T1"] / 8192.0) ** 2) * c["T3"] * 16.0
    t_fine = var1 + var2
    temperature = t_fine / 5120.0

    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * c["P6"] / 131072.0
    var2 += var1 * c["P5"] * 2.0
    var2 = var2 / 4.0 + c["P4"] * 65536.0
    var1 = (c["P3"] * var1 * var1 / 16384.0 + c["P2"] * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * c["P1"]

    pressure = 1048576.0 - float(press_adc)
    pressure = (pressure - var2 / 4096.0) * 6250.0 / var1
    var1 = c["P9"] * pressure * pressure / 2147483648.0
    var2 = pressure * c["P8"] / 32768.0
    var3 = (pressure / 256.0) ** 3 * c["P10"] / 131072.0
    pressure += (var1 + var2 + var3 + c["P7"] * 128.0) / 16.0
    return temperature, pressure / 100.0


def load_csv(path: Path) -> list[dict[str, int]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {name: int(value) for name, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot", type=Path, default=Path("cl3_0419_boot.txt"))
    parser.add_argument("--env", type=Path, default=Path("cl3_0419_env.csv"))
    parser.add_argument("--co2", type=Path, default=Path("cl3_0419_co2.csv"))
    parser.add_argument("--report", type=Path, default=Path("tvac_report.md"))
    args = parser.parse_args()

    c = calibration(load_registers(args.boot))
    rows = load_csv(args.env)
    co2 = load_csv(args.co2)

    temp: list[float] = []
    pressure: list[float] = []
    for row in rows:
        t, p = compensate(row["t_adc"], row["p_adc"], c)
        temp.append(t)
        pressure.append(p)

    print(f"Logger calibration: T1={c['T1']} P1={c['P1']}")
    print(f"Record 0: T={temp[0]:.3f} C, Bosch pressure={pressure[0]:.3f} hPa")
    print("Reference barometer: 1018.6 hPa")

    # An absolute-pressure mismatch is reported instead of being hidden.
    if abs(pressure[0] - 1018.6) > 5.0:
        print("WARNING: The raw pressure compensation disagrees with the reference.")
        print("The breach detector below uses pressure changes, not absolute pressure.")

    # Use temperature-normalized pressure to remove ideal-gas heating/cooling.
    proxy = [
        p / (t + 273.15)
        for p, t in zip(pressure, temp)
    ]

    # Select the cooling phase from the supplied thermal-vacuum report.
    report = args.report.read_text(encoding="utf-8")
    setpoints: list[tuple[int, float]] = []
    for line in report.splitlines():
        match = re.search(
            r"\|\s*\d{2}:\d{2}:\d{2}\s*\|\s*\+(\d+)\s*s\s*\|\s*([0-9.]+)\s*\|",
            line,
        )
        if match:
            setpoints.append((int(match.group(1)), float(match.group(2))))
    cooling_phases = [
        (start[0], end[0])
        for start, end in zip(setpoints, setpoints[1:])
        if end[1] < start[1]
    ]
    if not cooling_phases:
        raise ValueError("No decreasing-temperature interval in test report")
    cooling_start, cooling_end = max(cooling_phases, key=lambda pair: pair[1] - pair[0])

    # The first half of the cooling phase estimates the normal derivative.
    derivatives = [proxy[i] - proxy[i - 1] for i in range(1, len(proxy))]
    baseline_end = cooling_start + (cooling_end - cooling_start) // 2
    baseline = derivatives[cooling_start:baseline_end]
    center = median(baseline)
    mad = median(abs(value - center) for value in baseline)
    sigma = max(1.4826 * mad, 1.0e-12)
    print(f"Cooling phase from test report: rec={cooling_start}..{cooling_end}")
    print(f"Baseline interval: rec={cooling_start}..{baseline_end}")

    candidates: list[tuple[int, float]] = []
    for index in range(cooling_start + 1, min(cooling_end, len(rows) - 5)):
        score = (derivatives[index - 1] - center) / sigma
        if score < -8.0:
            following = derivatives[index - 1:index + 4]
            if sum(value < center - 3.0 * sigma for value in following) >= 3:
                candidates.append((index, score))

    print(f"Cooling baseline sigma: {sigma:.8g}")
    if not candidates:
        raise RuntimeError("No sustained breach candidate; inspect calibration and thresholds.")

    first, score = candidates[0]
    print(f"First sustained pressure anomaly: rec={rows[first]['rec']} z={score:.2f}")
    print(f"Pre-event CO2 median: {median(x['co2_ppm'] for x in co2 if x['rec'] < rows[first]['rec']):.1f} ppm")
    print(f"Final CO2: {co2[-1]['co2_ppm']} ppm")
    print(f"FLAG: GAIANSPACE{{{rows[first]['rec']}}}")


if __name__ == "__main__":
    main()
```

### Tools and References

- Python 3 standard library (`csv`, `statistics`, `re`, `pathlib`)
- Bosch Sensortec BME68x pressure/temperature compensation and NVM calibration mapping
- Provided `cl3_datasheet.md` and `tvac_report.md`
- Ideal-gas law for constant-volume containment checks

### Dead Ends and Caveats

- The CL3-0417 calibration table is **not** the calibration for this logger.
- A hot-soak pressure change is **not** sufficient evidence of a leak.
- The pressure-range PASS in the test report is not a seal-integrity test.
- CO2 ingress corroborates the breach but lags the first pressure anomaly, so it cannot determine the exact first record alone.

## Flag

```text
GAIANSPACE{6304}
```
