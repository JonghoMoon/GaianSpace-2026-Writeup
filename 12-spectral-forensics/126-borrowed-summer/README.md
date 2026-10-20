# 126 — Borrowed Summer

| | |
|---|---|
| **Category** | 12 — Spectral Forensics |
| **Points** | 316 |

## Description

15:40, the Babb farm. The review request for the north block is in. Babb's phone rings: a Dr. Kuko Rica, from Hajdúnánás, who heard about the rejected claim from the county office.

Dr. Rica grows corn on the other side of the plain, and last year it happened to him first. In July and August 2024, the driest summer anyone there remembers, his AgriLink mast kept delivering tiles of fat green corn. His irrigation planner believed them and held back the water. By the time anyone walked the north block, most of it was gone. AgriLink looked into it and says every tile was genuine. Dr. Rica's young agronomist still says the July tiles were the best of the season.

Dr. Rica kept everything his mast received that year, and he has sent it all to Babb. If the stranger's hand is in his archive, the office will have to look at both farms again.

Some of the deliveries are not what they say they are. Find every one.

The flag is their delivery IDs from the mast journal, in the order the mast received them, joined with hyphens.

**Flag format:** `GAIANSPACE{XXXX-XXXX-...}`

## Files

- `rica_tiles_2024.zip` — every tile Dr. Rica's mast received in 2024 (AgriLink tile format: one manifest line, then five channels of 256 × 256 bytes)
- `rica_mast_journal.log` — the mast's delivery journal for the season
- `rica_parcels_2024.geojson` — Dr. Rica's parcels on the north block and the crops he declared for 2024, in tile pixel coordinates
- `agrilink_integrity_review.txt` — AgriLink's answer to Dr. Rica's complaint

Contains modified Copernicus Sentinel data 2023 and 2024.

## Hints

Two hints were released during the event:

1. **Hint 1** — **No way back.** After midsummer a field on the plain only goes one way. It ripens, it dries, it gets cut. It doesn't turn back into a young green crop a fortnight later.
2. **Hint 2** — **Genuine is not the same as true.** AgriLink checked that every product is real. Nobody checked that the pixels came from that product.

## Solution

### 1. Decode the original tiles

The ZIP contains **16** `.alt` files. Each file begins with a single ASCII manifest line and then contains five planar **256 × 256** unsigned-byte bands in the order `B02,B03,B04,B08,B11`. The script validates the expected payload size and band order, then reads the byte arrays directly with NumPy. No radio demodulation is needed because the mast's archived tiles have already been delivered and stored.

### 2. Identify an independent seasonal control

The irrigation complaint focuses on corn, but green corn alone is not evidence of tampering. The parcel register includes a winter-wheat (`őszi búza`) field, **HNN-8976**, which serves as an independent seasonal control. Its polygon covers **3,453 pixel centers** in the tile grid.

Winter wheat should be harvested by the July–August observation period. In the archive its average NDVI falls from **0.865 on 10 May** to **0.228 on 24 June**, and stays around 0.20–0.25 in the adjacent normal July–August scenes.

### 3. Compare the vegetation signal over time

Compute normalized difference vegetation index from red and near-infrared reflectance:

```text
NDVI = (B08 - B04) / (B08 + B04)
```

The reflectance scaling cancels in the ratio. Calculate the **mean NDVI within the wheat polygon** for every acquisition date. The following anomalous scenes appear after harvest:

| Tile acquisition date | Delivery ID | Mean wheat NDVI | Finding |
|---|---|---:|---|
| 2024-07-09 | ZDJ7 | 0.826 | Suspicious |
| 2024-07-27 | UCZA | 0.823 | Suspicious |
| 2024-08-11 | JADX | 0.805 | Suspicious |
| 2024-08-23 | 7JEY | 0.554 | Suspicious |

The intervening scenes show normal harvested wheat: **0.248** (July 7), **0.215** (July 22), **0.224** (July 29), **0.229** (August 21), and **0.203** (August 31). The alternation from harvested to strongly green and back is inconsistent with the crop's seasonal progression.

The script uses a simple **0.45 mean-NDVI threshold in July and August** to reproduce these four detections. This threshold is an analytical choice supported by the strong separation in this archive, not a value stated by AgriLink.

### 4. Map anomalous tiles to delivery IDs

Use `rica_mast_journal.log` to preserve the **mast's reception order**, not ZIP filename order. The four suspicious acquisition dates correspond to the IDs `ZDJ7`, `UCZA`, `JADX`, and `7JEY`, in that order.

### Dead Ends and Interpretation

- **Looking only at corn:** Green corn is expected in summer, so it is a weak independent check. Harvested winter wheat exposes the temporal inconsistency.
- **Trusting catalogue metadata:** AgriLink verified that the named Sentinel products exist, their dates/cloud percentages match the catalogue, and the transfer CRC passed. Those checks do not prove the delivered pixel arrays are the genuine acquisitions.
- **Assuming a checksum failure:** A complete, CRC-valid delivery can still contain substituted image data.
- **Calling it cryptographic proof:** The evidence is strong temporal/phenological inconsistency, not a byte-for-byte comparison against original Copernicus scenes.

The `0.45` NDVI anomaly threshold is an analyst-selected test of post-harvest winter-wheat behavior, not a threshold supplied by the challenge. The four delivery IDs are recovered from the mast journal rather than hardcoded into the classifier.

## Reproduction

Place `126.py` beside the four original challenge files. Install dependencies:

```bash
python3 -m pip install numpy matplotlib
```

Run:

```bash
python3 126.py
```

**Expected relevant output:**

```text
Winter-wheat parcel: HNN-8976, pixels=3453
Tiles: 16; deliveries: 16
2024-07-09  ZDJ7  wheat_NDVI=0.826  SUSPECT
2024-07-27  UCZA  wheat_NDVI=0.823  SUSPECT
2024-08-11  JADX  wheat_NDVI=0.805  SUSPECT
2024-08-23  7JEY  wheat_NDVI=0.554  SUSPECT
FLAG: GAIANSPACE{ZDJ7-UCZA-JADX-7JEY}
```

### Python Source Code

{% raw %}
```python
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
```
{% endraw %}

## Tools and References

- Python 3, NumPy, Matplotlib polygon masking, ZIP archive parsing
- Supplied `rica_parcels_2024.geojson`, `rica_mast_journal.log`, and AgriLink integrity review
- Sentinel-2 red (B04) and near-infrared (B08) band interpretation and NDVI
- Seasonal behavior of harvested winter wheat as an internal control

## Flag

```text
GAIANSPACE{ZDJ7-UCZA-JADX-7JEY}
```
