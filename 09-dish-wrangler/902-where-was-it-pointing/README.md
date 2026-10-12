# 902-where-was-it-pointing

| | |
|---|---|
| **Category** | 09 — Dish Wrangler |
| **Points** | 119 |

## Description

Lindqvist has the night the dish walked. The motor was not drifting. Something was giving it places to go, and the station already keeps a catalog of the places it is willing to believe in. Each place remembers a scrap of a name.

Most of the trace is the motor clearing its throat. A few lines are the ones that named a destination. Pell divided the last byte by ten and announced a bearing. The dish did not go there.

Walk the destinations in the order the dish was sent. The scraps, in that order, are the proof.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `slew_log.txt` — the orders, as the controller spoke them
- `catalog.json` — the sky Kestrel Array is willing to believe
- `motor_notes.md` — Lindqvist’s card, rewritten twice

## Solution

### Steps

1. Read the controller log and select the five-byte USALS positioning commands beginning `E0 31 6E`.
2. Interpret the high nibble of the final 16-bit value as the direction (E positive, D negative).
3. Convert the remaining 12 bits to degrees using a divisor of 16, not 10.
4. Match the decoded motor angles to the catalog slots.
5. Concatenate each destination's fragment in the order the commands were sent.

### Reproduction

Run the supplied solver with the original challenge files in the locations expected by its source code.

```bash
python3 902.py
```

Expected relevant output:

```text
E0316EE060 -> +6.00 deg -> KESTREL-21B -> GAIANSPACE{
E0316ED048 -> -4.50 deg -> HALCYON-4W -> usals_a
E0316EE030 -> +3.00 deg -> MERIDIAN-3E -> rc_b
E0316ED0B0 -> -11.00 deg -> ORACLE-11W -> acktr
E0316EE018 -> +1.50 deg -> VESPER-1E -> 4ce
E0316ED100 -> -16.00 deg -> TALLIS-16W -> d}

FLAG: GAIANSPACE{usals_arc_backtr4ced}
```

### Exploit Code

```python

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
```

## Flag

```text
GAIANSPACE{usals_arc_backtr4ced}
```
