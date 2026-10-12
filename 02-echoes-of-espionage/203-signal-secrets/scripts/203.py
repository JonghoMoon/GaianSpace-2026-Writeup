
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

