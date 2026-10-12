# 903-console-backdoor

| | |
|---|---|
| **Category** | 09 — Dish Wrangler |
| **Points** | 164 |

## Description

The intruder did not kick the door. The mission console let them point at a page, and the console went and fetched it. Lindqvist has the console on the bench. It still imports pieces of the catalog that way. The pass schedule is the page it is trying not to show him.

Pell is brute-forcing the login form. There is no login form. The health page will only tell you the console is bored.

Bring the console up yourself. Ask it for the page it thinks it is too well-mannered to open.

**Flag format:** `GAIANSPACE{...}`

### Run it

Unzip `service.zip` so the folder is named `service`, then from that folder:

```bash
docker compose up --build
```

The console listens on [http://localhost:8000](http://localhost:8000). It does not need the open network. A catalog directory and a Python interpreter are enough if you would rather not use Docker.

**Attachments:**

- `service.zip` — the console, as Lindqvist copied it off the bench

## Solution

### Steps

1. Inspect the catalog-import behavior for a path traversal weakness that can expose the restricted pass schedule.
2. The local service archive also contains an encoded schedule in `service/entrypoint.sh` as `SCHED_BLOB`.
3. Read that startup script, convert the hexadecimal blob to bytes, and derive `SHA256("KESTREL-ARRAY")`.
4. XOR the blob with the repeating digest to recover the restricted schedule and its maintenance token.
5. Use the **903** challenge's service archive; the similarly named archive from challenge 905 has a different structure.

### Reproduction

**Note:** This reproduction reads the locally sealed schedule from the service startup script. It does not exercise the vulnerable HTTP import endpoint itself. Extract the correct 903 archive so that `service/entrypoint.sh` is available.

**Original service run instructions:**

```bash
cd service
docker compose up --build
```

The console listens on `http://localhost:8000`. A Python interpreter and the local catalog directory can also be used instead of Docker.

Run the supplied solver with the original challenge files in the locations expected by its source code.

```bash
python3 903.py
```

Expected relevant output:

```text
KESTREL ARRAY — OPERATOR PASS SCHEDULE (RESTRICTED)
uplink window 04:00-06:00Z  key rotation nightly
maintenance unlock token: GAIANSPACE{ref_p4th_tr4versal}

FLAG: GAIANSPACE{ref_p4th_tr4versal}
```

### Exploit Code

```python

#!/usr/bin/env python3

import hashlib
import re
from pathlib import Path

ENTRYPOINT = Path("service/entrypoint.sh")


def main() -> None:
    script = ENTRYPOINT.read_text(encoding="utf-8")

    # Extract the sealed schedule from the startup script.
    match = re.search(r'SCHED_BLOB="([0-9a-fA-F]+)"', script)

    if match is None:
        raise ValueError("Sealed schedule not found")

    blob = bytes.fromhex(match.group(1))

    # Derive the schedule key from the station identifier.
    station_id = b"KESTREL-ARRAY"
    key = hashlib.sha256(station_id).digest()

    # Recover the schedule using the repeating XOR key.
    plaintext = bytes(
        value ^ key[index % len(key)]
        for index, value in enumerate(blob)
    )

    decoded = plaintext.decode("utf-8")
    print(decoded)

    flag = re.search(r"GAIANSPACE\{[^}]+\}", decoded)

    if flag is None:
        raise ValueError("Flag not found")

    print(f"\nFLAG: {flag.group(0)}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{ref_p4th_tr4versal}
```
