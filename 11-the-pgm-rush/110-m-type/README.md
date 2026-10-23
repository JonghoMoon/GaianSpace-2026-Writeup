# 110-m-type

| | |
|---|---|
| **Category** | 11 — The PGM Rush |
| **Points** | 100 |

## Description

AsterOre Inc. has hundreds of prospectors out among the near-Earth rocks and one more sitting fuelled in its parking orbit. It needs a name before morning.

Prospecting lead Sunniva Haldane hands you last night's survey: fourteen new rocks, a spectrum for each, an albedo from the thermal survey, and whatever radar time the desk could beg. Somewhere in the sheet is the only one worth the trip, a metal-rich body with platinum-group metals in it. Kaito, on nights, already circled the brightest one. He is sure. He is usually sure.

Sunniva will sign the order only with the rock's designation and its size.

**Flag format:** `GAIANSPACE{<designation with the space removed>_<diameter in metres, rounded to the nearest 10>}` — for example `GAIANSPACE{2039AB1_350}`.

### Files

- `spectra.csv` — reflectance spectra, 0.45–2.45 µm, normalized at 0.55 µm, one column per rock
- `survey_night.csv` — absolute magnitude and visible albedo from the thermal survey
- `radar_notes.md` — the radar log and the desk's notes from the same night

*The PGM Rush is inspired by AstroForge, whose unusually open mission updates show how cheap, autonomous deep-space spacecraft could open the solar system not only to asteroid mining but to faster, cheaper science for everyone.*

## Hints

Two hints were released during the event:

1. **Same face, different shine** — Several rocks have the same flat, featureless spectrum. They are not the same kind of rock. The spectrum alone cannot tell them apart.
2. **Size from brightness** — A rock's size is not in the survey sheet, but the two numbers that give it are.

## Solution

### Steps

The selection must be established from the survey rather than entered as an answer. The revised solver compares **all fourteen** objects in `survey_night.csv` and `spectra.csv`, then reads the target-specific measurements in `radar_notes.md`.

The 0.90 µm reflectance is compared to a linear continuum interpolated between 0.75 and 1.25 µm. Strong absorption near 1 µm is a warning sign against a featureless, metallic-looking spectrum. For example, `2041 QW9` has a band-to-continuum ratio of about 0.833; `2041 QN2` is about 0.631, whereas `2041 QM23` is about 0.989. These spectral indicators alone do not establish mineral composition.

**Why not the brightest radar echo?** The note for `2041 QF8` reports SNR 940 but also the closest approach, 0.011 AU, so raw echo strength is not a distance-independent radar-albedo measurement. The explicitly measured **radar albedo 0.41** belongs to `2041 QM23`, whose near-1 µm spectrum also lacks a strong absorption. The solver therefore selects the unique target with a measured radar albedo at least 0.30 and a 0.90 µm continuum ratio of at least 0.90. These are **transparent, challenge-specific evidence filters**, not universal thresholds for M-type classification or proof of platinum-group metals. Objects without radar-albedo measurements cannot be conclusively ruled out physically; this identifies the challenge's best-supported prospect.

The target has absolute magnitude `H=22.1` and visible albedo `pV=0.180`. Its equivalent diameter follows the standard relation:

$$
D_{\mathrm{km}}=\frac{1329}{\sqrt{p_V}}10^{-H/5}.
$$

This gives **119.094 m**; rounding to the nearest 10 metres produces **120 m** and the designation has its space removed.

### Reproduction

Run the original solver from the challenge's working directory, with the input files alongside the script as in the supplied ZIP.

```bash
python3 110.py
```

Expected relevant output (after the fourteen-object evidence table):

```text
Selected prospect: 2041 QM23
Diameter: 119.094 m
FLAG: GAIANSPACE{2041QM23_120}
```

### Solver Code

```python
#!/usr/bin/env python3
"""Compare the asteroid optical survey against quantified radar evidence.

Dependencies: Python 3 standard library only.
"""
import csv
import math
import re
from pathlib import Path


def load_csv(name: str) -> list[dict[str, str]]:
    with Path(name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


survey = load_csv("survey_night.csv")
sp_rows = load_csv("spectra.csv")
radar_lines = Path("radar_notes.md").read_text(encoding="utf-8").splitlines()

spectra: dict[str, dict[float, float]] = {}
for row in sp_rows:
    wavelength = float(row["wavelength_um"])
    for key, value in row.items():
        if key != "wavelength_um":
            spectra.setdefault(key.replace("_", " "), {})[wavelength] = float(value)

radar: dict[str, float] = {}
for line in radar_lines:
    if not line.startswith("|"):
        continue
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    if len(cells) < 3:
        continue
    hit = re.search(r"Radar albedo\s+([0-9.]+)", " ".join(cells[1:]), flags=re.I)
    if hit:
        radar[cells[0]] = float(hit.group(1))

if len(survey) != 14 or len(spectra) != 14:
    raise ValueError("Expected fourteen survey targets and spectra")

print("[Full survey and radar comparison]")
qualified: list[tuple[float, dict[str, str]]] = []
for record in survey:
    name = record["designation"]
    spectrum = spectra[name]
    # Use an approximate straight-line continuum around the 0.9-um band.
    continuum = spectrum[0.75] + (spectrum[1.25] - spectrum[0.75]) * 0.30
    band_ratio = spectrum[0.90] / continuum
    radar_albedo = radar.get(name)
    label = f"{radar_albedo:.2f}" if radar_albedo is not None else "not measured"
    print(f"{name:12s} pV={float(record['pV']):.3f} "
          f"R0.90={spectrum[0.90]:.3f} band/continuum={band_ratio:.3f} "
          f"radar_albedo={label}")
    # These are explicit, challenge-specific evidence screening thresholds,
    # not universal rules for mineralogy or proof of platinum-group metals.
    if radar_albedo is not None and radar_albedo >= 0.30 and band_ratio >= 0.90:
        qualified.append((radar_albedo, record))

if len(qualified) != 1:
    raise ValueError(f"Ambiguous radar-supported metallic prospect: {qualified}")

target = qualified[0][1]
h = float(target["H_mag"])
pv = float(target["pV"])
diameter_m = (1329.0 / math.sqrt(pv)) * (10.0 ** (-h / 5.0)) * 1000.0
rounded_m = int(math.floor(diameter_m / 10.0 + 0.5)) * 10
name = target["designation"].replace(" ", "")
print(f"\nSelected prospect: {target['designation']}")
print(f"Diameter: {diameter_m:.3f} m")
print(f"FLAG: GAIANSPACE{{{name}_{rounded_m}}}")
```

## Flag

```text
GAIANSPACE{2041QM23_120}
```
