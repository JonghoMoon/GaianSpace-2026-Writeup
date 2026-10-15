#!/usr/bin/env python3
# Dependencies (Python >= 3.10):
#   python3 -m pip install numpy scipy
"""Decode the GaianSpace 133 capture offline with NumPy/SciPy, without GNU Radio.

This is a capture-specific reproducible solver, not a general-purpose LoRa receiver.
The time windows and eight channel centers were measured in the supplied capture.
It first validates TC DUMP NAV, then reconstructs and validates its hopping reply.

LoRa bit-layout references (GPL-3.0 gr-lora_sdr implementation):
https://github.com/tapparelj/gr-lora_sdr
  lib/{fft_demod,gray_mapping,deinterleaver,hamming_dec,header_decoder,
       dewhitening,crc_verif}_impl.cc
The synchronization, channel-bank reconstruction and batch validation here are
standalone offline implementations. No GNU Radio import or runtime is required.
"""
from __future__ import annotations

import argparse
import binascii
import json
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from scipy import fft, signal

CENTERS_HZ = np.asarray([
    433175000, 433325000, 433475000, 433625000,
    434225000, 434375000, 434525000, 434675000,
], dtype=np.float64)
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


def json_safe(result: dict[str, Any]) -> dict[str, Any]:
    copy = dict(result)
    payload = copy.pop('payload')
    copy['payload_ascii'] = bytes(payload).decode('ascii', errors='backslashreplace')
    return copy


def decode_uplink(capture: Capture) -> dict[str, Any]:
    start = 14.35
    samples = capture.channel(start, 14.80, 433925000.0, 3)
    sync = synchronize(samples, 7, 4)
    # Resolve residual sub-chip timing by requiring both header and payload CRCs.
    for delta in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5):
        data_start = int(sync['data_start']) + int(delta)
        values = [int(round(measure(samples, float(data_start + k * 512), 7, 4, float(sync['cfo_bins']))[0]))
                  for k in range(64)]
        result = decode_explicit(values, 7)
        if result is not None and result['crc_valid']:
            result.update(sf=7, bandwidth_hz=250000, center_hz=433925000,
                          sync_symbols=[int(round(measure(samples, float(data_start) - float(n) * 512.0, 7, 4, float(sync['cfo_bins']))[0])) for n in (4.25, 3.25)], sample_adjustment=int(delta),
                          preamble_start_s=float(start + (float(data_start) - 12.25 * 512.0) / (capture.fs / 3.0)))
            return result
    raise RuntimeError('The fixed-frequency uplink did not pass payload CRC.')


