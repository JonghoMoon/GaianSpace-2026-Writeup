# 201-uplink-origins

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 50 |

## Description

12 June 2025, 17:15 UTC. GaianSpace Mission Control catches a command it never sent climbing up to **GAIAN-13**, our old highly-elliptical bird. Someone on the ground pointed a dish at it and talked. The watch wants to know where they were standing.

The intrusion desk has pulled the element set the flight dynamics team kept for GAIAN-13 that day and dropped it on your console. Analyst Reyes is already sure the transmitter sat under a big coastal array and will not stop saying so. What the desk actually needs is colder than a hunch: at the instant of the uplink the satellite was almost straight over the attacker, so the spot on the ground beneath it is the spot to report, together with how far up the bird was.

The log also carries a second contact on a neighbouring object from an earlier pass. It is not this event. The catalog lists GAIAN-13 as mission `EL06QL`, NORAD `00005`; ignore the nearby birds that share the plane.

Report the sub-satellite point at the uplink instant and the satellite's altitude above it.

**Flag format:** `GAIANSPACE{[Latitude],[Longitude],[Altitude]}` — degrees to two decimals, altitude in kilometres, longitude negative for west. For example GAIANSPACE{12.34,-56.78,789.01}.

**Attachments:** `gaian-13.tle` — the element set flight dynamics kept for GAIAN-13 on the day

## Solution

### Steps

1. Read the two TLE lines from `gaian-13.tle` and verify that the satellite catalog number is `5`.
2. Propagate the orbit to the specified UTC instant using SGP4. The returned position is in **TEME**, not Earth-fixed coordinates.
3. Rotate TEME into an approximate Earth-fixed frame using Vallado's GMST expression.
4. Convert the resulting Cartesian coordinates to geodetic WGS-84 latitude, longitude and altitude. Use the ellipsoid's flattening, not a fixed spherical Earth radius.
5. Round the three values to two decimal places.

### Reproduction

The supplied solver is [`scripts/201.py`](./scripts/201.py). Required dependencies: `sgp4`.

From the challenge input directory (`challenges/`):

The code linked above is the solver **provided in the attached category archive**. It is the primary implementation referenced by this write-up.

```bash
python3 201.py
```

Expected relevant output:
```text
Latitude:   26.46
Longitude: -98.64
Altitude:  3296.64 km
FLAG: GAIANSPACE{26.46,-98.64,3296.64}
```

### Exploit Code

```python
from datetime import datetime, timezone
from math import atan2, cos, degrees, pi, sin, sqrt
from pathlib import Path

from sgp4.api import Satrec, jday, SGP4_ERRORS

TLE_FILE = Path("gaian-13.tle")
TARGET = datetime(2025, 6, 12, 17, 15, 0, tzinfo=timezone.utc)

# WGS-84 ellipsoid parameters in kilometres.
A = 6378.137
F = 1.0 / 298.257223563
E2 = F * (2.0 - F)


def gmst_angle(jd_ut1: float) -> float:
    # Vallado GMST expression for the TEME-to-PEF rotation.
    t = (jd_ut1 - 2451545.0) / 36525.0
    seconds = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * t
        + 0.093104 * t * t
        - 6.2e-6 * t * t * t
    )
    return (seconds % 86400.0) * (2.0 * pi / 86400.0)


def ecef_to_geodetic(
    x: float, y: float, z: float
) -> tuple[float, float, float]:
    lon = atan2(y, x)
    p = sqrt(x * x + y * y)
    lat = atan2(z, p * (1.0 - E2))

    # Iteratively solve geodetic latitude on the ellipsoid.
    for _ in range(20):
        s = sin(lat)
        n = A / sqrt(1.0 - E2 * s * s)
        new_lat = atan2(z + E2 * n * s, p)
        if abs(new_lat - lat) < 1e-14:
            lat = new_lat
            break
        lat = new_lat

    n = A / sqrt(1.0 - E2 * sin(lat) ** 2)
    alt = p / cos(lat) - n

    return degrees(lat), degrees(lon), alt


def main() -> None:
    lines = [
        line.replace("\u00a0", " ")
        for line in TLE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    line1 = next(line for line in lines if line.startswith("1 "))
    line2 = next(line for line in lines if line.startswith("2 "))

    sat = Satrec.twoline2rv(line1, line2)
    if sat.satnum != 5:
        raise ValueError(f"Unexpected NORAD ID: {sat.satnum}")

    jd, fr = jday(
        TARGET.year, TARGET.month, TARGET.day,
        TARGET.hour, TARGET.minute,
        float(TARGET.second),
    )

    error, position, _ = sat.sgp4(jd, fr)
    if error != 0:
        raise RuntimeError(SGP4_ERRORS.get(error, str(error)))

    # Convert TEME coordinates to Earth-fixed coordinates.
    theta = gmst_angle(jd + fr)
    x, y, z = position
    x_ecef = x * cos(theta) + y * sin(theta)
    y_ecef = -x * sin(theta) + y * cos(theta)

    lat, lon, alt = ecef_to_geodetic(x_ecef, y_ecef, z)

    print(f"Latitude:  {lat:.2f}")
    print(f"Longitude: {lon:.2f}")
    print(f"Altitude:  {alt:.2f} km")
    print(f"FLAG: GAIANSPACE{{{lat:.2f},{lon:.2f},{alt:.2f}}}")


if __name__ == "__main__":
    main()

```

## Flag

```text
GAIANSPACE{26.46,-98.64,3296.64}
```
