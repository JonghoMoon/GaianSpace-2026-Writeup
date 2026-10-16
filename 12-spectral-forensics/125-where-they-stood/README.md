# 125 — Where They Stood

| | |
|---|---|
| **Category** | 12 — Spectral Forensics |
| **Points** | ? |

## Description

13:40, the co-op yard, Mezőhegyes. The stranger's batch went out at 12:04 from somewhere on the plain. The co-op SDR heard every packet and has no idea where any of them came from.

The co-op runs four LoRa gateways for its soil probes: on Babb's grain dryer, on the co-op silo, on the town water tower and out at the pumps. Each one stamps what it hears with GPS time, down to the nanosecond, and all four were listening at noon. Laci, who looks after them, has already worked out a position from the survey sheet and drawn a circle round the big field west of the dryer. He is sure. The police are not driving out on a circle. They want a parcel number.

Find the parcel the stranger transmitted from.

**Flag format:** `GAIANSPACE{<parcel ID from the register>}` — for example `GAIANSPACE{MZH-0000}`.

### Files

- `gw_dryer_pktfwd.log` — the packet forwarder log from the gateway on Babb's grain dryer, 10:00–10:10 UTC
- `gw_silo_pktfwd.log` — the same from the co-op silo
- `gw_pivot7_pktfwd.log` — the same from the gateway out at the pumps
- `gw_tower_export.csv` — the water tower gateway's packet export for the same ten minutes
- `coop_gateways.csv` — the co-op's survey sheet for the four gateways
- `coop_worklog.txt` — Laci's work log for the gateways
- `parcels.geojson` — the parcel register for the area

Contains modified Copernicus Sentinel data 2025.

## Solution

### 1. Isolate the transmitted batch

**Time-zone interpretation:** The challenge narrative reports a transmission at 12:04 without explicitly identifying its time zone, while the gateway logs cover 10:00–10:10 UTC. During daylight-saving time in Hungary, 12:04 CEST corresponds to 10:04 UTC. This provides a plausible reconciliation of the timestamps, but the narrative does not explicitly establish that its clock uses local time.

The packet-forwarder logs contain a mix of soil-probe messages and the stranger's `CLAIM BATCH 2025-AREA BKS-0712` transmission. Base64-decode the `data` field of the three JSON forwarders and hex-decode the water tower CSV. Match **identical payload bytes** across all four gateways; this avoids incorrectly pairing unrelated packets merely because they arrived at similar times. The target batch frames start with the byte prefix `b7 2a`.

In the provided uploaded copies, 31 distinct target payloads are present at all four receivers after matching. This is fewer than the 37 packet matches noted in the earlier investigation; the solver reports the actual count rather than hardcoding it. These 31 packets are sufficient to identify the parcel.

### 2. Correct the gateway position

`coop_gateways.csv` lists the PUMP gateway at its old pump-house location. `coop_worklog.txt` records that on **2025-05-14** it was moved to the **pivot-7 mast**, and gives its surveyed EOV coordinates:

```text
EOV Y = 788457.44
EOV X = 111015.67
```

Transform the corrected EOV location (`EPSG:23700`) to WGS84 and then to UTM zone 34N (`EPSG:32634`), which is the coordinate reference system of `parcels.geojson`. The revised solver parses the EOV coordinates from the work log rather than embedding them in the source. The corrected pivot-7 position is approximately **(488120, 5130650) m UTM**. Using the obsolete pump-house location produces a misleading fix.

### 3. Compute arrival-time differences

The forwarders provide `tmms` (integer GPS milliseconds) and `ftime` (nanoseconds within the GPS second). The tower export uses `gps_ms` and `fine_ns` with the same timing semantics. Convert each timestamp into integer nanoseconds:

```python
timestamp_ns = gps_ms * 1_000_000 + fine_ns - (gps_ms % 1000) * 1_000_000
```

For each common packet, use DRYER as the reference. Convert the other receivers' arrival-time differences into range differences:

$$
\Delta r_i = c\,(t_i-t_0) - \frac{L_i-L_0}{0.85},
$$

where `c = 299792458 m/s`, `L` is the gateway's LMR-400 feeder length, and `0.85` is its velocity factor. The feeder correction is important because the four cables have different lengths.

Fit a 2D transmitter position to the three range-difference equations:

$$
\|\mathbf{x}-\mathbf{g}_i\|-\|\mathbf{x}-\mathbf{g}_0\|=\Delta r_i.
$$

### 4. Reject poorly conditioned fixes

The accepted fixes place the transmitter southwest of the gateway array, where the geometry is weak. Fitting all observations as one unweighted least-squares problem is vulnerable to bad packet timestamps and local minima. Instead, fit each packet separately from **five independent, data-derived initial positions** (the centroid of all four gateways plus each gateway location); retain the converged solution with the lowest residual, filter fixes with RMS range-difference residual below **5 m**, and combine the reliable positions with a coordinate-wise median. The threshold is an analyst-chosen outlier filter, not a value dictated by the challenge. Use the parcel polygons to check each reliable fix and the median.

