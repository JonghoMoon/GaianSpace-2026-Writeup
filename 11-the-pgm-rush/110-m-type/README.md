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

## Solution

### Steps

The radar notes warn against selecting `2041 QF8` simply because it has the strongest echo and a bright, flat-looking spectrum: its close approach boosts the echo. The metal-rich target is `2041 QM23`, whose radar albedo is 0.41 and whose optical properties must be assessed together with the full spectrum. The supplied solver takes the already identified target from `survey_night.csv`, reads its absolute magnitude `H` and visible albedo `pV`, and applies the standard diameter–albedo relation:

\[
D_{\mathrm{km}}=rac{1329}{\sqrt{p_V}}10^{-H/5}.
\]

Convert to metres and round to the nearest 10 m. **Reproduction limitation:** `110.py` hardcodes `2041 QM23` as the target and does not programmatically rank all fourteen spectra. The supporting selection rationale comes from the survey and radar evidence.

### Reproduction

Run the original solver from the challenge's working directory, with the input files alongside the script as in the supplied ZIP.

```bash
python3 110.py
```

Expected relevant output:

```text
Diameter: 119.094 m
FLAG: GAIANSPACE{2041QM23_120}
```

### Exploit Code

```python
import csv
import math

with open("survey_night.csv", encoding="utf-8", newline="") as file:
    records = list(csv.DictReader(file))

target = next(
    row for row in records
    if row["designation"] == "2041 QM23"
)

h = float(target["H_mag"])
pv = float(target["pV"])

diameter_m = (
    1329.0 / math.sqrt(pv)
    * 10.0 ** (-h / 5.0)
    * 1000.0
)

rounded_m = int(math.floor(diameter_m / 10.0 + 0.5) * 10)

designation = target["designation"].replace(" ", "")
print(f"Diameter: {diameter_m:.3f} m")
print(f"FLAG: GAIANSPACE{{{designation}_{rounded_m}}}")
```

## Flag

```text
GAIANSPACE{2041QM23_120}
```
