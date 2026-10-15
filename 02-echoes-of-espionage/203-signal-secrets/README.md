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

**1. Recover the instruction from the spectrogram.**

The recording is a mono, **16 kHz, 16-bit PCM** WAV file. Listening reveals noise, but a time-frequency plot exposes the text **`xor key = nimbus`**. This is the *key hint*, not the flag.

The updated `203.py` implements this discovery: it calculates an STFT of the original PCM samples, selects the **900–3400 Hz** band, thresholds the spectral magnitude at **45 dB (relative to full-scale PCM sample units)** and saves `203_spectrogram.png`. Tesseract OCR then reads the text and extracts the key after `xor key =`. The threshold is a visualization setting for this particular recording, not a secret or a precomputed key. If OCR varies with the local installation, inspect the saved image directly.

[!spectrogram](./images/203_spectrogram.png)

**2. Recover the lower-level bitstream.**

Read the least-significant bit of each 16-bit PCM sample, retain time order and pack bits **MSB first** into bytes. These bytes are still encrypted with a repeating XOR key.

**3. Find the key-phase offset and decode.**

Use the key obtained by OCR, testing all six **key-index offsets** (`0` through `5`). This does *not* change the byte boundaries: it only moves the starting index into the repeating key. Offset **1** produces the flag envelope.

**4. Extract the flag.**

Search the decoded byte stream for `GAIANSPACE{...}`.

### Reproduction

Put `203.py` and `downlink_signal.wav` in the same directory and run:

```bash
python3 203.py
```

Python dependencies and the Tesseract OCR installation command are documented at the top of `203.py`.

Expected output:

```text
Spectrogram OCR: xor key = nimbus
Spectrogram image: 203_spectrogram.png
Recovered XOR key: nimbus
Key offset: 1
FLAG: GAIANSPACE{tw0_l4yer_d0wnlink}
```

### Exploit Code

```python
#!/usr/bin/env python3
# Python dependencies: python3 -m pip install numpy scipy Pillow pytesseract
# System dependency (Ubuntu/Debian): sudo apt install tesseract-ocr
"""Read the spectrogram hint, then recover the LSB/XOR message from a WAV."""

import re
from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image
from scipy.io import wavfile
from scipy.signal import stft

INPUT_FILE = Path("downlink_signal.wav")
SPECTROGRAM_FILE = Path("203_spectrogram.png")
FLAG_PATTERN = rb"GAIANSPACE\{[^}]+\}"


def extract_key(samples: np.ndarray, sample_rate: int) -> bytes:
    # Make a time/frequency image directly from the WAV's signed PCM samples.
    freqs, _, spectrum = stft(
        samples.astype(np.float64),
        fs=int(sample_rate),
        nperseg=512,
        noverlap=448,
    )
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(spectrum), 1e-9))
    frequency_mask = (freqs >= 900.0) & (freqs <= 3400.0)
    region = magnitude_db[frequency_mask][::-1, :]

    # The watermark has a much stronger spectral amplitude than the noise.
    # This threshold is a visualization parameter, not the recovered XOR key.
    binary_pixels = np.where(region > 45.0, 0, 255).astype(np.uint8)
    image = Image.fromarray(binary_pixels, mode="L").resize((1530, 360))
    image.save(SPECTROGRAM_FILE)

    hint = str(pytesseract.image_to_string(image, config="--psm 7")).strip()
    print(f"Spectrogram OCR: {hint}")
    print(f"Spectrogram image: {SPECTROGRAM_FILE}")

    match = re.search(r"xor\s+key\s*=\s*([A-Za-z]+)", hint, re.IGNORECASE)
    if match is None:
        raise ValueError(
            "OCR could not read the XOR key. Inspect the saved spectrogram image."
        )
    return match.group(1).lower().encode("ascii")


def main() -> None:
    sample_rate, samples = wavfile.read(INPUT_FILE)
    if samples.dtype != np.int16 or samples.ndim != 1:
        raise ValueError("Expected 16-bit mono PCM WAV")

    key = extract_key(samples, int(sample_rate))
    print(f"Recovered XOR key: {key.decode('ascii')}")

    # Use the least significant bit of each PCM sample, then pack MSB-first.
    bits = (samples.astype(np.int32) & 1).astype(np.uint8)
    encoded = np.packbits(bits, bitorder="big").tobytes()

    # Search key-phase offsets; the byte boundaries are not changed.
    for offset in range(len(key)):
        decoded = bytes(
            int(value) ^ int(key[(index + offset) % len(key)])
            for index, value in enumerate(encoded)
        )
        match = re.search(FLAG_PATTERN, decoded)
        if match is not None:
            print(f"Key offset: {offset}")
            print(f"FLAG: {match.group().decode('ascii')}")
            return
    raise ValueError("No flag found with the recovered spectrogram key")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{tw0_l4yer_d0wnlink}
```
