# 202-downlink-deception

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 75 |

## Description

Two hours after the uplink, GAIAN-13 opened its downlink and dumped a frame it was never scheduled to send. One antenna on the ground was pointed the right way to hear it. The watch wants that antenna named, and the moment it happened.

The intrusion desk captured the frame as it came down and saved it off. Reyes is certain the big dishes caught it, because the big dishes catch everything. They did not. At the instant the frame came down the bird was only high enough over one site on the list below; the rest were looking at dirt.

Work out which site had GAIAN-13 in the clear when the frame arrived, and read the arrival time out of the capture itself.

Receiving-site roster (lat, lon; west is negative):

| Callsign | Operator | Latitude | Longitude |
|---|---|---:|---:|
| GDSN | Deep-space net, high desert | 35.42667 | -116.89000 |
| MDSN | Deep-space net, Iberia | 40.43194 | -4.24917 |
| CDSN | Deep-space net, southern hemisphere | -35.40139 | 148.98167 |
| CAPE | Coastal array, retired | 28.53830 | -81.37920 |
| VELA | GaianSpace mid-ocean array | 19.48000 | -155.60000 |

**Flag format:** `GAIANSPACE{[callsign],[timestamp]}` — callsign exactly as the roster prints it, timestamp in the form it appears in the capture (`YYYY-MM-DDThh:mm:ssZ`). For example `GAIANSPACE{ABCD,2025-01-02T03:04:05Z}`.

**Attachments:** `gaian-13.tle` — the element set for GAIAN-13; `telemetry_capture.bin` — the captured downlink telemetry frame

## Hints

Two hints were released during the event:

1. **Dishes miss things** — Reyes trusts the biggest antennas. Being big does not help if the satellite is below your horizon. Check who could actually see it.
2. **The frame is honest** — You do not have to guess the moment. The capture writes down when it arrived, in plain characters, near the top.

## Solution

### Steps

**1. Extract the reception time from the capture.**

Inspect `telemetry_capture.bin`. The `GSTM`/`GAIAN-13` telemetry frame contains an ASCII UTC timestamp:

```text
2025-06-12T19:15:00Z
```

The solver searches the capture for the timestamp rather than embedding it as a constant, then parses it as UTC.

**2. Propagate GAIAN-13 and calculate topocentric elevation.**

Read `gaian-13.tle` with Skyfield, propagate its orbit to the recovered instant and form each site-relative topocentric vector using the WGS-84 ground coordinates in the challenge roster. The elevation angles are:

| Callsign | Elevation | Above geometric horizon |
|---|---:|---|
| GDSN | +2.7620° | Yes |
| MDSN | −54.7217° | No |
| CDSN | −22.5975° | No |
| CAPE | −21.9414° | No |
| **VELA** | **+68.1723°** | **Yes** |

**3. Select the strongest intended station candidate.**

VELA is by far the highest, at **68.17°**. Importantly, **GDSN is also 2.76° above the geometric horizon**. Consequently, the data alone do not establish that VELA is the *only* site with line-of-sight under a zero-degree elevation criterion. The challenge's phrase *high enough* implies an operational minimum elevation or usable-link criterion, but no numerical threshold is specified. VELA is the clear intended candidate; this is not proof of exclusive geometric visibility.

**4. Construct the flag.**

Use the station callsign and the timestamp from the captured frame.

### Reproduction

Put `202.py`, `gaian-13.tle` and `telemetry_capture.bin` in the same directory and run:

```bash
python3 202.py
```

Dependency installation is documented at the top of `202.py` (`skyfield`).

Expected relevant output:

```text
Capture timestamp: 2025-06-12T19:15:00Z
GDSN: elevation=+2.7620 deg
MDSN: elevation=-54.7217 deg
CDSN: elevation=-22.5975 deg
CAPE: elevation=-21.9414 deg
VELA: elevation=+68.1723 deg
Note: GDSN is also above the geometric horizon; the problem implies
      an unspecified minimum elevation / usable-link criterion.
FLAG: GAIANSPACE{VELA,2025-06-12T19:15:00Z}
```

### Exploit Code

{% raw %}
```python
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
```
{% endraw %}

## Flag

```text
GAIANSPACE{VELA,2025-06-12T19:15:00Z}
```
