---
render_with_liquid: false
---

# 805-the-last-carrier

| | |
|---|---|
| **Category** | 08 — Silent Carrier |
| **Points** | 125 |

## Description

One carrier is still up. It is thin, it has wandered off the frequency the chip expects, and it keeps repeating a single frame into the dark. No demodulator on Meridian Kestrel will lock it. Oduya saved the raw sky, the sampler’s own card, and a physical-layer page with coffee through the handshake.

Pell thinks it is the same picture mode as the plate on the rack, one bit at a time. The page under the coffee says the letters ride four phases, and that the frame bows with the same word twice before it speaks.

Lock it by hand. Read HALCYON-7’s last transmission.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `halcyon_iq.cs16` — the raw sky, as the sampler wrote it
- `halcyon_iq.json` — the numbers the sampler printed on its own card
- `plheader_ref.md` — the physical-layer page, stained

## Hints

Two hints were released during the event:

1. **Four times around** — Oduya says the carrier is spinning faster than the letters. Count the spins before you believe the tone.
2. **The bow** — The frame announces itself with the same word twice. Turn the page until that word sits upright, and the letters follow it.

## Solution

### Steps

1. Load the interleaved 16-bit signed I/Q samples from the raw carrier capture.
2. Estimate carrier-frequency offset from the fourth-power QPSK spectrum and compensate for it.
3. Apply a root-raised-cosine matched filter and search eight possible symbol-sampling offsets.
4. Match the repeated `0x1ACFFC1D` synchronization word, estimate residual CFO and carrier phase.
5. Map the four constellation points to dibits, recover bytes, and extract the flag.

### Reproduction

Run the supplied Python solver with the original challenge files in the locations expected by its source code.

```bash
python3 805.py
```

Expected relevant output:

```text
Estimated CFO: 37502.29 Hz
Preamble alignment: sample offset=0, starting symbol=25
Residual CFO: -19.31 Hz; sync quality=0.99984
Recovered payload: b'FLAG:GAIANSPACE{qpsk_sof_lock_carrier}*rR'
FLAG: GAIANSPACE{qpsk_sof_lock_carrier}
```


### Receiver parameters and synchronization marker

Sample rate, symbol rate, samples per symbol, and RRC rolloff are now read directly from `halcyon_iq.json` rather than copied into the solver as constants. The sync word `0x1ACFFC1D` is the conventional CCSDS Attached Sync Marker (ASM), here searched twice in succession. This is a protocol-informed hypothesis, not a value explicitly stated in the short `plheader_ref.md`. The existing fourth-power CFO estimator, matched filter, timing/phase recovery, QPSK slicer, and flag detection are unchanged. Install dependencies with `python3 -m pip install numpy scipy`.

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies:
#   python3 -m pip install numpy scipy
"""Recover HALCYON-7's QPSK last carrier from raw CS16 IQ."""

import re
import json
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

# Receiver parameters are loaded from the challenge metadata.
METADATA_FILE = Path("halcyon_iq.json")
SAMPLE_RATE = 0.0
SYMBOL_RATE = 0.0
SPS = 0
RRC_ALPHA = 0.0
SYNC = 0x1ACFFC1D
CONSTELLATION = np.array([1+1j, -1+1j, -1-1j, 1-1j]) / np.sqrt(2)
DIBITS = ("00", "01", "11", "10")


def rrc_taps(alpha: float, sps: int, span: int) -> np.ndarray:
    times = np.arange(-span * sps // 2, span * sps // 2 + 1) / float(sps)
    taps = np.zeros(times.size, dtype=np.float64)
    for index, time in enumerate(times):
        if abs(time) < 1e-12:
            taps[index] = 1.0 + alpha * (4.0 / np.pi - 1.0)
        elif abs(abs(time) - 1.0 / (4.0 * alpha)) < 1e-12:
            taps[index] = alpha / np.sqrt(2.0) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * alpha))
                + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * alpha))
            )
        else:
            taps[index] = (
                np.sin(np.pi * time * (1.0 - alpha))
                + 4.0 * alpha * time * np.cos(np.pi * time * (1.0 + alpha))
            ) / (np.pi * time * (1.0 - (4.0 * alpha * time) ** 2))
    return taps / np.sqrt(np.sum(taps * taps))


