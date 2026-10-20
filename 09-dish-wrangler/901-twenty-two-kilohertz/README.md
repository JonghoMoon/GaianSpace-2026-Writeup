# 901-twenty-two-kilohertz

| | |
|---|---|
| **Category** | 09 — Dish Wrangler |
| **Points** | 50 |

## Description

The deep-field ground station **Kestrel Array** has started disobeying. During the uplink window the dish walks off the bird, comes back, and walks off again. Engineer Ravi Lindqvist clipped a scope onto the motor coax to hear who is giving the orders.

What he caught is not a voice. It is the old whistle the positioner uses when it wants the motor to move, chopped into moments that are lit and moments that are not. Lindqvist is sure the whistle is spelling. He is less sure he wants to know who taught it to spell.

A jacket label on the coax reads `LNB 10.6`. Someone added `listen for the pilot` in pencil. The night log also mentions a Morse practice tape in the same drawer as the scope. Lindqvist played it. It is a person sending the station callsign, badly, and it is not this recording.

Read what the motor was told.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `coax_tap_22k.wav` — scope tap from the motor coax
- `diseqc_notes.md` — Lindqvist’s card, coffee on the corner

## Hints

Two hints were released during the event:

1. **The lamp** — Lindqvist says ignore the song. Watch whether the lamp is lit.
2. **Manners** — A long glow and a short glow are not the same word. He saves one tick in each little group for luck, and luck is not one of the letters.

## Solution

### Analysis

The coax recording is a 48-kHz mono waveform containing a gated 22-kHz pilot tone. The carrier pitch itself is not an encoded character stream, and the Morse tape mentioned in the description is a distractor. The useful information is the **tone-on duty cycle**.

In the challenge's DiSEqC-style signaling, each bit occupies 1.5 ms:

| Bit | Tone ON | Tone OFF | Total |
|---|---:|---:|---:|
| `0` | 1.0 ms | 0.5 ms | 1.5 ms |
| `1` | 0.5 ms | 1.0 ms | 1.5 ms |

The solver reads 0.25-ms blocks, calculates RMS amplitude, and thresholds the result to obtain alternating tone and silence runs. Accordingly, on durations of **4 blocks** and **2 blocks** represent bits 0 and 1, respectively. It verifies the complete 1.5-ms symbol periods before converting them into bits.

Each nine-bit group carries **eight data bits (MSB first) plus one odd-parity bit**. A group must contain an odd number of set bits. The recovered bytes form a plain ASCII message; no additional XOR or ciphertext layer is used.

### Reproduction

Install the Python dependencies:

```bash
python3 -m pip install numpy soundfile
```

Place `coax_tap_22k.wav` and `901.py` together, then execute:

```bash
python3 901.py
```

Expected output:

```text
Decoded bits: 252
Parity-checked bytes: 28
FLAG: GAIANSPACE{dis3qc_t0ne_b1ts}
```

The 252 decoded bits correspond to 28 parity-checked, nine-bit characters. This directly validates the timing/parity interpretation rather than simply searching the WAV file for a preselected answer.

### Solver Code

```python
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
```

## Flag

```text
GAIANSPACE{dis3qc_t0ne_b1ts}
```
