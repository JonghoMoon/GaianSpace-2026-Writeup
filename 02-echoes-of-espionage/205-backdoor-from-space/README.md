# 205-backdoor-from-space

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 125 |

## Description

With the decoder armed, the array stopped being ours. For a few minutes it talked to something out on the open internet, sent it a shopping list, and got told what to do next. The span monitor caught all of it. The watch wants to know what the attacker told it to do.

This is the last of the capture. Most of it is the array doing its ordinary housekeeping; one conversation is not ordinary. The host that calls out does not call home, it calls somewhere else, and what comes back is not text and not an encoded file you can just unwrap — it is scrambled. The two sides agreed on how to scramble it earlier in the very same conversation, out in the open, if you read the whole exchange instead of only the reply. Reyes closed the case on the first familiar thing she saw. The watch log carries a training injection the array writes on purpose. The archive still hands out a park order and calls it tasking. A sync blob on a lookalike host names its own cipher and key in the headers. The range link still publishes a sample card. The encoded "nominal" block on the housekeeping link is the same kind of bait. None of that is the attacker.

Recover the attacker's next move.

**Flag format:** `GAIANSPACE{...}`

**Attachments:** `ground_c2_traffic.pcap` — the span monitor's capture, just after the downlink

## Solution

### Steps

1. Inspect `ground_c2_traffic.pcap` and separate ordinary traffic and decoy artifacts from the C2 exchange (`cdn-sat-sync.net`, `POST /relay/telemetry`).
2. Read **both** the request and response. The request carries `X-Relay-Session: 9f3a7c2e15b84d60` and identifies the exfiltration target (`foundation_one_gerber.zip`).
3. Decode the response body from Base64 and decrypt with **RC4**, using the session value as the **ASCII string**, not as bytes parsed from hexadecimal.
4. Extract the command and `flag=` field from the recovered plaintext. The attacker's task was `persist;rotate-keys`.

### Reproduction

The following source is the solver used for this challenge. Run it with its original working-directory layout and input paths.

```bash
python3 205.py
```

Expected relevant output:
```
TASKING v2
target=GAIAN-13
action=persist;rotate-keys
note=next move queued
flag=GAIANSPACE{c2_rc4_from_the_nonce}
```

### Exploit Code

```python

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
```

## Flag

```text
GAIANSPACE{c2_rc4_from_the_nonce}
```
