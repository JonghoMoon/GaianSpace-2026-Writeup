
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

