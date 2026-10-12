# 304-pcb-puzzle-probe

| | |
|---|---|
| **Category** | 03 — Orbital Oops at Mission Control |
| **Points** | 100 |

## Description

The stolen board is back in our hands, and now the hardware team wants to know what the intruder was so interested in. The review desk will not hand over its assessment until you prove you can actually read the design. Five questions. Answer them from the board itself.

Open the Foundation One Gerber set and look at it the way a reviewer would: how it is stacked, how big it is, what is populated, and what someone left exposed that should not be. The desk checks every answer before it says a word, and it gets suspicious if you guess.

Pass the review to get its assessment.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**
- `foundation_one_gerbers.zip` — the recovered Foundation One board files
- `server.py, Dockerfile, docker-compose.yml` — challenge review service

## Solution

### Steps

Inspect the Gerber stack, dimensions, component markings, exposed debug interface and layer count; submit the five canonical answers in order and unseal the assessment.

### Reproduction

Run the supplied solver with the original challenge inputs in the paths expected by the source code.

```bash
python3 304.py
```

Expected relevant output:

```text
FLAG: GAIANSPACE{pcb_qu1z_compl3te}
```

### Exploit Code

```python

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
```

## Flag

```text
GAIANSPACE{pcb_qu1z_compl3te}
```
