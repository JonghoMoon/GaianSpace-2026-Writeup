---
render_with_liquid: false
---

# 135-what-they-took

| | |
|---|---|
| **Category** | 13 — Night Shift |
| **Points** | 175 |

## Description

03:48. The stranger's last command was different. GAIAN-723 answered with the longest transmission of the night, and then the stranger went quiet.

This is what they came for. GAIAN-723 dumped its memory to someone who isn't us, and the dump isn't in the clear. Whatever the stranger used to lock it, they set it up in a hurry, in the middle of the night, on a satellite that was never built for it.

The incident report needs one line: what GAIAN-723 gave away tonight.

Recover it.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `vela_band_0347.sigmf-data` — the band recorder's raw capture (too large to attach: download it from [Hugging Face](https://huggingface.co/datasets/GaianSpace/ctf-2026-130/tree/main/135))
- `vela_band_0347.sigmf-meta` — the recorder's metadata for that capture
- `chat.txt` — the last messages on Aroz's phone before the report

## Hints

Two hints were released during the event:

1. **Old habits** — The flight computer has written memory dumps the same way for years. The stranger only changed what happens after it is written.
2. **Small locks** — A lock made in a hurry does not have many keys.

## Solution

### Steps

Recover the long downlink, verify packet CRCs, reassemble dump fragments, and reverse the intruder's lightweight encryption using the known `G723MEM` dump prefix. The recovered memory plaintext contains `SECRET_STORE` and the flag.

### Known-plaintext state recovery over GF(2)

The capture includes an unauthorized `TC DUMP MEM` and four downlink `DMP` fragments, all accepted only after LoRa explicit-header and PHY CRC checks. The fragment counter/index fields reassemble **195 ciphertext bytes**. The header clue `G723MEM` provides **seven known plaintext bytes** (56 known keystream bits); the rest of the dump is unknown before decryption.

A byte-wise XOR stream cipher implies `K_i = C_i XOR P_i` for the known prefix. The inferred generator is xorshift32, advancing once before output and using the lowest eight state bits per byte:

```text
x ^= (x << 13) & 0xFFFFFFFF
x ^= x >> 17
x ^= (x << 5) & 0xFFFFFFFF
K_i = x & 0xFF
```

Xorshift is **linear over GF(2)**, so each observed keystream bit produces one linear equation in the 32 unknown bits of the first output state. The solver propagates 32 basis states through successive xorshift updates, constructs the binary coefficient matrix and uses GF(2) elimination. The 56 equations have **rank 32**, giving a unique state rather than a guessed seed. The code checks the minimum number of known bytes needed to reach full rank, withholds the remaining magic bytes for verification, and reverses one xorshift step to recover the initial seed.

```text
Known keystream:       6418AD5677D1C9
First output state:    0xF2143764
Seed before first step: 0x009A293A
GF(2) system:          56 equations, rank 32
```

The full keystream decrypts the memory dump, whose `SECRET_STORE` contains `GAIANSPACE{wh4t_th3y_t00k_064CCB}`. Re-encryption byte-for-byte reproduces the ciphertext. **This is a consistency check, not cryptographic authentication:** no separate MAC over the plaintext was found. The xorshift model and use of the low output byte are inferred and cross-checked against the dump, not obtained from source code for the sender.

### Reproduction

Results are saved under `135_solution/`, including plaintext, flag and verification JSON.

```bash
python3 135.py vela_band_0347.sigmf-data --out-dir 135_solution
```

Expected relevant output:

