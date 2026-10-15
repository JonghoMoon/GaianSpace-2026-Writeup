#!/usr/bin/env python3
# Dependencies: pip install numpy soundfile

"""Decode the DiSEqC-style 22 kHz tone bursts in the scope WAV."""
from pathlib import Path
import numpy as np
import soundfile as sf

SOURCE = Path('coax_tap_22k.wav')
samples, rate = sf.read(SOURCE, dtype='float64')
if samples.ndim != 1 or rate != 48000:
    raise ValueError('Expected 48 kHz mono recording')

quarter_samples = rate // 4000
if samples.size % quarter_samples:
    raise ValueError('Unexpected sample count')
energy = np.sqrt(np.mean(samples.reshape(-1, quarter_samples) ** 2, axis=1))
on = energy > 0.1
edges = np.flatnonzero(np.diff(on.astype(np.int8))) + 1
starts = np.r_[0, edges]
lengths = np.diff(np.r_[starts, on.size])
runs = [(bool(on[start]), int(length)) for start, length in zip(starts, lengths)]

# Ignore the initial quiet region and treat trailing quiet as the final bit's off period.
if runs[0][0] or runs[-1][0]:
    raise ValueError('Expected leading and trailing silence')
active = runs[1:-1]
if len(active) % 2 != 1:
    raise ValueError('Expected alternating on/off durations')
bits = []
for index in range(0, len(active)-1, 2):
    tone, gap = active[index], active[index+1]
    if not tone[0] or gap[0] or tone[1] + gap[1] != 6:
        raise ValueError(f'Bad symbol near run {index}')
    bits.append({4: 0, 2: 1}[tone[1]])
last_tone = active[-1]
if not last_tone[0] or last_tone[1] not in (2, 4) or runs[-1][1] < 6-last_tone[1]:
    raise ValueError('Invalid final symbol')
bits.append({4: 0, 2: 1}[last_tone[1]])
if len(bits) % 9:
    raise ValueError('Incomplete 9-bit characters')

output = bytearray()
for start in range(0, len(bits), 9):
    word = bits[start:start+9]
    if sum(word) % 2 != 1:
        raise ValueError(f'Odd parity failed at character {start // 9}')
    output.append(int(''.join(str(bit) for bit in word[:8]), 2))
print(f'Decoded bits: {len(bits)}')
print(f'Parity-checked bytes: {len(output)}')
print(f'FLAG: {output.decode("ascii")}')
