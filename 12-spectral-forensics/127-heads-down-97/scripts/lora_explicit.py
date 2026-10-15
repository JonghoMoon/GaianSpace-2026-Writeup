#!/usr/bin/env python3
"""Recover the two AgriLink transmissions in GaianSpace CTF 122.

Usage:
    python3 122_v1.py
    python3 122_v1.py --data capture.sigmf-data --meta capture.sigmf-meta

Dependencies: numpy, Pillow

The demodulator is configured for the SF7/BW500k waveform observed in this
capture. It does not transmit, contact a server, or submit a flag.
The bit-pipeline arithmetic was checked against jkadbear/LoRaPHY (MIT):
https://github.com/jkadbear/LoRaPHY

The output includes every recovered packet, two separate channel sets,
the original NDVI, and an exact pixel-difference stencil of the erased stamp.
"""
from __future__ import annotations

import argparse
import binascii
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SF = 7
BW = 500_000.0
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
    n = int(nibble)
    if width == 5:
        return n | (parity(n, (1, 2, 3, 4)) << 4)
    result = n | (parity(n, (1, 2, 3)) << 4)
    result |= parity(n, (2, 3, 4)) << 5
    if width >= 7:
        result |= parity(n, (1, 2, 4)) << 6
    if width == 8:
        result |= parity(n, (1, 3, 4)) << 7
    return int(result)


HAMMING_TABLE = {
    width: tuple(hamming_encode(n, width) for n in range(16))
    for width in range(5, 9)
}


def hamming_decode(codewords: list[int], width: int) -> list[int]:
    if width <= 6:
        # CR4/5 cannot uniquely correct a single-bit error.
        # The final payload CRC is mandatory in this decoder.
        return [int(c) & 15 for c in codewords]
    result: list[int] = []
    for word in codewords:
        distances = [
            (int(word) ^ int(code)).bit_count()
            for code in HAMMING_TABLE[width]
        ]
        result.append(int(np.argmin(distances)))
    return result


def deinterleave(symbols: list[int], ppm: int) -> list[int]:
    codewords = [0] * int(ppm)
    for column, symbol in enumerate(symbols):
        for row in range(ppm):
            bit = (int(symbol) >> ((row - column) % ppm)) & 1
            codewords[row] |= int(bit) << int(column)
    return codewords


