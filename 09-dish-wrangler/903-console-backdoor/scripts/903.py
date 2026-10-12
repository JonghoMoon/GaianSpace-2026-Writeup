
#!/usr/bin/env python3

import hashlib
import re
from pathlib import Path

ENTRYPOINT = Path("service/entrypoint.sh")


def main() -> None:
    script = ENTRYPOINT.read_text(encoding="utf-8")

    # Extract the sealed schedule from the startup script.
    match = re.search(r'SCHED_BLOB="([0-9a-fA-F]+)"', script)

    if match is None:
        raise ValueError("Sealed schedule not found")

    blob = bytes.fromhex(match.group(1))

    # Derive the schedule key from the station identifier.
    station_id = b"KESTREL-ARRAY"
    key = hashlib.sha256(station_id).digest()

    # Recover the schedule using the repeating XOR key.
    plaintext = bytes(
        value ^ key[index % len(key)]
        for index, value in enumerate(blob)
    )

    decoded = plaintext.decode("utf-8")
    print(decoded)

    flag = re.search(r"GAIANSPACE\{[^}]+\}", decoded)

    if flag is None:
        raise ValueError("Flag not found")

    print(f"\nFLAG: {flag.group(0)}")


if __name__ == "__main__":
    main()

