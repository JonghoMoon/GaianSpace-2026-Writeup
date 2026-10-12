
#!/usr/bin/env python3
import json
import re
from pathlib import Path

LOG_FILE = Path("slew_log.txt")
CATALOG_FILE = Path("catalog.json")


def decode_motor_angle(command: bytes) -> float:
    if len(command) != 5 or command[:3] != bytes.fromhex("e0316e"):
        raise ValueError("Not a USALS positioning command")

    value = int.from_bytes(command[3:5], "big")
    direction = (value >> 12) & 0xF
    magnitude = value & 0x0FFF

    if direction == 0xE:
        sign = 1
    elif direction == 0xD:
        sign = -1
    else:
        raise ValueError(f"Unknown motor direction: {direction:X}")

    return float(sign) * float(magnitude) / 16.0


def main() -> None:
    catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    slots = {
        round(float(slot["motor_angle_deg"]), 6): slot
        for slot in catalog["slots"]
    }

    fragments: list[str] = []

    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        match = re.search(r"\bTX\s+([0-9a-fA-F]+)", line)

        if match is None:
            continue

        command = bytes.fromhex(match.group(1))

        if len(command) != 5 or command[:3] != bytes.fromhex("e0316e"):
            continue

        angle = decode_motor_angle(command)
        slot = slots.get(round(angle, 6))

        if slot is None:
            raise ValueError(f"No catalog match for {angle} degrees")

        fragment = str(slot["fragment"])
        fragments.append(fragment)

        print(
            f"{command.hex().upper()} -> {angle:+.2f} deg "
            f"-> {slot['callsign']} -> {fragment}"
        )

    flag = "".join(fragments)

    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError(f"Invalid flag format: {flag}")

    print(f"\nFLAG: {flag}")


if __name__ == "__main__":
    main()

