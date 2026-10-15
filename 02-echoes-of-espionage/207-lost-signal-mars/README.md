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

**1. Load the samples and receiver settings.**

`beacon_notes.md` describes a headerless stream of **little-endian IEEE 754 float32** real-valued samples, two-level differential keying, and **four samples per symbol**. The revised script reads this samples-per-symbol setting from the notes rather than assuming a value in the demodulator.

**2. Integrate and identify the repeated burst length.**

Read `deep_space_capture.f32` into 462,400 samples and average each group of four into 115,600 symbols. Since the sender repeats a short burst, calculate autocorrelation over the symbol stream (using the FFT) and look for periodic correlation peaks. The strong peaks occur at **289, 578 and 867 symbols**; choose the smallest strong length that divides the capture, **289 symbols per burst**. This yields **400 aligned repetitions**. Unlike the earlier solver, the script does **not** hardcode `BURST_SYMBOLS = 289`.

**3. Average the repetitions.**

Reshape the symbols into a `400 × 289` matrix and average down the repetition axis. This improves the signal-to-noise ratio enough for a zero threshold to distinguish the two transmitted levels.

**4. Differentially decode the levels.**

A level change from one symbol to the next is bit `1`; an unchanged level is bit `0`. There are **289 levels but 288 differential bits**, exactly **36 complete bytes**. Pack the bits MSB first. No initial bit is explicitly discarded by the code; one fewer bit arises naturally because differential decoding compares neighboring levels.

**5. Search for the flag envelope.**

The decoded byte stream starts with a non-printable prefix byte, followed by the flag. Do not interpret the prefix as a lost or discarded differential bit.

### Reproduction

Put `207.py`, `beacon_notes.md` and `deep_space_capture.f32` in the same directory and run:

```bash
python3 207.py
```

The installation command for `numpy` is at the top of `207.py`.

Expected relevant output:

```text
Samples per symbol: 4
Samples:     462400
Symbols:     115600
Burst size:  289 (autocorrelation=0.098)
Repetitions: 400
Decoded:     �GAIANSPACE{diff_enc0ded_and_buried}
FLAG: GAIANSPACE{diff_enc0ded_and_buried}
```

### Exploit Code

```python
#!/usr/bin/env python3
# Python dependencies: python3 -m pip install numpy
"""Find the beacon repetition period and demodulate differential symbols."""

import re
from pathlib import Path

import numpy as np

INPUT_FILE = Path("deep_space_capture.f32")
NOTES_FILE = Path("beacon_notes.md")


def samples_per_symbol(notes: str) -> int:
    # The receiver bench notes contain the recording's sample/symbol setting.
    match = re.search(r"\b([A-Za-z]+) samples per symbol\b", notes, re.IGNORECASE)
    if match is None:
        raise ValueError("Sample-per-symbol setting not found in the receiver notes")
    word = match.group(1).lower()
    values = {"one": 1, "two": 2, "three": 3, "four": 4, "eight": 8}
    if word in values:
        return int(values[word])
    if word.isdecimal():
        return int(word)
    raise ValueError(f"Unsupported sample-per-symbol description: {word}")


def recover_burst_length(symbols: np.ndarray) -> tuple[int, float]:
    # Correlate the entire noisy symbol recording with a delayed copy.
    centered = symbols.astype(np.float64) - float(symbols.mean())
    length = int(centered.size)
    padded_size = 2 * length
    freq = np.fft.rfft(centered, n=padded_size)
    ac = np.fft.irfft(freq * np.conjugate(freq), n=padded_size)
    max_lag = min(length // 4, 2048)
    lags = np.arange(max_lag + 1, dtype=np.int64)
    ac = ac[:max_lag + 1] / (length - lags)
    ac /= ac[0]

    # Repetitions produce peaks at the fundamental period and its multiples.
    baseline = ac[16:max_lag + 1]
    peak = float(np.max(baseline))
    threshold = max(0.04, peak * 0.70)
    possible = [
        index
        for index in range(16, max_lag)
        if float(ac[index]) >= threshold
        and float(ac[index]) >= float(ac[index - 1])
        and float(ac[index]) >= float(ac[index + 1])
        and length % index == 0
    ]
    if not possible:
        raise ValueError("Could not determine a repeated burst length")
    fundamental = int(min(possible))
    return fundamental, float(ac[fundamental])


def main() -> None:
    notes = NOTES_FILE.read_text(encoding="utf-8")
    sps = samples_per_symbol(notes)
    samples = np.fromfile(INPUT_FILE, dtype="<f4")
    if samples.size % sps != 0:
        raise ValueError("Incomplete final symbol")
    symbols = samples.reshape(-1, sps).mean(axis=1)
    burst_symbols, correlation = recover_burst_length(symbols)
    repetitions = int(symbols.size // burst_symbols)

    bursts = symbols.reshape(repetitions, burst_symbols)
    averaged = bursts.mean(axis=0)
    levels = averaged >= 0.0
    bits = np.not_equal(levels[1:], levels[:-1]).astype(np.uint8)

    # Differential decoding yields one fewer bit than the burst symbol count.
    complete_byte_bits = bits[: (int(bits.size) // 8) * 8]
    decoded = np.packbits(complete_byte_bits, bitorder="big").tobytes()

    print(f"Samples per symbol: {sps}")
    print(f"Samples:     {samples.size}")
    print(f"Symbols:     {symbols.size}")
    print(f"Burst size:  {burst_symbols} (autocorrelation={correlation:.3f})")
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
