# 801-torn-frames

| | |
|---|---|
| **Category** | 08 — Silent Carrier |
| **Points** | 50 |

## Description

Stardate 2189. The salvage tug *Meridian Kestrel* has been sitting beside the derelict relay **HALCYON-7** for six hours. The relay has been dark for forty years. Tonight a thin carrier keeps climbing out of the belt, and the bridge wants the name of whoever left it running.

Signals officer Tamsin Oduya pulled the tuner stick and kept whatever the front end would give her. The capture stops and starts, like someone tapping a microphone with a bad cable. She told the bridge the owner’s name is still inside the broadcast the relay has been shouting at nobody. She also told them the first theory is usually the wrong one.

A plate on the rack reads `PAL / 625`. Under it, in grease pencil: `weather fax?` The console still shows a lock from another pass, `11786.420`, which Oduya says belonged to a different bird. The carrier has not introduced itself.

Find the name the old operator left on the stream.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `halcyon_dump.bin` — the tuner stick, copied off in a hurry
- `operator_log.txt` — Oduya’s notes from the same watch

## Solution

### Steps

1. Treat the damaged tuner capture as fragmented DVB transport-stream data rather than a PAL image or weather fax.
2. Scan for 188-byte MPEG-TS packets with sync byte `0x47`, retaining PID `0x0011` (SDT).
3. Locate DVB service descriptors (tag `0x48`) in packets with the payload-unit-start indicator.
4. Decode the service name as UTF-16BE when preceded by character-set byte `0x11`.
5. Extract the service name matching the flag format.

### Reproduction

Run the supplied Python solver with the original challenge files in the locations expected by its source code.

```bash
python3 801.py
```

Expected relevant output:

```text
Matching service-name occurrences: 6
FLAG: GAIANSPACE{burst_r3align_sdt_r3ad}
```


### Validation scope

The capture is damaged and contains interruptions, so the solver scans for individual 188-byte transport-packet candidates rather than assuming a single global alignment. It filters for PID `0x0011`, requires the payload-unit-start indicator, then recognizes the DVB service descriptor (`0x48`). The `0x11` character-set identifier indicates UTF-16BE for the service name. **Six occurrences** are reported, not necessarily six distinct services. The approach validates the relevant packet/descriptor fields but does **not** claim to implement a full SDT section-length and CRC parser.

### Exploit Code

```python

#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.

import re
from pathlib import Path

INPUT_FILE = Path("halcyon_dump.bin")
TS_SIZE = 188
SDT_PID = 0x0011


def extract_service_names(data: bytes) -> list[str]:
    names: list[str] = []

    for offset in range(len(data) - TS_SIZE + 1):
        if data[offset] != 0x47:
            continue

        packet = data[offset:offset + TS_SIZE]

        pid = ((packet[1] & 0x1F) << 8) | packet[2]

        if pid != SDT_PID:
            continue

        # Require a payload unit start indicator.
        if (packet[1] & 0x40) == 0:
            continue

        # Locate the DVB service descriptor (tag 0x48).
        for index in range(4, TS_SIZE - 4):
            if packet[index] != 0x48:
                continue

            descriptor_length = int(packet[index + 1])
            descriptor_end = index + 2 + descriptor_length

            if descriptor_end > TS_SIZE:
                continue

            # Descriptor layout:
            # service_type (1)
            # provider_name_length (1)
            # provider_name (variable)
            # service_name_length (1)
            # service_name (variable)
            provider_length = int(packet[index + 3])
            service_length_offset = index + 4 + provider_length

            if service_length_offset >= descriptor_end:
                continue

            service_length = int(packet[service_length_offset])
            start = service_length_offset + 1
            end = start + service_length

            if end > descriptor_end or service_length < 2:
                continue

            service_bytes = packet[start:end]

            # 0x11 indicates a UTF-16BE service name.
            if service_bytes[0] != 0x11:
                continue

            encoded_name = service_bytes[1:]

            try:
                name = encoded_name.decode("utf-16-be")
            except UnicodeDecodeError:
                continue

            if re.fullmatch(r"GAIANSPACE\{[^}]+\}", name):
                names.append(name)
                break

    return names


def main() -> None:
    data = INPUT_FILE.read_bytes()
    names = extract_service_names(data)

    if not names:
        raise RuntimeError("No SDT service flag found")

    unique_names = sorted(set(names))

    print(f"Matching service-name occurrences: {len(names)}")

    for name in unique_names:
        print(f"FLAG: {name}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{burst_r3align_sdt_r3ad}
```
