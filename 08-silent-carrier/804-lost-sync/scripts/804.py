#!/usr/bin/env python3
"""Recover HALCYON station records after validating mid-stream BBHEADER sync."""
# Dependencies: Python 3 standard library only.
import re
from pathlib import Path

DATA_FILE = Path("halcyon_mid.bin")
BANNER_MARKER = b"STATIONLOG v2 | rec=type,len,payload | payload XOR 0x"

def crc8_bbheader(raw: bytes) -> int:
    # CRC-8: polynomial 0xD5, initial register 0.
    value = 0
    for octet in raw:
        value ^= int(octet)
        for _ in range(8):
            value = ((value << 1) ^ (0xD5 if value & 0x80 else 0)) & 0xFF
    return value

def recover_frames(data: bytes) -> list[tuple[int, bytes]]:
    frames = []
    for offset in range(len(data) - 9):
        candidate = data[offset:offset + 10]
        if candidate[0] != 0x62 or crc8_bbheader(candidate[:9]) != candidate[9]:
            continue
        data_field_bits = int.from_bytes(candidate[4:6], "big")
        if data_field_bits == 0 or data_field_bits % 8:
            continue
        end = offset + 10 + data_field_bits // 8
        if end > len(data):
            continue
        frames.append((offset, data[offset + 10:end]))
    if not frames:
        raise ValueError("No CRC-8-valid BBHEADER found")
    return frames

def main() -> None:
    data = DATA_FILE.read_bytes()
    frames = recover_frames(data)
    print(f"Validated BBHEADER candidates: {len(frames)}")
    for position, field in frames:
        print(f"BBHEADER @{position:#x}: DFL={len(field)} bytes, CRC-8 OK")
        banner_start = field.find(BANNER_MARKER)
        if banner_start < 0:
            continue
        trailer = b" (banner is plain)"
        end = field.find(trailer, banner_start)
        if end < 0:
            continue
        end += len(trailer)
        banner = field[banner_start:end].decode("ascii")
        match = re.search(r"payload XOR 0x([0-9A-Fa-f]{2})", banner)
        if match is None:
            raise ValueError("XOR key missing from validated banner")
        key = int(match.group(1), 16)
        print("Banner:", banner)
        offset = end
        while offset + 2 <= len(field):
            kind, length = int(field[offset]), int(field[offset + 1])
            if kind == 0 and length == 0:
                break
            payload_end = offset + 2 + length
            if payload_end > len(field):
                raise ValueError("Truncated station record within BBFRAME")
            plain = bytes(int(value) ^ key for value in field[offset + 2:payload_end])
            print(f"Record: type={kind:#04x}, len={length}, text={plain.decode('ascii')!r}")
            if kind == 0x07:
                found = re.search(rb"GAIANSPACE\{[^}]+\}", plain)
                if found:
                    print("FLAG:", found.group().decode("ascii"))
                    return
            offset = payload_end
    raise ValueError("No verified BBFRAME contained a keep-record flag")

if __name__ == "__main__":
    main()
