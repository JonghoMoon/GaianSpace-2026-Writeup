# 117-the-dark-moonlet

| | |
|---|---|
| **Category** | 11 — The PGM Rush (Bonus) |
| **Points** | 250 |

## Description

The lander is down on the metal. The order is fulfilled. Then the little onboard lab sends back a result nobody asked for.

AO-111 went to `2041 QM23` for platinum. When its anchor went in, it broke through a dark streak of dust that does not belong to the metal rock. It came off the small, dark moonlet that circles it. The lab is there to assay metal, but it can also cook a sample and look for small organic molecules. It did.

Kaito has already decided it is aliens. Sunniva has decided it is gloves. Somewhere in the run there is one molecule from the moonlet that really does prefer one hand over the other, the way the molecules of life on Earth do. If it is real, it is the most important thing AsterOre has ever found, and it was an accident.

Name the molecule and how strongly it leans.

**Flag format:** `GAIANSPACE{<compound as written in the standards>_L<enantiomeric excess in percent, nearest whole number>}` — for example `GAIANSPACE{leucine_L7}`.

### Files

- `moonlet_sample.csv` — the lab's peak list for the moonlet dust
- `procedural_blank.csv` — the same procedure with no rock, run before launch
- `standards.csv` — known compounds on the same column, and the ion each is measured on
- `isotopes.csv` — carbon and nitrogen isotope ratios per peak, separate injection
- `lab_notes.md` — how the lab reports, and the desk's argument

*The PGM Rush is inspired by AstroForge, whose unusually open mission updates show how cheap, autonomous deep-space spacecraft could open the solar system not only to asteroid mining but to faster, cheaper science for everyone.*

## Solution

### Steps

Match the chiral chromatogram peaks to `standards.csv` using a ±0.03-minute retention-time tolerance, and use the compound-specific quantitative ion area (not the total-ion peak area). For each D/L pair calculate enantiomeric excess:

\[
ee=100rac{L-D}{L+D}.
\]

The supplied solver computes `aspartic_acid` with D=820 and L=1670, giving +34.14% (rounded to L34). The high serine excess and alanine excess should not automatically be treated as extraterrestrial: the procedural blank and carbon/nitrogen isotope measurements are relevant to distinguishing terrestrial contamination from moonlet material. **Reproduction limitation:** the supplied `117.py` reads the blank and isotope files but does not use them in its selection logic; the solver explicitly chooses `aspartic_acid`. The final flag matches the supplied run, but a full scientific justification should independently compare those controls.

### Reproduction

Run the original solver from the challenge's working directory, with the input files alongside the script as in the supplied ZIP.

```bash
python3 117.py
```

Expected relevant output:

```text
[Enantiomeric Excess]
alanine              D= 2100 L= 3600 ee=+26.32%
isovaline            D=  655 L=  662 ee=+0.53%
valine               D= 1180 L= 1195 ee=+0.63%
serine               D=   60 L= 1910 ee=+93.91%
aspartic_acid        D=  820 L= 1670 ee=+34.14%
glutamic_acid        D=  418 L=  425 ee=+0.83%

FLAG: GAIANSPACE{aspartic_acid_L34}
```

### Exploit Code

```python

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
```

## Flag

```text
GAIANSPACE{aspartic_acid_L34}
```
