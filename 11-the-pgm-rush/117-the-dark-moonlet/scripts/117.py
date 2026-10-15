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