For the attached copies, the reliable fixes vote **4 for MZH-3240** and **1 for MZH-4631**. The median location, **(483529.54, 5127811.95) m UTM**, lies in **MZH-3240**. The earlier independent robust grid search reported approximately (483498, 5127787), also inside MZH-3240; the two methods agree on the parcel even though their point estimates differ.

### Dead Ends and Corrections

- **Obsolete survey sheet:** the PUMP gateway moved, but the sheet did not. The work log supersedes it.
- **Uncorrected coax delays:** different LMR-400 feeder lengths introduce non-negligible differential timing offsets.
- **One joint fit:** weak receiver geometry and timing outliers can move an unweighted fit outside the true parcel. Use low-residual packet fixes and robust aggregation.
- **Answer-adjacent initialization:** an initial estimate near the eventual flag location would make the process circular. The solver instead starts from gateway geometry (centroid and each receiver) and chooses the best converged solution.
- **Other LoRa traffic:** match the specific claim-batch payloads, not every packet heard during the ten-minute window.

### Reproduction

Install the required Python packages:

```bash
python3 -m pip install numpy scipy pyproj shapely
```

Place `125.py` alongside the seven original challenge files and run:

```bash
python3 125.py
```

Expected relevant output (for the uploaded data):

```text
Gateways: DRYER, SILO, TOWER, PUMP
Matching batch packets: 31
Reliable fixes (RMS < 5 m): 5
Parcel votes: {'MZH-3240': 4, 'MZH-4631': 1}
Median UTM (EPSG:32634): 483529.54, 5127811.95
Median parcel: MZH-3240
FLAG: GAIANSPACE{MZH-3240}
```

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies (install if needed):
#   python3 -m pip install numpy scipy pyproj shapely
"""Locate the 125 challenge transmitter from four GPS-timed LoRa gateways."""

import argparse
import base64
import csv
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.optimize import least_squares
from shapely.geometry import Point, shape

SPEED_OF_LIGHT = 299792458.0
FEEDER_VELOCITY_FACTOR = 0.85
SITES = ("DRYER", "SILO", "TOWER", "PUMP")


