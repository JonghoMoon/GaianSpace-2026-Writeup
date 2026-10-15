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
