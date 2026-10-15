
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

