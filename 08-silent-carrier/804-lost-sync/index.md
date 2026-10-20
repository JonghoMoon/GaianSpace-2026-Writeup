---
render_with_liquid: false
---

# 804-lost-sync

| | |
|---|---|
| **Category** | 08 — Silent Carrier |
| **Points** | 100 |

## Description

The recorder woke up late. Oduya has the relay’s own maintenance log, and the file begins in the middle of a breath, not at the start of anything. This is not the crew mailbox and not the split letter from the last grab. It is HALCYON talking to itself.

Part of the log is written in a steady hand. The rest is the same hand dragged through one smudge, over and over. The bridge wants the station’s last words, the ones under the smudge.

A sticker on the recorder says the key is the stardate. Oduya tried that before she saved the file. It is not the stardate.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `halcyon_mid.bin` — the log, started too late
- `stationlog_format.md` — a fragment of the maintenance manual

## Hints

Two hints were released during the event:

1. **Started late** — The beginning of the file is not the beginning of a frame. Walk until the frame is willing to introduce itself.
2. **The clean line** — One line of the log was never smudged. It talks about the ink. The ink is the same on every other line.

## Solution

### Steps

1. Search the mid-stream capture for the clear-text `STATIONLOG v2` banner.
2. Recover the payload XOR key (`0x5A`) from the banner instead of using the stardate.
3. Walk the type/length/payload records following the banner.
4. XOR each payload byte with the key and read the recovered maintenance messages.
5. Extract the flag from record type `0x07`.

### Reproduction

Run the supplied Python solver with the original challenge files in the locations expected by its source code.

```bash
python3 804.py
```

Expected relevant output:

```text
Banner: STATIONLOG v2 | rec=type,len,payload | payload XOR 0x5A (banner is plain)
Record @0xa4: type=0x03, len=53, text='reactor nominal; attitude locked; downlink carrier up'
Record @0xdb: type=0x07, len=34, text='FLAG=GAIANSPACE{syncd_led_me_home}'
FLAG: GAIANSPACE{syncd_led_me_home}
Record @0xff: type=0x03, len=16, text='end of shift log'
```


### Frame synchronization and validation

Rather than searching the entire raw file directly for the plaintext station-log banner, the revised solver scans possible byte offsets for a **CRC-8-valid 10-byte BBHEADER** (polynomial `0xD5`, initialization zero), checks the declared DFL in bits, and extracts the complete byte-aligned data field. The original capture begins partway through a frame; only a recovered valid frame containing the plaintext `STATIONLOG v2` banner is used. The banner states the XOR byte (`0x5A`) used for subsequent type/length/payload records. The record marked `0x07` contains the flag. This is a frame-header and data-field recovery for the archived capture, not a generic DVB-S2 demodulator.

### Exploit Code

```python
#!/usr/bin/env python3
"""Recover HALCYON station records after validating mid-stream BBHEADER sync."""
# Dependencies: Python 3 standard library only.
import re
from pathlib import Path

DATA_FILE = Path("halcyon_mid.bin")
BANNER_MARKER = b"STATIONLOG v2 | rec=type,len,payload | payload XOR 0x"

def crc8_bbheader(raw: bytes) -> int:
    # CRC-8: polynomial 0xD5, initial register 0.
    value = 0
    for octet in raw:
        value ^= int(octet)
        for _ in range(8):
            value = ((value << 1) ^ (0xD5 if value & 0x80 else 0)) & 0xFF
    return value

def recover_frames(data: bytes) -> list[tuple[int, bytes]]:
    frames = []
    for offset in range(len(data) - 9):
        candidate = data[offset:offset + 10]
        if candidate[0] != 0x62 or crc8_bbheader(candidate[:9]) != candidate[9]:
            continue
        data_field_bits = int.from_bytes(candidate[4:6], "big")
        if data_field_bits == 0 or data_field_bits % 8:
            continue
        end = offset + 10 + data_field_bits // 8
        if end > len(data):
            continue
        frames.append((offset, data[offset + 10:end]))
    if not frames:
        raise ValueError("No CRC-8-valid BBHEADER found")
    return frames

def main() -> None:
    data = DATA_FILE.read_bytes()
    frames = recover_frames(data)
    print(f"Validated BBHEADER candidates: {len(frames)}")
    for position, field in frames:
        print(f"BBHEADER @{position:#x}: DFL={len(field)} bytes, CRC-8 OK")
        banner_start = field.find(BANNER_MARKER)
        if banner_start < 0:
            continue
        trailer = b" (banner is plain)"
        end = field.find(trailer, banner_start)
        if end < 0:
            continue
        end += len(trailer)
        banner = field[banner_start:end].decode("ascii")
        match = re.search(r"payload XOR 0x([0-9A-Fa-f]{2})", banner)
        if match is None:
            raise ValueError("XOR key missing from validated banner")
        key = int(match.group(1), 16)
        print("Banner:", banner)
        offset = end
        while offset + 2 <= len(field):
            kind, length = int(field[offset]), int(field[offset + 1])
            if kind == 0 and length == 0:
                break
            payload_end = offset + 2 + length
            if payload_end > len(field):
                raise ValueError("Truncated station record within BBFRAME")
            plain = bytes(int(value) ^ key for value in field[offset + 2:payload_end])
            print(f"Record: type={kind:#04x}, len={length}, text={plain.decode('ascii')!r}")
            if kind == 0x07:
                found = re.search(rb"GAIANSPACE\{[^}]+\}", plain)
                if found:
                    print("FLAG:", found.group().decode("ascii"))
                    return
            offset = payload_end
    raise ValueError("No verified BBFRAME contained a keep-record flag")

if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{syncd_led_me_home}
```
