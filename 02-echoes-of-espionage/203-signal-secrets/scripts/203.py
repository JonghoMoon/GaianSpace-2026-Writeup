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
