#!/usr/bin/env python3
# Dependencies:
#   sudo apt update && sudo apt install -y gnuradio python3-numpy python3-scipy
#   Install the GNU Radio OOT module gr-lora_sdr against the SAME GNU Radio
#   version as /usr/bin/python3: https://github.com/tapparelj/gr-lora_sdr
#   Confirm with: PYTHONNOUSERSITE=1 /usr/bin/python3 -c "from gnuradio import lora_sdr"
# Python 3.10+ is required. The GNU Radio runtime is called as a subprocess.
"""Recover Challenge 132 GET HK ACK from original SigMF without preset answers.

  PYTHONNOUSERSITE=1 /usr/bin/python3 132.py vela_band_0136.sigmf-data \
      --gr-python /usr/bin/python3 --window 34.65:36.0 --sfs 10 --crs 2 --lengths 96
  PYTHONNOUSERSITE=1 /usr/bin/python3 132.py 132_DL_candidates/132_DL_3_32.5s.cf32

When given raw ci8 SigMF, find narrow-band bursts at the downlink,
extract each at 500 kS/s with an anti-alias FIR, then sweep implicit-header
LoRa SF/CR/length. Accept only matching GET HK acknowledgement and its
application CRC-16/CCITT-FALSE. The capture may require --window or
--frequency tuning; no intermediate IQ file is a prerequisite.
"""
from __future__ import annotations

import argparse
import binascii
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import numpy as np
from scipy import signal



def load_sigmf_info(data: Path, meta: Path | None) -> tuple[np.ndarray, float, float]:
    import json
    metadata = (meta or data.with_suffix('.sigmf-meta'))
    info = json.loads(metadata.read_text(encoding='utf-8'))
    if info['global']['core:datatype'] != 'ci8':
        raise ValueError('Only ci8 SigMF recordings are supported.')
    fs = float(info['global']['core:sample_rate'])
    center = float(info['captures'][0]['core:frequency'])
    samples = np.memmap(data, dtype=np.int8, mode='r')
    if samples.size % 2:
        raise ValueError('Incomplete IQ sample in capture.')
    return samples.reshape(-1, 2), fs, center


def extract_iq(raw: np.ndarray, fs: float, center: float, start: float,
               stop: float, channel_hz: float) -> np.ndarray:
    first = max(0, int(round(float(start) * float(fs))))
    last = min(int(raw.shape[0]), int(round(float(stop) * float(fs))))
    if last <= first:
        raise ValueError('Invalid extraction time window.')
    iq8 = np.asarray(raw[first:last], dtype=np.float32)
    iq = (iq8[:, 0] + 1j * iq8[:, 1]).astype(np.complex64)
    index = np.arange(int(iq.size), dtype=np.float64) + float(first)
    shift = np.exp(-2j * np.pi * (float(channel_hz) - float(center)) * index / float(fs))
    iq *= np.asarray(shift, dtype=np.complex64)
    # Narrow-band FIR anti-alias filter is part of resample_poly.
    return signal.resample_poly(iq, 1, 4, window=('kaiser', 8.0)).astype('<c8')


def detect_channel_bursts(raw: np.ndarray, fs: float, center: float,
                          channel_hz: float) -> list[tuple[float, float]]:
    # Scan short windows in the recorded band; no reference flag or known time is used.
    block = 16384
    total = int(raw.shape[0]) // block
    if total < 3:
        return []
    fft_freq = np.fft.fftfreq(block, 1.0 / float(fs))
    offset = float(channel_hz) - float(center)
    signal_bins = np.abs(fft_freq - offset) <= 68000.0
    reference_bins = (np.abs(fft_freq - offset) >= 145000.0) & (np.abs(fft_freq - offset) <= 240000.0)
    if not signal_bins.any() or not reference_bins.any():
        raise ValueError('Channel frequency is too close to recorder bandwidth edge.')
    scores = np.empty(total, dtype=np.float32)
    for index in range(total):
        segment = np.asarray(raw[index * block:(index + 1) * block], dtype=np.float32)
        spectrum = np.abs(np.fft.fft(segment[:, 0] + 1j * segment[:, 1])) ** 2
        p_signal = float(np.mean(spectrum[signal_bins]))
        p_noise = float(np.mean(spectrum[reference_bins]))
        scores[index] = float(p_signal / max(p_noise, 1e-12))
    # Relative spectral occupancy threshold; output is reviewed by PHY/application CRC.
    active = np.flatnonzero(scores > 4.0)
    if active.size == 0:
        return []
    delta = float(block) / float(fs)
    groups: list[list[int]] = [[int(active[0])]]
    for index in active[1:]:
        if int(index) - groups[-1][-1] <= max(1, int(round(0.12 / delta))):
            groups[-1].append(int(index))
        else:
            groups.append([int(index)])
    windows = []
    for group in groups:
        a = float(group[0]) * delta
        b = float(group[-1] + 1) * delta
        if b - a < 0.07:
            continue
        windows.append((max(0.0, a - 0.09), min(float(raw.shape[0]) / fs, b + 0.14)))
    return windows


