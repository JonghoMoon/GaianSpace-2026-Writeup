
import csv
from pathlib import Path

BASE = Path(".")
TOLERANCE_MIN = 0.03

def read_csv(filename: str) -> list[dict[str, str]]:
    with (BASE / filename).open(
        "r", encoding="utf-8", newline=""
    ) as file:
        return list(csv.DictReader(file))

standards = read_csv("standards.csv")
sample = read_csv("moonlet_sample.csv")
blank = read_csv("procedural_blank.csv")
isotopes = read_csv("isotopes.csv")

areas: dict[str, dict[str, int]] = {}

for standard in standards:
    compound = standard["compound"]
    enantiomer = standard["enantiomer"]

    if enantiomer not in ("D", "L"):
        continue

    retention = float(standard["retention_min"])
    ion = f"m{int(standard['quant_ion_mz'])}"

    matches = [
        row for row in sample
        if abs(float(row["rt_min"]) - retention) <= TOLERANCE_MIN
    ]

    if len(matches) != 1:
        raise ValueError(f"Ambiguous peak: {compound} {enantiomer}")

    area = int(matches[0][ion])
    areas.setdefault(compound, {})[enantiomer] = area

print("[Enantiomeric Excess]")

for compound, pair in areas.items():
    if "D" not in pair or "L" not in pair:
        continue

    d = pair["D"]
    l = pair["L"]
    ee = (float(l - d) / float(l + d)) * 100.0

    print(f"{compound:20s} D={d:5d} L={l:5d} ee={ee:+.2f}%")

target = "aspartic_acid"
d = areas[target]["D"]
l = areas[target]["L"]
ee = (float(l - d) / float(l + d)) * 100.0

print(f"\nFLAG: GAIANSPACE{{{target}_L{round(ee)}}}")
