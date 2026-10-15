#!/usr/bin/env python3
"""Extract short A-band transmissions after each B-band telecommand."""
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly

root = Path(__file__).resolve().parent
fs = 1_999_999.0
center_hz = 433_549_995.0
signal_hz = 433_174_995.0
raw = np.memmap(root / 'vela_band_0114.sigmf-data', dtype=np.int8, mode='r')
windows = [(1, 4.17, 0.48), (2, 16.03, 0.55), (3, 28.47, 0.40), (4, 39.22, 0.45)]
for idx, start, duration in windows:
    lo = int(start * fs)
    hi = int((start + duration) * fs)
    i8 = np.asarray(raw[2 * lo:2 * hi], dtype=np.float32).reshape(-1, 2)
    iq = np.asarray(i8[:, 0] + 1j * i8[:, 1], dtype=np.complex64)
    n = np.arange(iq.size, dtype=np.float64)
    shift_hz = signal_hz - center_hz
    iq *= np.exp(-2j * np.pi * shift_hz * n / fs).astype(np.complex64)
    result = resample_poly(iq, 1, 4).astype(np.complex64)
    path = root / f'131_A_reply_{idx}.cf32'
    result.tofile(path)
    print(path.name, result.size, path.stat().st_size)