def parse_window(value: str) -> tuple[float, float]:
    a, b = value.split(':', 1)
    start, stop = float(a), float(b)
    if not 0 <= start < stop:
        raise ValueError('Use --window START:STOP in seconds.')
    return start, stop

WORKER = r"""
import argparse
from gnuradio import blocks, gr
from gnuradio import lora_sdr

parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--sf', type=int, required=True)
parser.add_argument('--cr', type=int, required=True)
parser.add_argument('--length', type=int, required=True)
args = parser.parse_args()

class Receiver(gr.top_block):
    def __init__(self):
        super().__init__('GaianSpace 132 implicit LoRa decoder')
        src = blocks.file_source(gr.sizeof_gr_complex, args.input, False, 0, 0)
        rx = lora_sdr.lora_sdr_lora_rx(
            bw=125000, cr=int(args.cr), has_crc=False, impl_head=True,
            pay_len=int(args.length), samp_rate=500000, sf=int(args.sf),
            sync_word=[0x00], soft_decoding=False, ldro_mode=2,
            print_rx=[False, False])
        sink = blocks.file_sink(gr.sizeof_char, args.output, False)
        sink.set_unbuffered(True)
        self.connect(src, rx, sink)

Receiver().run()
"""

ACK_PATTERN = re.compile(rb'(TM,ACK,\d+,GET HK,HK,[^\r\n]{0,200}?CO2=(\d+),UP=(\d+)\*[0-9A-Fa-f]{4})')


def extract_valid_ack(data: bytes) -> tuple[int, int, bytes, int] | None:
    for match in ACK_PATTERN.finditer(data):
        message = match.group(1)
        body, tag = message.rsplit(b'*', 1)
        calculated = int(binascii.crc_hqx(body, 0xFFFF))
        received = int(tag, 16)
        if calculated != received:
            continue
        return int(match.group(2)), int(match.group(3)), message, calculated
    return None


def run_worker(python: Path, worker: Path, iq: Path, dest: Path,
               sf: int, cr: int, length: int, timeout: float) -> tuple[bytes, str]:
    dest.write_bytes(b'')
    env = dict(os.environ)
    env['PYTHONNOUSERSITE'] = '1'
    argv = [str(python), str(worker), '--input', str(iq.resolve()),
            '--output', str(dest.resolve()), '--sf', str(int(sf)),
            '--cr', str(int(cr)), '--length', str(int(length))]
    proc = subprocess.run(argv, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False, timeout=float(timeout))
    log = (proc.stdout + proc.stderr).decode('utf-8', errors='replace')
    if proc.returncode != 0:
        raise RuntimeError(f'GNU Radio receiver error: {log[-1200:]}')
    return dest.read_bytes(), log


