
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

