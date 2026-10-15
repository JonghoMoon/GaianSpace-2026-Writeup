# 132-no-name-on-the-door

| | |
|---|---|
| **Category** | 13 — Night Shift |
| **Points** | 125 |

## Description

01:40. The stranger is still talking. Every few minutes GAIAN-723 answers, and every answer comes back in a voice the station modem refuses to hear.

Whoever has GAIAN-723 changed how it speaks. The packets no longer say how long they are, and each one sounds slightly different from the last. Aroz can see them on the waterfall but can't read them. The ground station log has a single line from 01:31: `DL CFG CHANGED BY TC — NOT FROM MOC`.

At 01:37 the stranger asked the satellite something, and the satellite answered. The thermal team will want to know what the cabin looked like at that moment.

Find the carbon dioxide reading GAIAN-723 reported when it acknowledged the stranger's command at 01:37, and how long the satellite said it had been awake.

**Flag format:** `GAIANSPACE{[CO2 in ppm]_[uptime in seconds]}`

**Attachments:**

- `vela_band_0136.sigmf-data` — the band recorder's raw capture (too large to attach: download it from [Hugging Face](https://huggingface.co/datasets/GaianSpace/ctf-2026-130/tree/main/132))
- `vela_band_0136.sigmf-meta` — the recorder's metadata for that capture
- `station_log.txt` — the ground station's event log for the same hour

## Solution

### Analysis

The station log shows the ground modem lost lock after a **configuration change by an unauthorized telecommand** at 01:31:17 UTC. The follow-up downlink no longer transmits an explicit payload length. Therefore a receiver configured for the old SF9 explicit header cannot decode this packet.

The recorder metadata describes **ci8 IQ, 1,999,999 samples/s, center 433,549,995 Hz, starting 2026-10-11 01:36:45Z**. The downlink is near **433.175 MHz**. The original experiment used a cropped, translated, resampled **500 kS/s complex-float** file named `132_DL_3_32.5s.cf32`, but **that intermediate was not archived**. This revised script instead accepts the downloadable original SigMF data, detects band-limited bursts and creates candidate IQ windows itself. Use `--window` to choose an interval manually if the energy detector does not isolate the desired burst.

For each extracted candidate, `132.py` invokes GNU Radio/`gr-lora_sdr` in **implicit-header** mode and sweeps SF, coding-rate settings and candidate payload lengths. The default length candidates now include **68**, which was omitted by the earlier batch scanner. The original scan record also showed an intelligible, CRC-valid **application message prefix** when decoding length 96, so an exact PHY length need not be assumed to detect a valid message. This script tests candidate results against the actual ASCII packet's trailing `*XXXX` CRC field and **does not hardcode CO2, uptime, or the final flag**.

The documented successful receive setting is **SF10, coding-rate setting 2, BW125 kHz, implicit header, no PHY CRC, sync-word parameter 0x00, nominal decoded length 68**. For this packet the receiver's sync-word check is not decisive; the separate application CRC-16 provides the decisive integrity check.

The recovered ACK is:

```text
TM,ACK,1,GET HK,HK,V=4.51,I=0.1,T=21.82,P=996.24,CO2=432,UP=132*18FC
```

The `*18FC` field is the CRC-16/CCITT-FALSE of the preceding bytes, calculated with polynomial `0x1021` and initial value `0xFFFF` (using `binascii.crc_hqx`). It confirms the message, from which the requested fields are extracted: CO2 **432 ppm**, uptime **132 seconds**.

**Validation limit:** The large original `vela_band_0136.sigmf-data` was not included in the archived ZIP and the review environment lacks `gr-lora_sdr`. The parser and CRC checker were tested against the preserved decoded ACK; a fresh end-to-end execution from this original recording remains to be verified on a GNU Radio host. Do not confuse the previous manual decode log with a newly performed end-to-end test.

### Reproduction

On Ubuntu, install GNU Radio and the numerical libraries for the script's signal extraction:

```bash
sudo apt update
sudo apt install -y gnuradio git cmake build-essential python3-numpy python3-scipy
```

Install [`gr-lora_sdr`](https://github.com/tapparelj/gr-lora_sdr) using the build instructions **matching your installed GNU Radio version**, then confirm the extension is importable by the same interpreter:

```bash
PYTHONNOUSERSITE=1 /usr/bin/python3 -c "from gnuradio import lora_sdr; print('gr-lora_sdr OK')"
```

Use your GNU Radio-compatible Python. Download the original `vela_band_0136.sigmf-data` from the supplied Hugging Face link and keep the `.sigmf-meta` file next to it:

```bash
PYTHONNOUSERSITE=1 /usr/bin/python3     132.py     132_DL_candidates/132_DL_3_32.5s.cf32
```

A frequency-selective burst scan is attempted first. If more targeted extraction is required, the archived manual extraction name `132_DL_3_32.5s.cf32` suggests a relevant IQ window **around 32.5 seconds after recording start** (approximately 01:37:17.5 UTC). This is a clue from the historical extraction name, not an independently verified burst timestamp. Select the actual reply interval after examining the spectrogram, for example:

```bash
PYTHONNOUSERSITE=1 python3 132.py vela_band_0136.sigmf-data --gr-python /usr/bin/python3 --window 31.5:34.5
```

This interval is an **illustrative inspection window**, not a substitute for checking the captured burst. The window above is only a candidate to inspect; use measured signal timing to make the final selection. If you already have the 500 kS/s extraction, pass it directly:

```bash
PYTHONNOUSERSITE=1 python3 132.py 132_DL_candidates/132_DL_3_32.5s.cf32 --gr-python /usr/bin/python3
```

The program searches SF7–SF10, CR1–CR4 and multiple lengths, verifies each recognized acknowledgement's CRC, and reports the first authenticated candidate:

```text
PAYLOAD: TM,ACK,1,GET HK,HK,V=4.51,I=0.1,T=21.82,P=996.24,CO2=432,UP=132*18FC
CRC-16/CCITT-FALSE: calculated=18FC, received=18FC
FLAG: GAIANSPACE{432_132}
```

Both the exact decoder configuration and the candidate-scan results are documented for reproducibility; the CO2 and uptime values are never pre-entered into the code.

### Solver Code

**`132.py`**

```python
#!/usr/bin/env python3
# Dependencies:
#   sudo apt update && sudo apt install -y gnuradio python3-numpy python3-scipy
#   Install the GNU Radio OOT module gr-lora_sdr against the SAME GNU Radio
#   version as /usr/bin/python3: https://github.com/tapparelj/gr-lora_sdr
#   Confirm with: /usr/bin/python3 -c "from gnuradio import lora_sdr"
# Python 3.10+ is required. The GNU Radio runtime is called as a subprocess.
"""Recover Challenge 132 GET HK ACK from original SigMF without preset answers.

  python3 132.py vela_band_0136.sigmf-data --gr-python /usr/bin/python3
  python3 132.py 132_DL_3_32.5s.cf32 --gr-python /usr/bin/python3

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
    check = subprocess.run([str(args.gr_python), '-c', 'from gnuradio import lora_sdr'],
                           capture_output=True, text=True, check=False)
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
```

## Flag

```text
GAIANSPACE{432_132}
```
