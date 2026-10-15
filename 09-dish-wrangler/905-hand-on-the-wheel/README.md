# 905-hand-on-the-wheel

| | |
|---|---|
| **Category** | 09 — Dish Wrangler |
| **Points** | 125 |

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

### Analysis

The signed command log records three HMAC-SHA256-authenticated actions. The challenge provides the station identifier through these records and the integer epoch day **26278**. The fractional part of the epoch has been removed; the `.88204` comment is a deliberate distractor.

The service authenticates a canonical command of the form:

```text
station_id|action|angle_deg|nonce
```

and derives its signing key as:

```text
SHA256("station_id:full_epoch")
```

The Python solver checks all fractional epochs of widths 1–5 decimal digits. Each candidate is compared against the captured HMACs, and the matching epoch is accepted **only after all three signatures validate**.

```text
Recovered epoch: 26278.04117
Verified signatures: 3
```

The recovered key supports **two independent ways to retrieve the Flag**:

**Method 1 — Offline decryption.** Read `service/flag.enc` directly from `service.zip`. For each block counter `i`, derive an HMAC-SHA256 block over `b"SLEW-CTR" || uint32_be(i)`, concatenate the blocks, and XOR them with the ciphertext. This recovers `GAIANSPACE{f0rged_slew_t0_h0me}` without running the web service.

**Method 2 — Authorized park command.** Form a new command with `action="park"`, integer `angle_deg=0`, and a fresh nonce. Sign the exact canonical message with the recovered key and send the JSON as `POST /api/slew` to the **local challenge service**. The service verifies the signature and returns `{"status":"parked", "flag":"..."}`. The updated solver can execute this second route as well and compares the two Flags.

### Reproduction

Python dependencies: **standard library only**. Place `signed_cmds.log`, `service.zip`, and `905.py` together.

**Method 1 — no service required:**

```bash
python3 905.py
```

Expected output:

```text
Recovered epoch: 26278.04117
Verified signatures: 3
FLAG: GAIANSPACE{f0rged_slew_t0_h0me}
```

**Method 2 — signed park request:** start the service after recovering the epoch. From the directory containing the extracted `service` folder:

```bash
cd service
TLE_EPOCH='26278.04117' docker compose up --build
```

Then, in the directory containing the solver and challenge inputs:

```bash
python3 905.py --park
```

The solver derives the epoch anew, decrypts the local sealed Flag, creates an authenticated `park` command, posts it to `http://127.0.0.1:8000/api/slew`, and verifies that the returned Flag matches its offline result. The local service was tested successfully with this command:

```text
Server status: parked
Server FLAG: GAIANSPACE{f0rged_slew_t0_h0me}
Offline and HTTP methods agree.
```

`--park` is optional. The offline route is explicitly permitted by the challenge and remains the default, so no running service or Docker installation is required for Method 1.

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
# Offline mode needs signed_cmds.log and service.zip in the working directory.
# --park additionally requires the supplied local 905 service to be running.

"""Recover the HMAC key and use it to decrypt or authorize a park command."""

import argparse
import hashlib
import hmac
import json
import re
import secrets
import struct
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

LOG_FILE = Path("signed_cmds.log")
ZIP_FILE = Path("service.zip")
EPOCH_DAY = "26278"  # The integer day is explicitly supplied in the challenge.


def derive_key(station_id: str, epoch: str) -> bytes:
    return hashlib.sha256(f"{station_id}:{epoch}".encode("utf-8")).digest()


def canonical_command(command: dict) -> bytes:
    return (
        f"{command['station_id']}|{command['action']}|"
        f"{command['angle_deg']}|{command['nonce']}"
    ).encode("utf-8")


def sign_command(command: dict, key: bytes) -> str:
    return hmac.new(key, canonical_command(command), hashlib.sha256).hexdigest()


def verify_signature(command: dict, key: bytes) -> bool:
    return hmac.compare_digest(sign_command(command, key), str(command["sig"]))


def read_commands() -> list[dict]:
    commands: list[dict] = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("{"):
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("Unexpected signed command record")
            commands.append(record)
    if not commands:
        raise ValueError("No signed commands found")
    stations = {str(record["station_id"]) for record in commands}
    if len(stations) != 1:
        raise ValueError("Captured records have inconsistent station identifiers")
    return commands


def recover_epoch(commands: list[dict]) -> tuple[str, bytes]:
    station_id = str(commands[0]["station_id"])
    for width in range(1, 6):
        for number in range(10**width):
            epoch = f"{EPOCH_DAY}.{number:0{width}d}"
            key = derive_key(station_id, epoch)
            if not verify_signature(commands[0], key):
                continue
            if all(verify_signature(command, key) for command in commands):
                return epoch, key
    raise RuntimeError("Matching epoch not found")


def decrypt_flag(ciphertext: bytes, key: bytes) -> str:
    stream = bytearray()
    counter = 0
    while len(stream) < len(ciphertext):
        stream.extend(
            hmac.new(
                key,
                b"SLEW-CTR" + struct.pack(">I", counter),
                hashlib.sha256,
            ).digest()
        )
        counter += 1
    plaintext = bytes(
        value ^ stream[index]
        for index, value in enumerate(ciphertext)
    )
    return plaintext.decode("ascii")


def read_encrypted_flag() -> bytes:
    with zipfile.ZipFile(ZIP_FILE) as archive:
        return bytes(archive.read("service/flag.enc"))


def forge_park(key: bytes, station_id: str, url: str, nonce: str) -> str:
    # int(0) is used to match the server's canonical string formatting.
    command: dict = {
        "station_id": station_id,
        "action": "park",
        "angle_deg": 0,
        "nonce": nonce,
    }
    command["sig"] = sign_command(command, key)
    request = urllib.request.Request(
        url=f"{url.rstrip('/')}/api/slew",
        data=json.dumps(command).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = int(response.status)
            result = json.load(response)
    except urllib.error.URLError as error:
        raise RuntimeError("Local 905 console is unavailable") from error
    if status != 200 or result.get("status") != "parked":
        raise RuntimeError(f"Park command was rejected: {result}")
    flag = str(result.get("flag", ""))
    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError(f"Unexpected park response: {result}")
    print("[Signed park command]")
    print(json.dumps(command, indent=2))
    print(f"Server status: {result['status']}")
    print(f"Server FLAG: {flag}")
    return flag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--park", action="store_true", help="also send a signed park command")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--nonce", default=None, help="Optional fixed nonce for reproducibility")
    args = parser.parse_args()

    commands = read_commands()
    epoch, key = recover_epoch(commands)
    print(f"Recovered epoch: {epoch}")
    print(f"Verified signatures: {len(commands)}")

    decrypted = decrypt_flag(read_encrypted_flag(), key)
    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", decrypted) is None:
        raise ValueError("Invalid decrypted flag")
    print(f"FLAG: {decrypted}")

    if args.park:
        nonce = str(args.nonce) if args.nonce is not None else secrets.token_hex(8)
        server_flag = forge_park(
            key, str(commands[0]["station_id"]), str(args.url), nonce
        )
        if server_flag != decrypted:
            raise ValueError("Offline and live service flags do not match")
        print("Offline and HTTP methods agree.")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{f0rged_slew_t0_h0me}
```
