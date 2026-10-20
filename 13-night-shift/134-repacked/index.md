---
render_with_liquid: false
---

# 134-repacked

| | |
|---|---|
| **Category** | 13 — Night Shift |
| **Points** | 150 |

## Description

03:02. GAIAN-723 is back on one frequency, but its telemetry no longer looks like telemetry.

The stranger has repacked the downlink. There are no commas and no text, just short binary frames that never repeat. Aroz has the last good CSV line from before the incident, and the satellite is sitting on the same bench-test attitude it had then. Same gravity, same room, same air.

The flight software team's old note says the satellite numbers its frames, *"so you can always tell what's missing."*

Somewhere in the repacked frames, GAIAN-723 is carrying something it was never designed to carry.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `vela_band_0302.sigmf-data` — the band recorder's raw capture (too large to attach: download it from [Hugging Face](https://huggingface.co/datasets/GaianSpace/ctf-2026-130/tree/main/134))
- `vela_band_0302.sigmf-meta` — the recorder's metadata for that capture
- `last_good_frame.csv` — the last telemetry line the MOC decoded before 01:12, with the old column names

## Hints

Two hints were released during the event:

1. **Same air, same room** — Nothing GAIAN-723 measures has changed since the last good line. Only the way it writes the numbers down has.
2. **A borrowed habit** — The stranger did not invent a new way to hide the frames. They reused something GAIAN-723 already does to every packet, and started it from a number each frame carries in plain sight.

## Solution

### Steps

Decode the short binary downlink frames, check PHY and application CRCs, use frame counters to restore order, and interpret telemetry with the last known good CSV baseline. Extract the hidden message from the repacked stream.

### Binary frame structure and whitening verification

The capture contains 12 validated short downlink frames. The per-frame payload is 48 bytes; the explicit LoRa packet header and **PHY CRC** must be accepted before interpreting application bytes. After the LoRa receive layer, the application frame is:

| Offset | Size | Field |
|---|---:|---|
| `0x00` | 2 | Clear marker `3A 72` |
| `0x02` | 2 | Little-endian frame counter |
| `0x04` | 42 | Whitened application body |
| `0x2E` | 2 | Application CRC-16, stored big-endian |

For every frame, the solver tests **all 256** possible LFSR whitening seed bytes. Each candidate dewhitens the 42-byte body and checks the application CRC-16/CCITT-FALSE computed over `marker || counter || recovered body` with initial value `0xFFFF`. Exactly one seed passes for each received frame, and the successful seed is verified to match the **low byte of the frame counter**. This relation is therefore *checked*, not assumed as an initial unknown.

Within each dewhitened body, bytes 30 and 31 carry the fragment index and total count; bytes 32–39 contain eight text bytes. The 12 accepted frames provide **three identical copies of each of four fragments**, which are ordered by fragment index instead of RF arrival order. The concatenation yields:

```text
GAIANSPACE{r3p4ck3d_660413}
```

The other dewhitened fields are interpreted as sensor engineering readings by comparing their scales against `last_good_frame.csv`; this is an inference from the capture, not evidence of the original on-orbit struct definition. All 12 LoRa PHY and all 12 application CRC checks succeeded.

### Reproduction

Results are saved under `134_solution/`.

```bash
python3 134.py vela_band_0302.sigmf-data --out-dir 134_solution
```

Expected relevant output:

```text
DETECTED: 12 RF bursts
seq=02 PHY=FAFB/FAFB APP=69C7/69C7 seed=02 part=2/4 'k3d_6604'
seq=03 PHY=4D82/4D82 APP=EE46/EE46 seed=03 part=3/4 '13}\x00\x00\x00\x00\x00'
seq=04 PHY=0823/0823 APP=4AE7/4AE7 seed=04 part=0/4 'GAIANSPA'
seq=05 PHY=BF5A/BF5A APP=147C/147C seed=05 part=1/4 'CE{r3p4c'
seq=06 PHY=FA67/FA67 APP=8580/8580 seed=06 part=2/4 'k3d_6604'
seq=07 PHY=4D1E/4D1E APP=F011/F011 seed=07 part=3/4 '13}\x00\x00\x00\x00\x00'
seq=08 PHY=931C/931C APP=3E6B/3E6B seed=08 part=0/4 'GAIANSPA'
seq=09 PHY=2465/2465 APP=607D/607D seed=09 part=1/4 'CE{r3p4c'
seq=10 PHY=6158/6158 APP=0124/0124 seed=0A part=2/4 'k3d_6604'
seq=11 PHY=D621/D621 APP=A5CB/A5CB seed=0B part=3/4 '13}\x00\x00\x00\x00\x00'
seq=12 PHY=9380/9380 APP=66F6/66F6 seed=0C part=0/4 'GAIANSPA'
seq=13 PHY=24F9/24F9 APP=7F89/7F89 seed=0D part=1/4 'CE{r3p4c'
PHY CRC: 12/12 valid
APPLICATION CRC: 12/12 valid
FRAGMENT COPIES: 0:3, 1:3, 2:3, 3:3
FLAG: GAIANSPACE{r3p4ck3d_660413}
OUTPUT: <output-directory>
```


