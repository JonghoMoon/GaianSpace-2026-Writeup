#!/usr/bin/env python3
# Dependencies: python3 -m pip install sgp4

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