def main() -> None:
    global SAMPLE_RATE, SYMBOL_RATE, SPS, RRC_ALPHA
    metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    SAMPLE_RATE = float(metadata["samp_rate_hz"])
    SYMBOL_RATE = float(metadata["symbol_rate_hz"])
    SPS = int(metadata["samples_per_symbol"])
    RRC_ALPHA = float(metadata["rrc_alpha"])
    if abs(SAMPLE_RATE / SYMBOL_RATE - float(SPS)) > 1e-6:
        raise ValueError("Inconsistent IQ sample rate and samples-per-symbol")
    raw = np.fromfile(Path(__file__).with_name("halcyon_iq.cs16"), dtype="<i2")
    if raw.size % 2:
        raise ValueError("Uneven I/Q sample count")
    iq = raw.reshape(-1, 2)
    signal = (iq[:, 0].astype(np.float64) + 1j * iq[:, 1].astype(np.float64)) / 32768.0

    # Estimate the dominant fourth-power tone (QPSK removes data phase under x^4).
    nfft = 131072
    fft = np.fft.fft(signal**4, n=nfft)
    frequencies = np.fft.fftfreq(nfft, d=1.0 / SAMPLE_RATE)
    coarse_cfo = float(frequencies[np.argmax(np.abs(fft))] / 4.0)
    print(f"Estimated CFO: {coarse_cfo:.2f} Hz")

    sample_index = np.arange(signal.size, dtype=np.float64)
    corrected = signal * np.exp(-2j * np.pi * coarse_cfo * sample_index / SAMPLE_RATE)
    filtered = fftconvolve(corrected, rrc_taps(RRC_ALPHA, SPS, 10), mode="same")

    preamble = f"{SYNC:032b}" * 2
    ideal_preamble = np.array([
        CONSTELLATION[DIBITS.index(preamble[index:index + 2])]
        for index in range(0, len(preamble), 2)
    ])

    best = None
    for offset in range(SPS):
        symbols = filtered[offset::SPS]
        for start in range(12, min(50, symbols.size - len(ideal_preamble))):
            ratio = symbols[start:start + 32] / ideal_preamble
            residual_hz = (np.angle(np.sum(ratio[1:] * np.conj(ratio[:-1])))
                           * SYMBOL_RATE / (2.0 * np.pi))
            relative_index = np.arange(32, dtype=np.float64)
            derotated = ratio * np.exp(-2j * np.pi * residual_hz * relative_index / SYMBOL_RATE)
            quality = float(abs(np.mean(derotated)) / np.mean(abs(derotated)))
            if best is None or quality > best[0]:
                phase = float(np.angle(np.mean(derotated)))
                best = (quality, offset, start, residual_hz, phase)

    if best is None:
        raise RuntimeError("No QPSK synchronization candidate")

    quality, offset, start, residual_hz, phase = best
    symbols = filtered[offset::SPS]
    symbol_index = np.arange(symbols.size, dtype=np.float64) - float(start)
    symbols *= np.exp(-1j * (phase + 2.0 * np.pi * residual_hz * symbol_index / SYMBOL_RATE))
    point_indices = np.argmin(np.abs(symbols[:, None] - CONSTELLATION[None, :]), axis=1)
    bits = "".join(DIBITS[int(index)] for index in point_indices)

    found = bits[2 * start:2 * start + 64]
    if found != preamble:
        raise RuntimeError(f"Invalid preamble: {found}")
    message_bits = bits[2 * start + 64:]
    message_bits = message_bits[:len(message_bits) // 8 * 8]
    message = bytes(int(message_bits[index:index+8], 2)
                    for index in range(0, len(message_bits), 8))
    matched = re.search(rb"GAIANSPACE\{[^}]+\}", message)
    if matched is None:
        raise RuntimeError(f"Flag not found. Payload: {message!r}")
    print(f"Preamble alignment: sample offset={offset}, starting symbol={start}")
    print(f"Residual CFO: {residual_hz:.2f} Hz; sync quality={quality:.5f}")
    print(f"Recovered payload: {message!r}")
    print(f"FLAG: {matched.group().decode('ascii')}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{qpsk_sof_lock_carrier}
```
