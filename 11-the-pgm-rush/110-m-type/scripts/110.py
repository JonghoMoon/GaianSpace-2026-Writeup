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
