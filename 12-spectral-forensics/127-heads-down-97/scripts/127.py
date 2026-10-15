#!/usr/bin/env python3
# Dependencies (install if needed):
#   python3 -m pip install numpy scipy matplotlib scikit-learn threadpoolctl Pillow
"""GaianSpace 127: recover forged AgriLink and Johnripper parcel decisions.

Requires lora_explicit.py (the 122 receiver) and lora_implicit.py (the 123
receiver) in the same directory. Both modules are bundled with this script.

Example:
  python3 127.py --morning-data szot_sdr_0641.sigmf-data \
    --morning-meta szot_sdr_0641.sigmf-meta \
    --dealer-data szot_sdr_0705.sigmf-data \
    --dealer-meta szot_sdr_0705.sigmf-meta \
    --parcels szotyola_parcels_2025.geojson
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
from matplotlib.path import Path as PolygonPath
from sklearn.cluster import KMeans
from threadpoolctl import threadpool_limits

import lora_explicit
import lora_implicit

CLASS_CONCENTRATION_THRESHOLD = 0.99  # Analyst-defined tolerance for stray pixels.
CLUSTER_SEEDS = (0, 1, 2, 3, 4)
READY_THRESHOLD = 0.44
WEST_WIDTH = 128
HEIGHT = 128


def load_iq(path: Path, meta_path: Path):
    """Memory-map interleaved signed 8-bit IQ and obtain capture boundaries."""
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta["global"]["core:datatype"] != "ci8":
        raise ValueError("Expected ci8 IQ data")
    raw = np.memmap(path, dtype=np.int8, mode="r").reshape(-1, 2)
    captures = meta["captures"]
    starts = [int(entry["core:sample_start"]) for entry in captures]
    starts.append(int(raw.shape[0]))
    if starts[0] != 0 or any(b <= a for a, b in zip(starts, starts[1:])):
        raise ValueError("Invalid SigMF capture boundaries")
    return raw, captures, starts, float(meta["global"]["core:sample_rate"])


def iq_burst(raw: np.ndarray, start: int, end: int) -> np.ndarray:
    """Convert a single AGC-normalized capture to complex samples."""
    samples = raw[start:end].astype(np.float64)
    return samples[:, 0] + 1j * samples[:, 1]


def decode_morning(data_path: Path, meta_path: Path, out: Path):
    """Decode all AgriLink frames, then separate the two CFO populations."""
    raw, captures, starts, fs = load_iq(data_path, meta_path)
    receiver = lora_explicit.Demodulator(fs)
    packets = []

    for index, capture in enumerate(captures):
        iq = iq_burst(raw, starts[index], starts[index + 1])
        payload, crc, cfo, drift = receiver.decode(iq)
        if len(payload) < 6 or payload[:3] != b"AL\x03":
            raise ValueError(f"Unexpected AgriLink packet at burst {index}")
        packets.append({
            "index": index,
            "utc": capture["core:datetime"],
            "payload": payload,
            "crc": crc,
            "cfo": cfo,
            "power": float(np.mean(np.abs(iq) ** 2)),
            "drift": drift,
        })
        if (index + 1) % 100 == 0 or index + 1 == len(captures):
            print(f"AgriLink CRC verified: {index + 1}/{len(captures)}", flush=True)

    cfos = np.array([[entry["cfo"]] for entry in packets], dtype=np.float64)
    with threadpool_limits(limits=1):
        groups = KMeans(n_clusters=2, n_init=20, random_state=0).fit_predict(cfos)

    cubes = np.zeros((2, 5, HEIGHT, WEST_WIDTH), dtype=np.uint8)
    complete = []
    records = []
    for group in (0, 1):
        rows = {}
        manifest = None
        ends = 0
        for packet, label in zip(packets, groups):
            if int(label) != group:
                continue
            body = packet["payload"]
            kind = body[5:6]
            if kind == b"M":
                manifest = body[6:].decode("ascii")
            elif kind == b"E":
                ends += 1
            elif kind == b"D":
                if len(body) != 136:
                    raise ValueError(f"Invalid AgriLink row size: {len(body)}")
                channel = int(body[6])
                row = int(body[7])
                key = (channel, row)
                if key in rows and rows[key] != body[8:]:
                    raise ValueError(f"Conflicting rows in CFO group {group}: {key}")
                rows[key] = body[8:]
            else:
                raise ValueError(f"Unknown AgriLink frame kind {kind!r}")

            records.append({
                "burst": packet["index"],
                "group": group,
                "cfo_hz": packet["cfo"],
                "power": packet["power"],
                "kind": kind.decode("ascii"),
            })

        for (channel, row), pixels in rows.items():
            cubes[group, channel, row] = np.frombuffer(pixels, dtype=np.uint8)

        complete.append(len(rows) == 640 and manifest is not None and ends > 0)
        group_cfos = cfos[groups == group, 0]
        print(
            f"Group {group}: rows={len(rows)}, median CFO="
            f"{np.median(group_cfos):.1f} Hz, sigma={np.std(group_cfos):.1f} Hz"
        )
        print(f"  Manifest: {manifest}")

    if not all(complete):
        raise RuntimeError("Expected two complete, independent 5-band passes")

    # The more frequency-stable, regular source is the nominal AgriLink sender.
    # This attribution should be cross-checked with spectral boundaries.
    cfo_spreads = [float(np.std(cfos[groups == group, 0])) for group in (0, 1)]
    genuine = int(np.argmin(cfo_spreads))
    forged = 1 - genuine

    np.save(out / "morning_genuine.npy", cubes[genuine])
    np.save(out / "morning_forged.npy", cubes[forged])
    (out / "morning_packets.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8"
    )
    print(f"Genuine CFO group={genuine}; forged CFO group={forged}")
    return cubes[genuine], cubes[forged]


def decode_dealer(data_path: Path, meta_path: Path, out: Path) -> np.ndarray:
    """Decode the 1280 JRM row halves, skipping a non-frame initial burst."""
    raw, captures, starts, fs = load_iq(data_path, meta_path)
    receiver = lora_implicit.Receiver(fs)
    rows = {}
    rejected = []
    for index in range(len(captures)):
        iq = iq_burst(raw, starts[index], starts[index + 1])
        try:
            frame, info = receiver.decode(iq)
        except ValueError as error:
            if index == 0:
                rejected.append({"burst": index, "reason": str(error)})
                continue
            raise ValueError(f"Dealer burst {index}: {error}") from error

        if len(frame) != 73:
            raise ValueError(f"Dealer frame {index}: unexpected length {len(frame)}")
        channel, row, half, sequence = (int(value) for value in frame[3:7])
        if not (0 <= channel < 5 and 0 <= row < 128 and half in (0, 1)):
            raise ValueError(f"Invalid dealer row address at burst {index}")
        if sequence != (index - 1) % 256:
            raise ValueError(f"Unexpected dealer sequence at burst {index}")
        key = (channel, row, half)
        if key in rows:
            raise ValueError(f"Duplicate dealer row half {key}")
        rows[key] = frame[7:-2]

        if (index + 1) % 100 == 0 or index + 1 == len(captures):
            print(f"Dealer bursts processed: {index + 1}/{len(captures)}", flush=True)

    if len(rows) != 1280:
        raise RuntimeError(f"Expected 1280 dealer row halves, found {len(rows)}")

    cube = np.zeros((5, 128, 128), dtype=np.uint8)
    for (channel, row, half), pixels in rows.items():
        if len(pixels) != 64:
            raise ValueError("Dealer row half is not 64 bytes")
        cube[channel, row, 64 * half:64 * (half + 1)] = np.frombuffer(
            pixels, dtype=np.uint8
        )
    np.save(out / "dealer_cube.npy", cube)
    (out / "dealer_skipped.json").write_text(
        json.dumps(rejected, indent=2), encoding="utf-8"
    )
    print(f"Dealer cube: {cube.shape}, decoded halves={len(rows)}")
    return cube


def polygon_mask(feature: dict, offset: int) -> np.ndarray:
    """Rasterize a parcel using pixel-center point-in-polygon tests."""
    yy, xx = np.mgrid[0:128, 0:128]
    points = np.column_stack((
        xx.ravel().astype(np.float64) + 0.5 + float(offset),
        yy.ravel().astype(np.float64) + 0.5,
    ))
    geometry = feature["geometry"]
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        raise ValueError("Unexpected parcel geometry type")

    result = np.zeros(len(points), dtype=bool)
    for rings in polygons:
        exterior = PolygonPath(np.asarray(rings[0], dtype=np.float64))
        inside = exterior.contains_points(points)
        for hole in rings[1:]:
            inside &= ~PolygonPath(np.asarray(hole, dtype=np.float64)).contains_points(points)
        result |= inside
    return result.reshape(128, 128)


def read_current_band_order(path: Path) -> tuple[str, ...]:
    """Read the current mast settings, which may postdate the recording."""
    content = path.read_text(encoding="utf-8")
    entries = {
        int(channel): band
        for channel, band in re.findall(r"^ch([0-4])\s*=\s*(B\d+)\s*$", content, re.M)
    }
    if set(entries) != set(range(5)) or set(entries.values()) != {
        "B02", "B03", "B04", "B08", "B11"
    }:
        raise ValueError("Unexpected band_order.conf channel assignments")
    return tuple(entries[index] for index in range(5))


def ndvi(cube: np.ndarray, order: tuple[str, ...]) -> np.ndarray:
    """Compute NDVI using an explicit candidate channel-to-band mapping."""
    red = cube[order.index("B04")].astype(np.float64)
    nir = cube[order.index("B08")].astype(np.float64)
    return (nir - red) / np.maximum(nir + red, 1.0)


def infer_morning_band_order(
    genuine: np.ndarray, features: list[dict], current: tuple[str, ...]
) -> tuple[str, ...]:
    """Choose between post-capture settings and a B08/B11 swap using crops."""
    changed = list(current)
    idx_nir, idx_swir = changed.index("B08"), changed.index("B11")
    changed[idx_nir], changed[idx_swir] = changed[idx_swir], changed[idx_nir]
    candidates = [current, tuple(changed)]
    decisions: list[tuple[float, tuple[str, ...]]] = []
    for candidate in candidates:
        index = ndvi(genuine, candidate)
        stubble: list[float] = []
        corn: list[float] = []
        for feature in features:
            mask = polygon_mask(feature, 0)
            if not np.any(mask):
                continue
            crop = str(feature["properties"]["crop_2025"])
            value = float(np.median(index[mask]))
            if crop == "kukorica":
                corn.append(value)
            elif "tarló" in crop:
                stubble.append(value)
        if not stubble or not corn:
            raise ValueError("Reference corn and harvested-wheat parcels missing")
        stubble_median = float(np.median(stubble))
        corn_median = float(np.median(corn))
        separation = corn_median - stubble_median
        print(
            f"Band mapping {candidate}: corn NDVI={corn_median:.3f}, "
            f"stubble NDVI={stubble_median:.3f}, separation={separation:.3f}"
        )
        decisions.append((separation, candidate))
    best_score, best_order = max(decisions, key=lambda item: item[0])
    if best_score <= 0.0:
        raise RuntimeError("Neither candidate mapping matches the crop reference")
    print(f"Inferred capture-time band order: {best_order}")
    return best_order


def find_sprayed_green(
    genuine: np.ndarray, forged: np.ndarray, features: list[dict], order: tuple[str, ...]
):
    real_ndvi = ndvi(genuine, order)
    forged_ndvi = ndvi(forged, order)
    green = []
    for feature in features:
        name = feature["properties"]["parcel"]
        if feature["properties"]["crop_2025"] != "napraforgó":
            continue
        mask = polygon_mask(feature, 0)
        if int(mask.sum()) == 0:
            continue
        actual = float(np.median(real_ndvi[mask]))
        reported = float(np.median(forged_ndvi[mask]))
        if actual >= READY_THRESHOLD and reported < READY_THRESHOLD:
            green.append(name)
        print(f"WEST {name}: genuine={actual:.3f}, forged={reported:.3f}")
    return green


def classify_parcel_concentration(
    labels: np.ndarray, features: list[dict], threshold: float
) -> list[tuple[str, list[tuple[int, int, int, float]]]]:
    """Identify sunflower parcels that dominate a spectral class estate-wide."""
    registered: list[tuple[str, str, np.ndarray]] = []
    for feature in features:
        mask = polygon_mask(feature, 128)
        if np.any(mask):
            registered.append((
                str(feature["properties"]["parcel"]),
                str(feature["properties"]["crop_2025"]),
                mask,
            ))

    class_totals = np.bincount(labels.ravel(), minlength=7)
    candidates: list[tuple[str, list[tuple[int, int, int, float]]]] = []
    for parcel, crop, mask in registered:
        if crop != "napraforgó":
            continue
        occupied = np.bincount(labels[mask], minlength=7)
        concentrated: list[tuple[int, int, int, float]] = []
        for label, count in enumerate(occupied):
            total = int(class_totals[label])
            share = float(count) / float(total) if total else 0.0
            if int(count) > 0 and share >= threshold:
                concentrated.append((label, int(count), total, share))
        if concentrated:
            candidates.append((parcel, concentrated))
    return candidates


def find_tonight(cube: np.ndarray, features: list[dict], out: Path) -> str:
    """Select the unique target using estate-wide class concentration for five seeds."""
    data = cube.transpose(1, 2, 0).reshape(-1, 5).astype(np.float64)
    selections: list[str] = []
    seed_evidence = []
    for seed in CLUSTER_SEEDS:
        with threadpool_limits(limits=1):
            model = KMeans(n_clusters=7, n_init=20, random_state=seed).fit(data)
        labels = model.labels_.reshape(128, 128)
        if seed == CLUSTER_SEEDS[0]:
            np.save(out / "dealer_classes.npy", labels)

        candidates = classify_parcel_concentration(
            labels, features, CLASS_CONCENTRATION_THRESHOLD
        )
        print(f"Seed {seed}: estate-wide candidate parcels={len(candidates)}")
        for parcel, classes in candidates:
            for label, count, total, share in classes:
                print(
                    f"  {parcel}: class={label}, inside={count}/{total} "
                    f"({share:.2%} of all class pixels)"
                )
        if len(candidates) != 1:
            raise RuntimeError(f"Seed {seed}: target not uniquely established: {candidates}")
        parcel, classes = candidates[0]
        selections.append(parcel)
        seed_evidence.append({
            "seed": seed, "parcel": parcel,
            "concentrated_classes": [
                {"label": label, "inside": count, "total": total, "fraction": share}
                for label, count, total, share in classes
            ],
        })

    if len(set(selections)) != 1:
        raise RuntimeError(f"Seed-dependent target: {selections}")
    (out / "dealer_concentration.json").write_text(
        json.dumps({
            "threshold": CLASS_CONCENTRATION_THRESHOLD,
            "threshold_is_analyst_choice": True,
            "seeds": seed_evidence,
        }, indent=2), encoding="utf-8"
    )
    print(f"Tonight's field: {selections[0]} (agreed across {len(selections)} seeds)")
    return selections[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--morning-data", type=Path, default=Path("szot_sdr_0641.sigmf-data"))
    parser.add_argument("--morning-meta", type=Path, default=Path("szot_sdr_0641.sigmf-meta"))
    parser.add_argument("--dealer-data", type=Path, default=Path("szot_sdr_0705.sigmf-data"))
    parser.add_argument("--dealer-meta", type=Path, default=Path("szot_sdr_0705.sigmf-meta"))
    parser.add_argument("--parcels", type=Path, default=Path("szotyola_parcels_2025.geojson"))
    parser.add_argument("--band-order", type=Path, default=Path("band_order.conf"))
    parser.add_argument("--out", type=Path, default=Path("127_output"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    features = json.loads(args.parcels.read_text(encoding="utf-8"))["features"]
    genuine, forged = decode_morning(args.morning_data, args.morning_meta, args.out)
    current_order = read_current_band_order(args.band_order)
    capture_order = infer_morning_band_order(genuine, features, current_order)
    green = find_sprayed_green(genuine, forged, features, capture_order)
    dealer = decode_dealer(args.dealer_data, args.dealer_meta, args.out)
    tonight = find_tonight(dealer, features, args.out)
    flag = f"GAIANSPACE{{{'-'.join(green)}_{tonight}}}"
    print(f"FLAG: {flag}")
    (args.out / "flag.txt").write_text(flag + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
