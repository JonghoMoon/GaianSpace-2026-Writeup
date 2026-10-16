# 124-subsidy-claim

| | |
|---|---|
| **Category** | 12 — Spectral Forensics |
| **Points** | 175 |

## Description

13:10, the county agricultural office, Békéscsaba. Babb's area claim for the north block has been rejected: *parcel already claimed, declared as pasture, satellite check passed.*

Someone filed a claim on Babb's corn, and the office's satellite check agreed with them. The clerk is helpful, up to a point. The office checks every declaration against the same Copernicus image with its own classifier and its own statistics file, and Babb may take copies of all of it. The clerk mentions, as if it were nothing, that the office left one class out of its statistics this year. Fieldwork is expensive, and nobody claims that crop around here anyway.

At 12:05 the co-op SDR caught the stranger transmitting one more time, on yet another channel. The stranger was talking to someone else now.

The north block is not the only parcel they lied about. Find every false declaration in the stranger's batch.

The flag is the stranger's claim codes for the false declarations, in the order the stranger sent them, joined with hyphens.

**Flag format:** `GAIANSPACE{XXXX-XXXX-...}`

**Attachments:**

- `coop_sdr_1205.sigmf-data` — the co-op SDR's bursts at noon
- `coop_sdr_1205.sigmf-meta` — the SDR's metadata for that file
- `office_check_20250704.tif` — the image the office checks against (five channels, georeferenced)
- `office_training.sta` — the office's class statistics
- `training_fields.geojson` — the office's training fields
- `parcels.geojson` — the parcel register for the area
- `rejection_letter.txt` — the office's letter to Babb

Contains modified Copernicus Sentinel data 2025.

## Hints

Two hints were released during the event:

1. **Greener is better** — The office's classifier does more than name a class. It can also say how sure it is, and a parcel it is sure about tells you more than one it shrugs at.
2. **The field nobody walked** — A classifier that never met a class can't recognise it. The office kept the field. It only threw away what it learned there.

## Solution

### Steps

1. Decode and CRC-validate all 64 SDR frames, yielding two transmissions of the same 30-claim batch text. The complete frame payloads are distinct because their frame counters continue across the two transmissions.
2. Read the five-channel georeferenced TIFF, parcel polygons, published class statistics, and training fields.
3. Reconstruct the omitted `kukorica` (corn) class from the training pixels.
4. Classify parcel pixels with the restored class and compare dominant classes to the submitted declarations.
5. Verify that the restored-statistics classifier agrees with a fully recomputed training classifier, then list false claims in transmitted order.

The code reconstructs the omitted `kukorica` class from training-field pixels; the published-plus-restored classifier and a fully recomputed training classifier can differ at one pixel without changing the parcel-level decisions.

### Repeated batch text, distinct frame payloads

The decoded application payload starts with `b7 2a`, followed by a two-byte little-endian frame counter and the ASCII text: `b7 2a | counter (LE16) | text`. Each transmission contains 32 text lines: the `CLAIM BATCH 2025-AREA BKS-0712 applicant=AGRO-LIGET KFT n=30` header, 30 claim lines, and `END BKS-0712`.

| Transmission | Frame counters | Text |
|---|---|---|
| First | 0–31 | Batch header, 30 claims, and END |
| Second | 32–63 | The same 32 text lines |

The saved `scripts/124_recovered/radio_packets.json` records both the `sequence` and the complete `payload_hex` for every frame. Comparing the text after the four-byte header gives two identical 32-line sequences, while comparing the complete payloads gives **64 distinct values**. The solver's output phrase `2 identical transmissions` refers to the decoded batch contents, not byte-for-byte identity of the complete frame payloads. This distinction matters in 125, which matches the complete payload across gateways so that the two transmissions are not merged.

### Reproduction

Run from the `124-subsidy-claim/` directory with the original inputs in `challenges/`:

```bash
python3 scripts/124.py --input-dir challenges --output-dir scripts/124_recovered
```

Expected relevant output:

