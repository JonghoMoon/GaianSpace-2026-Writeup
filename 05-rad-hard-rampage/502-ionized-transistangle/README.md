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

## Hints

Two hints were released during the event:

1. **A short is a lie** — A shorted gate ignores its inputs and holds one value. The design still records what that gate was meant to compute. Trust the design, not the short.
2. **Feed the probes** — Each output bit assembles into one character. Run every probe word through the repaired logic, in order.

## Solution

### Analysis

The attached `status_encoder.netlist` contains XOR/NOT gate assignments and a
`PROBES` line with **31** hexadecimal input bytes. Each probe is interpreted as
`i7 ... i0` (most- to least-significant bit). Each output byte is assembled
from `o7 ... o0` in the same bit order.

Two gate declarations include physical-damage annotations:

```text
n6  = XOR i0 i1  [SHORTED=0]
n15 = XOR i1 i3  [SHORTED=1]
```

These annotations say how the **damaged** encoder currently behaves. The question
asks for the status line the **healthy design was meant to produce**, so the
solver ignores `SHORTED` and evaluates the stated XOR/NOT operations instead.
In particular, `n6` and `n15` are calculated from their inputs rather than
forced to zero or one.

The assignments appear in dependency order, allowing a forward evaluation for
each input vector. Joining the output bits into bytes and interpreting the
31 resulting bytes as ASCII yields the flag.

### Steps

1. Parse the gate equations and the hexadecimal probe values.
2. Map the input byte's bit 0 to `i0`, and bit 7 to `i7`.
3. Evaluate the designed XOR/NOT gates in netlist order, ignoring shorted-state annotations.
4. Assemble `o0` (LSB) through `o7` (MSB) into a byte for each probe.
5. Decode the bytes as ASCII and validate the flag format.

### Reproduction

Place the solver and this challenge's input files in the same directory and run:

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

### Solver Code

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
        # i0 is the least-significant bit; i7 is the most-significant bit.
        signals = {
            f"i{i}": (probe >> i) & 1
            for i in range(8)
        }

        # The SHORTED tags describe physical faults, not the intended
        # gate behavior requested by the challenge.
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
