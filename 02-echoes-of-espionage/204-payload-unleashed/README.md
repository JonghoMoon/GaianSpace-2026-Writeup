# 204-payload-unleashed

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 100 |

## Description

The malicious frame did not just arrive at the array. It woke something that was already living in the decoder. The station runs an old telemetry decoder called ground_server, and after the frame came down the decoder started answering to a key it should never have accepted.

Forensics pulled the decoder off the array for you. It wants one argument, a key, and it throws back everything that is not the one it is waiting for. Reyes tried the mission id, the callsign, and his own initials, in that order, and got three rejections and a bad mood. Somewhere in the program is the key it actually wants and the thing it hands over when it hears it.

Make the decoder give up what the attacker armed.

**Flag format:** `GAIANSPACE{...}`

**Attachments:** `ground_server` — the station's telemetry decoder (Linux x86-64 ELF)

## Solution

### Steps

1. Disassemble or inspect the ELF `ground_server` instead of guessing the input argument.
2. The code reconstructs its expected **13-byte** validation key by XORing stored bytes with `0xA7`. It resolves to `EL06QL-UNLOCK`.
3. The embedded payload at file offsets `0x3020:0x3043` is XORed with that same reconstructed key, repeated across the payload.
4. Extract the two byte ranges directly and recover the plaintext without executing the binary.

### Reproduction

The following source is the solver used for this challenge. Run it with its original working-directory layout and input paths.

```bash
python3 204.py
```

Expected relevant output:
```
Key: EL06QL-UNLOCK
FLAG: GAIANSPACE{b4ckd00r_in_the_dec0der}
```

### Exploit Code

```python

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
```

## Flag

```text
GAIANSPACE{b4ckd00r_in_the_dec0der}
```
