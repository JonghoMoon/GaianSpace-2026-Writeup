
from pathlib import Path

binary = Path("ground_server").read_bytes()

# File offsets of the encoded key and encrypted payload.
encoded_key = binary[0x3048:0x3055]
encrypted_payload = binary[0x3020:0x3043]

# Recover the 13-byte validation key.
key = bytes(value ^ 0xA7 for value in encoded_key)

# Decrypt the payload using the repeating key.
decoded = bytes(
    value ^ key[index % len(key)]
    for index, value in enumerate(encrypted_payload)
)

print("Key:", key.decode("ascii"))
print("FLAG:", decoded.decode("ascii"))

