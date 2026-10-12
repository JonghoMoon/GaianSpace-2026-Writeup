# 203-signal-secrets

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 100 |

## Description

The mid-ocean array recorded the whole downlink while it was being hit. When the desk played it back, it was eighteen seconds of hiss and nothing else. The operator who caught it swears the attacker left a signature in the transmission, the way they always want the last word.

The recording is here. Reyes listened to it twice, called it dead air, and went for coffee. He heard noise because he was listening, and the one thing he did notice he threw away: there is writing in the sound if you look at it instead of playing it, but what it spells is not the answer. It is the instruction for the answer. The real message is carried under the noise floor, locked, and the writing tells you how to unlock it.

Work the recording in two passes and read the operator's parting line.

**Flag format:** `GAIANSPACE{...}`

**Attachments:** `downlink_signal.wav` — the array's recording of the malicious downlink

## Solution

### Steps

1. Inspect `downlink_signal.wav` (mono, 16 kHz, 16-bit PCM) in a spectrogram. The writing reads **`xor key = nimbus`**. It is an instruction, not the flag.
2. Read the least-significant bit of each signed PCM sample and pack consecutive bits MSB first.
3. XOR the resulting bytes with the repeating ASCII key `nimbus`. Test its six possible byte alignments; the correct alignment begins at offset **1**.
4. Search the decoded stream for the `GAIANSPACE{...}` envelope.

### Reproduction

The following source is the solver used for this challenge. Run it with its original working-directory layout and input paths.

```bash
python3 203.py
```

Expected relevant output:
```
Key offset: 1
FLAG: GAIANSPACE{tw0_l4yer_d0wnlink}
```

### Exploit Code

```python

import re
import numpy as np
from scipy.io import wavfile

sample_rate, samples = wavfile.read("downlink_signal.wav")

# Extract one least-significant bit from each PCM sample.
bits = (samples.astype(np.int32) & 1).astype(np.uint8)

# Pack bits into bytes in MSB-first order.
encoded = np.packbits(bits, bitorder="big").tobytes()

key = b"nimbus"

# Try all six possible XOR key alignments.
for offset in range(len(key)):
    decoded = bytes(
        value ^ key[(index + offset) % len(key)]
        for index, value in enumerate(encoded)
    )

    matches = re.findall(rb"GAIANSPACE\{[^}]+\}", decoded)

    for match in matches:
        print(f"Key offset: {offset}")
        print(f"FLAG: {match.decode('ascii')}")
```

## Flag

```text
GAIANSPACE{tw0_l4yer_d0wnlink}
```
