
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

