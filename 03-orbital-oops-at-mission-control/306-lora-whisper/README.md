# 306-lora-whisper

| | |
|---|---|
| **Category** | 03 — Orbital Oops at Mission Control |
| **Points** | 50 |

## Description

During the Foundation One descent, the ground radio sat on the CanSat band and wrote down every frame it heard. Two things were talking at once. One of them was ours, counting down something as it fell. The watch wants whatever our bird was saying, in the order it meant to say it.

The log is a plain record of received frames: who sent each one, where it sat in the sender's own count, and the bytes it carried. The bytes do not read as anything yet — they come off the modem still scrambled, the same way for every frame. The weather beacon on the next channel is louder and chattier and completely beside the point.

Reassemble what the CanSat transmitted.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**
- `lora_capture.log` — the ground radio's record of the descent window
- `radio_notes.md` — the watch's notes on the receiver

## Solution

### Steps

Filter the CanSat address 0x1F, order frames by sequence number, XOR payload bytes with 0x12, and concatenate the decoded fragments.

### Reproduction

Run the supplied solver with the original challenge inputs in the paths expected by the source code.

```bash
python3 306.py
```

Expected relevant output:

```text
[Decoded Frames]
seq=00: GAIAN
seq=01: SPACE
seq=02: {l0ra
seq=03: _fr4g
seq=04: ments
seq=05: _in_0
seq=06: rder}

FLAG: GAIANSPACE{l0ra_fr4gments_in_0rder}
```

### Exploit Code

```python

#!/usr/bin/env python3
import re
from pathlib import Path

LOG_FILE = Path("lora_capture.log")
CANSAT_ADDR = 0x1F
XOR_KEY = 0x12


def main() -> None:
    text = LOG_FILE.read_text(encoding="utf-8")

    pattern = re.compile(
        r"addr=0x([0-9a-fA-F]+)"
        r"\s+seq=(\d+)"
        r".*?len=(\d+)"
        r"\s+payload=([0-9a-fA-F]+)"
    )

    frames: dict[int, bytes] = {}

    for match in pattern.finditer(text):
        addr = int(match.group(1), 16)
        seq = int(match.group(2), 10)
        length = int(match.group(3), 10)
        payload = bytes.fromhex(match.group(4))

        if addr != CANSAT_ADDR:
            continue

        if len(payload) != length:
            raise ValueError(f"Length mismatch at seq={seq}")

        if seq in frames:
            raise ValueError(f"Duplicate frame: seq={seq}")

        # Descramble each byte using the LoRa sync byte.
        decoded = bytes(value ^ XOR_KEY for value in payload)
        frames[seq] = decoded

    if not frames:
        raise ValueError("No CanSat frames found")

    expected = list(range(max(frames) + 1))
    if sorted(frames) != expected:
        raise ValueError("Missing frame sequence")

    print("[Decoded Frames]")
    for seq in sorted(frames):
        print(f"seq={seq:02d}: {frames[seq].decode('ascii')}")

    message = b"".join(frames[seq] for seq in sorted(frames))
    flag = message.decode("ascii")

    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError("Invalid flag format")

    print(f"\nFLAG: {flag}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{l0ra_fr4gments_in_0rder}
```
