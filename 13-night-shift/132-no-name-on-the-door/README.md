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
- `vela_band_0136.sigmf-data` — raw SDR recording ([external download](https://huggingface.co/datasets/GaianSpace/ctf-2026-130/tree/main/132); intentionally not bundled in the writeup ZIP).
- `vela_band_0136.sigmf-meta` — SigMF capture metadata.
- `station_log.txt` — station event and receiver-lock history.

## Hints

Two hints were released during the event:

1. **It still signs its work** — GAIAN-723 never stopped checking its own sums. If a guess is right, the satellite will agree with you.
2. **Count the breaths** — A packet that won't say how long it is still takes exactly as long as it needs.

## Solution

### Analysis

The station log records a 433.175 MHz downlink lock at SF9 at **01:23:09 UTC**, followed by a configuration change from an unauthorized telecommand at **01:31:17 UTC**. The next log entry describes a missing header and unknown payload length. Thus, simply reusing the earlier SF9 **explicit-header** receiver does not recover the response.

The supplied SigMF metadata specifies:

| Property | Value |
|---|---|
| Capture start | `2026-10-11T01:36:45Z` |
| IQ format | signed complex int8 (`ci8`) |
| Sample rate | 1,999,999 samples/s |
| Recorder center frequency | 433,549,995 Hz |
| Downlink channel | approximately 433,175,000 Hz |

The downlink was isolated by translating the recorder's complex IQ to the 433.175 MHz channel, then using anti-alias FIR filtering and **4:1 decimation** to approximately **500 kS/s** (the actual rate is 499,999.75 samples/s). LoRa preamble analysis of the relevant burst establishes **SF10**; its recovered payload is consistent with **CR2 (4/6)** and an **implicit header**. The application carries a `*XXXX` CRC-16/CCITT-FALSE trailer, enabling independent validation even without a LoRa PHY CRC.

The original GNU Radio solution had successfully decoded a pre-extracted IQ file named `132_DL_candidates/132_DL_3_32.5s.cf32` using **SF10 / CR2 / implicit / LEN96**. `LEN96` is the *receiver's implicit payload-length hint*, not necessarily the number of printable characters in the ACK. The archive does not include that intermediate file; its filename must not be interpreted as an exact offset into the original SigMF.

#### Locate and distinguish the two ACKs

The previously attempted `31.5:34.5`-second window failed to recover the ACK. Inspecting the original recording revealed the relevant SF10 burst at about **34.79–35.87 seconds** from capture start, or approximately **01:37:19.79–01:37:20.87 UTC**. An extraction window of **34.65:36.25 seconds** includes synchronization margin and the end of the implicit-length decoding interval. The earlier `34.65:36.0` extraction was too short for a complete **LEN96** GNU Radio receiver run, though that alone was not proven to be the only cause of failure.

An earlier, separately CRC-validated `GET HK` reply occurs around 01:36:52 UTC. The two decoded responses are:

| Response | Approximate reception | CO2 | Uptime | CRC-16/CCITT-FALSE |
|---|---|---:|---:|---|
| `TM,ACK,0` | 01:36:52 UTC | 424 ppm | 105 s | `E945` (PASS) |
| **`TM,ACK,1`** | **01:37:20 UTC** | **432 ppm** | **132 s** | **`18FC` (PASS)** |

The challenge asks for the reply at **01:37**, so **ACK index 1** is the target. The check is not based merely on seeing a recognizable substring: for each packet, the application CRC is calculated over the message preceding `*` using CRC-16/CCITT-FALSE (polynomial `0x1021`, initial value `0xFFFF`).

The complete target packet is:

```text
TM,ACK,1,GET HK,HK,V=4.51,I=0.1,T=21.82,P=996.24,CO2=432,UP=132*18FC
```

The recovered flag is therefore:

```text
GAIANSPACE{432_132}
```

### Reproduction

The accompanying `132.py` preserves both approaches:

- **GNU Radio receiver (`--backend gnuradio`, default):** the original workstation solution, including the successful `.cf32` replay and SF/CR/implicit length sweep.
- **Independent offline receiver (`--backend offline`):** NumPy/SciPy implementation that was actually tested end-to-end on both the uploaded original SigMF and the extracted 500 kS/s IQ; it does not require GNU Radio.

#### Method A — Verified direct SigMF decoding without GNU Radio

Install the Python dependencies:

```bash
python3 -m pip install numpy scipy
```

Place `vela_band_0136.sigmf-data`, `vela_band_0136.sigmf-meta`, and `132.py` in one directory, then run:

```bash
python3 132.py vela_band_0136.sigmf-data \
  --backend offline --window 34.65:36.25
```

The default offline window is also `34.65:36.25`, but it is given explicitly above to preserve the analysis trail. The expected tested output is:

```text
SigMF window: 34.65..36.25 s, IQ samples: 800000
RECEIVER SETTINGS: SF=10 CR=2 implicit=True, data_offset=182424 samples
PAYLOAD: TM,ACK,1,GET HK,HK,V=4.51,I=0.1,T=21.82,P=996.24,CO2=432,UP=132*18FC
CRC-16/CCITT-FALSE: calculated=18FC, received=18FC valid=True
ACK INDEX: 1
FLAG: GAIANSPACE{432_132}
```

You can also save the extracted complex-float32 IQ while decoding:

```bash
python3 132.py vela_band_0136.sigmf-data \
  --backend offline --window 34.65:36.25 \
  --save-extracted 132_DL_34.65_36.25.cf32
```

Or independently decode an already extracted file:

```bash
python3 132.py 132_DL_34.65_36.25.cf32 --backend offline
```

For comparison, the earlier reply can be examined using `--ack-index 0 --window 7.25:8.65`. **It is not the answer to this challenge**, although its application CRC also validates.

#### Method B — Original GNU Radio approach

On Ubuntu, install GNU Radio with its compatible NumPy/SciPy packages, and compile/install [`gr-lora_sdr`](https://github.com/tapparelj/gr-lora_sdr) against the GNU Radio version used by `/usr/bin/python3`:

```bash
sudo apt update
sudo apt install -y gnuradio git cmake build-essential python3-numpy python3-scipy
```

On the original workstation a Python/NumPy conflict was avoided by disabling user-site packages with `PYTHONNOUSERSITE=1`. Check that the system GNU Radio imports successfully:

```bash
PYTHONNOUSERSITE=1 /usr/bin/python3 -c \
  "from gnuradio import lora_sdr; print('gr-lora_sdr OK')"
```

The **historically successful** replay, using the previously extracted IQ retained on the workstation, was:

```bash
PYTHONNOUSERSITE=1 /usr/bin/python3 132.py \
  132_DL_candidates/132_DL_3_32.5s.cf32
```

```text
CANDIDATE 1/1: 132_DL_candidates/132_DL_3_32.5s.cf32
  FOUND SF10 CR2 LEN96, valid application CRC=18FC
RECEIVER SETTINGS: SF=10 CR=2 implicit=True length_hint=96
PAYLOAD: TM,ACK,1,GET HK,HK,V=4.51,I=0.1,T=21.82,P=996.24,CO2=432,UP=132*18FC
CRC-16/CCITT-FALSE: calculated=18FC, received=18FC
FLAG: GAIANSPACE{432_132}
```

To test GNU Radio directly on the *original* SigMF, use the corrected longer extraction window:

```bash
PYTHONNOUSERSITE=1 /usr/bin/python3 132.py \
  vela_band_0136.sigmf-data \
  --backend gnuradio --gr-python /usr/bin/python3 \
  --window 34.65:36.25 \
  --sfs 10 --crs 2 --lengths 96
```

**Verification distinction:** the offline raw-SigMF command above is **PASS** and the historical GNU Radio `.cf32` replay is **PASS**, but this *new* longer-window **GNU Radio raw-SigMF invocation has not been independently executed** in the review environment. The `--window 31.5:34.5` command failed and should not be used as the reproducing command.

### Solver Code

The source below is identical to the downloadable `132.py` and contains both backends. GNU Radio is not imported in offline mode, so its availability and Python environment cannot affect that path.

**`132.py`**

```python
#!/usr/bin/env python3
# Dependencies:
#   Offline decoder: python3 -m pip install numpy scipy
#   GNU Radio backend: sudo apt install -y gnuradio python3-numpy python3-scipy
#   Install the GNU Radio OOT module gr-lora_sdr against the SAME GNU Radio
#   version as /usr/bin/python3: https://github.com/tapparelj/gr-lora_sdr
#   Confirm with: PYTHONNOUSERSITE=1 /usr/bin/python3 -c "from gnuradio import lora_sdr"
# Python 3.10+ is required. The GNU Radio runtime is called as a subprocess.
"""Recover the 01:37 GET HK ACK using either an offline or GNU Radio decoder.

Verified offline direct-from-SigMF mode:
    python3 132.py vela_band_0136.sigmf-data --backend offline \
        --window 34.65:36.25

Workstation-verified GNU Radio mode on previously extracted IQ:
    PYTHONNOUSERSITE=1 /usr/bin/python3 132.py \
        132_DL_candidates/132_DL_3_32.5s.cf32

GNU Radio raw-SigMF mode (the longer window has not been runtime-verified):
    PYTHONNOUSERSITE=1 /usr/bin/python3 132.py vela_band_0136.sigmf-data \
        --backend gnuradio --window 34.65:36.25 \
        --sfs 10 --crs 2 --lengths 96

The decoder validates the embedded CRC-16/CCITT-FALSE and chooses ACK index 1,
which corresponds to the command acknowledgement at 01:37 UTC.
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
from scipy import fft, signal



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


HAMMING = np.asarray([0, 23, 45, 58, 78, 89, 99, 116,
                      139, 156, 166, 177, 197, 210, 232, 255], dtype=np.int64)
HAMMING_45 = np.asarray([0, 24, 40, 48, 72, 80, 96, 120,
                         136, 144, 160, 184, 192, 216, 232, 240], dtype=np.int64)
ACK = re.compile(rb'(TM,ACK,(\d+),GET HK,HK,[^\r\n\x00]{0,150}?CO2=(\d+),UP=(\d+)\*([0-9A-Fa-f]{4}))')


def whitening(length: int) -> list[int]:
    state = 255
    output: list[int] = []
    for _ in range(int(length)):
        output.append(int(state))
        feedback = ((state >> 7) ^ (state >> 5) ^ (state >> 4) ^ (state >> 3)) & 1
        state = int(((state << 1) & 255) | feedback)
    return output


WHITENING = whitening(512)


def ref_chirp(sf: int) -> np.ndarray:
    samples = np.arange(1 << int(sf), dtype=np.float64)
    return np.exp(1j * np.pi * (samples * samples / float(1 << int(sf)) - samples))


def measure(samples: np.ndarray, start: float, sf: int,
            cfo_bins: float = 0.0, fft_multiplier: int = 1,
            downchirp: bool = False) -> tuple[float, float]:
    width = int(1 << int(sf))
    index = int(round(float(start))) + np.arange(width, dtype=np.int64) * 4
    if int(index[0]) < 0 or int(index[-1]) >= int(samples.size):
        return -1.0, 0.0
    ref = ref_chirp(int(sf))
    correction = np.exp(-2j * np.pi * float(cfo_bins) * np.arange(width, dtype=np.float64) / float(width))
    values = samples[index] * (ref if bool(downchirp) else np.conj(ref)) * correction
    spectrum = np.abs(fft.fft(values, n=width * int(fft_multiplier))) ** 2
    peak = int(np.argmax(spectrum))
    energy = float(np.sum(np.abs(values) ** 2)) * float(width)
    return float(peak) / float(fft_multiplier), float(spectrum[peak]) / (energy + 1e-30)


def synchronize(samples: np.ndarray, sf: int = 10) -> dict[str, float | int]:
    stride = (1 << int(sf)) * 4
    grid = np.arange(0, int(samples.size) - stride, stride, dtype=np.int64)
    measurements = np.asarray([measure(samples, float(p), sf) for p in grid], dtype=np.float64)
    candidate = None
    for index in range(int(grid.size) - 3):
        near = (measurements[index:index + 4, 0] - measurements[index, 0] + 512.0) % 1024.0 - 512.0
        if float(np.min(measurements[index:index + 4, 1])) > 0.20 and float(np.max(np.abs(near))) <= 1.0:
            candidate = int(index)
            break
    if candidate is None:
        raise ValueError('SF10 preamble was not found in this time window.')
    down_index = None
    for j in range(candidate + 4, min(candidate + 40, int(grid.size) - 1)):
        if measure(samples, float(grid[j]), sf, downchirp=True)[1] > 0.18 and \
           measure(samples, float(grid[j + 1]), sf, downchirp=True)[1] > 0.35:
            down_index = int(j)
            break
    if down_index is None:
        raise ValueError('Could not find the downchirp pair.')
    p, d = int(grid[candidate]), int(grid[down_index])
    up = measure(samples, float(p + stride), sf, fft_multiplier=64)[0]
    down = measure(samples, float(d + stride), sf, fft_multiplier=64, downchirp=True)[0]
    up_signed = (up + 512.0) % 1024.0 - 512.0
    down_signed = (down + 512.0) % 1024.0 - 512.0
    coarse_cfo = (up_signed + down_signed) / 2.0
    correlation = np.vdot(samples[p:p + 3 * stride], samples[p + stride:p + 4 * stride])
    fractional_cfo = float(np.angle(correlation)) / (2.0 * np.pi)
    cfo = float(round(coarse_cfo - fractional_cfo)) + fractional_cfo
    down_start = float(d) - (up_signed - down_signed) * 2.0
    data_start = int(round(down_start + 2.25 * float(stride)))
    return {'data_start': data_start, 'cfo_bins': cfo}


def decode_block(symbols: np.ndarray, sf_effective: int, cr: int) -> tuple[list[int], int]:
    labels = np.asarray(symbols, dtype=np.int64)
    gray = labels ^ (labels >> 1)
    width = int(cr + 4)
    bits = np.zeros((int(sf_effective), width), dtype=np.int64)
    for col in range(width):
        for row in range(int(sf_effective)):
            bits[(col - row - 1) % int(sf_effective), col] = (int(gray[col]) >> (int(sf_effective) - 1 - row)) & 1
    words = bits.dot(1 << np.arange(width - 1, -1, -1, dtype=np.int64))
    lut = (HAMMING_45 if int(cr) == 1 else HAMMING) >> (8 - width)
    result: list[int] = []
    errors = 0
    for word in words:
        distances = [int(int(word) ^ int(entry)).bit_count() for entry in lut]
        index = int(np.argmin(np.asarray(distances, dtype=np.int64)))
        result.append(int(f'{index:04b}'[::-1], 2))
        errors += int(distances[index])
    return result, errors


def decode_ack(samples: np.ndarray) -> tuple[bytes, int, int, int, int, int] | None:
    sf = 10
    sync = synchronize(samples, sf)
    stride = 4096
    for adjustment in (0, -2, 2, -4, 4):
        symbols: list[int] = []
        for i in range(160):
            start = int(sync['data_start']) + int(adjustment) + int(i) * stride
            if start < 0 or start + stride > int(samples.size):
                break
            symbol, _ = measure(samples, float(start), sf, float(sync['cfo_bins']))
            symbols.append(int(round(symbol)))
        if len(symbols) < 14:
            continue
        for symbol_shift in (0, 1, -1, 2, -2):
            modulus = 1 << sf
            nibs, _ = decode_block(((np.asarray(symbols[:8], dtype=np.int64) - 1 + int(symbol_shift)) % modulus) // 4, 8, 4)
            for first in range(8, len(symbols) - 5, 6):
                decoded, _ = decode_block((np.asarray(symbols[first:first + 6], dtype=np.int64) - 1 + int(symbol_shift)) % modulus, sf, 2)
                nibs.extend(decoded)
            raw = bytes(int(nibs[i] | (nibs[i + 1] << 4)) for i in range(0, len(nibs) - 1, 2))
            data = bytes(int(value) ^ int(WHITENING[i]) for i, value in enumerate(raw))
            for match in ACK.finditer(data):
                message = bytes(match.group(1))
                body, hex_crc = message.rsplit(b'*', 1)
                calculated = int(binascii.crc_hqx(body, 0xFFFF))
                received = int(hex_crc, 16)
                if calculated == received:
                    return message, int(match.group(2)), int(match.group(3)), int(match.group(4)), calculated, int(sync['data_start'])
    return None




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

ACK_PATTERN = re.compile(rb'(TM,ACK,(\d+),GET HK,HK,[^\r\n]{0,200}?CO2=(\d+),UP=(\d+)\*[0-9A-Fa-f]{4})')


def extract_valid_ack(data: bytes, ack_index: int) -> tuple[int, int, bytes, int] | None:
    for match in ACK_PATTERN.finditer(data):
        message = match.group(1)
        body, tag = message.rsplit(b'*', 1)
        calculated = int(binascii.crc_hqx(body, 0xFFFF))
        received = int(tag, 16)
        if calculated != received or int(match.group(2)) != int(ack_index):
            continue
        return int(match.group(3)), int(match.group(4)), message, calculated
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
             timeout: float, ack_index: int) -> tuple[int, int, bytes, int, int, int, int] | None:
    # First try extended lengths: a valid ACK can be a prefix of a longer decoded buffer.
    for sf in sfs:
        for cr in crs:
            for length in lengths:
                try:
                    data, log = run_worker(gr_python, worker, iq, output, sf, cr, length, timeout)
                except subprocess.TimeoutExpired:
                    print(f'  SF{sf} CR{cr} LEN{length}: timeout', flush=True)
                    continue
                candidate = extract_valid_ack(data, ack_index)
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
    parser.add_argument('--backend', choices=['offline', 'gnuradio'], default='gnuradio',
                        help='Select offline NumPy/SciPy demodulator or GNU Radio receiver.')
    parser.add_argument('--ack-index', type=int, default=1,
                        help='Requested GET HK ACK sequence (default 1 for 01:37 UTC).')
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
    if not args.input.exists():
        parser.error(f'Input does not exist: {args.input}')

    if args.backend == 'offline':
        if args.input.suffix.lower() == '.cf32':
            samples = np.fromfile(args.input, dtype='<c8')
        else:
            raw, fs, center = load_sigmf_info(args.input, args.meta)
            # The selected burst is the 01:37 SF10 ACK seen in the RF survey.
            selected_window = args.window if args.window is not None else (34.65, 36.25)
            a, b = selected_window
            samples = extract_iq(raw, fs, center, float(a), float(b), float(args.frequency))
            print(f'SigMF window: {a:.2f}..{b:.2f} s, IQ samples: {samples.size}', flush=True)
            if args.save_extracted is not None:
                samples.tofile(args.save_extracted)
                print('EXTRACTED IQ:', args.save_extracted)
        result = decode_ack(samples)
        if result is None:
            raise RuntimeError('No application-CRC-valid SF10 CR2 GET HK ACK in selected IQ.')
        payload, seq, co2, uptime, crc, sync_offset = result
        print(f'RECEIVER SETTINGS: SF=10 CR=2 implicit=True, data_offset={sync_offset} samples')
        print('PAYLOAD:', payload.decode('ascii'))
        print(f'CRC-16/CCITT-FALSE: calculated={crc:04X}, received={crc:04X} valid=True')
        print('ACK INDEX:', seq)
        if int(seq) != int(args.ack_index):
            raise ValueError(f'CRC-valid ACK {seq} != target {args.ack_index}')
        print(f'FLAG: GAIANSPACE{{{co2}_{uptime}}}')
        return 0

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
                             args.lengths, float(args.timeout), int(args.ack_index))
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

### Flag

```text
GAIANSPACE{432_132}
```