```text
Decoded and CRC-verified: 64/64
Batch BKS-0712: 30 claims, 2 identical transmissions
Restored kukorica: 3514 pixels, mean=[228.75697211155378, 403.2438816163916, 243.26807057484348, 3320.5071143995447, 1753.4667046101308]
Published-plus-restored vs fully recomputed classifier: 1 pixel disagreements
01 MZH-8140 CUVE legelo -> kukorica: 93.10% FALSE
10 MZH-9183 UKEJ legelo -> kukorica: 84.03% FALSE
28 MZH-1402 TRP6 legelo -> kukorica: 79.80% FALSE
All parcel decisions agree when every class is re-estimated from training pixels
False declarations: 3/30
FLAG: GAIANSPACE{CUVE-UKEJ-TRP6}
```

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies (install if needed):
#   python3 -m pip install numpy rasterio
"""GaianSpace 124 - recover the claim batch and audit the missing crop class.

Usage:
    python3 124.py
    python3 124.py --input-dir /path/to/files --output-dir 124_recovered

Dependencies: numpy, rasterio

This is an offline decoder. It does not transmit or submit a flag.
Radio parameters measured from this capture: SF9, BW about 125 kHz,
8 preamble symbols, explicit header, sync word 0x34, payload CRC enabled.
The LoRa bit pipeline follows the same convention as the previously supplied
122 decoder (reference implementation: https://github.com/jkadbear/LoRaPHY).
No claim codes, false parcel IDs, or final flag are embedded in this script.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.features import geometry_mask

SF = 9
BW = 125_000.0
HEADER_CHECK = np.array([
    [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1],
    [0, 1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0],
    [0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1],
    [0, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1],
], dtype=np.int64)


def parity(value: int, positions: tuple[int, ...]) -> int:
    result = 0
    for position in positions:
        result ^= (int(value) >> (int(position) - 1)) & 1
    return int(result)


def hamming_encode(nibble: int, width: int) -> int:
    value = int(nibble)
    if width == 5:
        return int(value | (parity(value, (1, 2, 3, 4)) << 4))
    value |= parity(nibble, (1, 2, 3)) << 4
    value |= parity(nibble, (2, 3, 4)) << 5
    if width >= 7:
        value |= parity(nibble, (1, 2, 4)) << 6
    if width == 8:
        value |= parity(nibble, (1, 3, 4)) << 7
    return int(value)


HAMMING = {w: tuple(hamming_encode(n, w) for n in range(16))
           for w in range(5, 9)}


def hamming_decode(words: list[int], width: int) -> list[int]:
    if width <= 6:
        # These coding rates cannot uniquely correct arbitrary single-bit errors.
        # Always validate the resulting frame using its payload CRC.
        return [int(word) & 15 for word in words]
    result = []
    for word in words:
        distances = [(int(word) ^ int(code)).bit_count()
                     for code in HAMMING[width]]
        minimum = min(distances)
        if distances.count(minimum) != 1:
            raise ValueError("Ambiguous Hamming codeword")
        result.append(int(distances.index(minimum)))
    return result


def deinterleave(symbols: list[int], bits_per_symbol: int) -> list[int]:
    words = [0] * int(bits_per_symbol)
    for column, symbol in enumerate(symbols):
        for row in range(bits_per_symbol):
            bit = (int(symbol) >> ((row - column) % bits_per_symbol)) & 1
            words[row] |= int(bit) << int(column)
    return words


def read_header(symbols: np.ndarray) -> tuple[int, int, list[int]]:
    reduced = [int(symbol) // 4 for symbol in symbols[:8]]
    gray = [value ^ (value >> 1) for value in reduced]
    nibbles = hamming_decode(deinterleave(gray, SF - 2), 8)
    length = int(nibbles[0]) * 16 + int(nibbles[1])
    coding_rate = int(nibbles[2]) >> 1
    crc_present = int(nibbles[2]) & 1
    bits = np.array([(int(nibble) >> bit) & 1
                     for nibble in nibbles[:3] for bit in (3, 2, 1, 0)],
                    dtype=np.int64)
    stored = np.array([int(nibbles[3]) & 1]
                      + [(int(nibbles[4]) >> bit) & 1 for bit in (3, 2, 1, 0)],
                      dtype=np.int64)
    if coding_rate not in (1, 2, 3, 4):
        raise ValueError("Invalid coding rate in explicit header")
    if not np.array_equal(stored, (HEADER_CHECK @ bits) % 2):
        raise ValueError("LoRa explicit-header checksum failed")
    if crc_present != 1:
        raise ValueError("Expected a LoRa payload CRC")
    # At SF9 the first block contains five header nibbles and two payload nibbles.
    return length, coding_rate, nibbles[5:]


def symbol_count(length: int, coding_rate: int) -> int:
    remaining_nibbles = 2 * int(length) + 4 - (SF - 7)
    return 8 + (int(coding_rate) + 4) * max(
        0, int(math.ceil(float(remaining_nibbles) / float(SF))))


def whitening_bytes(length: int) -> bytes:
    state = 0xFF
    output = bytearray()
    for _ in range(length):
        output.append(int(state))
        bit = ((state >> 7) ^ (state >> 5) ^ (state >> 4) ^ (state >> 3)) & 1
        state = ((state << 1) | bit) & 0xFF
    return bytes(output)


def lora_crc(payload: bytes) -> int:
    if not payload:
        return 0
    if len(payload) == 1:
        return int(payload[0])
    return (int(binascii.crc_hqx(payload[:-2], 0)) ^ int(payload[-1])
            ^ (int(payload[-2]) << 8))


def decode_symbols(symbols: np.ndarray) -> tuple[bytes, int, int]:
    length, coding_rate, nibbles = read_header(symbols)
    needed = symbol_count(length, coding_rate)
    if int(symbols.size) < needed:
        raise ValueError("Incomplete LoRa symbol sequence")
    width = int(coding_rate) + 4
    for start in range(8, needed, width):
        reduced = [(int(symbol) - 1) % (1 << SF)
                   for symbol in symbols[start:start + width]]
        gray = [value ^ (value >> 1) for value in reduced]
        nibbles.extend(hamming_decode(deinterleave(gray, SF), width))
    packed = bytes(int(nibbles[i]) | (int(nibbles[i + 1]) << 4)
                   for i in range(0, len(nibbles) - 1, 2))
    if len(packed) < length + 2:
        raise ValueError("Not enough decoded bytes")
    payload = bytes(int(a) ^ int(b)
                    for a, b in zip(packed[:length], whitening_bytes(length)))
    expected = int.from_bytes(packed[length:length + 2], "little")
    actual = lora_crc(payload)
    if actual != expected:
        raise ValueError(f"Payload CRC failed: {actual:04X} != {expected:04X}")
    return payload, actual, coding_rate


class Receiver:
    def __init__(self, sample_rate: float) -> None:
        self.fs = float(sample_rate)
        self.oversampling = int(round(self.fs / BW))
        if self.oversampling != 8:
            raise ValueError("Expected approximately 1 MHz sampling at BW125k")
        self.n = (1 << SF) * self.oversampling
        axis = np.arange(self.n, dtype=np.float64)
        self.up = np.exp(1j * np.pi * (
            axis * axis / float(self.oversampling * self.n)
            - axis / float(self.oversampling)))

    def peaks(self, blocks: np.ndarray, reference: np.ndarray,
              padding: int = 8) -> tuple[np.ndarray, np.ndarray]:
        spectrum = np.abs(np.fft.fft(blocks * reference,
                                    n=self.n * padding, axis=-1))
        folded = spectrum.reshape(spectrum.shape[:-1]
                                  + (self.oversampling, (1 << SF) * padding)).sum(axis=-2)
        indices = folded.argmax(axis=-1)
        bins = indices.astype(np.float64) / float(padding)
        quality = np.take_along_axis(folded, indices[..., None], axis=-1)[..., 0]
        quality /= np.maximum(np.linalg.norm(folded, axis=-1), 1e-20)
        return bins, quality

    def decode(self, iq: np.ndarray) -> tuple[bytes, dict[str, Any]]:
        n = self.n
        window = 128
        power = np.convolve(np.abs(iq) ** 2,
                            np.ones(window, dtype=np.float64) / float(window),
                            mode="valid")
        threshold = 0.4 * float(np.percentile(power, 70.0))
        active = np.flatnonzero(power > threshold)
        if int(active.size) == 0:
            raise ValueError("No burst energy detected")
        start = max(0, int(active[0]) + window // 2 - 20)
        preamble = iq[start + n:start + 7 * n].reshape(6, n)
        pre, _ = self.peaks(preamble, np.conj(self.up))
        pre_bin = float(np.median(pre))
        sync, _ = self.peaks(iq[start + 8 * n:start + 10 * n].reshape(2, n),
                             np.conj(self.up))
        sync_symbols = np.rint((sync - pre_bin) % float(1 << SF)).astype(np.int64) % (1 << SF)
        if not np.array_equal(sync_symbols, np.array([24, 32], dtype=np.int64)):
            raise ValueError(f"Unexpected synchronization symbols: {sync_symbols}")
        data_start = start + int(round(12.25 * float(n)))
        available = (int(iq.size) - data_start) // n
        if available < 8:
            raise ValueError("Burst does not contain a complete header")
        peaks, quality = self.peaks(
            iq[data_start:data_start + available * n].reshape(available, n),
            np.conj(self.up))
        initial = np.rint((peaks - pre_bin) % float(1 << SF)).astype(np.int64) % (1 << SF)
        length, coding_rate, _ = read_header(initial)
        count = symbol_count(length, coding_rate)
        if count > available:
            raise ValueError("Burst is missing payload symbols")
        relative = peaks[:count] - pre_bin
        fractional = np.unwrap(2.0 * np.pi * (relative - np.rint(relative))) / (2.0 * np.pi)
        axis = np.arange(count, dtype=np.float64)
        fit = np.polyfit(axis, fractional, 1)
        for _ in range(2):
            good = ((np.abs(fractional - np.polyval(fit, axis)) < 0.12)
                    & (quality[:count] > 0.18))
            if int(np.count_nonzero(good)) < 8:
                raise ValueError("Not enough reliable symbols for drift correction")
            fit = np.polyfit(axis[good], fractional[good], 1)
        symbols = np.rint(relative - np.polyval(fit, axis)).astype(np.int64) % (1 << SF)
        payload, crc, coding_rate = decode_symbols(symbols)
        return payload, {"preamble_start": start, "data_symbols": count,
                         "payload_length": len(payload), "coding_rate": f"4/{4 + coding_rate}",
                         "sync_symbols": [int(value) for value in sync_symbols],
                         "drift_bins_per_symbol": float(fit[0]), "crc16": f"{crc:04X}"}


def decode_radio(root: Path, out: Path) -> list[dict[str, Any]]:
    meta = json.loads((root / "coop_sdr_1205.sigmf-meta").read_text(encoding="utf-8"))
    if meta["global"]["core:datatype"] != "ci8":
        raise ValueError("Expected signed int8 interleaved I/Q")
    data_path = root / "coop_sdr_1205.sigmf-data"
    if int(data_path.stat().st_size) % 2 != 0:
        raise ValueError("Odd byte count in ci8 recording")
    raw = np.memmap(data_path, dtype=np.int8, mode="r").reshape(-1, 2)
    captures = meta["captures"]
    starts = [int(item["core:sample_start"]) for item in captures] + [int(raw.shape[0])]
    if starts[0] != 0 or any(b <= a for a, b in zip(starts, starts[1:])):
        raise ValueError("Invalid burst boundaries")
    receiver = Receiver(float(meta["global"]["core:sample_rate"]))
    records = []
    for index, capture in enumerate(captures):
        pairs = raw[starts[index]:starts[index + 1]].astype(np.float64)
        iq = pairs[:, 0] + 1j * pairs[:, 1]
        try:
            payload, details = receiver.decode(iq)
        except ValueError as exc:
            raise ValueError(f"Burst {index}: {exc}") from exc
        if len(payload) < 4:
            raise ValueError("Application header is too short")
        text = payload[4:].decode("ascii")
        records.append({"burst": index, "utc": str(capture["core:datetime"]),
                        "application_prefix": payload[:2].hex(),
                        "sequence": int.from_bytes(payload[2:4], "little"),
                        "payload_hex": payload.hex(), "text": text, **details})
        print(f"RX {index:02d}: {text}", flush=True)
    if len({record["application_prefix"] for record in records}) != 1:
        raise ValueError("Unexpected application mark")
    seq = [int(record["sequence"]) for record in records]
    if seq != list(range(seq[0], seq[0] + len(records))):
        raise ValueError("Application sequence is not contiguous")
    (out / "radio_packets.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Decoded and CRC-verified: {len(records)}/{len(captures)}")
    return records


def parse_claims(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    header_re = re.compile(r"^CLAIM BATCH \S+ (\S+) applicant=(.+) n=(\d+)$")
    claim_re = re.compile(r"^(\d+);([^;]+);([^;]+);(\d+(?:\.\d+)?);([A-Z0-9]{4})$")
    batches = []
    current = None
    for record in records:
        text = str(record["text"])
        match = header_re.fullmatch(text)
        if match is not None:
            if current is not None:
                raise ValueError("New batch before the preceding batch ended")
            current = {"id": match.group(1), "applicant": match.group(2),
                       "expected": int(match.group(3)), "claims": []}
        elif text.startswith("END "):
            if current is None or text[4:] != current["id"]:
                raise ValueError("Unmatched batch terminator")
            if len(current["claims"]) != current["expected"]:
                raise ValueError("Incomplete claim batch")
            batches.append(current)
            current = None
        else:
            match = claim_re.fullmatch(text)
            if current is None or match is None:
                raise ValueError(f"Unexpected application record: {text}")
            order = int(match.group(1))
            if order != len(current["claims"]) + 1:
                raise ValueError("Claim order is not contiguous")
            current["claims"].append({"order": order, "parcel": match.group(2),
                                      "declared": match.group(3), "area_ha": float(match.group(4)),
                                      "code": match.group(5)})
    if current is not None or not batches:
        raise ValueError("No complete batch")
    if any(batch != batches[0] for batch in batches[1:]):
        raise ValueError("Repeated batches disagree")
    print(f"Batch {batches[0]['id']}: {batches[0]['expected']} claims, {len(batches)} identical transmissions")
    return list(batches[0]["claims"])


def read_office_stats(path: Path) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    current = None
    for source_line in path.read_text(encoding="utf-8").splitlines():
        line = source_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "CLASS":
            current = parts[1]
            if current in stats or len(parts) != 6:
                raise ValueError("Invalid CLASS record")
            stats[current] = {"field": parts[3], "n": int(parts[5]), "cov": []}
        elif current is not None and parts[0] == "MEAN":
            stats[current]["mean"] = np.array([float(v) for v in parts[1:]], dtype=np.float64)
        elif current is not None and parts[0] == "COV":
            stats[current]["cov"].append([float(v) for v in parts[1:]])
        else:
            raise ValueError(f"Unrecognized statistics line: {line}")
    for record in stats.values():
        record["cov"] = np.asarray(record["cov"], dtype=np.float64)
        if record["cov"].shape != (5, 5) or record["mean"].shape != (5,):
            raise ValueError("Expected five-band mean and covariance")
    return stats


def geographic_mask(feature: dict[str, Any], shape: tuple[int, int],
                    transform: Any, valid: np.ndarray) -> np.ndarray:
    return (geometry_mask([feature["geometry"]], out_shape=shape,
                          transform=transform, invert=True, all_touched=False) & valid)


def classify(cube: np.ndarray, stats: dict[str, dict[str, Any]],
             names: list[str]) -> np.ndarray:
    pixels = cube.reshape(cube.shape[0], -1).T
    scores = []
    for name in names:
        record = stats[name]
        covariance = np.asarray(record["cov"], dtype=np.float64)
        sign, logdet = np.linalg.slogdet(covariance)
        if float(sign) <= 0.0 or float(np.linalg.eigvalsh(covariance)[0]) <= 0.0:
            raise ValueError(f"Covariance is not positive definite: {name}")
        delta = pixels - record["mean"]
        distance = np.einsum("ij,jk,ik->i", delta, np.linalg.inv(covariance), delta)
        # Equal priors and a common dimension allow the other constants to cancel.
        scores.append(-0.5 * (float(logdet) + distance))
    return np.argmax(np.stack(scores), axis=0).astype(np.uint8).reshape(cube.shape[1:])


def audit_claims(root: Path, out: Path, claims: list[dict[str, Any]]) -> str:
    with rasterio.open(root / "office_check_20250704.tif") as source:
        if source.count != 5 or source.descriptions != ("B02", "B03", "B04", "B08", "B11"):
            raise ValueError("Unexpected image bands or band order")
        cube = source.read().astype(np.float64)
        valid = np.all(source.read_masks() > 0, axis=0)
        transform, crs = source.transform, source.crs
    fields = json.loads((root / "training_fields.geojson").read_text(encoding="utf-8"))
    parcels = json.loads((root / "parcels.geojson").read_text(encoding="utf-8"))
    for collection in (fields, parcels):
        vector_crs = rasterio.crs.CRS.from_string(str(collection["crs"]["properties"]["name"]))
        if vector_crs != crs:
            raise ValueError("Image and vector coordinate systems differ")
    original = read_office_stats(root / "office_training.sta")
    restored = dict(original)
    recomputed: dict[str, dict[str, Any]] = {}
    for feature in fields["features"]:
        properties = feature["properties"]
        name = str(properties["class"])
        mask = geographic_mask(feature, cube.shape[1:], transform, valid)
        samples = cube[:, mask].T
        count = int(samples.shape[0])
        if count != int(properties["pixels"]):
            raise ValueError(f"Training-pixel count mismatch: {name}")
        if count <= cube.shape[0]:
            raise ValueError(f"Insufficient training pixels: {name}")
        mean = np.mean(samples, axis=0)
        covariance = np.cov(samples, rowvar=False, ddof=1)
        recomputed[name] = {"field": str(properties["field"]), "n": count,
                            "mean": mean, "cov": covariance}
        if name in original:
            mean_error = float(np.max(np.abs(mean - original[name]["mean"])))
            cov_error = float(np.max(np.abs(covariance - original[name]["cov"])))
            if (count != original[name]["n"] or properties["field"] != original[name]["field"]
                    or mean_error > 0.000501 or cov_error > 0.000501):
                raise ValueError(f"Published statistics were not reproduced: {name}")
            print(f"Training {name}: {count} pixels; published statistics agree to rounding")
        else:
            restored[name] = recomputed[name]
            print(f"Restored {name}: {count} pixels, mean={mean.tolist()}")
    missing = sorted(set(recomputed) - set(original))
    if len(missing) != 1:
        raise ValueError(f"Expected one omitted class, found {missing}")
    old_names, new_names = list(original), list(restored)
    old_labels = classify(cube, original, old_names)
    labels = classify(cube, restored, new_names)
    reference_names = list(recomputed)
    reference_labels = classify(cube, recomputed, reference_names)
    # Class numbers are local to each model; compare names rather than IDs.
    disagreement = int(np.count_nonzero(
        np.array(new_names)[labels] != np.array(reference_names)[reference_labels]))
    print(f"Published-plus-restored vs fully recomputed classifier: {disagreement} pixel disagreements")
    registry = {str(feature["properties"]["parcel"]): feature for feature in parcels["features"]}
    pixel_area_ha = abs(float(transform.a * transform.e - transform.b * transform.d)) / 10_000.0
    results, false_codes = [], []
    for claim in claims:
        parcel = str(claim["parcel"])
        if parcel not in registry:
            raise ValueError(f"Unknown parcel: {parcel}")
        feature = registry[parcel]
        mask = geographic_mask(feature, cube.shape[1:], transform, valid)
        counts = np.bincount(labels[mask], minlength=len(new_names))
        old_counts = np.bincount(old_labels[mask], minlength=len(old_names))
        total = int(counts.sum())
        if total == 0:
            raise ValueError(f"No image pixels in parcel: {parcel}")
        area = float(total) * pixel_area_ha
        if (abs(area - float(feature["properties"]["area_ha"])) > 0.005
                or abs(area - float(claim["area_ha"])) > 0.005):
            raise ValueError(f"Parcel area does not agree: {parcel}")
        order = np.argsort(counts)
        if counts[order[-1]] == counts[order[-2]] or float(counts.max()) / float(total) <= 0.5:
            raise ValueError(f"No strict parcel majority: {parcel}")
        actual = new_names[int(counts.argmax())]
        former = old_names[int(old_counts.argmax())]
        reference_counts = np.bincount(reference_labels[mask], minlength=len(reference_names))
        if reference_names[int(reference_counts.argmax())] != actual:
            raise ValueError(f"Parcel result is sensitive to published-statistics rounding: {parcel}")
        false = str(claim["declared"]) != actual
        if former != claim["declared"]:
            raise ValueError(f"Claim did not pass the original office model: {parcel}")
        percent = 100.0 * float(counts.max()) / float(total)
        row = {**claim, "original_class": former, "restored_class": actual,
               "majority_percent": percent, "pixels": total, "false": bool(false),
               "class_counts": {name: int(counts[i]) for i, name in enumerate(new_names)}}
        results.append(row)
        if false:
            false_codes.append(str(claim["code"]))
        print(f"{int(claim['order']):02d} {parcel} {claim['code']} "
              f"{claim['declared']} -> {actual}: {percent:.2f}% "
              f"{'FALSE' if false else 'consistent'}")
    np.save(out / "classes_original.npy", old_labels)
    np.save(out / "classes_restored.npy", labels)
    (out / "class_names.json").write_text(json.dumps({"original": old_names, "restored": new_names}, indent=2), encoding="utf-8")
    (out / "claim_review.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    serializable = {name: {"field": record["field"], "pixels": record["n"],
                           "mean": record["mean"].tolist(), "cov": record["cov"].tolist()}
                    for name, record in restored.items()}
    (out / "restored_statistics.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    columns = ["order", "parcel", "code", "declared", "original_class", "restored_class", "majority_percent", "pixels", "false"]
    with (out / "claim_review.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    if not false_codes:
        raise ValueError("No false declarations found")
    flag = "GAIANSPACE{" + "-".join(false_codes) + "}"
    (out / "flag.txt").write_text(flag + "\n", encoding="ascii")
    print("All parcel decisions agree when every class is re-estimated from training pixels")
    print(f"False declarations: {len(false_codes)}/{len(claims)}")
    print(f"FLAG: {flag}")
    return flag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("124_recovered"))
    args = parser.parse_args()
    root, out = args.input_dir.resolve(), args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    records = decode_radio(root, out)
    claims = parse_claims(records)
    audit_claims(root, out, claims)
    input_names = ["coop_sdr_1205.sigmf-meta", "coop_sdr_1205.sigmf-data", "office_check_20250704.tif",
                   "office_training.sta", "training_fields.geojson", "parcels.geojson"]
    hashes = {}
    for name in input_names:
        digest = hashlib.sha256()
        with (root / name).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        hashes[name] = digest.hexdigest()
    (out / "input_sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{CUVE-UKEJ-TRP6}
```
