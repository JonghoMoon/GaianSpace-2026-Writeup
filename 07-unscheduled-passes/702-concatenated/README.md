# 702-concatenated

| | |
|---|---|
| **Category** | 07 — Unscheduled Passes |
| **Points** | 75 |

## Description

The command to dump the data computer's memory went out a day ago. The answer arrived tonight, as faint as anything the station has ever locked onto.

Pilgrim-1 obeyed. It read back its own memory and sent it home. At this distance the signal is barely above the noise, which is why the 1977 designers wrapped every frame in two codes, one inside the other. The station recorded the raw symbols. Nobody on the desk has decoded a Pilgrim-1 readout since the 1990s.

Somewhere in the readout the computer signs its name.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `pilgrim_symbols.s8` — the raw received symbols, signed 8-bit
- `coding_sheet.md` — what is left of the handbook page on the coding

## Hints

Two hints were released during the event:

1. **Not just yes or no** — Every sample says how sure the receiver was, not only which way it leaned. Throwing that away costs more than this link can afford.
2. **Four at a time** — The outer code never sees the bytes in the order they arrived.

## Solution

### Steps

1. Read the signed 8-bit soft-decision symbols and decode the inner convolutional code (rate 1/2, constraint length 7, generators 171 and 133 in octal) with Viterbi decoding.
2. Search the decoded bitstream for the 32-bit sync word `0x1ACFFC1D` and extract complete coded frames.
3. Deinterleave each frame's four Reed–Solomon `(255,223)` codewords.
4. Correct symbol errors, recover frame counters and valid data lengths, and concatenate valid payload bytes in frame order.
5. Decompress the recovered zlib/DEFLATE stream, verify its checksum, and locate the flag.

### Why this decoding order works

The recording contains **signed 8-bit soft symbols**, not recovered bits. A positive sample favours transmitted bit `0` and a negative sample favours `1`; a larger absolute value is stronger evidence. A hard decision based only on the sign would discard that reliability information. The solver therefore maximizes a **soft-decision Viterbi path metric** across all 64 trellis states (constraint length 7), trying both possible alignments of the incoming two-symbol pairs.

The inner convolutional code uses generators **`171` and `133` (octal)**. For each data bit the `171` output was transmitted first, while the `133` output was **inverted** before transmission. Accounting for that inversion is essential. The sync marker `0x1ACFFC1D` passed through the same inner code, so the decoder searches for it **after** Viterbi decoding.

After each recovered sync marker come `4 × 255 = 1020` bytes forming four interleaved RS(255,223) codewords over GF(256), using field polynomial `0x11D` and 32 parity bytes per codeword. Transmitted byte position `4*i + j` belongs to byte `i` of codeword `j`. The solver takes `encoded[j::4]`, corrects each RS codeword, then **interleaves the 223-byte decoded data sections back into their transmitted order**, rather than concatenating the four messages.

The resulting 892 bytes consist of a 2-byte big-endian frame counter, a 2-byte valid-length field, and 888 available data bytes. Valid-length, `0x55` filler and consecutive frame counters are checked before joining payloads. In this capture, the three frames require **11 RS byte corrections** in total. Finally, the recovered 2050-byte stream is inflated to 3778 bytes; the detected **zlib wrapper's checksum** is validated by the decompressor. The code also has a raw-DEFLATE fallback, for which no zlib wrapper checksum is available; the observed solution takes the checksum-verified zlib path.

<!-- BEGIN CATEGORY07 REVIEW: 702 -->

### Hard-decision vs. soft-decision: experimental comparison

To verify whether soft-decision decoding was necessary for this
capture, the same signed 8-bit symbols were also processed using
hard-decision Viterbi decoding.

This follows Ade's suggestion in `coding_sheet.md`: retain only
the sign of each received symbol and discard its magnitude.

Both experiments use the same convolutional-code parameters,
including the inverted second encoder output.

| Verification | Hard-decision | Soft-decision |
|---|---|---|
| Synchronization markers recovered | 3 | 3 |
| Frames successfully decoded | 0/3 | 3/3 |
| Reed-Solomon decoding | Failed for all frames | Passed |
| Total corrected RS bytes | Not available | 11 |
| zlib checksum verification | Not reached | Passed |

Finding all three synchronization markers with hard-decision
decoding does not establish that the subsequent frame payloads
are recoverable.

#### Reed-Solomon correction capability

