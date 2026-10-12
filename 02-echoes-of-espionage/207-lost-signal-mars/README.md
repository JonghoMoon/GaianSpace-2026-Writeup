# 207-lost-signal-mars

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 75 |

## Description

A listening post that usually eavesdrops on satellites just a few thousand kilometres up was pointed, for once, at something very far away. It came back with a file that every meter on the rack calls empty. There is a message in it. The distance just buried it, and the sender was clever about how it keyed it.

Close in, a downlink is loud and you read it on the first pass. This was not close in. The sender is so far off that one copy of its message is weaker than the noise sitting on top of it, so it says the same thing again, and again, and again, and trusts the far end to be patient. And it does not spell with loud-and-quiet, which would be easy to fake across that much noise; it spells with change and no-change, so a single stolen glance tells you nothing even after you clean it up. Reyes looked at one slice, saw snow, and moved on.

Recover what the distant transmitter kept repeating.

**Flag format:** `GAIANSPACE{...}`

**Attachments:** `beacon_notes.md` — the operator's settings for the capture, `deep_space_capture.f32` — the raw recording from the post

## Solution

### Steps

1. Read little-endian float32 samples from `deep_space_capture.f32` and the symbol settings from `beacon_notes.md`.
2. Average **four samples per symbol**. The capture contains **115,600 symbols**, arranged as **400 repeats × 289 symbols**.
3. Average the aligned repeats to improve SNR.
4. Turn averaged amplitudes into two levels, then decode bits by testing whether each level differs from its predecessor (`change = 1`).
5. Pack the recovered bits MSB first and locate the flag. The first decoded byte can contain a non-printable prefix and is not part of the flag.

### Reproduction

The following source is the solver used for this challenge. Run it with its original working-directory layout and input paths.

```bash
python3 207.py
```

Expected relevant output:
```
Samples:     462400
Symbols:     115600
Burst size:  289
Repetitions: 400
Decoded:     �GAIANSPACE{diff_enc0ded_and_buried}
FLAG: GAIANSPACE{diff_enc0ded_and_buried}
```

### Exploit Code

```python

#!/usr/bin/env python3
import re
from pathlib import Path

import numpy as np

INPUT_FILE = Path("deep_space_capture.f32")
SAMPLES_PER_SYMBOL = 4
BURST_SYMBOLS = 289


def main() -> None:
    # Read raw little-endian IEEE float32 samples.
    samples = np.fromfile(INPUT_FILE, dtype="<f4")

    if samples.size % SAMPLES_PER_SYMBOL != 0:
        raise ValueError("Invalid number of samples")

    # Integrate four samples into one symbol.
    symbols = samples.reshape(-1, SAMPLES_PER_SYMBOL).mean(axis=1)

    if symbols.size % BURST_SYMBOLS != 0:
        raise ValueError("Incomplete repetition sequence")

    repetitions = int(symbols.size // BURST_SYMBOLS)

    # Coherently average repeated bursts to suppress noise.
    bursts = symbols.reshape(repetitions, BURST_SYMBOLS)
    averaged = bursts.mean(axis=0)

    # Recover two-level transmitted symbols.
    levels = averaged >= 0.0

    # Differential decoding: a level change represents bit 1.
    bits = np.not_equal(levels[1:], levels[:-1])
    bits = bits.astype(np.uint8)

    # The first decoded bit is outside the byte-aligned message.
    message_bits = bits[: (bits.size // 8) * 8]
    decoded = np.packbits(message_bits, bitorder="big").tobytes()

    print(f"Samples:     {samples.size}")
    print(f"Symbols:     {symbols.size}")
    print(f"Burst size:  {BURST_SYMBOLS}")
    print(f"Repetitions: {repetitions}")
    print(f"Decoded:     {decoded.decode('ascii', errors='replace')}")

    match = re.search(rb"GAIANSPACE\{[^}]+\}", decoded)
    if match is None:
        raise ValueError("Flag not found")

    print(f"FLAG: {match.group().decode('ascii')}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{diff_enc0ded_and_buried}
```
