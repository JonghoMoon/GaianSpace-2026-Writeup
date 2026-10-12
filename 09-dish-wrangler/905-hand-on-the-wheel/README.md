# 905-hand-on-the-wheel

| | |
|---|---|
| **Category** | 09 — Dish Wrangler |
| **Points** | 205 |

## Description

Last of the night. The positioner will not move for a shouted order. It only believes an order that carries the same seal as the ones already in the log. Lindqvist has those orders. He does not have the seal’s secret, except he almost does.

The integer day is painted on the wall of the control room: **26278**. The fraction after the dot was scratched off the whiteboard and out of the log. Pell thinks the secret is the station’s name said three times. The station’s name is not a secret. It is printed on the door.

The console will park the dish at home for anyone who can seal that order. The same secret opens a copy of the token Lindqvist already lifted off the disk, if you would rather not ask the console.

**Flag format:** `GAIANSPACE{...}`

### Run it

Unzip `service.zip` so the folder is named `service`. The fraction is not in the folder. When you have the full epoch, from that folder:

```bash
TLE_EPOCH='26278.?????' docker compose up --build
```

The console listens on [http://localhost:8000](http://localhost:8000).

**Attachments:**

- `signed_cmds.log` — orders the positioner already believed
- `slew_protocol.md` — Lindqvist’s notes on how an order is supposed to look
- `service.zip` — the console, and the sealed copy of the token

## Solution

### Steps

1. Read the signed JSON commands and reconstruct the canonical message `station_id|action|angle_deg|nonce`.
2. Derive candidate keys as `SHA256("KESTREL-ARRAY:" + epoch)` while brute-forcing the missing fractional epoch.
3. Validate each candidate with HMAC-SHA256 against all three captured signatures.
4. Recover epoch `26278.04117`.
5. Read `service/flag.enc` from the archive and decrypt it using the HMAC-SHA256 counter-mode keystream labeled `SLEW-CTR`.

### Reproduction

**Original service run instructions:**

```bash
cd service
TLE_EPOCH='26278.04117' docker compose up --build
```

The console listens on `http://localhost:8000`. The solver below recovers the flag directly from the sealed archive, without running the service.

Run the supplied solver with the original challenge files in the locations expected by its source code.

```bash
python3 905.py
```

Expected relevant output:

```text
Recovered epoch: 26278.04117
Verified signatures: 3
FLAG: GAIANSPACE{f0rged_slew_t0_h0me}
```

### Exploit Code

```python

#!/usr/bin/env python3
import hashlib
import hmac
import json
import re
import struct
import zipfile
from pathlib import Path

LOG_FILE = Path("signed_cmds.log")
ZIP_FILE = Path("service.zip")

STATION_ID = "KESTREL-ARRAY"
EPOCH_DAY = "26278"


def derive_key(epoch: str) -> bytes:
    value = f"{STATION_ID}:{epoch}".encode("utf-8")
    return hashlib.sha256(value).digest()


def canonical_command(command: dict) -> bytes:
    value = (
        f"{command['station_id']}|"
        f"{command['action']}|"
        f"{command['angle_deg']}|"
        f"{command['nonce']}"
    )
    return value.encode("utf-8")


def verify_signature(command: dict, key: bytes) -> bool:
    actual = hmac.new(
        key,
        canonical_command(command),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(actual, str(command["sig"]))


def recover_epoch(commands: list[dict]) -> tuple[str, bytes]:
    # Search fractional epoch lengths from one through five digits.
    for width in range(1, 6):
        for number in range(10 ** width):
            epoch = f"{EPOCH_DAY}.{number:0{width}d}"
            key = derive_key(epoch)

            if not verify_signature(commands[0], key):
                continue

            # Verify every captured command before accepting the key.
            if all(verify_signature(command, key) for command in commands):
                return epoch, key

    raise RuntimeError("Matching epoch not found")


def decrypt_flag(ciphertext: bytes, key: bytes) -> str:
    stream = bytearray()
    counter = 0

    while len(stream) < len(ciphertext):
        block = hmac.new(
            key,
            b"SLEW-CTR" + struct.pack(">I", counter),
            hashlib.sha256,
        ).digest()
        stream.extend(block)
        counter += 1

    plaintext = bytes(
        value ^ stream[index]
        for index, value in enumerate(ciphertext)
    )

    return plaintext.decode("ascii")


def main() -> None:
    commands = []

    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("{"):
            commands.append(json.loads(line))

    if len(commands) < 1:
        raise ValueError("No signed commands found")

    epoch, key = recover_epoch(commands)

    print(f"Recovered epoch: {epoch}")
    print(f"Verified signatures: {len(commands)}")

    with zipfile.ZipFile(ZIP_FILE) as archive:
        ciphertext = archive.read("service/flag.enc")

    flag = decrypt_flag(ciphertext, key)

    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError("Invalid decrypted flag")

    print(f"FLAG: {flag}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{f0rged_slew_t0_h0me}
```
