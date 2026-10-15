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