```text
CAPTURE: vela_band_0347.sigmf-data, 50.000000 s
DETECTED: 13 energy intervals
00 DL SF9 CR4/5 LEN=165 CRC=B324/B324 valid=True b'1609459220,-0.02,0.08,9.80,2.75,1.94,0.16,-0.62,-0.17,-0.47,0.46,0.12,164.86,427,24.95,47.19,996.20,28.19,38.00,380,35,0.000000,0.000000,0,0,0.00,0.00,4.63,0.00,0.00'
01 UL SF7 CR4/8 LEN=13 CRC=DD75/DD75 valid=True b'}*\x00\x00TC GET HK'
02 DL SF9 CR4/5 LEN=62 CRC=A8BB/A8BB valid=True b'TM,ACK,0,GET HK,HK,V=4.61,I=0.0,T=24.95,P=996.20,CO2=427,UP=10'
03 DL SF9 CR4/5 LEN=165 CRC=B997/B997 valid=True b'1609459233,-0.01,0.07,9.79,2.76,1.97,0.18,-0.63,-0.16,-0.48,0.42,0.04,165.73,444,24.48,48.41,996.22,28.29,36.00,380,35,0.000000,0.000000,0,0,0.00,0.00,4.53,0.10,0.00'
04 UL SF7 CR4/8 LEN=15 CRC=C86A/C86A valid=True b'}*\x01\x00TC DUMP MEM'
05 DL SF9 CR4/5 LEN=70 CRC=20C6/20C6 valid=True b"DMP\x01\x00\x04#/\x9fe:\x94\x84o\xa0\xe9\xc9\x1e\x14\xa2'\xbc\x98'\xc3\xd8[\x1f\xe4Y\x7f\x15R\xe2/q\x99<\xdfx\xd9\xe2\xe7\x94\xf3\n\xcd\x98\xcc\x1b;\x8e\xc1\x04\xea}\xb0\x1cG*\x08'\xa8\xdc\x14\xfcu\x99\xde\x11"
06 DL SF9 CR4/5 LEN=70 CRC=C2BE/C2BE valid=True b'DMP\x01\x01\x04\xfe\xac\x9dJ9sO\x87\xd3"\xd7\n\x0fD\x97S\x8d"<\x89\x07\xa7\xbd\x14\x95X\x9d\xad.\xe4=VQ\xa6Z\xd4\x8d\xb6\x18\x98hvO\x0c\xe3(i\x0fmV\xd9\x91\xd9\x80n\xd2 +\xbc#\xd5N\xa5\x04'
07 DL SF9 CR4/5 LEN=70 CRC=5E79/5E79 valid=True b'DMP\x01\x02\x04%"\\\x06\x97\xa2\xe35\xda\xef\xedL\xa4\xcb\x86\xc3\xb7\xd7NwW\x9e\x08\xad\x12\x80\x8a8R)\xa2`c\'\xfe\x98\x15\xd3\xec\x90\'\xf3\x7f%_\x80\x13\xce,\xff9\xc1\xd0f\xd7P\xa2\x1f\xa1\x8e\x88#"\xde'
08 DL SF9 CR4/5 LEN=9 CRC=7711/7711 valid=True b'DMP\x01\x03\x04A\xe1\x9f'
09 DL SF9 CR4/5 LEN=165 CRC=AE6F/AE6F valid=True b'1609459256,-0.01,0.07,9.80,2.69,1.88,0.22,-0.62,-0.17,-0.46,0.44,0.07,164.77,441,23.54,50.90,996.22,28.42,35.00,404,40,0.000000,0.000000,0,0,0.00,0.00,4.62,0.10,0.00'
10 UL SF7 CR4/8 LEN=11 CRC=09B8/09B8 valid=True b'}*\x02\x00TC PING'
11 DL SF9 CR4/5 LEN=21 CRC=CBCF/CBCF valid=True b'TM,ACK,2,PING,PONG,46'
12 DL 49.86..49.99 s: incomplete_at_capture_end
DMP FRAGMENTS: 4/4, 195 ciphertext bytes
KNOWN KEYSTREAM: 6418AD5677D1C9
GF2: 56 equations, rank 32, unique=True
FIRST OUTPUT STATE: 0xF2143764
SEED BEFORE FIRST STEP: 0x009A293A
HELD-OUT MAGIC: 2 bytes valid=True
DUMP PHY CRC: 4/4 valid
REENCRYPTION: identical=True
PLAINTEXT: G723MEM1|BANK2|0x4000-0x40FF|OBC_LOG:BOOT OK;SENS OK;DL CFG B;FHSS ON;REPACK ON;SECRET_STORE:GAIANSPACE{wh4t_th3y_t00k_064CCB};TLE_CACHE:1 72301U 26001A 26284.08 .00001 00000-0 12345-4 0 9990;END
FLAG: GAIANSPACE{wh4t_th3y_t00k_064CCB}
OUTPUT: <output-directory>
```


### Solver Code

**`135.py`**

```python
#!/usr/bin/env python3
# Dependencies (Python >= 3.10):
#   python3 -m pip install numpy scipy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Recover GaianSpace 135 directly from its ci8 SigMF recording.

