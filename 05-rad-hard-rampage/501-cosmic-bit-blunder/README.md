# 501-cosmic-bit-blunder

| | |
|---|---|
| **Category** | 05 — Rad Hard Rampage |
| **Points** | 55 |

## Description

High in the Foundation One orbit, a single cosmic-ray proton punched through the flight computer and flipped exactly one bit in the key that protects the mission log. The log still decrypts to garbage. The reliability team wants the log back, and they are sure the rest of the key survived intact.

You have the ciphertext and the key as it reads now — one bit wrong, somewhere. Nothing else is damaged. The particle did not hit the data, only the key, and it only had the energy for one bit. The on-call engineer insists the whole key is corrupt and wants to rewrite it from scratch; that would take the log with it.

Undo the particle's one mistake and read the log.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `cipher.bin` — the encrypted mission log (AES, one block scheme)
- `corrupted.key` — the 128-bit key as it reads after the hit

## Solution

### Steps

1. Load the 16-byte corrupted AES-128 key and encrypted mission log.
2. Try each of the 128 possible single-bit corrections.
3. Decrypt each candidate with AES-ECB and check PKCS#7 padding.
4. Select the candidate whose plaintext matches the required flag format.

### Reproduction

Run the provided solver with the challenge input files in the locations expected by the script.

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

### Exploit Code

```python

#!/usr/bin/env python3
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

    if len(ciphertext) % 16 != 0:
        raise ValueError("Invalid AES ciphertext length")

    # Test every possible single-bit correction.
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

        print(f"Corrected bit index: {bit_index}")
        print(f"Corrected byte index: {byte_index}")
        print(f"Corrected key: {key.hex()}")
        print(f"FLAG: {decoded.decode('ascii')}")
        return

    raise RuntimeError("No valid single-bit correction found")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{s1ngle_event_upset}
```