def parse_header(symbols: np.ndarray) -> tuple[int, int, int]:
    reduced = [int(s) // 4 for s in symbols[:8]]
    gray = [int(s) ^ (int(s) >> 1) for s in reduced]
    nibbles = hamming_decode(deinterleave(gray, SF - 2), 8)
    length = int(nibbles[0]) * 16 + int(nibbles[1])
    cr = int(nibbles[2]) >> 1
    crc_present = int(nibbles[2]) & 1
    bits = np.array([
        (int(nibble) >> bit) & 1
        for nibble in nibbles[:3] for bit in (3, 2, 1, 0)
    ], dtype=np.int64)
    stored = np.array(
        [int(nibbles[3]) & 1]
        + [(int(nibbles[4]) >> bit) & 1 for bit in (3, 2, 1, 0)],
        dtype=np.int64,
    )
    if cr not in (1, 2, 3, 4) or not np.array_equal(
        stored, (HEADER_CHECK @ bits) % 2
    ):
        raise ValueError(f"Invalid explicit header: {nibbles}")
    if crc_present != 1:
        raise ValueError("This script requires a payload CRC")
    return length, cr, crc_present


def whitening_bytes(length: int) -> bytes:
    state = 0xFF
    out = bytearray()
    for _ in range(length):
        out.append(int(state))
        feedback = ((state >> 7) ^ (state >> 5) ^ (state >> 4)
                    ^ (state >> 3)) & 1
        state = ((state << 1) | feedback) & 0xFF
    return bytes(out)


def payload_crc(data: bytes) -> int:
    if not data:
        return 0
    if len(data) == 1:
        return int(data[0])
    return int(binascii.crc_hqx(data[:-2], 0)) ^ int(data[-1]) ^ (int(data[-2]) << 8)


def decode_symbols(symbols: np.ndarray) -> tuple[bytes, int]:
    length, cr, crc_present = parse_header(symbols)
    count = 8 + (cr + 4) * int(math.ceil(float(2 * length + 4 * crc_present) / 7.0))
    if int(symbols.size) < count:
        raise ValueError("Truncated symbol sequence")
    nibbles: list[int] = []
    for start in range(8, count, cr + 4):
        reduced = [(int(s) - 1) % 128 for s in symbols[start:start + cr + 4]]
        gray = [s ^ (s >> 1) for s in reduced]
        nibbles.extend(hamming_decode(deinterleave(gray, SF), cr + 4))
    packed = bytes(
        int(nibbles[i]) | (int(nibbles[i + 1]) << 4)
        for i in range(0, len(nibbles) - 1, 2)
    )
    if len(packed) < length + 2:
        raise ValueError("Decoded packet is too short")
    payload = bytes(a ^ b for a, b in zip(packed[:length], whitening_bytes(length)))
    expected = int.from_bytes(packed[length:length + 2], "little")
    actual = payload_crc(payload)
    if actual != expected:
        raise ValueError(f"Payload CRC failed: computed={actual:04X}, stored={expected:04X}")
    return payload, actual


@dataclass
class Packet:
    index: int
    utc: str
    power: float
    cfo_hz: float
    drift_bins_per_symbol: float
    payload: bytes
    crc16: int


class Demodulator:
    def __init__(self, sample_rate: float) -> None:
        self.fs = float(sample_rate)
        self.os = int(round(self.fs / BW))
        self.n = (1 << SF) * self.os
        if self.os != 4:
            raise ValueError("Expected approximately four samples per chip")
        t = np.arange(self.n, dtype=np.float64)
        self.up = np.exp(1j * np.pi * (
            t * t / float(self.os * self.n) - t / float(self.os)
        ))

    def peaks(self, blocks: np.ndarray, reference: np.ndarray,
              padding: int = 8) -> tuple[np.ndarray, np.ndarray]:
        ft = np.abs(np.fft.fft(blocks * reference, n=self.n * padding, axis=-1))
        shape = ft.shape[:-1] + (self.os, (1 << SF) * padding)
        folded = ft.reshape(shape).sum(axis=-2)
        indexes = folded.argmax(axis=-1)
        peaks = indexes.astype(np.float64) / float(padding)
        quality = np.take_along_axis(folded, indexes[..., None], axis=-1)[..., 0]
        quality /= np.maximum(np.linalg.norm(folded, axis=-1), 1e-20)
        return peaks, quality

    def decode(self, iq: np.ndarray) -> tuple[bytes, int, float, float]:
        n = self.n
        power = np.abs(iq) ** 2
        window = 128
        local_power = np.convolve(power, np.ones(window, dtype=np.float64)
                                  / float(window), mode="valid")
        threshold = 0.4 * float(np.percentile(local_power, 70.0))
        active = np.flatnonzero(local_power > threshold)
        if int(active.size) == 0:
            raise ValueError("No preamble energy found")
        # Locate the ramp separately within each squelched capture.
        start = max(0, int(active[0]) + window // 2 - 20)
        data_start = start + int(round(12.25 * float(n)))
        count = min(256, (int(iq.size) - data_start) // n)
        if count < 8:
            raise ValueError("Capture too short for a header")
        preamble = iq[start + n:start + 7 * n].reshape(6, n)
        down = iq[start + 10 * n:start + 12 * n].reshape(2, n)
        pre, _ = self.peaks(preamble, np.conj(self.up))
        pre_bin = float(np.median(pre))
        blocks = iq[data_start:data_start + count * n].reshape(count, n)
        peaks, quality = self.peaks(blocks, np.conj(self.up))
        provisional = np.rint((peaks - pre_bin) % 128.0).astype(np.int64) % 128
        length, cr, crc_present = parse_header(provisional)
        needed = 8 + (cr + 4) * int(math.ceil(float(2 * length + 4 * crc_present) / 7.0))
        if needed > count:
            raise ValueError("Missing symbols at the end of this burst")

        # Fit fractional FFT-bin drift without imposing any payload bytes.
        # Integer symbol modulation disappears modulo one bin.
        relative = peaks[:needed] - pre_bin
        fractional = np.unwrap(2.0 * np.pi * (relative - np.rint(relative))) / (2.0 * np.pi)
        axis = np.arange(needed, dtype=np.float64)
        fit = np.polyfit(axis, fractional, 1)
        for _ in range(2):
            residual = fractional - np.polyval(fit, axis)
            good = (np.abs(residual) < 0.12) & (quality[:needed] > 0.18)
            if int(np.count_nonzero(good)) < 8:
                raise ValueError("Insufficient reliable symbols for timing-drift fit")
            fit = np.polyfit(axis[good], fractional[good], 1)
        symbols = np.rint(relative - np.polyval(fit, axis)).astype(np.int64) % 128
        payload, crc = decode_symbols(symbols)

        # An upchirp/downchirp pair separates timing displacement from CFO.
        pu, _ = self.peaks(preamble, np.conj(self.up), 16)
        pd, _ = self.peaks(down, self.up, 16)
        up_bin = float(np.median((pu + 64.0) % 128.0 - 64.0))
        down_bin = float(np.median((pd + 64.0) % 128.0 - 64.0))
        cfo = (up_bin + down_bin) * 0.5 * self.fs / float(n)
        return payload, crc, float(cfo), float(fit[0])


def save_gray(path: Path, array: np.ndarray, scale: int = 6) -> None:
    image = Image.fromarray(np.asarray(array, dtype=np.uint8))
    image.resize((image.width * scale, image.height * scale),
                 Image.Resampling.NEAREST).save(path)


def read_exact_bitmap(stencil: np.ndarray) -> list[str]:
    """Read the small bitmap lettering only if it matches a built-in font exactly.

    This is an optional final verification, not needed for the radio decoder.
    No final flag, token suffix, or text coordinates are embedded in the script.
    """
    loader = getattr(ImageFont, "load_default_imagefont", None)
    if loader is None:
        return []
    font = loader()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_{}: "

    def render(text: str) -> np.ndarray:
        image = Image.new("L", (6 * len(text), 11), 0)
        ImageDraw.Draw(image).text((0, 0), text, font=font, fill=1)
        return np.asarray(image).astype(bool)

    glyphs = {char: render(char) for char in alphabet}
    occupied = np.flatnonzero(np.any(stencil, axis=1))
    if int(occupied.size) == 0:
        return []
    groups = np.split(occupied, np.flatnonzero(np.diff(occupied) != 1) + 1)
    lines: list[str] = []
    for group in groups:
        first = int(group[0])
        last = int(group[-1])
        xs = np.flatnonzero(np.any(stencil[first:last + 1], axis=0))
        valid: set[str] = set()
        for top in (first - 2, first - 3):
            if top < 0 or top + 11 > int(stencil.shape[0]):
                continue
            for left_shift in range(3):
                left = int(xs[0]) - left_shift
                if left < 0:
                    continue
                count = int(math.ceil(float(int(xs[-1]) - left + 1) / 6.0))
                if left + 6 * count > int(stencil.shape[1]):
                    continue
                text = ""
                for index in range(count):
                    cell = stencil[top:top + 11, left + 6 * index:left + 6 * (index + 1)]
                    text += min(alphabet, key=lambda c: int(np.count_nonzero(cell != glyphs[c])))
                actual = stencil[top:top + 11, left:left + 6 * count]
                if np.array_equal(actual, render(text)):
                    valid.add(text.strip())
        if len(valid) != 1:
            return []
        lines.append(next(iter(valid)))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("coop_sdr_0655.sigmf-data"))
    parser.add_argument("--meta", type=Path, default=Path("coop_sdr_0655.sigmf-meta"))
    parser.add_argument("--out", type=Path, default=Path("122_out"))
    args = parser.parse_args()
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    if meta["global"]["core:datatype"] != "ci8":
        raise ValueError("Expected interleaved signed int8 I/Q samples")
    byte_count = int(args.data.stat().st_size)
    if byte_count % 2:
        raise ValueError("Odd byte count in ci8 recording")
    raw = np.memmap(args.data, dtype=np.int8, mode="r").reshape(-1, 2)
    captures = meta["captures"]
    starts = [int(c["core:sample_start"]) for c in captures] + [int(raw.shape[0])]
    if starts[0] != 0 or any(b <= a for a, b in zip(starts, starts[1:])):
        raise ValueError("Invalid or unordered capture boundaries")
    receiver = Demodulator(float(meta["global"]["core:sample_rate"]))
    packets: list[Packet] = []
    for index, capture in enumerate(captures):
        pairs = raw[starts[index]:starts[index + 1]].astype(np.float64)
        iq = pairs[:, 0] + 1j * pairs[:, 1]
        try:
            payload, crc, cfo, slope = receiver.decode(iq)
        except ValueError as exc:
            raise ValueError(f"Burst {index}: {exc}") from exc
        packets.append(Packet(index, str(capture["core:datetime"]),
                              float(np.mean(np.abs(iq) ** 2)), cfo, slope, payload, crc))
        if (index + 1) % 100 == 0 or index + 1 == len(captures):
            print(f"Decoded and CRC-verified: {index + 1}/{len(captures)}", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "packets.json").write_text(json.dumps([
        {"burst": p.index, "utc": p.utc, "power": p.power, "cfo_hz": p.cfo_hz,
         "drift_bins_per_symbol": p.drift_bins_per_symbol, "crc16": f"{p.crc16:04X}",
         "payload_hex": p.payload.hex()}
        for p in packets
    ], indent=2), encoding="utf-8")

    # The largest power gap separates two extremely distinct RF groups.
    powers = np.sort(np.array([p.power for p in packets], dtype=np.float64))
    split = int(np.argmax(np.diff(np.log(powers))))
    threshold = float(math.sqrt(float(powers[split] * powers[split + 1])))
    groups = [[p for p in packets if (p.power > threshold) == bool(g)] for g in (0, 1)]
    frames: list[dict[tuple[int, int], bytes]] = [{}, {}]
    metadata: list[dict[str, str]] = [{}, {}]
    end_counts: list[int | None] = [None, None]
    tile_ids: set[int] = set()
    for g, group in enumerate(groups):
        for packet in group:
            body = packet.payload
            if len(body) < 6 or body[:3] != b"AL\x03":
                raise ValueError(f"Unexpected AgriLink header in burst {packet.index}")
            tile_ids.add(int.from_bytes(body[3:5], "little"))
            kind = body[5:6]
            if kind == b"M":
                print("Metadata:", body[6:].decode("ascii"))
                metadata[g] = dict(token.split("=", 1) for token in body[6:].decode("ascii").split()
                                   if "=" in token)
            elif kind == b"E":
                end_counts[g] = int.from_bytes(body[6:], "little")
            elif kind == b"D":
                if len(body) != 136 or not 0 <= int(body[6]) < 5 or not 0 <= int(body[7]) < 128:
                    raise ValueError("Unexpected tile row dimensions")
                key = (int(body[6]), int(body[7]))
                if key in frames[g] and frames[g][key] != body[8:]:
                    raise ValueError(f"Conflicting same-source row: group={g}, row={key}")
                frames[g][key] = body[8:]
            else:
                raise ValueError(f"Unknown packet kind: {kind!r}")
        print(f"RF group {g}: packets={len(group)}, image rows={len(frames[g])}, "
              f"median CFO={float(np.median([p.cfo_hz for p in group])):.1f} Hz")
    if len(tile_ids) != 1:
        raise ValueError("This script expects a single tile identifier")
    full_groups = [g for g in (0, 1) if len(frames[g]) == 5 * 128
                   and metadata[g] and end_counts[g] == 640]
    if len(full_groups) != 1:
        raise ValueError("Expected exactly one complete, framed tile transmission")
    original_group = int(full_groups[0])
    original = np.zeros((5, 128, 128), dtype=np.uint8)
    for (channel, row), pixels in frames[original_group].items():
        original[channel, row, :] = np.frombuffer(pixels, dtype=np.uint8)
    latest = original.copy()
    for packet in packets:
        p = packet.payload
        if p[5:6] == b"D":
            latest[int(p[6]), int(p[7]), :] = np.frombuffer(p[8:], dtype=np.uint8)
    np.savez_compressed(args.out / "channels.npz", original=original, last_arrival=latest)
    for channel in range(5):
        save_gray(args.out / f"original_ch{channel}.png", original[channel])
        save_gray(args.out / f"last_arrival_ch{channel}.png", latest[channel])

    # The scene identifies ch0 as NIR and ch3 as red. Save both NIR hypotheses
    # so the inferred band assignment can be independently inspected.
    red = original[3].astype(np.float64)
    for nir_channel in (0, 2):
        nir = original[nir_channel].astype(np.float64)
        ndvi = np.divide(nir - red, nir + red, out=np.zeros_like(nir), where=(nir + red) != 0.0)
        np.save(args.out / f"ndvi_ch{nir_channel}.npy", ndvi)
        save_gray(args.out / f"ndvi_ch{nir_channel}.png",
                  np.rint(127.5 * (ndvi + 1.0)).astype(np.uint8))

    # Red-channel replacements identify exactly the pixels used to erase the
    # original lettering. This is a measured mask, not a newly drawn label.
    stencil = latest[3] != original[3]
    save_gray(args.out / "red_replacement_mask.png", np.where(stencil, 0, 255).astype(np.uint8))
    ys, xs = np.nonzero(stencil)
    if int(xs.size) == 0:
        raise ValueError("No red-channel replacement stencil was found")
    x0, x1 = max(0, int(xs.min()) - 2), min(128, int(xs.max()) + 3)
    y0, y1 = max(0, int(ys.min()) - 2), min(128, int(ys.max()) + 3)
    save_gray(args.out / "stamp.png", np.where(stencil[y0:y1, x0:x1], 0, 255).astype(np.uint8), 10)
    print(f"Red pixels replaced: {int(np.count_nonzero(stencil))}")
    lines = read_exact_bitmap(stencil)
    if lines:
        text = "".join(lines)
        if re.fullmatch(r"GAIANSPACE\{[A-Z0-9_\-]+\}", text):
            print("Exact bitmap-font match:", " / ".join(lines))
            print("FLAG:", text)
            (args.out / "flag.txt").write_text(text + "\n", encoding="ascii")
        else:
            print("Bitmap lines:", lines)
    else:
        print("Read the recovered stamp.png; automatic bitmap matching was not available.")
    print("Saved analysis to", args.out.resolve())


if __name__ == "__main__":
    main()
