#!/usr/bin/env python3
"""Locate the 125 challenge transmitter from four GPS-timed LoRa gateways."""

import argparse
import base64
import csv
import json
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


def read_gateways(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Convert corrected gateway positions into parcel-register UTM coordinates."""
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32634", always_xy=True)
    from_eov = Transformer.from_crs("EPSG:23700", "EPSG:4326", always_xy=True)

    with path.open(encoding="utf-8", newline="") as handle:
        rows = {row["site"]: row for row in csv.DictReader(handle)}

    positions: list[tuple[float, float]] = []
    feeders: list[float] = []
    for site in SITES:
        row = rows[site]
        if site == "PUMP":
            # The worklog supersedes the obsolete survey-sheet location.
            longitude, latitude = from_eov.transform(788457.44, 111015.67)
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
    """Fit a 2D TDOA position using three range differences."""
    def residual(position: np.ndarray) -> np.ndarray:
        distances = np.linalg.norm(gateways - position, axis=1)
        return distances[1:] - distances[0] - observed

    initial = np.array([483500.0, 5127800.0], dtype=float)
    result = least_squares(residual, initial, max_nfev=300)
    rms = float(np.sqrt(np.mean(result.fun ** 2)))
    return np.asarray(result.x, dtype=float), rms


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

    gateways, feeder_lengths = read_gateways(directory / "coop_gateways.csv")
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
