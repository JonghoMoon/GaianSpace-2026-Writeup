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

