# 902-where-was-it-pointing

| | |
|---|---|
| **Category** | 09 — Dish Wrangler |
| **Points** | 75 |

## Description

Lindqvist has the night the dish walked. The motor was not drifting. Something was giving it places to go, and the station already keeps a catalog of the places it is willing to believe in. Each place remembers a scrap of a name.

Most of the trace is the motor clearing its throat. A few lines are the ones that named a destination. Pell divided the last byte by ten and announced a bearing. The dish did not go there.

Walk the destinations in the order the dish was sent. The scraps, in that order, are the proof.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `slew_log.txt` — the orders, as the controller spoke them
- `catalog.json` — the sky Kestrel Array is willing to believe
- `motor_notes.md` — Lindqvist’s card, rewritten twice

## Hints

Two hints were released during the event:

1. **The long orders** — The short lines start the motor and stop it. The lines that name a place are the longer ones.
2. **Finer than a degree** — The old positioner does not speak in whole degrees. The catalog already stores the angle the motor would be given. East and west are not the same direction.

## Solution

### Analysis

Read `slew_log.txt` in its original chronological order. Most entries are not pointing commands. The relevant five-byte motor commands begin with `E0 31 6E`.

The remaining two bytes form a **big-endian** value. Its most significant hexadecimal digit is a direction code (`E` for positive/east and `D` for negative/west); the remaining 12 bits contain a magnitude in **sixteenths of one degree**, not tenths of a degree.

For example, `E0 31 6E E0 60` gives `E` and `0x060 = 96`, hence `+96/16 = +6.00°`. That angle matches `KESTREL-21B` in the supplied catalog. Process every pointing command in capture order, look up its motor angle in `catalog.json`, and append the catalog's associated `fragment`.

### Reproduction

This solver uses only Python 3's standard library. Place `slew_log.txt`, `catalog.json`, and `902.py` together:

```bash
python3 902.py
```

Expected output:

```text
E0316EE060 -> +6.00 deg -> KESTREL-21B -> GAIANSPACE{
E0316ED048 -> -4.50 deg -> HALCYON-4W -> usals_a
E0316EE030 -> +3.00 deg -> MERIDIAN-3E -> rc_b
E0316ED0B0 -> -11.00 deg -> ORACLE-11W -> acktr
E0316EE018 -> +1.50 deg -> VESPER-1E -> 4ce
E0316ED100 -> -16.00 deg -> TALLIS-16W -> d}

FLAG: GAIANSPACE{usals_arc_backtr4ced}
```

All six fragments are taken directly from the provided catalog. No previously decoded fragment or final Flag is hardcoded into the solver.

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
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