def decode_reply(capture: Capture, out_dir: Path) -> dict[str, Any]:
    start, stop = 14.70, 15.65
    fs_out = capture.fs / 6.0
    print('Building eight non-overlapping receive channels ...', flush=True)
    bank = np.stack([capture.channel(start, stop, float(f), 6) for f in CENTERS_HZ])
    # Resampling alone is insufficient: adjacent channels otherwise overlap.
    taps = signal.firwin(129, 70000.0, fs=500000.0).astype(np.float32)
    bank = signal.fftconvolve(bank, taps[None, :], mode='same', axes=1).astype(np.complex64)
    # The measured reply starts on 434.225 MHz.
    initial_channel = 4
    sync = synchronize(bank[initial_channel], 9, 4)
    sf, stride = 9, 2048
    nominal = int(sync['data_start'])
    found: dict[str, Any] | None = None
    selected: list[int] = []
    winning_start = nominal
    winning_symbols: list[int] = []
    winning_quality: list[float] = []
    for delta in (0, -1, 1, -2, 2, -3, 3, -4, 4):
        data_start = nominal + int(delta)
        values: list[int] = []
        channels: list[int] = []
        quality: list[float] = []
        # Begin with the eight-symbol header; extend only after it validates.
        limit = 8
        k = 0
        while k < limit:
            a, b = data_start + k * stride, data_start + (k + 1) * stride
            if b > int(bank.shape[1]):
                break
            powers = np.mean(np.abs(bank[:, a:b]) ** 2, axis=1)
            channel_id = int(np.argmax(powers))
            symbol, score = measure(bank[channel_id], float(a), sf, 4, float(sync['cfo_bins']))
            values.append(int(round(symbol)))
            channels.append(channel_id)
            quality.append(float(score))
            k += 1
            if k == 8:
                head_nibbles, _ = decode_block(((np.asarray(values, dtype=np.int64) - 1) % (1 << sf)) // 4, sf - 2, 4)
                header = header_info(head_nibbles)
                if not bool(header['checksum_valid']) or not 1 <= int(header['cr']) <= 4 or not bool(header['has_crc']):
                    break
                payload_length = int(header['length'])
                limit = int(8 + math.ceil(float(8 * payload_length - 4 * sf + 28 + 16) / float(4 * sf)) * (int(header['cr']) + 4))
        result = decode_explicit(values, sf)
        if result is not None and result['crc_valid']:
            found, selected = result, channels
            winning_start, winning_symbols, winning_quality = data_start, values, quality
            break
    if found is None:
        raise RuntimeError('No reconstructed downlink passed payload CRC.')
    needed = int(found['data_symbol_count'])
    selected = selected[:needed]
    winning_symbols = winning_symbols[:needed]
    winning_quality = winning_quality[:needed]
    # Preserve sample indices; replace the selected RF channel, not the time axis.
    dehopped = bank[initial_channel].copy()
    for k, index in enumerate(selected):
        a, b = winning_start + k * stride, winning_start + (k + 1) * stride
        dehopped[a:b] = bank[index, a:b]
    dehopped.astype('<c8').tofile(out_dir / '133_reply_dehopped_500ksps.cf32')
    hop_start_symbols = [0] + [k for k in range(1, len(selected)) if selected[k] != selected[k - 1]]
    hops = []
    for k in hop_start_symbols:
        hops.append(dict(data_symbol_index=int(k), capture_time_s=float(start + float(winning_start + k * stride) / fs_out),
                         center_hz=int(CENTERS_HZ[selected[k]])))
    trace = [dict(index=int(k), center_hz=int(CENTERS_HZ[selected[k]]),
                  symbol=int(winning_symbols[k]), fft_peak_fraction=float(winning_quality[k]))
             for k in range(needed)]
    (out_dir / '133_symbols.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')
    found.update(sf=9, bandwidth_hz=125000, sample_rate_nominal_hz=500000,
                 sample_rate_effective_hz=float(fs_out), implicit_header=False,
                 preamble_upchirps=12, sync_symbols=sync['netids'], hop_period_symbols=8,
                 hop_period_seconds=0.032768, first_hop_after_data_symbols=1,
                 channel_centers_hz=[int(f) for f in CENTERS_HZ],
                 preamble_start_s=float(start + (float(winning_start) - 16.25 * float(stride)) / fs_out),
                 sample_adjustment=int(winning_start - nominal),
                 observed_channel_changes=hops)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, help='vela_wide_0212.sigmf-data')
    parser.add_argument('--meta', type=Path, help='Matching SigMF metadata; inferred by default.')
    parser.add_argument('--out-dir', type=Path, default=Path('133_solution'))
    args = parser.parse_args()
    metadata = args.meta if args.meta is not None else args.data.with_suffix('.sigmf-meta')
    args.out_dir.mkdir(parents=True, exist_ok=True)
    capture = Capture(args.data, metadata)
    uplink = decode_uplink(capture)
    print('UPLINK:', repr(uplink['payload']), flush=True)
    print(f"UPLINK CRC: received={uplink['crc_received']} calculated={uplink['crc_calculated']} valid={uplink['crc_valid']}", flush=True)
    reply = decode_reply(capture, args.out_dir)
    text = bytes(reply['payload']).decode('ascii', errors='strict')
    if not text.startswith('TM,ACK,1,DUMP NAV,'):
        raise RuntimeError('The valid packet is not the expected command acknowledgement.')
    match = re.search(r'GAIANSPACE\{[^}]+\}', text)
    if match is None:
        raise RuntimeError('The validated acknowledgement contains no flag.')
    flag = str(match.group(0))
    epoch = datetime.fromisoformat(str(capture.meta['captures'][0]['core:datetime']).replace('Z', '+00:00'))
    for packet in (uplink, reply):
        packet['preamble_start_utc'] = (epoch + timedelta(seconds=float(packet['preamble_start_s']))).isoformat()
    report = dict(capture=args.data.name, capture_metadata=capture.meta,
                  uplink=json_safe(uplink), downlink=json_safe(reply), flag=flag)
    (args.out_dir / '133_verified_results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    (args.out_dir / '133_reply_payload.bin').write_bytes(bytes(reply['payload']))
    (args.out_dir / '133_reply_payload.txt').write_text(text + '\n', encoding='ascii')
    print('DOWNLINK:', text, flush=True)
    print(f"HEADER checksum valid: {reply['header']['checksum_valid']}", flush=True)
    print(f"PAYLOAD CRC: received={reply['crc_received']} calculated={reply['crc_calculated']} valid={reply['crc_valid']}", flush=True)
    print('FLAG:', flag, flush=True)
    print('Outputs:', str(args.out_dir.resolve()), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
