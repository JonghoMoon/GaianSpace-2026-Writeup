---
render_with_liquid: false
---

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

## Hints

Two hints were released during the event:

1. **One bit too high** — The latch set a single bit. You only need to consider bits that are currently high; clearing the right one makes the stored integrity word match.
2. **The registers are the key** — Once the integrity word agrees, the corrected register bytes derive the key that opens the payload. The spec says how.

## Solution

### Analysis

The layout in `recovery_spec.md` identifies the three sections of
`reg_dump.bin`:

| Offset | Length | Meaning |
|---|---:|---|
| `0x00` | 32 bytes | Registers `R0`–`R7` (eight little-endian 32-bit values) |
| `0x20` | 4 bytes | Stored CRC32 of the **healthy** 32 register bytes, little-endian |
| `0x24` | Remainder | AES-ECB ciphertext with PKCS#7 padding |

The damaged register bytes no longer match their stored CRC32. Unlike the
single-event upset in challenge 501, this latch-up caused **one bit to stick
at 1**. Recovering the healthy image therefore means clearing a currently-set
bit, not blindly toggling every possible bit. The solver enumerates all such
candidates and retains those satisfying:

$$
\mathrm{CRC32}(\text{candidate register bytes})
=\text{stored CRC32}.
$$

The dump yields a **single** matching correction: register `R1`, bit 5
(bit numbering starts at the least significant bit of each 32-bit register).
The resulting 32-byte healthy register image is hashed to derive the AES key:

```text
AES-128 key = SHA256(healthy R0..R7 bytes)[:16]
           = 178199ffd98d0f72841b0e909fac41d1
```

AES-ECB decryption and PKCS#7 unpadding then recover the flag. The CRC32 is an
integrity check for this constrained one-bit search, not a cryptographic
message authentication code.

### Steps

1. Split the dump into registers, stored little-endian CRC32, and ciphertext.
2. Clear each set register bit in turn; compute CRC32 for each candidate.
3. Require a unique match against the healthy-state integrity word.
4. Hash the recovered 32 register bytes and take the first 16 SHA-256 bytes.
5. AES-ECB decrypt, remove PKCS#7 padding, and check the flag format.

### Reproduction

Place the solver and this challenge's input files in the same directory and run:

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
# Dependencies: cryptography (AES cipher and PKCS#7 padding)
# Install: python3 -m pip install cryptography

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

    # A latch-up only sets a bit from 0 to 1, so recovery clears
    # currently set bits rather than toggling arbitrary bits.
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
