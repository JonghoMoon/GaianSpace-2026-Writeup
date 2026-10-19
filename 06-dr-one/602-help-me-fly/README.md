---
render_with_liquid: false
---

# 602-help-me-fly

| | |
|---|---|
| **Category** | 06 — DR-ONE |
| **Points** | 75 |

## Description

The rotorcraft and its relay never stop talking. The relay pokes it a few times a second, the aircraft pokes back, and in between the pilot's stick commands ride the same channel. We have a clean stretch of that conversation from a single flight. The flight dynamics team wants to read the aircraft's side of it — not the commands going up, but what the aircraft says as it flies.

Every poke from the ground gets an answer from the aircraft. On a parked unit those answers are all the same dull acknowledgement. This unit was not parked. As it flew, its answers carried a changing field that the pilot never sees — the kind of thing a maintenance log quietly records. Pull that field out of the aircraft's replies, keep them in the order they were sent, and the aircraft tells you something plainly.

Read what the aircraft was saying as it flew.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `mars_control.pcap` — one flight's control conversation

## Hints

Two hints were released during the event:

1. **The aircraft's side** — Separate the aircraft's replies from the ground's pokes. Every answer to a poke starts with the same two-byte tag. Anything the aircraft sends on its own carries a different tag.
2. **One field, in order** — A parked unit always answers with zeros. In flight, one byte of each reply changes. Collect that byte across the replies, in sequence. The radio link is not polite: replies arrive late, out of order, and sometimes twice. The last two bytes are the aircraft's own counter, low byte first.

## Solution

### Steps

1. Parse the PCAP and select UDP replies sent by the aircraft (`10.42.0.1:7099`).
2. Identify the five-byte acknowledgement packets beginning with `53 01`.
3. Read the changing third byte as an ASCII character and the final two bytes as a little-endian sequence number.

   The five-byte reply layout is:

   | Offset | Size | Field |
   |---:|---:|---|
   | 0 | 1 byte | Reply marker `0x53` |
   | 1 | 1 byte | ACK type `0x01` |
   | 2 | 1 byte | ASCII data character |
   | 3 | 2 bytes | Little-endian sequence number |

   For instance, `53 01 47 F0 00` represents character `G` at sequence `0x00F0`.
4. Sort by sequence, check for missing/conflicting entries, and concatenate the characters.

### Reproduction

Run the solver with the original challenge files in the paths expected by the source code.

```bash
python3 602.py
```

Expected relevant output:

```text
Start sequence: 0x00F0
End sequence:   0x0112
Characters:     35
Decoded:        GAIANSPACE{fl1ght_telemetry_str3am}
FLAG: GAIANSPACE{fl1ght_telemetry_str3am}
```



### Exploit Code

```python

#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
import re
import socket
import struct
from pathlib import Path

PCAP_FILE = Path("mars_control.pcap")
AIRCRAFT_IP = "10.42.0.1"
AIRCRAFT_PORT = 7099


def extract_udp_payloads(data: bytes):
    if data[:4] != b"\xd4\xc3\xb2\xa1":
        raise ValueError("Expected little-endian PCAP")

    offset = 24

    while offset + 16 <= len(data):
        _, _, captured_len, _ = struct.unpack_from(
            "<IIII", data, offset
        )
        offset += 16

        frame = data[offset:offset + captured_len]
        offset += captured_len

        if len(frame) < 42 or frame[12:14] != b"\x08\x00":
            continue

        ip = frame[14:]
        ihl = (ip[0] & 0x0F) * 4

        if ip[9] != 17:
            continue

        source_ip = socket.inet_ntoa(ip[12:16])
        udp = ip[ihl:]

        if len(udp) < 8:
            continue

        source_port = struct.unpack_from("!H", udp, 0)[0]

        if source_ip == AIRCRAFT_IP and source_port == AIRCRAFT_PORT:
            yield udp[8:]


def main() -> None:
    data = PCAP_FILE.read_bytes()
    characters: dict[int, int] = {}

    for payload in extract_udp_payloads(data):
        if len(payload) != 5:
            continue

        if payload[:2] != b"\x53\x01" or payload[2] == 0:
            continue

        char = int(payload[2])
        sequence = int.from_bytes(payload[3:5], "little")

        if sequence in characters and characters[sequence] != char:
            raise ValueError(f"Conflicting character at {sequence}")

        characters[sequence] = char

    if not characters:
        raise ValueError("No encoded telemetry characters found")

    positions = sorted(characters)

    if positions != list(range(positions[0], positions[-1] + 1)):
        raise ValueError("Missing character sequence numbers")

    message = bytes(characters[index] for index in positions)
    flag = message.decode("ascii")

    print(f"Start sequence: 0x{positions[0]:04X}")
    print(f"End sequence:   0x{positions[-1]:04X}")
    print(f"Characters:     {len(positions)}")
    print(f"Decoded:        {flag}")

    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError("Invalid flag format")

    print(f"FLAG: {flag}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{fl1ght_telemetry_str3am}
```
