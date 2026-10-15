#!/usr/bin/env python3
# Dependencies: python3 -m pip install skyfield

"""Recover the 202-downlink-deception flag from capture and TLE."""

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from skyfield.api import EarthSatellite, load, wgs84

SITES = {
    "GDSN": (35.42667, -116.89000),
    "MDSN": (40.43194, -4.24917),
    "CDSN": (-35.40139, 148.98167),
    "CAPE": (28.53830, -81.37920),
    "VELA": (19.48000, -155.60000),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, default=Path("telemetry_capture.bin"))
    parser.add_argument("--tle", type=Path, default=Path("gaian-13.tle"))
    args = parser.parse_args()

    capture = args.capture.read_bytes()
    match = re.search(rb"\b(20\d{2}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", capture)
    if match is None:
        raise ValueError("UTC timestamp not found in the capture")
    timestamp = match.group(1).decode("ascii")
    when = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    print(f"Capture timestamp: {timestamp}")

    lines = [
        line.replace("\u00a0", " ").strip()
        for line in args.tle.read_text(encoding="utf-8").splitlines()
    ]
    line1 = next(line for line in lines if line.startswith("1 "))
    line2 = next(line for line in lines if line.startswith("2 "))
    timescale = load.timescale()
    satellite = EarthSatellite(line1, line2, "GAIAN-13", timescale)
    target_time = timescale.from_datetime(when)

    elevations: dict[str, float] = {}
    for callsign, (lat, lon) in SITES.items():
        observer = wgs84.latlon(lat, lon)
        altitude, _, _ = (satellite - observer).at(target_time).altaz()
        elevation = float(altitude.degrees)
        elevations[callsign] = elevation
        print(f"{callsign}: elevation={elevation:+.4f} deg")

    # This is a ranking, not proof of exclusive visibility without an elevation mask.
    callsign = max(elevations, key=elevations.get)
    print("Note: GDSN is also above the geometric horizon; the problem implies")
    print("      an unspecified minimum elevation / usable-link criterion.")
    print(f"FLAG: GAIANSPACE{{{callsign},{timestamp}}}")


if __name__ == "__main__":
    main()

