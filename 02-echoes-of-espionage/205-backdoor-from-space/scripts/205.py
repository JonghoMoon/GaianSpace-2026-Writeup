
import base64

# Values extracted from the attacker's HTTP conversation.
session = "9f3a7c2e15b84d60"
payload = (
    "VxKfG5OtdAkdsGbX8AM7soeVJGU+WOs7dLPyIAuu8edqBwL2wDHT5Bm9RZr5s4hqRyc6SvLh+m0pbKL6cG45k6y2vwdnbF6Hm//jC9yWwMgbHg/rwKDcGKX4/cCg3qJi8rxUQIU12Hu3/E4b1uHGCl3DgA=="
)


def rc4_decrypt(data: bytes, key: bytes) -> bytes:
    state = list(range(256))
    j = 0

    # RC4 key scheduling algorithm.
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]

    i = 0
    j = 0
    output = bytearray()

    # RC4 pseudo-random generation algorithm.
    for value in data:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        keystream = state[(state[i] + state[j]) % 256]
        output.append(value ^ keystream)

    return bytes(output)


ciphertext = base64.b64decode(payload)
plaintext = rc4_decrypt(ciphertext, session.encode("ascii"))

print(plaintext.decode("ascii"))