def read_forwarder(path: Path) -> dict[bytes, int]:
    """Map received payloads to absolute GPS nanosecond timestamps."""
    packets: dict[bytes, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "JSON up: " not in line:
            continue
        entry = json.loads(line.split("JSON up: ", 1)[1])
        for packet in entry.get("rxpk", []):
            if int(packet.get("stat", 0)) != 1:
                continue
            payload = base64.b64decode(packet["data"])
            gps_ms = int(packet["tmms"])
            fine_ns = int(packet["ftime"])
            packets[payload] = gps_ms * 1_000_000 + fine_ns - (gps_ms % 1000) * 1_000_000
    return packets


def read_tower(path: Path) -> dict[bytes, int]:
    """Read the tower CSV, which stores payloads as hexadecimal bytes."""
    packets: dict[bytes, int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        lines = (line for line in handle if not line.startswith("#"))
        for row in csv.DictReader(lines):
            if row["crc"] != "OK":
                continue
            payload = bytes.fromhex(row["payload_hex"])
            gps_ms = int(row["gps_ms"])
            fine_ns = int(row["fine_ns"])
            packets[payload] = gps_ms * 1_000_000 + fine_ns - (gps_ms % 1000) * 1_000_000
    return packets


def read_pivot7_eov(path: Path) -> tuple[float, float]:
    """Extract the surveyed replacement gateway location from the work log."""
    content = path.read_text(encoding="utf-8")
    match = re.search(
        r"2025-05-14\s+PUMP\b[\s\S]*?EOV\s+Y\s+"
        r"([0-9]+(?:\.[0-9]+)?)\s+X\s+([0-9]+(?:\.[0-9]+)?)",
        content,
    )
    if match is None:
        raise ValueError("PUMP EOV coordinates not found in coop_worklog.txt")
    return float(match.group(1)), float(match.group(2))


def read_gateways(path: Path, worklog: Path) -> tuple[np.ndarray, np.ndarray]:
    """Convert corrected gateway positions into parcel-register UTM coordinates."""
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32634", always_xy=True)
    from_eov = Transformer.from_crs("EPSG:23700", "EPSG:4326", always_xy=True)

    with path.open(encoding="utf-8", newline="") as handle:
        rows = {row["site"]: row for row in csv.DictReader(handle)}

    pump_eov_y, pump_eov_x = read_pivot7_eov(worklog)
    positions: list[tuple[float, float]] = []
    feeders: list[float] = []
    for site in SITES:
        row = rows[site]
        if site == "PUMP":
            # The worklog supersedes the obsolete survey-sheet location.
            longitude, latitude = from_eov.transform(pump_eov_y, pump_eov_x)
        else:
            longitude = float(row["lon"])
            latitude = float(row["lat"])
        positions.append(to_utm.transform(longitude, latitude))
        feeders.append(float(row["feeder_m"]))

    return np.asarray(positions, dtype=float), np.asarray(feeders, dtype=float)


def find_parcel(point: np.ndarray, features: list[dict]) -> str | None:
    """Return the registered parcel containing a UTM position."""
    location = Point(float(point[0]), float(point[1]))
    for feature in features:
        if shape(feature["geometry"]).covers(location):
            return str(feature["properties"]["parcel"])
    return None


def solve_packet(observed: np.ndarray, gateways: np.ndarray) -> tuple[np.ndarray, float]:
    """Fit TDOA from independent geometry-derived initial guesses."""
    def residual(position: np.ndarray) -> np.ndarray:
        distances = np.linalg.norm(gateways - position, axis=1)
        return distances[1:] - distances[0] - observed

    # Multiple starts reduce sensitivity to local minima outside the array.
    centroid = np.mean(gateways, axis=0)
    starts = [centroid, *gateways]
    solutions: list[tuple[float, np.ndarray]] = []
    for start in starts:
        result = least_squares(residual, np.asarray(start, dtype=float), max_nfev=300)
        rms = float(np.sqrt(np.mean(result.fun ** 2)))
        if result.success and np.all(np.isfinite(result.x)):
            solutions.append((rms, np.asarray(result.x, dtype=float)))
    if not solutions:
        raise RuntimeError("No TDOA fit converged from the gateway-derived starts")
    best_rms, best_position = min(solutions, key=lambda item: item[0])
    return best_position, best_rms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--max-rms", type=float, default=5.0)
    args = parser.parse_args()
    directory = args.directory

    paths = {
        "DRYER": directory / "gw_dryer_pktfwd.log",
        "SILO": directory / "gw_silo_pktfwd.log",
        "TOWER": directory / "gw_tower_export.csv",
        "PUMP": directory / "gw_pivot7_pktfwd.log",
    }
    readings = {
        site: read_tower(path) if site == "TOWER" else read_forwarder(path)
        for site, path in paths.items()
    }
    common = set.intersection(*(set(readings[site]) for site in SITES))
    batch = sorted(
        (payload for payload in common if payload.startswith(bytes.fromhex("b72a"))),
        key=lambda payload: readings["DRYER"][payload],
    )
    if not batch:
        raise RuntimeError("No matching CLAIM-BATCH packets were received by all gateways")

    gateways, feeder_lengths = read_gateways(directory / "coop_gateways.csv", directory / "coop_worklog.txt")
    feeder_ranges = feeder_lengths / FEEDER_VELOCITY_FACTOR
    features = json.loads((directory / "parcels.geojson").read_text(encoding="utf-8"))["features"]

    reliable: list[np.ndarray] = []
    votes: Counter[str] = Counter()
    for payload in batch:
        timestamps = np.asarray([readings[site][payload] for site in SITES], dtype=np.int64)
        dt_ns = timestamps[1:] - timestamps[0]
        observed = dt_ns.astype(float) * (SPEED_OF_LIGHT * 1.0e-9)
        observed -= feeder_ranges[1:] - feeder_ranges[0]
        position, rms = solve_packet(observed, gateways)
        if rms < args.max_rms:
            reliable.append(position)
            parcel = find_parcel(position, features)
            if parcel is not None:
                votes[parcel] += 1

    if not reliable:
        raise RuntimeError("No reliable per-packet fixes; inspect GPS time and feeder delays")
    median_position = np.median(np.asarray(reliable), axis=0)
    median_parcel = find_parcel(median_position, features)
    if median_parcel is None:
        raise RuntimeError("Median position falls outside the provided parcel register")

    print(f"Gateways: {', '.join(SITES)}")
    print(f"Matching batch packets: {len(batch)}")
    print(f"Reliable fixes (RMS < {args.max_rms:g} m): {len(reliable)}")
    print(f"Parcel votes: {dict(votes)}")
    print(f"Median UTM (EPSG:32634): {median_position[0]:.2f}, {median_position[1]:.2f}")
    print(f"Median parcel: {median_parcel}")
    print(f"FLAG: GAIANSPACE{{{median_parcel}}}")


if __name__ == "__main__":
    main()
```

### Tools and References

- Python 3, NumPy, SciPy (`least_squares`), pyproj, Shapely
- Provided LoRa packet-forwarder logs, survey sheet, gateway work log, and GeoJSON parcel register
- GPS fine timestamps, TDOA multilateration, LMR-400 feeder velocity factor
- EPSG:23700 (Hungarian EOV) and EPSG:32634 (UTM zone 34N)

## Flag

```text
GAIANSPACE{MZH-3240}
```
