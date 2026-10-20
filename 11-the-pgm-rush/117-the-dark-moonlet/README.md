# 117-the-dark-moonlet

| | |
|---|---|
| **Category** | 11 — The PGM Rush |
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

## Hints

Two hints were released during the event:

1. **Our own hands** — Anything the lab finds on an empty run was brought from home. Take it away before you count.
2. **Too much signal** — Not every big peak is one molecule. Count each compound on the ion it is meant to be counted on.

## Solution

### Steps

Match each chiral chromatogram peak to the known standard using a **±0.03-minute** retention-time tolerance. Use the corresponding compound's quantitative ion (`quant_ion_mz`), **not** the total-ion area, to calculate enantiomeric excess:

$$
ee = 100 \cdot \frac{L - D}{L + D}
$$

The sample alone is insufficient to determine which positive ee is authentic. The revised code examines **both D and L peaks** in the procedural blank and carbon/nitrogen isotope run. The relevant comparison is:

| Compound | Sample ee | Blank at D/L quant-ion peaks | Isotope evidence |
|---|---:|---|---|
| Alanine | +26.32% | L blank=1,480 versus sample L=3,600 | L carbon ratio less elevated than other extraterrestrial candidates |
| Serine | +93.91% | L blank=1,850 versus sample L=1,910 | L peak δ¹³C = −22.7‰, δ¹⁵N = +3.1‰, terrestrial-like |
| **Aspartic acid** | **+34.14%** | **No overlapping procedural-blank peaks** | **D: +27.2/+88.4‰; L: +27.8/+86.9‰ (δ¹³C/δ¹⁵N)** |

Isovaline and glutamic acid have heavy isotopes and low blank contamination, but almost no handed excess (+0.53% and +0.83%); valine is similarly nearly racemic and has an unavailable isotope measurement. The solver screens for (a) ≤5% blank contribution to each enantiomer's sample area, (b) both D and L isotope values >+15‰ carbon and >+25‰ nitrogen, and (c) ≥5% L excess. **These cutoffs are explicit heuristics for this dataset, not validated laboratory thresholds or proof of biological activity.** Only aspartic acid passes all three screens, so the target is derived rather than hardcoded.

For aspartic acid, quantitative-ion areas are D=820 and L=1670:

$$
ee = 100 \cdot \frac{1670 - 820}{1670 + 820} = 34.14
$$

The requested whole-percent flag is **`GAIANSPACE{aspartic_acid_L34}`**.

### Reproduction

Run the original solver from the challenge's working directory, with the input files alongside the script as in the supplied ZIP.

```bash
python3 117.py
```

Expected relevant output (showing the key contamination tests):

```text
[Enantiomeric Excess and provenance controls]
alanine              D= 2100 L= 3600 ee=+26.32% blank(D/L)=0/1480 heavy_isotopes=False clean_blank=False L_excess=True
serine               D=   60 L= 1910 ee=+93.91% blank(D/L)=0/1850 heavy_isotopes=False clean_blank=False L_excess=True
aspartic_acid        D=  820 L= 1670 ee=+34.14% blank(D/L)=0/0 heavy_isotopes=True clean_blank=True L_excess=True

Selected compound: aspartic_acid
FLAG: GAIANSPACE{aspartic_acid_L34}
```

### Solver Code

{% raw %}
```python
#!/usr/bin/env python3
"""Resolve chiral peak excess with blank and isotopic controls.

Dependencies: Python 3 standard library only.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

RT_TOLERANCE_MIN = 0.03


def read_csv(filename: str) -> list[dict[str, str]]:
    with Path(filename).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def peak_near(rows: list[dict[str, str]], retention: float) -> dict[str, str] | None:
    matches = [row for row in rows if abs(float(row["rt_min"]) - retention) <= RT_TOLERANCE_MIN]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous retention peak at {retention}")
    return matches[0] if matches else None


def optional_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class Evidence:
    sample_area: int
    blank_area: int
    carbon: float | None
    nitrogen: float | None


standards = read_csv("standards.csv")
sample = read_csv("moonlet_sample.csv")
blank = read_csv("procedural_blank.csv")
isotopes = read_csv("isotopes.csv")

observations: dict[str, dict[str, Evidence]] = {}
for standard in standards:
    handedness = standard["enantiomer"]
    if handedness not in ("D", "L"):
        continue
    compound = standard["compound"]
    retention = float(standard["retention_min"])
    quant_ion = f"m{int(standard['quant_ion_mz'])}"
    sample_peak = peak_near(sample, retention)
    isotope_peak = peak_near(isotopes, retention)
    blank_peak = peak_near(blank, retention)
    if sample_peak is None or isotope_peak is None:
        raise ValueError(f"Missing evidence: {compound} {handedness}")
    observations.setdefault(compound, {})[handedness] = Evidence(
        sample_area=int(sample_peak[quant_ion]),
        blank_area=int(blank_peak[quant_ion]) if blank_peak else 0,
        carbon=optional_float(isotope_peak["d13C_permil_VPDB"]),
        nitrogen=optional_float(isotope_peak["d15N_permil_AIR"]),
    )

print("[Enantiomeric Excess and provenance controls]")
qualified: list[tuple[str, float]] = []
for compound, pair in observations.items():
    if set(pair) != {"D", "L"}:
        continue
    d, l = pair["D"], pair["L"]
    ee = 100.0 * float(l.sample_area - d.sample_area) / float(l.sample_area + d.sample_area)
    blank_d = float(d.blank_area) / float(d.sample_area)
    blank_l = float(l.blank_area) / float(l.sample_area)
    # Transparent dataset-specific screening thresholds, not universal
    # laboratory limits for contamination or extraterrestrial provenance.
    clean_blank = max(blank_d, blank_l) <= 0.05
    heavy_isotopes = all(
        p.carbon is not None and p.nitrogen is not None
        and p.carbon > 15.0 and p.nitrogen > 25.0
        for p in (d, l)
    )
    significant_left_excess = ee >= 5.0
    print(f"{compound:20s} D={d.sample_area:5d} L={l.sample_area:5d} "
          f"ee={ee:+.2f}% blank(D/L)={d.blank_area}/{l.blank_area} "
          f"heavy_isotopes={heavy_isotopes} clean_blank={clean_blank} "
          f"L_excess={significant_left_excess}")
    if clean_blank and heavy_isotopes and significant_left_excess:
        qualified.append((compound, ee))

if len(qualified) != 1:
    raise ValueError(f"Expected one fully supported candidate, got {qualified}")

target, ee = qualified[0]
print(f"\nSelected compound: {target}")
print(f"FLAG: GAIANSPACE{{{target}_L{round(ee)}}}")
```
{% endraw %}

## Flag

```text
GAIANSPACE{aspartic_acid_L34}
```
