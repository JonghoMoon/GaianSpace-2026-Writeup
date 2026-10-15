#!/usr/bin/env python3
# Dependencies (install if needed):
#   python3 -m pip install numpy matplotlib
"""Detect temporally inconsistent AgriLink deliveries using wheat phenology."""

import argparse
import json
import re
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
from matplotlib.path import Path as PolygonPath

WIDTH = 256
HEIGHT = 256
BANDS = ("B02", "B03", "B04", "B08", "B11")
NDVI_THRESHOLD = 0.45


def polygon_mask(geometry: dict) -> np.ndarray:
    """Rasterize the wheat parcel with pixel-center inclusion tests."""
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    points = np.column_stack((xx.ravel() + 0.5, yy.ravel() + 0.5))
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    result = np.zeros(points.shape[0], dtype=bool)
    for rings in polygons:
        inside = PolygonPath(np.asarray(rings[0], dtype=float)).contains_points(points)
        for hole in rings[1:]:
            inside &= ~PolygonPath(np.asarray(hole, dtype=float)).contains_points(points)
        result |= inside
    return result.reshape(HEIGHT, WIDTH)


def read_journal(path: Path) -> list[tuple[date, str]]:
    """Read deliveries in actual mast reception order."""
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.search(r"tile (\d{8})\s+delivery ([A-Z0-9]{4})", line)
        if match:
            result.append((date.fromisoformat(f"{match[1][:4]}-{match[1][4:6]}-{match[1][6:]}"), match[2]))
    if not result:
        raise ValueError("No delivery IDs found in the mast journal")
    return result


def read_tiles(path: Path) -> dict[date, np.ndarray]:
    """Decode one ASCII manifest followed by five planar 256x256 uint8 bands."""
    result = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith(".alt"):
                continue
            raw = archive.read(name)
            header, separator, body = raw.partition(b"\n")
            if not separator or len(body) != len(BANDS) * HEIGHT * WIDTH:
                raise ValueError(f"Invalid tile size: {name}")
            manifest = header.decode("ascii")
            match = re.search(r"date=(\d{4}-?\d{2}-?\d{2})", manifest)
            if match is None:
                raise ValueError(f"Missing tile date: {name}")
            if "ch=B02,B03,B04,B08,B11" not in manifest:
                raise ValueError(f"Unexpected band order: {name}")
            date_string = match.group(1).replace("-", "")
            day = date.fromisoformat(f"{date_string[:4]}-{date_string[4:6]}-{date_string[6:]}")
            result[day] = np.frombuffer(body, dtype=np.uint8).reshape(
                len(BANDS), HEIGHT, WIDTH
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tiles", type=Path, default=Path("rica_tiles_2024.zip"))
    parser.add_argument("--journal", type=Path, default=Path("rica_mast_journal.log"))
    parser.add_argument("--parcels", type=Path, default=Path("rica_parcels_2024.geojson"))
    args = parser.parse_args()

    features = json.loads(args.parcels.read_text(encoding="utf-8"))["features"]
    wheat = [item for item in features if item["properties"]["crop_2024"] == "őszi búza"]
    if len(wheat) != 1:
        raise ValueError(f"Expected one winter-wheat parcel, got {len(wheat)}")
    mask = polygon_mask(wheat[0]["geometry"])
    tiles = read_tiles(args.tiles)
    deliveries = read_journal(args.journal)
    print(f"Winter-wheat parcel: {wheat[0]['properties']['parcel']}, pixels={int(mask.sum())}")
    print(f"Tiles: {len(tiles)}; deliveries: {len(deliveries)}")
    suspects = []
    for day, delivery in deliveries:
        cube = tiles[day]
        red = cube[BANDS.index("B04")].astype(np.float64)
        nir = cube[BANDS.index("B08")].astype(np.float64)
        ndvi = (nir - red) / np.maximum(nir + red, 1.0)
        mean_ndvi = float(np.mean(ndvi[mask]))
        # Harvested wheat should remain low-NDVI in July and August.
        suspect = day.month in (7, 8) and mean_ndvi > NDVI_THRESHOLD
        if suspect:
            suspects.append(delivery)
        print(f"{day}  {delivery}  wheat_NDVI={mean_ndvi:.3f}  {'SUSPECT' if suspect else 'normal'}")
    print(f"FLAG: GAIANSPACE{{{'-'.join(suspects)}}}")


if __name__ == "__main__":
    main()