def sweep_iq(iq: Path, worker: Path, output: Path, gr_python: Path,
             sfs: list[int], crs: list[int], lengths: list[int],
             timeout: float) -> tuple[int, int, bytes, int, int, int, int] | None:
    # First try extended lengths: a valid ACK can be a prefix of a longer decoded buffer.
    for sf in sfs:
        for cr in crs:
            for length in lengths:
                try:
                    data, log = run_worker(gr_python, worker, iq, output, sf, cr, length, timeout)
                except subprocess.TimeoutExpired:
                    print(f'  SF{sf} CR{cr} LEN{length}: timeout', flush=True)
                    continue
                candidate = extract_valid_ack(data)
                if candidate is None:
                    continue
                co2, uptime, payload, crc = candidate
                print(f'  FOUND SF{sf} CR{cr} LEN{length}, valid application CRC={crc:04X}', flush=True)
                return co2, uptime, payload, crc, int(sf), int(cr), int(length)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, nargs='?', default=Path('vela_band_0136.sigmf-data'))
    parser.add_argument('--meta', type=Path, default=None)
    parser.add_argument('--gr-python', type=Path, default=Path('/usr/bin/python3'))
    parser.add_argument('--window', type=parse_window, default=None,
                        help='Optional START:STOP seconds interval in the raw capture.')
    parser.add_argument('--frequency', type=float, default=433175000.0)
    parser.add_argument('--sfs', type=int, nargs='+', default=[7, 8, 9, 10])
    parser.add_argument('--crs', type=int, nargs='+', default=[1, 2, 3, 4])
    parser.add_argument('--lengths', type=int, nargs='+', default=[96, 68, 64, 80, 128, 48],
                        help='Implicit payload lengths. The legacy scanner missed 68.')
    parser.add_argument('--timeout', type=float, default=20.0)
    parser.add_argument('--max-bursts', type=int, default=25)
    parser.add_argument('--save-extracted', type=Path, default=None)
    args = parser.parse_args()
    if not args.gr_python.exists():
        parser.error('GNU Radio Python executable is missing. Use --gr-python PATH.')
    # Isolate GNU Radio from user-site NumPy/SciPy during the import probe too.
    gr_env = dict(os.environ)
    gr_env['PYTHONNOUSERSITE'] = '1'
    check = subprocess.run([str(args.gr_python), '-c', 'from gnuradio import lora_sdr'],
                           capture_output=True, text=True, check=False, env=gr_env)
    if check.returncode != 0:
        parser.error('GNU Radio/gr-lora_sdr is not importable in the selected Python:\n' + check.stderr[-1200:])
    if not args.input.exists():
        parser.error(f'Input does not exist: {args.input}')

    with tempfile.TemporaryDirectory(prefix='gaianspace132_') as folder:
        root = Path(folder)
        worker = root / 'gnuradio_receiver.py'
        worker.write_text(WORKER, encoding='utf-8')
        output = root / 'rx.bin'
        iq_path = root / 'burst.cf32'
        if args.input.suffix.lower() == '.cf32':
            inputs = [(0., 0., args.input, 0.)]
        else:
            raw, fs, center = load_sigmf_info(args.input, args.meta)
            windows = ([args.window] if args.window is not None
                       else detect_channel_bursts(raw, fs, center, float(args.frequency)))
            # Print every candidate instead of selecting a known timestamp.
            print(f'SigMF: duration={raw.shape[0] / fs:.3f} s, candidate windows={len(windows)}', flush=True)
            inputs = [(a, b, iq_path, 1.) for a, b in windows[:max(1, int(args.max_bursts))]]
            if not inputs:
                raise RuntimeError('No candidate bursts detected; retry with --window START:STOP.')
        for index, (start, stop, path, need_extract) in enumerate(inputs):
            if bool(need_extract):
                iq = extract_iq(raw, fs, center, float(start), float(stop), float(args.frequency))
                iq.tofile(path)
            print(f'CANDIDATE {index+1}/{len(inputs)}: '
                  + (f'{start:.3f}..{stop:.3f} s' if bool(need_extract) else str(path)), flush=True)
            valid = sweep_iq(path, worker, output, args.gr_python, args.sfs, args.crs,
                             args.lengths, float(args.timeout))
            if valid is None:
                continue
            co2, uptime, payload, crc, sf, cr, length = valid
            if args.save_extracted is not None and bool(need_extract):
                args.save_extracted.write_bytes(path.read_bytes())
                print('EXTRACTED IQ:', args.save_extracted)
            print('RECEIVER SETTINGS:', f'SF={sf} CR={cr} implicit=True length_hint={length}')
            print('PAYLOAD:', payload.decode('ascii', errors='strict'))
            print(f'CRC-16/CCITT-FALSE: calculated={crc:04X}, received={crc:04X}')
            print(f'FLAG: GAIANSPACE{{{co2}_{uptime}}}')
            return 0
    raise RuntimeError('No candidate passed the application CRC; inspect burst detection or extend --lengths.')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print('ERROR:', exc, file=sys.stderr)
        raise SystemExit(1)