### Solver Code

**`134.py`**

```python
#!/usr/bin/env python3
# Dependencies (Python >= 3.10):
#   python3 -m pip install numpy scipy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Recover GaianSpace 134 directly from its ci8 SigMF recording.

Dependencies: Python >= 3.10, NumPy, SciPy. GNU Radio is not required.
This is a capture-specific offline receiver, not a general LoRa receiver.
The measured downlink is 433.175 MHz, SF9/BW125 kHz, explicit header.
Only payloads passing both PHY CRC and the application CRC are assembled.
No flag bytes or predecoded payloads are embedded in this program.

The LoRa bit layout follows gr-lora_sdr (GPL-3.0):
https://github.com/tapparelj/gr-lora_sdr
The offline synchronization helpers are reused from solve_133_hopscotch_v1.py.
Application layout and counter-seeded whitening were inferred from this capture.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import json
import math
import re
import struct
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from scipy import fft, signal

HAMMING = np.asarray([0, 23, 45, 58, 78, 89, 99, 116,
                      139, 156, 166, 177, 197, 210, 232, 255], dtype=np.int64)
HAMMING_45 = np.asarray([0, 24, 40, 48, 72, 80, 96, 120,
                         136, 144, 160, 184, 192, 216, 232, 240], dtype=np.int64)


def whitening(length: int) -> list[int]:
    state = 255
    result: list[int] = []
    for _ in range(int(length)):
        result.append(int(state))
        feedback = ((state >> 7) ^ (state >> 5) ^ (state >> 4) ^ (state >> 3)) & 1
        state = ((state << 1) & 255) | int(feedback)
    return result


WHITENING = whitening(512)


def ref_chirp(sf: int) -> np.ndarray:
    n = np.arange(1 << int(sf), dtype=np.float64)
    return np.exp(1j * np.pi * (n * n / float(1 << int(sf)) - n))


def measure(x: np.ndarray, start: float, sf: int, oversample: int = 4,
            cfo_bins: float = 0.0, fft_multiplier: int = 1,
            downchirp: bool = False) -> tuple[float, float]:
    size = int(1 << int(sf))
    indices = int(round(float(start))) + np.arange(size, dtype=np.int64) * int(oversample)
    if int(indices[0]) < 0 or int(indices[-1]) >= int(x.size):
        return -1.0, 0.0
    reference = ref_chirp(int(sf))
    correction = np.exp(-2j * np.pi * float(cfo_bins) * np.arange(size, dtype=np.float64) / float(size))
    y = x[indices] * (reference if downchirp else np.conj(reference)) * correction
    spectrum = np.abs(fft.fft(y, n=int(size * int(fft_multiplier)))) ** 2
    peak = int(np.argmax(spectrum))
    energy = float(np.sum(np.abs(y) ** 2)) * float(size)
    return float(peak) / float(fft_multiplier), float(spectrum[peak]) / (energy + 1e-30)


def synchronize(x: np.ndarray, sf: int, oversample: int = 4) -> dict[str, Any]:
    size = int(1 << int(sf))
    stride = int(size * int(oversample))
    grid = np.arange(0, int(x.size) - stride, stride, dtype=np.int64)
    measurements = np.asarray([measure(x, float(p), sf, oversample) for p in grid], dtype=np.float64)
    candidate = None
    for i in range(int(grid.size) - 3):
        delta = (measurements[i:i + 4, 0] - measurements[i, 0] + float(size) / 2.0) % float(size) - float(size) / 2.0
        if float(np.min(measurements[i:i + 4, 1])) > 0.20 and float(np.max(np.abs(delta))) <= 1.0:
            candidate = int(i)
            break
    if candidate is None:
        raise RuntimeError('No run of reference upchirps was detected.')
    down_index = None
    for j in range(candidate + 4, min(candidate + 40, int(grid.size) - 1)):
        a = measure(x, float(grid[j]), sf, oversample, downchirp=True)
        b = measure(x, float(grid[j + 1]), sf, oversample, downchirp=True)
        if a[1] > 0.18 and b[1] > 0.35:
            down_index = int(j)
            break
    if down_index is None:
        raise RuntimeError('A downchirp pair was not detected after the preamble.')
    p, d = int(grid[candidate]), int(grid[down_index])
    up_bin = measure(x, float(p + stride), sf, oversample, fft_multiplier=64)[0]
    down_bin = measure(x, float(d + stride), sf, oversample, fft_multiplier=64, downchirp=True)[0]
    up_signed = (up_bin + float(size) / 2.0) % float(size) - float(size) / 2.0
    down_signed = (down_bin + float(size) / 2.0) % float(size) - float(size) / 2.0
    coarse_cfo = (up_signed + down_signed) / 2.0
    correlation = np.vdot(x[p:p + 3 * stride], x[p + stride:p + 4 * stride])
    fractional_cfo = float(np.angle(correlation)) / (2.0 * np.pi)
    cfo = float(round(coarse_cfo - fractional_cfo)) + fractional_cfo
    timing_chips = (up_signed - down_signed) / 2.0
    down_start = float(d) - timing_chips * float(oversample)
    data_start = int(round(down_start + 2.25 * float(stride)))
    netids = [int(round(measure(x, down_start - float(k * stride), sf, oversample, cfo)[0])) for k in (2, 1)]
    return dict(data_start=data_start, down_start=down_start, cfo_bins=cfo, netids=netids)


def decode_block(symbols: np.ndarray, sf_effective: int, cr: int) -> tuple[list[int], list[int]]:
    labels = np.asarray(symbols, dtype=np.int64)
    gray = labels ^ (labels >> 1)
    width = int(cr + 4)
    bits = np.zeros((int(sf_effective), width), dtype=np.int64)
    for i in range(width):
        for j in range(int(sf_effective)):
            bits[(i - j - 1) % int(sf_effective), i] = (int(gray[i]) >> (int(sf_effective) - 1 - j)) & 1
    codewords = bits.dot(1 << np.arange(width - 1, -1, -1, dtype=np.int64))
    lut = (HAMMING_45 if int(cr) == 1 else HAMMING) >> (8 - width)
    nibbles: list[int] = []
    distances: list[int] = []
    for codeword in codewords:
        distance = [int(int(codeword) ^ int(entry)).bit_count() for entry in lut]
        index = int(np.argmin(np.asarray(distance, dtype=np.int64)))
        nibbles.append(int(f'{index:04b}'[::-1], 2))
        distances.append(int(distance[index]))
    return nibbles, distances


def header_info(nibbles: list[int]) -> dict[str, Any]:
    a, b, c, d, e = [int(v) for v in nibbles[:5]]
    bit = lambda value, index: (int(value) >> int(index)) & 1
    parity = [
        bit(a, 3) ^ bit(a, 2) ^ bit(a, 1) ^ bit(a, 0),
        bit(a, 3) ^ bit(b, 3) ^ bit(b, 2) ^ bit(b, 1) ^ bit(c, 0),
        bit(a, 2) ^ bit(b, 3) ^ bit(b, 0) ^ bit(c, 3) ^ bit(c, 1),
        bit(a, 1) ^ bit(b, 2) ^ bit(b, 0) ^ bit(c, 2) ^ bit(c, 1) ^ bit(c, 0),
        bit(a, 0) ^ bit(b, 1) ^ bit(c, 3) ^ bit(c, 2) ^ bit(c, 1) ^ bit(c, 0),
    ]
    calculated = int(''.join(str(int(v)) for v in parity), 2)
    received = int(((d & 1) << 4) | e)
    return dict(length=int((a << 4) | b), cr=int(c >> 1), has_crc=bool(c & 1),
                checksum_valid=bool(calculated == received and (d & 14) == 0),
                checksum_calculated=calculated, checksum_received=received)


def decode_explicit(symbols: list[int], sf: int) -> dict[str, Any] | None:
    values = np.asarray(symbols, dtype=np.int64)
    if int(values.size) < 8:
        return None
    modulus = int(1 << int(sf))
    nibbles, errors = decode_block(((values[:8] - 1) % modulus) // 4, int(sf) - 2, 4)
    header = header_info(nibbles)
    if not header['checksum_valid'] or not 1 <= int(header['cr']) <= 4:
        return None
    cr, length = int(header['cr']), int(header['length'])
    symbol_count = int(8 + math.ceil(float(8 * length - 4 * int(sf) + 28 + 16) / float(4 * int(sf))) * (cr + 4))
    values = values[:symbol_count]
    payload_nibbles = list(nibbles[5:])
    for i in range(8, int(values.size) - (cr + 4) + 1, cr + 4):
        block = (values[i:i + cr + 4] - 1) % modulus
        decoded, distance = decode_block(block, int(sf), cr)
        payload_nibbles.extend(decoded)
        errors.extend(distance)
    raw_bytes = bytes(int(payload_nibbles[i] | (payload_nibbles[i + 1] << 4))
                      for i in range(0, len(payload_nibbles) - 1, 2))
    if len(raw_bytes) < length + 2 or not bool(header['has_crc']):
        return None
    decoded_bytes = bytes(int(v) ^ int(WHITENING[i]) if i < length else int(v)
                          for i, v in enumerate(raw_bytes))
    payload = decoded_bytes[:length]
    received_crc = int.from_bytes(decoded_bytes[length:length + 2], byteorder='little')
    calculated_crc = int(binascii.crc_hqx(payload[:-2], 0) ^ int(payload[-1]) ^ (int(payload[-2]) << 8))
    symbol_count = int(8 + math.ceil(float(8 * length - 4 * int(sf) + 28 + 16) / float(4 * int(sf))) * (cr + 4))
    return dict(header=header, payload=payload, payload_hex=payload.hex(),
                crc_valid=bool(received_crc == calculated_crc),
                crc_calculated=f'{calculated_crc:04X}', crc_received=f'{received_crc:04X}',
                data_symbol_count=symbol_count, codeword_bit_distance_sum=int(sum(errors)))


class Capture:
    def __init__(self, data: Path, meta: Path) -> None:
        self.data = data
        self.meta = json.loads(meta.read_text(encoding='utf-8'))
        if self.meta['global']['core:datatype'] != 'ci8':
            raise ValueError('Expected interleaved signed int8 I/Q (ci8).')
        if int(data.stat().st_size) % 2:
            raise ValueError('The IQ file has an incomplete sample.')
        self.fs = float(self.meta['global']['core:sample_rate'])
        self.center = float(self.meta['captures'][0]['core:frequency'])
        self.raw = np.memmap(data, dtype=np.int8, mode='r').reshape(-1, 2)

    def channel(self, start: float, stop: float, frequency: float, decimation: int) -> np.ndarray:
        first, last = int(round(start * self.fs)), int(round(stop * self.fs))
        if first < 0 or last > int(self.raw.shape[0]) or first >= last:
            raise ValueError(f'Capture does not contain interval {start}..{stop} s.')
        iq = np.asarray(self.raw[first:last], dtype=np.float32)
        samples = (iq[:, 0] + 1j * iq[:, 1]).astype(np.complex64)
        indices = np.arange(int(samples.size), dtype=np.float64) + float(first)
        shift = np.exp(-2j * np.pi * (float(frequency) - self.center) * indices / self.fs).astype(np.complex64)
        samples *= shift
        return signal.resample_poly(samples, 1, int(decimation)).astype(np.complex64)



def lfsr_bytes(seed: int, length: int) -> bytes:
    """Emit one state byte per step, using taps 7, 5, 4 and 3."""
    state = int(seed) & 0xFF
    result = bytearray()
    for _ in range(int(length)):
        result.append(int(state))
        feedback = ((state >> 7) ^ (state >> 5) ^ (state >> 4) ^ (state >> 3)) & 1
        state = int(((state << 1) & 0xFF) | feedback)
    return bytes(result)


def detect_bursts(capture: Capture) -> list[tuple[float, float]]:
    """Locate high-energy bursts using sparse 10 ms energy measurements."""
    duration = float(capture.raw.shape[0]) / float(capture.fs)
    tick = 0.01
    width = 4096
    times = np.arange(tick, duration - tick, tick, dtype=np.float64)
    starts = (times * float(capture.fs)).astype(np.int64)
    keep = starts + int(width) <= int(capture.raw.shape[0])
    times, starts = times[keep], starts[keep]
    if int(times.size) == 0:
        raise ValueError('The capture is too short for burst detection.')
    powers = np.empty(int(times.size), dtype=np.float64)
    offsets = np.arange(width, dtype=np.int64)
    for first in range(0, int(times.size), 256):
        rows = starts[first:first + 256, None] + offsets
        samples = np.asarray(capture.raw[rows], dtype=np.float32)
        powers[first:first + int(rows.shape[0])] = np.mean(
            samples[:, :, 0] ** 2 + samples[:, :, 1] ** 2, axis=1
        ).astype(np.float64)
    selected = np.flatnonzero(powers > float(np.median(powers)) * 2.0)
    groups = np.split(selected, np.flatnonzero(np.diff(selected) > 1) + 1)
    return [(float(times[g[0]]), float(times[g[-1]] + tick))
            for g in groups if int(g.size) >= 2]


def decode_burst(capture: Capture, interval: tuple[float, float]) -> dict[str, Any]:
    """Search residual timing phases and accept only a valid LoRa PHY CRC."""
    sf, oversample, stride = 9, 4, 2048
    duration = float(capture.raw.shape[0]) / float(capture.fs)
    first = max(0.0, float(interval[0]) - 0.12)
    last = min(duration, float(interval[1]) + 0.12)
    full = capture.channel(first, last, 433175000.0, 4)
    for crop in (0, 256, 512, 768, 1024, 1280, 1536, 1792):
        samples = full[int(crop):]
        try:
            sync = synchronize(samples, sf, oversample)
        except RuntimeError:
            continue
        for adjustment in (0, -1, 1, -2, 2, -3, 3, -4, 4):
            data_start = int(sync['data_start']) + int(adjustment)
            symbol_limit = min(75, (int(samples.size) - data_start) // stride)
            symbols = [int(round(measure(
                samples, float(data_start + k * stride), sf, oversample,
                float(sync['cfo_bins']))[0])) for k in range(symbol_limit)]
            decoded = decode_explicit(symbols, sf)
            if decoded is None or not bool(decoded['crc_valid']):
                continue
            corrected_netids = [int(round(measure(
                samples, float(data_start) - n * float(stride), sf, oversample,
                float(sync['cfo_bins']))[0])) for n in (4.25, 3.25)]
            decoded.update(
                capture_data_start_s=float(first + float(data_start + crop) / (capture.fs / 4.0)),
                capture_preamble_start_s=float(first + float(data_start + crop - 16.25 * stride) / (capture.fs / 4.0)),
                rf_energy_interval_s=[float(v) for v in interval],
                channel_center_hz=433175000, bandwidth_hz=125000, sf=sf,
                sample_rate_effective_hz=float(capture.fs / 4.0),
                preamble_upchirps=12, sync_symbols=corrected_netids,
                cfo_bins=float(sync['cfo_bins']), crop_samples=int(crop),
                timing_adjustment_samples=int(adjustment),
                symbols=[int(v) for v in symbols[:int(decoded['data_symbol_count'])]],
            )
            return decoded
    raise RuntimeError(f'No valid PHY CRC for burst {interval[0]:.3f}..{interval[1]:.3f} s.')


def engineering_fields(body: bytes) -> dict[str, Any]:
    """Interpret candidate field units by comparison with last_good_frame.csv."""
    signed = [int(v) for v in struct.unpack_from('<9h', body, 0)]
    values: dict[str, Any] = {}
    for names, raw, divisor in (
        (('accel_x_ms2', 'accel_y_ms2', 'accel_z_ms2'), signed[0:3], 1000.0),
        (('gyro_x_dps', 'gyro_y_dps', 'gyro_z_dps'), signed[3:6], 100.0),
        (('mag_x_gauss', 'mag_y_gauss', 'mag_z_gauss'), signed[6:9], 10000.0),
    ):
        values.update({str(name): float(value) / float(divisor) for name, value in zip(names, raw)})
    values.update(
        co2_ppm=int.from_bytes(body[18:20], 'little'),
        cabin_temp_c=float(int.from_bytes(body[20:22], 'little', signed=True)) / 100.0,
        cabin_rh_pct=float(int.from_bytes(body[22:24], 'little')) / 100.0,
        pressure_hpa=float(int.from_bytes(body[24:28], 'little')) / 100.0,
        bus_v=float(int.from_bytes(body[28:30], 'little')) / 1000.0,
        uptime_s_candidate=int.from_bytes(body[40:42], 'little'),
    )
    return values


def decode_application(payload: bytes) -> dict[str, Any]:
    """Infer the unique whitening seed by checking the clear application CRC."""
    if len(payload) != 48 or payload[:2] != bytes.fromhex('3a72'):
        raise ValueError('Unexpected binary frame size or marker.')
    counter = int.from_bytes(payload[2:4], byteorder='little')
    received = int.from_bytes(payload[46:48], byteorder='big')
    matches: list[tuple[int, bytes, int]] = []
    for seed in range(256):
        mask = lfsr_bytes(seed, 42)
        body = bytes(int(a) ^ int(b) for a, b in zip(payload[4:46], mask))
        calculated = int(binascii.crc_hqx(payload[:4] + body, 0xFFFF))
        if calculated == received:
            matches.append((int(seed), bytes(body), int(calculated)))
    if len(matches) != 1:
        raise ValueError(f'Frame {counter}: expected one valid whitening seed, found {len(matches)}.')
    seed, body, calculated = matches[0]
    if seed != (counter & 0xFF):
        raise ValueError(f'Frame {counter}: CRC-valid seed does not match the frame counter.')
    index, count = int(body[30]), int(body[31])
    if count == 0 or index >= count:
        raise ValueError('Invalid fragment index or fragment count.')
    fragment = bytes(body[32:40])
    fragment.decode('ascii', errors='strict')
    clear_frame = payload[:4] + body + payload[46:48]
    return dict(
        frame_counter=int(counter), whitening_seed=int(seed), seed_matches=[int(seed)],
        body_plain_hex=body.hex(), frame_plain_hex=clear_frame.hex(),
        application_crc_received=f'{received:04X}',
        application_crc_calculated=f'{calculated:04X}', application_crc_valid=True,
        fragment_index=index, fragment_count=count,
        fragment_hex=fragment.hex(), fragment_ascii=fragment.decode('ascii'),
        engineering_fields=engineering_fields(body),
    )


def assemble(packets: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Reorder by the embedded fragment index and require identical repetitions."""
    if not packets:
        raise ValueError('No packets were recovered.')
    counts = {int(p['application']['fragment_count']) for p in packets}
    if len(counts) != 1:
        raise ValueError('Inconsistent fragment counts.')
    count = int(next(iter(counts)))
    pieces: dict[int, bytes] = {}
    observed: dict[int, list[int]] = {}
    for packet in packets:
        app = packet['application']
        if not bool(packet['crc_valid']) or not bool(app['application_crc_valid']):
            raise ValueError('Refusing to assemble an unverified packet.')
        index = int(app['fragment_index'])
        fragment = bytes.fromhex(str(app['fragment_hex']))
        if index in pieces and pieces[index] != fragment:
            raise ValueError(f'Conflicting repetitions of fragment {index}.')
        pieces[index] = fragment
        observed.setdefault(index, []).append(int(app['frame_counter']))
    if sorted(pieces) != list(range(count)):
        raise ValueError(f'Missing fragments: expected 0..{count - 1}, found {sorted(pieces)}.')
    message = b''.join(pieces[i] for i in range(count)).rstrip(b'\x00')
    text = message.decode('ascii', errors='strict')
    if re.fullmatch(r'GAIANSPACE\{[^{}]+\}', text) is None:
        raise ValueError('The assembled data does not match the flag format.')
    fragments = [dict(index=int(i), fragment_hex=pieces[i].hex(),
                      fragment_ascii=pieces[i].decode('ascii'),
                      frame_counters=observed[i], copies=int(len(observed[i])))
                 for i in range(count)]
    return text, fragments


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return str(digest.hexdigest())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, help='vela_band_0302.sigmf-data')
    parser.add_argument('--meta', type=Path, help='Matching SigMF metadata; inferred by default.')
    parser.add_argument('--last-good', type=Path, help='Baseline CSV, for the comparison report.')
    parser.add_argument('--out-dir', type=Path, default=Path('134_solution'))
    args = parser.parse_args()
    metadata = args.meta if args.meta is not None else args.data.with_suffix('.sigmf-meta')
    capture = Capture(args.data, metadata)
    if abs(float(capture.fs / 4.0) - 500000.0) > 1.0:
        raise ValueError('This solver expects the supplied approximately 2 MS/s recording.')
    args.out_dir.mkdir(parents=True, exist_ok=True)
    bursts = detect_bursts(capture)
    if not bursts:
        raise RuntimeError('No bursts detected.')
    print(f'DETECTED: {len(bursts)} RF bursts', flush=True)
    recovered: list[dict[str, Any]] = []
    epoch = datetime.fromisoformat(str(capture.meta['captures'][0]['core:datetime']).replace('Z', '+00:00'))
    for index, interval in enumerate(bursts):
        packet = decode_burst(capture, interval)
        payload = bytes(packet.pop('payload'))
        packet['application'] = decode_application(payload)
        packet['burst_index'] = int(index)
        packet['capture_preamble_start_utc'] = (epoch + timedelta(seconds=float(packet['capture_preamble_start_s']))).isoformat()
        app = packet['application']
        recovered.append(packet)
        print(f"seq={app['frame_counter']:02d} PHY={packet['crc_received']}/{packet['crc_calculated']} "
              f"APP={app['application_crc_received']}/{app['application_crc_calculated']} "
              f"seed={app['whitening_seed']:02X} part={app['fragment_index']}/{app['fragment_count']} "
              f"{app['fragment_ascii']!r}", flush=True)
    flag, fragments = assemble(recovered)
    baseline_path = args.last_good if args.last_good is not None else args.data.parent / 'last_good_frame.csv'
    baseline = None
    if baseline_path.exists():
        with baseline_path.open(encoding='utf-8', newline='') as handle:
            baseline = next(csv.DictReader(handle), None)
    report = dict(
        capture=str(args.data.name), capture_sha256=file_sha256(args.data),
        metadata=capture.meta, decoded_packets=int(len(recovered)),
        all_phy_crc_valid=bool(all(p['crc_valid'] for p in recovered)),
        all_application_crc_valid=bool(all(p['application']['application_crc_valid'] for p in recovered)),
        all_seeds_unique=True, seed_rule_in_observed_frames='seed = frame_counter & 0xff',
        marker_hex='3a72', application_frame_length=48,
        whitening_range_inclusive=[4,45], unmasked_crc_range_inclusive=[46,47],
        application_crc=dict(polynomial_hex='1021', initial_hex='FFFF', xorout_hex='0000',
                             reflected=False, stored_byte_order='big',
                             coverage='clear bytes 0..45: header plus dewhitened body'),
        baseline_csv=baseline,
        field_interpretation_note='Sensor units and uptime are inferred from the supplied CSV and numeric behavior, not a supplied binary schema.',
        fragments=fragments, packets=recovered, flag=flag,
    )
    (args.out_dir / '134_verified_results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (args.out_dir / '134_radio_payloads.bin').write_bytes(b''.join(bytes.fromhex(str(p['payload_hex'])) for p in recovered))
    (args.out_dir / '134_plain_frames.bin').write_bytes(b''.join(bytes.fromhex(str(p['application']['frame_plain_hex'])) for p in recovered))
    (args.out_dir / '134_flag.txt').write_text(flag + '\n', encoding='ascii')
    rows = []
    for p in recovered:
        app = p['application']
        rows.append(dict(frame_counter=app['frame_counter'], capture_start_s=p['capture_preamble_start_s'],
                         **app['engineering_fields'], fragment_index=app['fragment_index'],
                         fragment_count=app['fragment_count'], fragment_hex=app['fragment_hex'],
                         application_crc=app['application_crc_received']))
    with (args.out_dir / '134_decoded_telemetry.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"PHY CRC: {len(recovered)}/{len(recovered)} valid", flush=True)
    print(f"APPLICATION CRC: {len(recovered)}/{len(recovered)} valid", flush=True)
    print('FRAGMENT COPIES:', ', '.join(f"{f['index']}:{f['copies']}" for f in fragments), flush=True)
    print('FLAG:', flag, flush=True)
    print('OUTPUT:', str(args.out_dir.resolve()), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, IndexError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
```
## Flag

```text
GAIANSPACE{r3p4ck3d_660413}
```
