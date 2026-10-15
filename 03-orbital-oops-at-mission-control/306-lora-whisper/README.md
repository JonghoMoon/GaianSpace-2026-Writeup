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

### Analysis

This challenge provides a decoded frame log, not raw LoRa IQ. The receiver settings and protocol-specific payload transformation are given in `radio_notes.md`:

- The CanSat is node `0x1F`; the unrelated weather beacon is node `0x2A`.
- The payload is XOR-scrambled with the sync byte `0x12`.
- Sequence numbers restore ordering when frames arrive out of order.

The revised script first reads the actual node address and sync byte from the supplied notes rather than hardcoding them. It filters frames by sender, verifies declared payload lengths and sequence completeness, applies `byte XOR sync_byte`, sorts by sequence number, and concatenates the fragments.

**This XOR operation is the rule explicitly specified by the challenge's receiver notes. It should not be presented as a generic LoRa physical-layer decoding rule.**

### Reproduction

Place `lora_capture.log`, `radio_notes.md`, and `306.py` in one directory:

```bash
python3 306.py
```

Expected relevant output:

```text
CanSat address: 0x1F, XOR byte: 0x12
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

No third-party Python packages are needed.

### Solver Code

```python

#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.

import re
from pathlib import Path

LOG_FILE = Path("lora_capture.log")
NOTES_FILE = Path("radio_notes.md")


def read_radio_settings() -> tuple[int, int]:
    # Extract the node address and challenge-specific XOR byte from notes.
    notes = NOTES_FILE.read_text(encoding="utf-8")
    node_match = re.search(r"our bird answers to node `0x([0-9a-fA-F]+)`", notes, re.I)
    sync_match = re.search(r"sync byte `0x([0-9a-fA-F]+)`", notes)
    if node_match is None or sync_match is None:
        raise ValueError("Node address or sync byte missing from radio notes")
    return int(node_match.group(1), 16), int(sync_match.group(1), 16)


def main() -> None:
    text = LOG_FILE.read_text(encoding="utf-8")
    cansat_addr, xor_key = read_radio_settings()
    print(f"CanSat address: 0x{cansat_addr:02X}, XOR byte: 0x{xor_key:02X}")

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

        if addr != cansat_addr:
            continue

        if len(payload) != length:
            raise ValueError(f"Length mismatch at seq={seq}")

        if seq in frames:
            raise ValueError(f"Duplicate frame: seq={seq}")

        # Descramble each byte using the LoRa sync byte.
        decoded = bytes(value ^ xor_key for value in payload)
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
