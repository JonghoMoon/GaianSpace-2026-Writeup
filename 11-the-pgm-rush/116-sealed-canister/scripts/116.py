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
