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

### Exploit Code

```python
#!/usr/bin/env python3
"""Recover maintenance records from the HALCYON mid-stream capture."""
import re
from pathlib import Path

DATA_FILE = Path(__file__).with_name("halcyon_mid.bin")
BANNER_MARKER = b"STATIONLOG v2 | rec=type,len,payload | payload XOR 0x"


def main() -> None:
    data = DATA_FILE.read_bytes()
    start = data.find(BANNER_MARKER)
    if start < 0:
        raise ValueError("Station log banner not found")
    end = data.find(b" (banner is plain)", start)
    if end < 0:
        raise ValueError("Banner terminator not found")
    end += len(b" (banner is plain)")
    banner = data[start:end].decode("ascii")
    match = re.search(r"payload XOR 0x([0-9A-Fa-f]{2})", banner)
    if match is None:
        raise ValueError("XOR key not found in banner")
    key = int(match.group(1), 16)
    print("Banner:", banner)
    offset = end
    while offset + 2 <= len(data):
        kind = int(data[offset])
        length = int(data[offset + 1])
        if kind == 0 and length == 0:
            break
        payload_start = offset + 2
        payload_end = payload_start + length
        if payload_end > len(data):
            raise ValueError(f"Truncated record at offset {offset:#x}")
        plain = bytes(int(value) ^ key for value in data[payload_start:payload_end])
        print(f"Record @{offset:#x}: type={kind:#04x}, len={length}, text={plain.decode('ascii')!r}")
        if kind == 0x07:
            flag = re.search(rb"GAIANSPACE\{[^}]+\}", plain)
            if flag is not None:
                print("FLAG:", flag.group().decode("ascii"))
        offset = payload_end


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{syncd_led_me_home}
```
