# 504-lunar-latch-up

| | |
|---|---|
| **Category** | 05 — Rad Hard Rampage |
| **Points** | 125 |

## Description

A single heavy ion hit the Foundation One power-management block and triggered a latch-up — a parasitic path that slams one bit high and holds it there, drawing current until someone cuts the rail. We dumped the register file mid-event. One bit in there is stuck high that should not be. Everything downstream is keyed off those registers, so until the latched bit is reset, the sealed mission payload stays sealed.

The dump is the eight power registers exactly as they latched, the integrity word the block stores for its own healthy state, and the sealed payload. One bit flipped high. Find it the only honest way — the one that makes the integrity word agree again — reset it, and the registers become the key they were always meant to be.

Reset the latch and open the payload.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `reg_dump.bin` — the latched register file, its integrity word, and the sealed payload
- `recovery_spec.md` — the power block's dump layout and key scheme

## Solution

### Steps

1. Parse the 32 register bytes, stored CRC32, and encrypted payload.
2. Enumerate every set bit and test clearing it.
3. Compare each corrected register image against the stored CRC32.
4. Derive the AES-128 key from the SHA-256 digest of the unique healthy register image.
5. Decrypt the payload with AES-ECB, remove PKCS#7 padding, and extract the flag.

### Reproduction

Run the provided solver with the challenge input files in the locations expected by the script.

```bash
python3 504.py
```

Expected relevant output:

```text
Stored CRC32:    0xA70B003B
Corrupted CRC32: 0x91B4A39B
Recovered register: R1
Cleared bit:        5
AES key: 178199ffd98d0f72841b0e909fac41d1
FLAG: GAIANSPACE{s1ngle_event_l4tchup}
```

### Exploit Code

```python

#!/usr/bin/env python3
import hashlib
import re
import struct
import zlib
from pathlib import Path

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

INPUT_FILE = Path("reg_dump.bin")


def main() -> None:
    data = INPUT_FILE.read_bytes()

    if len(data) < 52 or (len(data) - 36) % 16 != 0:
        raise ValueError("Invalid register dump length")

    registers = data[:32]
    expected_crc = struct.unpack_from("<I", data, 32)[0]
    ciphertext = data[36:]

    print(f"Stored CRC32:    0x{expected_crc:08X}")
    print(f"Corrupted CRC32: 0x{zlib.crc32(registers):08X}")

    matches: list[tuple[int, int, bytes]] = []

    # Clear each currently set bit and verify the healthy CRC.
    for byte_index in range(32):
        for bit_index in range(8):
            mask = 1 << bit_index

            if (registers[byte_index] & mask) == 0:
                continue

            candidate = bytearray(registers)
            candidate[byte_index] &= ~mask

            if zlib.crc32(candidate) == expected_crc:
                matches.append((byte_index, bit_index, bytes(candidate)))

    if len(matches) != 1:
        raise ValueError(f"Expected one CRC match, got {len(matches)}")

    byte_index, bit_index, healthy = matches[0]
    register_index = byte_index // 4

    print(f"Recovered register: R{register_index}")
    print(f"Cleared bit:        {bit_index + (byte_index % 4) * 8}")

    # Derive the AES-128 key from the healthy register image.
    key = hashlib.sha256(healthy).digest()[:16]

    cipher = Cipher(algorithms.AES(key), modes.ECB())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS#7 padding.
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()

    flag = plaintext.decode("ascii")

    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError("Decrypted plaintext is not a valid flag")

    print(f"AES key: {key.hex()}")
    print(f"FLAG: {flag}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{s1ngle_event_l4tchup}
```