Requires Python >= 3.10, NumPy and SciPy. GNU Radio is not required.
This is a capture-specific offline solver, not a general-purpose LoRa receiver.
The capture uses a 433.175 MHz SF9/BW125 downlink and a 433.925 MHz
SF7/BW250 uplink. Packet boundaries are detected from the raw recording.

Pipeline:
  channel selection -> LoRa synchronization -> explicit header and PHY CRC
  -> DMP fragment ordering -> xorshift32 state recovery from G723MEM
  -> memory plaintext and flag extraction.

No recovered key, ciphertext, plaintext or flag is embedded in this program.
The seven-byte dump magic is the known-plaintext clue supplied with the task.
The LoRa helpers are reused from solve_134_repacked_v1.py and follow the
GPL-3.0 gr-lora_sdr bit layout: https://github.com/tapparelj/gr-lora_sdr
The xorshift state recovery below solves binary linear equations directly.
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


MASK32 = int(0xFFFFFFFF)
KNOWN_MAGIC = b'G723MEM'


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return str(digest.hexdigest())


def detect_bursts(capture: Capture) -> list[tuple[float, float]]:
    """Detect separated bursts with sparse 10 ms raw-energy measurements."""
    duration = float(capture.raw.shape[0]) / float(capture.fs)
    tick, width = 0.01, 4096
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
        raw = np.asarray(capture.raw[rows], dtype=np.float32)
        powers[first:first + int(rows.shape[0])] = np.mean(
            raw[:, :, 0] ** 2 + raw[:, :, 1] ** 2, axis=1
        ).astype(np.float64)
    selected = np.flatnonzero(powers > float(np.median(powers)) * 2.0)
    groups = np.split(selected, np.flatnonzero(np.diff(selected) > 1) + 1)
    return [(float(times[g[0]]), float(times[g[-1]] + tick))
            for g in groups if int(g.size) >= 2]


