#!/usr/bin/env python3
# Dependencies (install if needed):
#   python3 -m pip install numpy Pillow scikit-learn threadpoolctl
"""GaianSpace CTF 123: recover the FieldLink image and its spectral lettering.

Usage:
    python3 123.py
    python3 123.py --cube 123_recovered/cube.npy --out 123_rerun

Dependencies: numpy, Pillow, scikit-learn

The default run decodes the uploaded ci8 recording, verifies every application
CRC, reconstructs the image, performs seven-class centroid clustering, and
reads the measured mask by exact bitmap matching. This is a fixed-seven
K-means analysis, not an implementation of adaptive split/merge ISODATA.
No flag text, token suffix, text coordinates, or class IDs are hard-coded.
The RF decoder is specialized to the supplied SF7/BW500k capture.

LoRa symbol processing follows the earlier 122.py decoder, checked against
jkadbear/LoRaPHY (MIT): https://github.com/jkadbear/LoRaPHY
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import math
import re
import string
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.cluster import KMeans
from threadpoolctl import threadpool_limits


SF = 7
BW = 500_000.0
PREAMBLE_SYMBOLS = 10
CODING_RATE = 1


def parity(value: int, positions: tuple[int, ...]) -> int:
    result = 0
    for position in positions:
        result ^= (int(value) >> (int(position) - 1)) & 1
    return int(result)


def hamming84(nibble: int) -> int:
    value = int(nibble)
    value |= parity(nibble, (1, 2, 3)) << 4
    value |= parity(nibble, (2, 3, 4)) << 5
    value |= parity(nibble, (1, 2, 4)) << 6
    value |= parity(nibble, (1, 3, 4)) << 7
    return int(value)


HAMMING84 = tuple(hamming84(n) for n in range(16))


def deinterleave(symbols: list[int], ppm: int) -> list[int]:
    codewords = [0] * int(ppm)
    for column, symbol in enumerate(symbols):
        for row in range(ppm):
            bit = (int(symbol) >> ((row - column) % ppm)) & 1
            codewords[row] |= int(bit) << int(column)
    return codewords


def whitening_bytes(length: int) -> bytes:
    state = 0xFF
    output = bytearray()
    for _ in range(length):
        output.append(int(state))
        feedback = ((state >> 7) ^ (state >> 5) ^ (state >> 4)
                    ^ (state >> 3)) & 1
        state = ((state << 1) | feedback) & 0xFF
    return bytes(output)


def decode_implicit(symbols: np.ndarray, frame_length: int | None = None) -> bytes:
    """Decode an implicit-header LoRa packet; infer length by application CRC."""
    reduced = [int(s) // 4 for s in symbols[:8]]
    gray = [s ^ (s >> 1) for s in reduced]
    nibbles: list[int] = []
    for word in deinterleave(gray, SF - 2):
        distances = [(int(word) ^ int(c)).bit_count() for c in HAMMING84]
        minimum = min(distances)
        if distances.count(minimum) != 1:
            raise ValueError("Ambiguous first-block FEC decoding")
        nibbles.append(int(distances.index(minimum)))

    width = CODING_RATE + 4
    for start in range(8, int(symbols.size) - width + 1, width):
        values = [(int(s) - 1) % (1 << SF)
                  for s in symbols[start:start + width]]
        gray = [s ^ (s >> 1) for s in values]
        # CR4/5 cannot uniquely correct errors; the frame CRC validates the result.
        nibbles.extend(int(word) & 15 for word in deinterleave(gray, SF))

    packed = bytes(int(nibbles[i]) | (int(nibbles[i + 1]) << 4)
                   for i in range(0, len(nibbles) - 1, 2))
    decoded = bytes(int(a) ^ int(b)
                    for a, b in zip(packed, whitening_bytes(len(packed))))
    if not decoded.startswith(b"JRM"):
        raise ValueError("Dealer mark or map-frame type is invalid")

    # Radio CRC is disabled. The actual frame has a big-endian CCITT-FALSE CRC.
    possible_lengths = range(9, len(decoded) + 1) if frame_length is None else [int(frame_length)]
    lengths = [length for length in possible_lengths
               if int(binascii.crc_hqx(decoded[:length - 2], 0xFFFF))
               == int.from_bytes(decoded[length - 2:length], "big")]
    if len(lengths) != 1:
        raise ValueError(f"Expected one CRC-valid frame length, got {lengths}")
    return decoded[:lengths[0]]


class Receiver:
    def __init__(self, sample_rate: float) -> None:
        self.fs = float(sample_rate)
        self.frame_length: int | None = None
        self.os = int(round(self.fs / BW))
        self.n = (1 << SF) * self.os
        if self.os != 4:
            raise ValueError("This decoder expects approximately 2 MHz sampling")
        t = np.arange(self.n, dtype=np.float64)
        self.up = np.exp(1j * np.pi * (
            t * t / float(self.os * self.n) - t / float(self.os)))

    def peaks(self, blocks: np.ndarray, reference: np.ndarray,
              padding: int = 8) -> tuple[np.ndarray, np.ndarray]:
        spectrum = np.abs(np.fft.fft(blocks * reference,
                                    n=self.n * padding, axis=-1))
        shape = spectrum.shape[:-1] + (self.os, (1 << SF) * padding)
        folded = spectrum.reshape(shape).sum(axis=-2)
        indices = folded.argmax(axis=-1)
        peaks = indices.astype(np.float64) / float(padding)
        quality = np.take_along_axis(folded, indices[..., None], axis=-1)[..., 0]
        quality /= np.maximum(np.linalg.norm(folded, axis=-1), 1e-20)
        return peaks, quality

    def decode(self, iq: np.ndarray) -> tuple[bytes, dict]:
        n = self.n
        window = 128
        local_power = np.convolve(np.abs(iq) ** 2,
                                  np.ones(window, dtype=np.float64) / float(window),
                                  mode="valid")
        threshold = 0.4 * float(np.percentile(local_power, 70.0))
        active = np.flatnonzero(local_power > threshold)
        if int(active.size) == 0:
            raise ValueError("No burst energy found")
        start = max(0, int(active[0]) + window // 2 - 20)
        data_start = start + int(round(float(PREAMBLE_SYMBOLS + 4.25) * n))
        available = (int(iq.size) - data_start) // n
        if available < 8:
            raise ValueError("Burst too short")
        preamble = iq[start + n:start + 9 * n].reshape(8, n)
        pre, _ = self.peaks(preamble, np.conj(self.up))
        pre_bin = float(np.median(pre))
        sync, _ = self.peaks(iq[start + 10 * n:start + 12 * n].reshape(2, n),
                             np.conj(self.up))
        sync_symbols = np.rint((sync - pre_bin) % 128.0).astype(np.int64) % 128
        if not np.array_equal(sync_symbols, np.array([16, 96], dtype=np.int64)):
            raise ValueError(f"Unexpected network word symbols: {sync_symbols}")

        blocks = iq[data_start:data_start + available * n].reshape(available, n)
        peaks, quality = self.peaks(blocks, np.conj(self.up))
        reliable = np.flatnonzero(quality > 0.15)
        if int(reliable.size) == 0:
            raise ValueError("No reliable data symbols")
        last = int(reliable[-1]) + 1
        count = 8 + max(0, (last - 8) // 5) * 5
        relative = peaks[:count] - pre_bin
        quality = quality[:count]
        fractional = np.unwrap(2.0 * np.pi * (relative - np.rint(relative))) / (2.0 * np.pi)
        axis = np.arange(count, dtype=np.float64)
        good = quality > 0.15
        fit = np.polyfit(axis[good], fractional[good], 1)
        for _ in range(2):
            good = (np.abs(fractional - np.polyval(fit, axis)) < 0.12) & (quality > 0.18)
            if int(np.count_nonzero(good)) < 8:
                raise ValueError("Not enough symbols to fit sampling drift")
            fit = np.polyfit(axis[good], fractional[good], 1)
        symbols = np.rint(relative - np.polyval(fit, axis)).astype(np.int64) % 128
        payload = decode_implicit(symbols, self.frame_length)
        if self.frame_length is None:
            self.frame_length = int(len(payload))
        return payload, {
            "preamble_start": int(start),
            "data_symbols": int(count),
            "drift_bins_per_symbol": float(fit[0]),
            "sync_symbols": [int(s) for s in sync_symbols],
        }


def decode_capture(data_path: Path, meta_path: Path, out: Path) -> np.ndarray:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta["global"]["core:datatype"] != "ci8":
        raise ValueError("Expected interleaved signed int8 I/Q samples")
    if int(data_path.stat().st_size) % 2 != 0:
        raise ValueError("Odd byte count in ci8 recording")
    raw = np.memmap(data_path, dtype=np.int8, mode="r").reshape(-1, 2)
    captures = meta["captures"]
    starts = [int(c["core:sample_start"]) for c in captures] + [int(raw.shape[0])]
    if starts[0] != 0 or any(b <= a for a, b in zip(starts, starts[1:])):
        raise ValueError("Invalid capture boundaries")
    receiver = Receiver(float(meta["global"]["core:sample_rate"]))
    rows: dict[tuple[int, int, int], bytes] = {}
    records = []
    widths: set[int] = set()
    lengths: set[int] = set()
    for index, capture in enumerate(captures):
        pairs = raw[starts[index]:starts[index + 1]].astype(np.float64)
        iq = pairs[:, 0] + 1j * pairs[:, 1]
        try:
            frame, info = receiver.decode(iq)
        except ValueError as exc:
            raise ValueError(f"Burst {index}: {exc}") from exc
        channel, row, half, sequence = (int(v) for v in frame[3:7])
        if half not in (0, 1) or sequence != index % 256:
            raise ValueError(f"Invalid half/sequence in burst {index}")
        key = (channel, row, half)
        if key in rows:
            raise ValueError(f"Duplicate row half: {key}")
        rows[key] = frame[7:-2]
        widths.add(len(rows[key]))
        lengths.add(len(frame))
        records.append({"burst": int(index), "utc": str(capture["core:datetime"]),
                        "channel": channel, "row": row, "half": half,
                        "sequence": sequence, "payload_hex": frame.hex(),
                        "crc16": frame[-2:].hex(), **info})
        if (index + 1) % 100 == 0 or index + 1 == len(captures):
            print(f"Decoded and CRC-verified: {index + 1}/{len(captures)}", flush=True)
    if len(widths) != 1 or len(lengths) != 1:
        raise ValueError("Inconsistent fixed-length frames")
    half_width = int(next(iter(widths)))
    channels = max(k[0] for k in rows) + 1
    height = max(k[1] for k in rows) + 1
    expected = {(c, y, h) for c in range(channels)
                for y in range(height) for h in (0, 1)}
    if set(rows) != expected:
        raise ValueError("Missing image row halves")
    cube = np.empty((channels, height, 2 * half_width), dtype=np.uint8)
    for (channel, row, half), pixels in rows.items():
        cube[channel, row, half * half_width:(half + 1) * half_width] = np.frombuffer(pixels, dtype=np.uint8)
    np.save(out / "cube.npy", cube)
    (out / "packets.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Fixed frame length: {next(iter(lengths))} bytes")
    print(f"Reconstructed cube: {cube.shape}; no missing row halves")
    return cube


def save_gray(path: Path, array: np.ndarray, scale: int = 6) -> None:
    image = Image.fromarray(np.asarray(array, dtype=np.uint8))
    image.resize((image.width * scale, image.height * scale),
                 Image.Resampling.NEAREST).save(path)


def classify(cube: np.ndarray, out: Path) -> tuple[np.ndarray, list[dict]]:
    if cube.ndim != 3 or cube.dtype != np.uint8:
        raise ValueError("Expected an unsigned 8-bit band-major image cube")
    channels, height, width = (int(v) for v in cube.shape)
    x = cube.transpose(1, 2, 0).reshape(-1, channels).astype(np.float64)
    with threadpool_limits(limits=1):
        model = KMeans(n_clusters=7, n_init=20, random_state=0).fit(x)
    labels = model.labels_.reshape(height, width)
    np.save(out / "labels7.npy", labels)
    stats = []
    selected = []
    for label in range(7):
        ys, xs = np.nonzero(labels == label)
        if int(xs.size) == 0:
            raise ValueError("An empty class was produced")
        box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        area = int((box[2] - box[0] + 1) * (box[3] - box[1] + 1))
        # The planted spectral populations are confined to a small interior patch.
        # The other populations span almost the entire recovered scene.
        compact = area < (height * width) // 4
        if compact:
            selected.append(label)
        stats.append({"class": int(label), "pixels": int(xs.size),
                      "bounds_xyxy": box, "bounding_area": area,
                      "centroid": [float(v) for v in model.cluster_centers_[label]],
                      "compact": bool(compact)})
        print(f"Class {label}: {int(xs.size)} pixels, bounds={box}, compact={compact}")
        save_gray(out / f"class_{label}.png", np.uint8(labels == label) * 255)
    if not selected:
        raise ValueError("No compact spectral classes found")
    stencil = np.isin(labels, selected)
    print(f"Compact-class union: {int(stencil.sum())} pixels")
    (out / "clusters.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    np.save(out / "stamp_mask.npy", stencil)
    save_gray(out / "stamp_mask.png", np.where(stencil, 0, 255).astype(np.uint8))
    ys, xs = np.nonzero(stencil)
    y0 = max(0, int(ys.min()) - 2)
    y1 = min(height, int(ys.max()) + 3)
    x0 = max(0, int(xs.min()) - 3)
    x1 = min(width, int(xs.max()) + 4)
    save_gray(out / "stamp_crop.png", np.where(stencil[y0:y1, x0:x1], 0, 255).astype(np.uint8), 12)
    for channel in range(channels):
        save_gray(out / f"band_{channel}.png", cube[channel])
    return stencil, stats


def read_bitmap(stencil: np.ndarray) -> list[dict]:
    """Accept lettering only when its complete measured bitmap matches exactly.

    A plain bitmap-font rendering and a one-pixel horizontal dilation are tested.
    This method does not make OCR language guesses or edit observed pixels.
    """
    loader = getattr(ImageFont, "load_default_imagefont", None)
    if loader is None:
        raise RuntimeError("Update Pillow; load_default_imagefont() is required")
    font = loader()
    advance = int(font.getlength("A"))
    glyph_height = int(font.getbbox("A")[3])
    height, width = (int(v) for v in stencil.shape)
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-_{}"

    def render(text: str, left: int, dilation: int) -> np.ndarray:
        image = Image.new("1", (width, glyph_height), 0)
        ImageDraw.Draw(image).text((left, 0), text, font=font, fill=1)
        a = np.asarray(image, dtype=bool)
        if dilation == 1:
            shifted = np.zeros_like(a)
            shifted[:, 1:] = a[:, :-1]
            a = a | shifted
        return a

    def match_line(top: int, left: int, count: int, dilation: int) -> list[str]:
        if top < 0 or top + glyph_height > height or left < 0:
            return []
        end = left + advance * count + 1
        if end > width:
            return []
        observed = stencil[top:top + glyph_height]
        if bool(observed[:, :left].any()) or bool(observed[:, end:].any()):
            return []
        states = [""]
        for index in range(1, count + 1):
            next_states = []
            # Leave the final column undecided because the next glyph may touch it.
            stable_end = left + advance * index - 1
            for prefix in states:
                for character in alphabet:
                    text = prefix + character
                    a = render(text, left, dilation)
                    if np.array_equal(a[:, :stable_end], observed[:, :stable_end]):
                        next_states.append(text)
            states = next_states
            if not states:
                return []
        return [text for text in states
                if np.array_equal(render(text, left, dilation), observed)]

    occupied = np.flatnonzero(np.any(stencil, axis=1))
    groups = np.split(occupied, np.flatnonzero(np.diff(occupied) != 1) + 1)
    result = []
    for group in groups:
        first, last = int(group[0]), int(group[-1])
        xs = np.flatnonzero(np.any(stencil[first:last + 1], axis=0))
        hits = []
        for dilation in (0, 1):
            for top in range(first - 4, first + 1):
                for left in range(int(xs[0]) - 2, int(xs[0]) + 2):
                    count = int(math.ceil(float(int(xs[-1]) - left + 1) / float(advance)))
                    for text in match_line(top, left, count, dilation):
                        hits.append({"text": text, "left": int(left), "top": int(top),
                                     "horizontal_dilation": int(dilation), "mismatch_pixels": 0})
        if len(hits) != 1:
            raise RuntimeError(f"Expected one exact bitmap reading for rows {first}..{last}, got {hits}")
        result.append(hits[0])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("shed_sdr_0930.sigmf-data"))
    parser.add_argument("--meta", type=Path, default=Path("shed_sdr_0930.sigmf-meta"))
    parser.add_argument("--cube", type=Path, help="Reuse a previously CRC-verified image cube")
    parser.add_argument("--out", type=Path, default=Path("123_recovered"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.cube is not None:
        cube = np.load(args.cube, allow_pickle=False)
        print("Reusing cube:", args.cube)
    else:
        cube = decode_capture(args.data, args.meta, args.out)
    print("Cube SHA256:", hashlib.sha256(cube.tobytes()).hexdigest())
    stencil, stats = classify(cube, args.out)
    lines = read_bitmap(stencil)
    flag = "".join(str(line["text"]) for line in lines)
    if re.fullmatch(r"GAIANSPACE\{[A-Za-z0-9_-]+\}", flag) is None:
        raise ValueError(f"Exact bitmap result does not have flag syntax: {flag}")
    report = {"cube_shape": list(cube.shape),
              "cube_sha256": hashlib.sha256(cube.tobytes()).hexdigest(),
              "clustering": "KMeans, seven classes, raw unsigned channel values",
              "classes": stats, "mask_pixels": int(stencil.sum()),
              "bitmap_lines": lines, "flag": flag}
    (args.out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.out / "flag.txt").write_text(flag + "\n", encoding="ascii")
    print("Exact bitmap lines:", " / ".join(str(line["text"]) for line in lines))
    print("Bitmap mismatches: 0")
    print("FLAG:", flag)
    print("Saved analysis to", args.out.resolve())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
