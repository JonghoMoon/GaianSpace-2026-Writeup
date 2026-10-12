
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

