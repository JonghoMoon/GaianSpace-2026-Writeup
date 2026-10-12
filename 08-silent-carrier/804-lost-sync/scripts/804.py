#!/usr/bin/env python3
"""Recover maintenance records from the HALCYON mid-stream capture."""
import re
from pathlib import Path

DATA_FILE = Path(__file__).with_name("halcyon_mid.bin")
BANNER_MARKER = b"STATIONLOG v2 | rec=type,len,payload | payload XOR 0x"


def main() -> None:
    data = DATA_FILE.read_bytes()
    start = data.find(BANNER_MARKER)
    if start < 0:
        raise ValueError("Station log banner not found")
    end = data.find(b" (banner is plain)", start)
    if end < 0:
        raise ValueError("Banner terminator not found")
    end += len(b" (banner is plain)")
    banner = data[start:end].decode("ascii")
    match = re.search(r"payload XOR 0x([0-9A-Fa-f]{2})", banner)
    if match is None:
        raise ValueError("XOR key not found in banner")
    key = int(match.group(1), 16)
    print("Banner:", banner)
    offset = end
    while offset + 2 <= len(data):
        kind = int(data[offset])
        length = int(data[offset + 1])
        if kind == 0 and length == 0:
            break
        payload_start = offset + 2
        payload_end = payload_start + length
        if payload_end > len(data):
            raise ValueError(f"Truncated record at offset {offset:#x}")
        plain = bytes(int(value) ^ key for value in data[payload_start:payload_end])
        print(f"Record @{offset:#x}: type={kind:#04x}, len={length}, text={plain.decode('ascii')!r}")
        if kind == 0x07:
            flag = re.search(rb"GAIANSPACE\{[^}]+\}", plain)
            if flag is not None:
                print("FLAG:", flag.group().decode("ascii"))
        offset = payload_end


if __name__ == "__main__":
    main()