The outer code is RS(255,223), with 32 parity bytes per codeword.

Without erasure information, its maximum error-correction
capability is:

\[
t = \frac{255-223}{2} = 16
\]

This limit applies to **each RS codeword**, not to an entire
transmitted frame.

Each frame contains four interleaved RS(255,223) codewords.

In the hard-decision experiment, all three frames failed
Reed-Solomon decoding because the recovered data could not
be corrected within the supported decoding capability.

This does not independently establish that every codeword
contained more than 16 erroneous bytes. It establishes that
the implemented RS decoder could not recover the hard-decision
output under the specified coding parameters.

#### Soft-decision correction results

Soft-decision Viterbi decoding recovered all three frames.

The Reed-Solomon correction counts were:

| Frame | Corrections per RS codeword | Total |
|---|---|---:|
| 0 | 2, 2, 0, 1 | 5 |
| 1 | 0, 0, 0, 0 | 0 |
| 2 | 1, 2, 2, 1 | 6 |
| **Total** | | **11** |

The recovered compressed stream contained 2050 bytes and
decompressed to 3778 bytes.

The zlib checksum verification also passed.

The comparison demonstrates that the reliability information
preserved in the received soft symbols was essential to the
successful decoding path **for this capture and implementation**.

It does not prove that every possible hard-decision receiver
would necessarily fail under different synchronization or
decoding conditions.

The successful processing chain is:

    Signed 8-bit received symbols
        |
        v
    Soft-decision Viterbi decoding
        |
        v
    Synchronization marker recovery
        |
        v
    Reed-Solomon deinterleaving and correction
        |
        v
    Payload reconstruction
        |
        v
    zlib decompression and checksum verification
        |
        v
    GAIANSPACE{s0ft_v1terbi_th3n_r33d_s0l0m0n}

**Reproduction scope:** The hard-decision results were obtained in a separate diagnostic experiment. The published `702.py` implements the successful soft-decision decoding path and does not include a hard-decision mode.

<!-- END CATEGORY07 REVIEW: 702 -->

### Reproduction

Required dependencies: NumPy. The solver implements Viterbi and Reed–Solomon decoding internally.

Run the solver from the directory containing the original challenge inputs, as in the uploaded working archive.

```bash
python3 702.py
```

Expected relevant output:

```text
VITERBI: soft decisions, symbol-pair phase 0
FRAME 0: sync bit 1337, valid=888 bytes, RS corrections=[2, 2, 0, 1]
FRAME 1: sync bit 9529, valid=888 bytes, RS corrections=[0, 0, 0, 0]
FRAME 2: sync bit 17721, valid=274 bytes, RS corrections=[1, 2, 2, 1]
RS CORRECTED BYTES: 11
DEFLATE: 2050 -> 3778 bytes (zlib)
COMPRESSION CHECKSUM VERIFIED: True
FLAG: GAIANSPACE{s0ft_v1terbi_th3n_r33d_s0l0m0n}
```



### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies:
#   python3 -m pip install numpy
"""Solve 702-concatenated from signed 8-bit receiver symbols.

Example:
    python3 702.py pilgrim_symbols.s8 --out-dir 702_solution

Dependency: NumPy. Viterbi and RS(255,223) decoding are implemented here.
No GNU Radio, reedsolo, known plaintext, or precomputed decoded data is used.
The zlib wrapper checksum is verified when the stream uses that wrapper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Any

import numpy as np

SYNC = 0x1ACFFC1D
CODEWORD_BYTES = 255
DATA_BYTES = 223
PARITY_BYTES = 32
DEPTH = 4
FRAME_BITS = (4 + CODEWORD_BYTES * DEPTH) * 8


class Galois256:
    """GF(256), alpha=2, reduction polynomial 0x11D."""
    def __init__(self) -> None:
        self.exp = [0] * 510
        self.log = [0] * 256
        state = 1
        for index in range(255):
            self.exp[index] = int(state)
            self.log[state] = int(index)
            state = int(state << 1)
            if state & 0x100:
                state = int(state ^ 0x11D)
        if state != 1 or len(set(self.exp[:255])) != 255:
            raise RuntimeError('Invalid GF(256) tables.')
        for index in range(255, 510):
            self.exp[index] = int(self.exp[index - 255])

    def mul(self, a: int, b: int) -> int:
        a, b = int(a), int(b)
        return int(self.exp[self.log[a] + self.log[b]]) if a != 0 and b != 0 else 0

    def div(self, a: int, b: int) -> int:
        a, b = int(a), int(b)
        if b == 0:
            raise ValueError('Division by zero in GF(256).')
        return int(self.exp[(self.log[a] - self.log[b]) % 255]) if a != 0 else 0

    def evaluate(self, coefficients: list[int] | bytes, x: int) -> int:
        value = 0
        for coefficient in coefficients:
            value = int(self.mul(value, int(x)) ^ int(coefficient))
        return value

    def syndromes(self, data: list[int] | bytes) -> list[int]:
        return [int(self.evaluate(data, self.exp[index])) for index in range(PARITY_BYTES)]


GF = Galois256()


def solve_gf_matrix(matrix: list[list[int]]) -> list[int]:
    """Solve a square augmented system by exact GF(256) row reduction."""
    size = int(len(matrix))
    rows = [[int(value) for value in row] for row in matrix]
    for column in range(size):
        candidates = [row for row in range(column, size) if rows[row][column] != 0]
        if not candidates:
            raise ValueError('Singular error-magnitude system.')
        pivot = int(candidates[0])
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = int(rows[column][column])
        rows[column] = [int(GF.div(value, divisor)) for value in rows[column]]
        for row in range(size):
            if row == column:
                continue
            multiplier = int(rows[row][column])
            for index in range(column, size + 1):
                rows[row][index] = int(rows[row][index] ^ GF.mul(multiplier, rows[column][index]))
    return [int(rows[row][-1]) for row in range(size)]


def rs_decode(codeword: bytes) -> tuple[bytes, bytes, list[int]]:
    """Berlekamp-Massey, Chien search, then a small exact magnitude solve."""
    if len(codeword) != CODEWORD_BYTES:
        raise ValueError('RS codewords must be 255 bytes.')
    corrected = [int(value) for value in codeword]
    syndrome = GF.syndromes(corrected)
    if not any(syndrome):
        return bytes(codeword[:DATA_BYTES]), bytes(codeword), []
    locator = [1] + [0] * PARITY_BYTES
    previous = locator.copy()
    degree, spacing, previous_discrepancy = 0, 1, 1
    for index in range(PARITY_BYTES):
        discrepancy = int(syndrome[index])
        for j in range(1, degree + 1):
            discrepancy = int(discrepancy ^ GF.mul(locator[j], syndrome[index - j]))
        if discrepancy == 0:
            spacing += 1
            continue
        saved = locator.copy()
        scale = int(GF.div(discrepancy, previous_discrepancy))
        for j in range(PARITY_BYTES + 1 - spacing):
            locator[j + spacing] = int(locator[j + spacing] ^ GF.mul(scale, previous[j]))
        if 2 * degree <= index:
            degree = int(index + 1 - degree)
            previous = saved
            previous_discrepancy = int(discrepancy)
            spacing = 1
        else:
            spacing += 1
    if not 1 <= degree <= PARITY_BYTES // 2:
        raise ValueError('RS error count exceeds the correction capability.')
    positions: list[int] = []
    error_locations: list[int] = []
    for position in range(CODEWORD_BYTES):
        power = int(CODEWORD_BYTES - 1 - position)
        inverse = int(GF.exp[(-power) % 255])
        if GF.evaluate(locator[:degree + 1][::-1], inverse) == 0:
            positions.append(int(position))
            error_locations.append(int(GF.exp[power]))
    if len(positions) != degree:
        raise ValueError('The RS locator does not have the expected number of roots.')
    # S[k] = sum(error[j] * alpha**((254-position[j])*k)).
    matrix = [[int(GF.exp[(GF.log[value] * row) % 255]) for value in error_locations]
              + [int(syndrome[row])] for row in range(degree)]
    magnitudes = solve_gf_matrix(matrix)
    for position, magnitude in zip(positions, magnitudes):
        corrected[position] = int(corrected[position] ^ magnitude)
    if any(GF.syndromes(corrected)):
        raise ValueError('RS corrected codeword still has nonzero syndromes.')
    actual_positions = [index for index in range(CODEWORD_BYTES)
                        if int(codeword[index]) != int(corrected[index])]
    if actual_positions != positions:
        raise ValueError('RS correction locations are inconsistent.')
    return bytes(corrected[:DATA_BYTES]), bytes(corrected), positions


def viterbi(samples: np.ndarray, phase: int) -> np.ndarray:
    """Maximum-correlation soft decoding, with all 64 initial states allowed.

    The shift register inserts a new information bit at bit zero. Generator
    171(octal) is transmitted first; generator 133(octal) is inverted on air.
    Signed sample magnitudes remain in the branch metric, not just their signs.
    """
    shifted = samples[int(phase):]
    pairs = shifted[:int(shifted.size) // 2 * 2].reshape(-1, 2).astype(np.int64)
    states = np.arange(64, dtype=np.int64)
    low_predecessor = states >> 1
    high_predecessor = low_predecessor + 32

    def expected_signs(predecessor: np.ndarray) -> np.ndarray:
        registers = (predecessor << 1) | (states & 1)
        first = [1 - 2 * (int(int(value) & 0o171).bit_count() & 1) for value in registers]
        second = [1 - 2 * ((int(int(value) & 0o133).bit_count() & 1) ^ 1) for value in registers]
        return np.asarray(list(zip(first, second)), dtype=np.int64)

    low_signs = expected_signs(low_predecessor)
    high_signs = expected_signs(high_predecessor)
    metric = np.zeros(64, dtype=np.int64)
    survivor = np.empty((int(pairs.shape[0]), 64), dtype=np.bool_)
    for index, pair in enumerate(pairs):
        s0, s1 = int(pair[0]), int(pair[1])
        low = metric[low_predecessor] + s0 * low_signs[:, 0] + s1 * low_signs[:, 1]
        high = metric[high_predecessor] + s0 * high_signs[:, 0] + s1 * high_signs[:, 1]
        survivor[index] = high > low
        metric = np.maximum(low, high)
    if int(pairs.shape[0]) == 0:
        raise ValueError('No complete convolutional symbol pairs.')
    state = int(np.argmax(metric))
    bits = np.empty(int(pairs.shape[0]), dtype=np.uint8)
    for index in range(int(pairs.shape[0]) - 1, -1, -1):
        bits[index] = np.uint8(state & 1)
        state = int((state >> 1) | (int(survivor[index, state]) << 5))
    return bits


def find_sync(bits: np.ndarray) -> list[int]:
    result: list[int] = []
    window = 0
    for index, value in enumerate(bits):
        window = int(((window << 1) | int(value)) & 0xFFFFFFFF)
        if index >= 31 and window == SYNC:
            result.append(int(index - 31))
    return result


def decode_frames(bits: np.ndarray) -> tuple[list[dict[str, Any]], bytes, bytes]:
    records: list[dict[str, Any]] = []
    payloads: list[bytes] = []
    corrected_frames: list[bytes] = []
    for start in find_sync(bits):
        stop = int(start + FRAME_BITS)
        if stop > int(bits.size):
            continue
        encoded = np.packbits(bits[start + 32:stop], bitorder='big').tobytes()
        decoded_words: list[bytes] = []
        corrected_words: list[bytes] = []
        locations: list[list[int]] = []
        try:
            for interleave in range(DEPTH):
                decoded, corrected, errors = rs_decode(encoded[interleave::DEPTH])
                decoded_words.append(decoded)
                corrected_words.append(corrected)
                locations.append(errors)
        except ValueError:
            continue
        # Restore row-major data order, rather than concatenating four RS messages.
        data = bytes(int(decoded_words[j][i]) for i in range(DATA_BYTES) for j in range(DEPTH))
        counter = int.from_bytes(data[:2], byteorder='big')
        valid_length = int.from_bytes(data[2:4], byteorder='big')
        if valid_length > DATA_BYTES * DEPTH - 4:
            continue
        if any(int(value) != 0x55 for value in data[4 + valid_length:]):
            continue
        if records:
            if start != int(records[-1]['sync_bit_index']) + FRAME_BITS:
                raise ValueError('A complete frame is missing from the decoded stream.')
            if counter != (int(records[-1]['counter']) + 1) & 0xFFFF:
                raise ValueError('Frame counters are not consecutive.')
        records.append(dict(sync_bit_index=int(start), counter=int(counter),
                            valid_bytes=int(valid_length),
                            corrected_bytes_per_codeword=[int(len(v)) for v in locations],
                            corrected_positions_per_codeword=locations,
                            corrected_bytes=int(sum(len(v) for v in locations)),
                            all_rs_syndromes_zero=True, filler_valid=True))
        payloads.append(bytes(data[4:4 + valid_length]))
        corrected = bytes(int(corrected_words[j][i])
                          for i in range(CODEWORD_BYTES) for j in range(DEPTH))
        corrected_frames.append(SYNC.to_bytes(4, 'big') + corrected)
    if not records:
        raise ValueError('No complete RS-validated telemetry frames found.')
    return records, b''.join(payloads), b''.join(corrected_frames)


def inflate(stream: bytes) -> tuple[bytes, str, bool]:
    failures: list[str] = []
    limit = 16 * 1024 * 1024
    for window_bits, name, has_checksum in ((15, 'zlib', True), (-15, 'raw-deflate', False)):
        try:
            decoder = zlib.decompressobj(int(window_bits))
            result = decoder.decompress(stream, limit + 1)
            if len(result) > limit or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
                raise ValueError('Incomplete, overlong, or trailing compressed data.')
            return bytes(result), str(name), bool(has_checksum)
        except (zlib.error, ValueError) as exc:
            failures.append(f'{name}: {exc}')
    raise ValueError('Deflate decoding failed: ' + '; '.join(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('symbols', type=Path, nargs='?', default=Path('pilgrim_symbols.s8'))
    parser.add_argument('--phase', choices=('auto', '0', '1'), default='auto',
                        help='First sample of a generator pair; auto tests both alignments if needed.')
    parser.add_argument('--out-dir', type=Path, default=Path('702_solution'))
    args = parser.parse_args()
    samples = np.fromfile(args.symbols, dtype=np.int8)
    if int(samples.size) < 2 * FRAME_BITS:
        raise ValueError('The recording is too short to contain one complete frame.')
    phases = [0, 1] if args.phase == 'auto' else [int(args.phase)]
    failures: list[str] = []
    for phase in phases:
        try:
            bits = viterbi(samples, int(phase))
            records, compressed, corrected_frames = decode_frames(bits)
            plaintext, wrapper, checksum = inflate(compressed)
            flags = sorted(set(value.decode('ascii') for value in
                               re.findall(rb'GAIANSPACE\{[^}\r\n\x00]{1,200}\}', plaintext)))
            if len(flags) != 1:
                raise ValueError('Expected one unique flag in the validated memory readout.')
            break
        except ValueError as exc:
            failures.append(f'phase {phase}: {exc}')
    else:
        raise RuntimeError('No symbol-pair alignment decoded successfully. ' + '; '.join(failures))
    flag = str(flags[0])
    report = dict(flag=flag, symbol_phase=int(phase), input_symbols=int(samples.size),
                  decoded_information_bits=int(bits.size), frames=records,
                  corrected_bytes_total=int(sum(int(row['corrected_bytes']) for row in records)),
                  compressed_bytes=int(len(compressed)), decoded_bytes=int(len(plaintext)),
                  compression_wrapper=wrapper, compression_checksum_verified=bool(checksum),
                  input_sha256=hashlib.sha256(args.symbols.read_bytes()).hexdigest(),
                  plaintext_sha256=hashlib.sha256(plaintext).hexdigest(),
                  earlier_attempts=failures)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / 'pilgrim_decoded.bin').write_bytes(plaintext)
    (args.out_dir / 'pilgrim_decoded.txt').write_text(
        plaintext.decode('utf-8', errors='backslashreplace'), encoding='utf-8')
    (args.out_dir / '702_compressed.bin').write_bytes(compressed)
    (args.out_dir / '702_corrected_frames.bin').write_bytes(corrected_frames)
    (args.out_dir / '702_verified_results.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (args.out_dir / 'flag.txt').write_text(flag + '\n', encoding='ascii')
    print(f'VITERBI: soft decisions, symbol-pair phase {phase}')
    for record in records:
        print(f'FRAME {record["counter"]}: sync bit {record["sync_bit_index"]}, '
              f'valid={record["valid_bytes"]} bytes, '
              f'RS corrections={record["corrected_bytes_per_codeword"]}')
    print(f'RS CORRECTED BYTES: {report["corrected_bytes_total"]}')
    print(f'DEFLATE: {len(compressed)} -> {len(plaintext)} bytes ({wrapper})')
    print(f'COMPRESSION CHECKSUM VERIFIED: {checksum}')
    print(f'FLAG: {flag}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
```

## Flag

```text
GAIANSPACE{s0ft_v1terbi_th3n_r33d_s0l0m0n}
```
