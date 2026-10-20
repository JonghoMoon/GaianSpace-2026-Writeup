# 501-cosmic-bit-blunder

| | |
|---|---|
| **Category** | 05 — Rad Hard Rampage |
| **Points** | 50 |

## Description

High in the Foundation One orbit, a single cosmic-ray proton punched through the flight computer and flipped exactly one bit in the key that protects the mission log. The log still decrypts to garbage. The reliability team wants the log back, and they are sure the rest of the key survived intact.

You have the ciphertext and the key as it reads now — one bit wrong, somewhere. Nothing else is damaged. The particle did not hit the data, only the key, and it only had the energy for one bit. The on-call engineer insists the whole key is corrupt and wants to rewrite it from scratch; that would take the log with it.

Undo the particle's one mistake and read the log.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `cipher.bin` — the encrypted mission log (AES, one block scheme)
- `corrupted.key` — the 128-bit key as it reads after the hit

## Hints

Two hints were released during the event:

1. **Only one** — Exactly one bit of the key is wrong. The data is fine. The search space is very small.
2. **Try them all** — There are only so many single-bit changes to a 16-byte key. Walk them until the log turns into words.

## Solution

### Analysis

The provided `corrupted.key` contains 16 bytes (128 bits) and the encrypted log
`cipher.bin` contains two 16-byte AES blocks. The challenge states that **exactly
one key bit was flipped**, while the ciphertext itself is intact. Consequently,
the original AES-128 key must be among precisely 128 candidates, each obtained
by toggling one bit of the corrupted key.

The solver numbers candidate bits from zero and uses the **least significant bit
first within each byte**:

```text
byte_index = bit_index // 8
bit_position = bit_index % 8
candidate_key[byte_index] ^= (1 << bit_position)
```

Each candidate is decrypted with AES-ECB, which processes individual 16-byte
blocks and does **not** use an IV. After decrypting, the solver removes PKCS#7
padding and checks for the expected `GAIANSPACE{...}` flag structure. Padding
alone is not sufficient to identify the correct candidate, since an incorrect
key could accidentally produce plausible padding.

The matching candidate toggles bit index **50**, i.e. bit **2** of key byte **6**
(both indices zero-based). The recovered key is
`a3f1c09e42b7d6150c8e2f9b71aa4e33`.

### Steps

1. Load the key and ciphertext, checking their lengths.
2. Toggle each of the 128 individual key bits in turn.
3. AES-ECB decrypt the ciphertext using each candidate key.
4. Verify PKCS#7 padding, ASCII decoding, and the flag prefix and suffix.
5. Report the matching correction and plaintext.

### Reproduction

Place the solver and this challenge's input files in the same directory and run:

```bash
python3 501.py
```

Expected relevant output:

```text
Corrected bit index: 50
Corrected byte index: 6
Corrected key: a3f1c09e42b7d6150c8e2f9b71aa4e33
FLAG: GAIANSPACE{s1ngle_event_upset}
```

### Solver Code

```python
#!/usr/bin/env python3
# Dependencies: cryptography (AES cipher and PKCS#7 padding)
# Install: python3 -m pip install cryptography

from pathlib import Path
from cryptography.hazmat.primitives.ciphers import (
    Cipher, algorithms, modes,
)
from cryptography.hazmat.primitives import padding

CIPHER_FILE = Path("cipher.bin")
KEY_FILE = Path("corrupted.key")


def decrypt_aes_ecb(ciphertext: bytes, key: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def main() -> None:
    ciphertext = CIPHER_FILE.read_bytes()
    corrupted_key = KEY_FILE.read_bytes()

    if len(corrupted_key) != 16:
        raise ValueError("Expected a 128-bit AES key")

    if not ciphertext or len(ciphertext) % 16 != 0:
        raise ValueError("Invalid AES ciphertext length")

    # Test all 128 bit positions, LSB-first within each byte.
    for bit_index in range(128):
        key = bytearray(corrupted_key)

        byte_index = bit_index // 8
        bit_position = bit_index % 8

        key[byte_index] ^= 1 << bit_position

        plaintext = decrypt_aes_ecb(ciphertext, bytes(key))

        # Validate PKCS#7 padding.
        try:
            unpadder = padding.PKCS7(128).unpadder()
            decoded = (
                unpadder.update(plaintext)
                + unpadder.finalize()
            )
        except ValueError:
            continue

        if not (
            decoded.startswith(b"GAIANSPACE{")
            and decoded.endswith(b"}")
        ):
            continue

        try:
            flag = decoded.decode("ascii")
        except UnicodeDecodeError:
            continue

        print(f"Corrected bit index: {bit_index}")
        print(f"Corrected byte index: {byte_index}")
        print(f"Corrected key: {key.hex()}")
        print(f"FLAG: {flag}")
        return

    raise RuntimeError("No valid single-bit correction found")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{s1ngle_event_upset}
```