def classify_channel(capture: Capture, interval: tuple[float, float]) -> dict[str, Any]:
    """Compare spectral energy, not packet duration, to choose the receive band."""
    a, b = [float(v) for v in interval]
    width = 16384
    center_index = int(round(((a + b) / 2.0) * float(capture.fs)))
    first = max(0, min(center_index - width // 2, int(capture.raw.shape[0]) - width))
    raw = np.asarray(capture.raw[first:first + width], dtype=np.float32)
    x = (raw[:, 0] + 1j * raw[:, 1]).astype(np.complex64)
    power = np.abs(fft.fft(x)) ** 2
    frequencies = fft.fftfreq(int(x.size), 1.0 / float(capture.fs)) + float(capture.center)
    down_power = float(np.sum(power[np.abs(frequencies - 433175000.0) < 85000.0]))
    up_power = float(np.sum(power[np.abs(frequencies - 433925000.0) < 150000.0]))
    uplink = bool(up_power > down_power)
    return dict(direction='uplink' if uplink else 'downlink',
                center_hz=433925000 if uplink else 433175000,
                bandwidth_hz=250000 if uplink else 125000,
                sf=7 if uplink else 9, decimation=2 if uplink else 4,
                uplink_energy=float(up_power), downlink_energy=float(down_power))


def decode_packet(capture: Capture, interval: tuple[float, float],
                  channel: dict[str, Any]) -> dict[str, Any]:
    """Accept a packet only after its explicit header and payload CRC validate."""
    sf, decimation = int(channel['sf']), int(channel['decimation'])
    oversample, stride = 4, int((1 << sf) * 4)
    duration = float(capture.raw.shape[0]) / float(capture.fs)
    first = max(0.0, float(interval[0]) - 0.10)
    last = min(duration, float(interval[1]) + 0.10)
    full = capture.channel(first, last, float(channel['center_hz']), decimation)
    saw_header = None
    insufficient = False
    for crop in range(0, stride, stride // 8):
        samples = full[int(crop):]
        try:
            sync = synchronize(samples, sf, oversample)
        except RuntimeError:
            continue
        for adjustment in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6):
            start = int(sync['data_start']) + int(adjustment)
            symbols = [int(round(measure(
                samples, float(start + k * stride), sf, oversample,
                float(sync['cfo_bins']))[0])) for k in range(8)]
            head_nibbles, _ = decode_block(
                ((np.asarray(symbols, dtype=np.int64) - 1) % (1 << sf)) // 4,
                sf - 2, 4)
            header = header_info(head_nibbles)
            if (not bool(header['checksum_valid']) or
                    not 1 <= int(header['cr']) <= 4 or not bool(header['has_crc'])):
                continue
            saw_header = dict(header)
            count = int(8 + math.ceil(float(8 * int(header['length']) - 4 * sf + 44)
                                      / float(4 * sf)) * (int(header['cr']) + 4))
            if start + count * stride > int(samples.size):
                insufficient = True
                continue
            symbols.extend(int(round(measure(
                samples, float(start + k * stride), sf, oversample,
                float(sync['cfo_bins']))[0])) for k in range(8, count))
            decoded = decode_explicit(symbols, sf)
            if decoded is None or not bool(decoded['crc_valid']):
                continue
            payload = bytes(decoded.pop('payload'))
            data_time = float(first + float(crop + start) / (capture.fs / float(decimation)))
            epoch = datetime.fromisoformat(str(capture.meta['captures'][0]['core:datetime']).replace('Z', '+00:00'))
            netids = [int(round(measure(
                samples, float(start) - n * float(stride), sf, oversample,
                float(sync['cfo_bins']))[0])) for n in (4.25, 3.25)]
            decoded.update(
                direction=str(channel['direction']), channel_center_hz=int(channel['center_hz']),
                bandwidth_hz=int(channel['bandwidth_hz']), sf=sf,
                sample_rate_effective_hz=float(capture.fs / float(decimation)),
                rf_energy_interval_s=[float(v) for v in interval],
                data_start_s=data_time,
                data_start_utc=(epoch + timedelta(seconds=data_time)).isoformat(),
                sync_symbols=netids, cfo_bins=float(sync['cfo_bins']),
                crop_samples=int(crop), timing_adjustment_samples=int(adjustment),
                payload_ascii=payload.decode('ascii', errors='backslashreplace'),
                symbols=[int(v) for v in symbols], status='verified')
            return decoded
    return dict(status='incomplete_at_capture_end' if insufficient and last >= duration else 'not_decoded',
                direction=str(channel['direction']), sf=sf,
                rf_energy_interval_s=[float(v) for v in interval],
                valid_header_observed=saw_header,
                note='No payload from this burst is used in reconstruction.')


def assemble_dump(packets: list[dict[str, Any]]) -> tuple[bytes, dict[str, Any]]:
    """Use all indexed DMP fragments of one CRC-verified transfer."""
    groups: dict[tuple[int, int], dict[int, bytes]] = {}
    records: dict[tuple[int, int], list[dict[str, Any]]] = {}
    requests: list[dict[str, Any]] = []
    for packet in packets:
        if packet.get('status') != 'verified' or not bool(packet.get('crc_valid', False)):
            continue
        payload = bytes.fromhex(str(packet['payload_hex']))
        if packet['direction'] == 'uplink' and payload[4:] == b'TC DUMP MEM':
            requests.append(dict(request_id=int.from_bytes(payload[2:4], 'little'),
                                 payload_hex=payload.hex(), data_start_s=float(packet['data_start_s']),
                                 crc_received=str(packet['crc_received']), crc_calculated=str(packet['crc_calculated'])))
        if len(payload) < 7 or payload[:3] != b'DMP':
            continue
        transfer, index, count = int(payload[3]), int(payload[4]), int(payload[5])
        if count == 0 or index >= count:
            raise ValueError('A DMP packet contains an invalid index/count pair.')
        key = (transfer, count)
        fragments = groups.setdefault(key, {})
        body = bytes(payload[6:])
        if index in fragments and fragments[index] != body:
            raise ValueError(f'DMP {transfer}/{index}: conflicting duplicates.')
        fragments[index] = body
        records.setdefault(key, []).append(dict(index=index, count=count, transfer_id=transfer,
            fragment_length=len(body), fragment_hex=body.hex(), header_hex=payload[:6].hex(),
            payload_length=len(payload), phy_crc_received=str(packet['crc_received']),
            phy_crc_calculated=str(packet['crc_calculated']), phy_crc_valid=True,
            data_start_s=float(packet['data_start_s']), data_start_utc=str(packet['data_start_utc'])))
    complete = [key for key, fragments in groups.items() if sorted(fragments) == list(range(key[1]))]
    if len(complete) != 1:
        raise ValueError(f'Expected one complete dump, found {len(complete)}.')
    key = complete[0]
    matching_requests = [r for r in requests if int(r['request_id']) == int(key[0])]
    if len(matching_requests) != 1:
        raise ValueError('The reconstructed dump has no unique matching DUMP MEM request.')
    ordered = sorted(records[key], key=lambda record: int(record['index']))
    ciphertext = b''.join(groups[key][i] for i in range(int(key[1])))
    return ciphertext, dict(transfer_id=int(key[0]), fragment_count=int(key[1]),
                            ciphertext_length=int(len(ciphertext)), request=matching_requests[0],
                            fragments=ordered,
                            interpretation_note='DMP header fields are inferred from the observed index/count pattern and matching request ID.')


def xorshift32(state: int) -> int:
    """Perform the 32-bit left-13, right-17, left-5 state transition."""
    value = int(state) & MASK32
    value ^= (value << 13) & MASK32
    value ^= value >> 17
    value ^= (value << 5) & MASK32
    return int(value & MASK32)


def solve_binary_system(rows: list[tuple[int, int]]) -> tuple[int | None, int]:
    """Solve coefficient-mask equations over GF(2); report inconsistencies."""
    pivots: dict[int, tuple[int, int]] = {}
    for coefficient, right_hand_side in rows:
        coefficient, right_hand_side = int(coefficient), int(right_hand_side) & 1
        while coefficient != 0:
            pivot = int(coefficient.bit_length() - 1)
            if pivot in pivots:
                old_coefficient, old_rhs = pivots[pivot]
                coefficient ^= int(old_coefficient)
                right_hand_side ^= int(old_rhs)
            else:
                pivots[pivot] = (int(coefficient), int(right_hand_side))
                break
        if coefficient == 0 and right_hand_side != 0:
            return None, int(len(pivots))
    solution = 0
    for pivot, (coefficient, rhs) in sorted(pivots.items()):
        if int((coefficient & solution).bit_count() & 1) != int(rhs):
            solution |= 1 << int(pivot)
    for coefficient, rhs in rows:
        if int((int(coefficient) & solution).bit_count() & 1) != int(rhs):
            raise RuntimeError('The binary solver failed its own equation check.')
    return int(solution), int(len(pivots))


def state_from_low_bytes(observed: bytes, byte_shift: int = 0) -> tuple[int | None, int]:
    """Form output-bit equations using all 32 basis states, then eliminate."""
    basis = [int(1 << i) for i in range(32)]
    rows: list[tuple[int, int]] = []
    for byte in observed:
        for bit in range(8):
            coefficient = 0
            for i, state in enumerate(basis):
                coefficient |= int((int(state) >> (int(byte_shift) + bit)) & 1) << i
            rows.append((int(coefficient), int((int(byte) >> bit) & 1)))
        basis = [int(xorshift32(state)) for state in basis]
    return solve_binary_system(rows)


def undo_left_xor(value: int, shift: int) -> int:
    result, amount = int(value) & MASK32, int(shift)
    while amount < 32:
        result ^= (result << amount) & MASK32
        amount *= 2
    return int(result & MASK32)


def undo_right_xor(value: int, shift: int) -> int:
    result, amount = int(value) & MASK32, int(shift)
    while amount < 32:
        result ^= result >> amount
        amount *= 2
    return int(result & MASK32)


def inverse_xorshift32(state: int) -> int:
    return int(undo_left_xor(undo_right_xor(undo_left_xor(int(state), 5), 17), 13))


def apply_keystream(data: bytes, seed: int) -> bytes:
    """Advance once per byte and XOR the state's low byte with the input."""
    state = int(seed) & MASK32
    output = bytearray()
    for byte in data:
        state = int(xorshift32(state))
        output.append(int(byte) ^ int(state & 0xFF))
    return bytes(output)


def recover_plaintext(ciphertext: bytes) -> tuple[bytes, dict[str, Any], str]:
    if len(ciphertext) < len(KNOWN_MAGIC):
        raise ValueError('The reconstructed ciphertext is too short for the known magic.')
    known_stream = bytes(int(a) ^ int(b) for a, b in zip(ciphertext, KNOWN_MAGIC))
    tested: list[dict[str, Any]] = []
    for byte_shift in (0, 8, 16, 24):
        candidate, rank = state_from_low_bytes(known_stream, byte_shift)
        tested.append(dict(output_byte_shift=int(byte_shift), consistent=candidate is not None,
                           rank=int(rank), first_output_state=None if candidate is None else f'{candidate:08X}'))
    state, rank = state_from_low_bytes(known_stream, 0)
    if state is None or rank != 32:
        raise ValueError('The known prefix did not determine one xorshift32 low-byte state.')
    seed = int(inverse_xorshift32(state))
    if xorshift32(seed) != state:
        raise RuntimeError('The recovered predecessor state failed forward verification.')
    rank_tests = []
    for length in range(1, len(known_stream) + 1):
        candidate, subrank = state_from_low_bytes(known_stream[:length], 0)
        rank_tests.append(dict(known_bytes=int(length), rank=int(subrank),
                               consistent=candidate is not None,
                               same_unique_state=bool(subrank == 32 and candidate == state)))
    minimal = min(int(r['known_bytes']) for r in rank_tests if bool(r['same_unique_state']))
    partial_state, partial_rank = state_from_low_bytes(known_stream[:minimal], 0)
    if partial_state != state or partial_rank != 32:
        raise RuntimeError('Independent prefix-state recovery failed.')
    plaintext = apply_keystream(ciphertext, seed)
    keystream = apply_keystream(bytes(len(KNOWN_MAGIC)), seed)
    if keystream != known_stream or not plaintext.startswith(KNOWN_MAGIC):
        raise ValueError('The recovered state does not reproduce the full known magic.')
    if apply_keystream(plaintext, seed) != ciphertext:
        raise RuntimeError('Re-encryption does not reproduce the assembled ciphertext.')
    text = plaintext.decode('ascii', errors='strict')
    matches = re.findall(r'GAIANSPACE\{[^{}\r\n]+\}', text)
    if len(matches) != 1 or not text.endswith(';END'):
        raise ValueError('The decoded dump does not contain one flag and a complete END marker.')
    scope = re.search(r'\|(?P<bank>BANK\d+)\|(?P<address>0x[0-9A-Fa-f]+-0x[0-9A-Fa-f]+)\|', text)
    info = dict(
        model='xorshift32(13,17,5), step before output, low 8 bits, XOR stream',
        model_note='This model is inferred from the capture and validated by the known prefix and coherent full plaintext; transmitter source was not provided.',
        state_bits=32, known_plaintext_ascii=KNOWN_MAGIC.decode('ascii'),
        known_ciphertext_hex=ciphertext[:len(KNOWN_MAGIC)].hex(),
        known_keystream_hex=known_stream.hex(), equation_count=8 * len(KNOWN_MAGIC),
        equation_rank=int(rank), state_solution_unique=True,
        first_output_state_hex=f'{state:08X}', seed_before_first_step_hex=f'{seed:08X}',
        first_transition_verified=True, output_byte_hypotheses=tested, prefix_rank_tests=rank_tests,
        state_recovery_bytes=int(minimal), held_out_magic_bytes=int(len(KNOWN_MAGIC) - minimal),
        held_out_magic_verified=True, continuous_state_across_fragments=True,
        plaintext_length=int(len(plaintext)), reencrypted_ciphertext_identical=True,
        plaintext_ascii=text, plaintext_sha256=hashlib.sha256(plaintext).hexdigest(),
        ciphertext_sha256=hashlib.sha256(ciphertext).hexdigest(),
        declared_memory_scope=None if scope is None else scope.groupdict(),
        integrity_note='LoRa PHY CRCs validate each received ciphertext fragment. No separate plaintext MAC or checksum was identified; re-encryption is a consistency check, not authentication.')
    return plaintext, info, str(matches[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, help='vela_band_0347.sigmf-data')
    parser.add_argument('--meta', type=Path, help='SigMF metadata; inferred from the data filename by default.')
    parser.add_argument('--out-dir', type=Path, default=Path('135_solution'))
    args = parser.parse_args()
    meta = args.meta if args.meta is not None else args.data.with_suffix('.sigmf-meta')
    capture = Capture(args.data, meta)
    if abs(float(capture.fs / 4.0) - 500000.0) > 1.0:
        raise ValueError('Expected the supplied approximately 2 MS/s capture.')
    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload_dir = args.out_dir / 'radio_payloads'
    payload_dir.mkdir(parents=True, exist_ok=True)
    bursts = detect_bursts(capture)
    if not bursts:
        raise RuntimeError('No RF bursts were detected.')
    duration = float(capture.raw.shape[0]) / float(capture.fs)
    print(f'CAPTURE: {args.data.name}, {duration:.6f} s', flush=True)
    print(f'DETECTED: {len(bursts)} energy intervals', flush=True)
    packets = []
    for i, interval in enumerate(bursts):
        channel = classify_channel(capture, interval)
        packet = decode_packet(capture, interval, channel)
        packet['burst_index'] = int(i)
        packets.append(packet)
        label = 'UL' if str(channel['direction']) == 'uplink' else 'DL'
        if packet['status'] != 'verified':
            print(f'{i:02d} {label} {interval[0]:.2f}..{interval[1]:.2f} s: {packet["status"]}', flush=True)
            continue
        payload = bytes.fromhex(str(packet['payload_hex']))
        (payload_dir / f'{i:02d}_{label.lower()}.bin').write_bytes(payload)
        print(f'{i:02d} {label} SF{packet["sf"]} CR4/{int(packet["header"]["cr"]) + 4} '
              f'LEN={len(payload)} CRC={packet["crc_received"]}/{packet["crc_calculated"]} valid=True '
              f'{payload!r}', flush=True)
    ciphertext, dump = assemble_dump(packets)
    plaintext, cryptanalysis, flag = recover_plaintext(ciphertext)
    complete_count = sum(int(p.get('status') == 'verified') for p in packets)
    print(f'DMP FRAGMENTS: {dump["fragment_count"]}/{dump["fragment_count"]}, {len(ciphertext)} ciphertext bytes', flush=True)
    print(f'KNOWN KEYSTREAM: {cryptanalysis["known_keystream_hex"].upper()}', flush=True)
    print(f'GF2: {cryptanalysis["equation_count"]} equations, rank {cryptanalysis["equation_rank"]}, unique=True', flush=True)
    print(f'FIRST OUTPUT STATE: 0x{cryptanalysis["first_output_state_hex"]}', flush=True)
    print(f'SEED BEFORE FIRST STEP: 0x{cryptanalysis["seed_before_first_step_hex"]}', flush=True)
    print(f'HELD-OUT MAGIC: {cryptanalysis["held_out_magic_bytes"]} bytes valid=True', flush=True)
    print(f'DUMP PHY CRC: {dump["fragment_count"]}/{dump["fragment_count"]} valid', flush=True)
    print('REENCRYPTION: identical=True', flush=True)
    print('PLAINTEXT:', plaintext.decode('ascii'), flush=True)
    print('FLAG:', flag, flush=True)
    (args.out_dir / '135_dump_ciphertext.bin').write_bytes(ciphertext)
    (args.out_dir / '135_dump_plaintext.bin').write_bytes(plaintext)
    (args.out_dir / '135_dump_plaintext.txt').write_text(plaintext.decode('ascii') + '\n', encoding='ascii')
    (args.out_dir / '135_flag.txt').write_text(flag + '\n', encoding='ascii')
    report = dict(capture=args.data.name, capture_sha256=file_sha256(args.data), metadata=capture.meta,
                  capture_duration_s=duration, energy_intervals=int(len(bursts)),
                  verified_complete_packets=int(complete_count),
                  incomplete_or_unverified_intervals=int(len(bursts) - complete_count),
                  packets=packets, dump=dump, cryptanalysis=cryptanalysis, flag=flag)
    (args.out_dir / '135_verified_results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
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
GAIANSPACE{wh4t_th3y_t00k_064CCB}
```
