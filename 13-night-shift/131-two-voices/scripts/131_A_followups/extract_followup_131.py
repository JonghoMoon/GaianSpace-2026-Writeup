#!/usr/bin/env python3
"""Extract subsequent GAIAN-723 candidate LoRa bursts from the original SigMF recording."""
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly

root = Path(__file__).resolve().parent
fs = 1_999_999.0
center = 433_549_995.0
target = 433_174_995.0
raw = np.memmap(root / 'vela_band_0114.sigmf-data', dtype=np.int8, mode='r')

# Include preamble lead-in and trailing silence around observed A-band bursts.
windows = [(2, 14.60, 1.20), (3, 26.96, 1.20), (4, 37.80, 1.20)]
for index, start_sec, duration_sec in windows:
    begin = int(start_sec * fs)
    end = int((start_sec + duration_sec) * fs)
    pairs = np.asarray(raw[begin * 2:end * 2], dtype=np.float32).reshape(-1, 2)
    iq = (pairs[:, 0] + 1j * pairs[:, 1]).astype(np.complex64)
    sample_idx = np.arange(iq.size, dtype=np.float64)
    iq *= np.exp(-2j * np.pi * (target - center) * sample_idx / fs).astype(np.complex64)
    result = resample_poly(iq, 1, 4).astype(np.complex64)
    destination = root / f'131_A_{index}.cf32'
    result.tofile(destination)
    print(f'{destination.name}: {result.size} samples, {destination.stat().st_size} bytes, approximately {fs / 4:.2f} S/s')
