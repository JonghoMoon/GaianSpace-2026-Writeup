# 502-ionized-transistangle

| | |
|---|---|
| **Category** | 05 — Rad Hard Rampage |
| **Points** | 75 |

## Description

Months of accumulated dose finally caught up with the Foundation One status encoder. Total ionizing dose does not flip a bit and move on — it leaves transistors shorted, stuck, permanently. The encoder now spits nonsense. We still have the original design, gate for gate, with the damaged nodes marked.

The encoder turns a stream of probe words into a status line. On the bench it reads as junk, because a couple of gates are shorted and hold their outputs no matter what feeds them. The design on file is the healthy one; the shorted gates are flagged on it. Rebuild what the encoder was supposed to do, run the probe words through the intended logic, and the status line comes back.

Read the status line the encoder should have produced.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `status_encoder.netlist` — the gate-level design; shorted gates are tagged, probe words are listed at the end

## Solution

### Steps

1. Parse the gate assignments and hexadecimal probe words from the netlist.
2. Simulate the original intended XOR and NOT gates in order, ignoring the shorted-state annotations.
3. Assemble output bits `o0` through `o7` into bytes for each probe.
4. Decode the resulting byte stream as ASCII and verify the flag format.

### Reproduction

Run the provided solver with the challenge input files in the locations expected by the script.

```bash
python3 502.py
```

Expected relevant output:

```text
Probe count: 31
Decoded hex: 474149414e53504143457b743074616c5f316f6e697a696e675f643073657d
Decoded text: GAIANSPACE{t0tal_1onizing_d0se}
FLAG: GAIANSPACE{t0tal_1onizing_d0se}
```

### Exploit Code

```python

#!/usr/bin/env python3
import re
from pathlib import Path

NETLIST = Path("status_encoder.netlist")

GATE_PATTERN = re.compile(
    r"^(\w+)\s*=\s*(XOR|NOT)\s+(\w+)(?:\s+(\w+))?"
)


def main() -> None:
    lines = NETLIST.read_text(encoding="utf-8").splitlines()

    gates = []
    probes = []

    for line in lines:
        line = line.strip()

        if line.startswith("PROBES "):
            probes = [
                int(value, 16)
                for value in line.split()[1:]
            ]
            continue

        match = GATE_PATTERN.match(line)
        if match:
            gates.append(match.groups())

    if not probes or not gates:
        raise ValueError("Missing gates or probe vectors")

    result = bytearray()

    for probe in probes:
        # Map input byte bits to i0 through i7.
        signals = {
            f"i{i}": (probe >> i) & 1
            for i in range(8)
        }

        # Evaluate the designed logic, ignoring SHORTED tags.
        for output, op, source_a, source_b in gates:
            a = signals[source_a]

            if op == "XOR":
                if source_b is None:
                    raise ValueError(f"Missing XOR operand: {output}")
                signals[output] = a ^ signals[source_b]
            elif op == "NOT":
                signals[output] = 1 ^ a
            else:
                raise ValueError(f"Unsupported gate: {op}")

        # Assemble output bits as o7..o0.
        value = 0
        for i in range(8):
            value |= signals[f"o{i}"] << i

        result.append(value)

    decoded = result.decode("ascii")
    print(f"Probe count: {len(probes)}")
    print(f"Decoded hex: {result.hex()}")
    print(f"Decoded text: {decoded}")

    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", decoded) is None:
        raise ValueError("Invalid flag format")

    print(f"FLAG: {decoded}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{t0tal_1onizing_d0se}
```
