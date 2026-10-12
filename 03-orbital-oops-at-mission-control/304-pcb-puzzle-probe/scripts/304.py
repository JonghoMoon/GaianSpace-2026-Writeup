
import hashlib

answers = ["2", "50", "u2", "swd", "6"]

encrypted = bytes.fromhex(
    "eb6db0ec34531efa33556c0025c2bb98"
    "67348c6c9e287d2217e6637a68"
)

# Derive the key using canonical answer order.
key = hashlib.sha256("|".join(answers).encode("ascii")).digest()

# Generate the SHA-256 counter-mode keystream.
stream = bytearray()
counter = 0

while len(stream) < len(encrypted):
    block = hashlib.sha256(
        key + counter.to_bytes(4, "big")
    ).digest()
    stream.extend(block)
    counter += 1

# Unseal the encrypted flag.
flag = bytes(
    value ^ stream[index]
    for index, value in enumerate(encrypted)
).decode("ascii")

print("FLAG:", flag)

