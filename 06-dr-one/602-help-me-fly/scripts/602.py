
#!/usr/bin/env python3
import re
import socket
import struct
from pathlib import Path

PCAP_FILE = Path("mars_control.pcap")
AIRCRAFT_IP = "10.42.0.1"
AIRCRAFT_PORT = 7099


def extract_udp_payloads(data: bytes):
    if data[:4] != b"\xd4\xc3\xb2\xa1":
        raise ValueError("Expected little-endian PCAP")

    offset = 24

    while offset + 16 <= len(data):
        _, _, captured_len, _ = struct.unpack_from(
            "<IIII", data, offset
        )
        offset += 16

        frame = data[offset:offset + captured_len]
        offset += captured_len

        if len(frame) < 42 or frame[12:14] != b"\x08\x00":
            continue

        ip = frame[14:]
        ihl = (ip[0] & 0x0F) * 4

        if ip[9] != 17:
            continue

        source_ip = socket.inet_ntoa(ip[12:16])
        udp = ip[ihl:]

        if len(udp) < 8:
            continue

        source_port = struct.unpack_from("!H", udp, 0)[0]

        if source_ip == AIRCRAFT_IP and source_port == AIRCRAFT_PORT:
            yield udp[8:]


def main() -> None:
    data = PCAP_FILE.read_bytes()
    characters: dict[int, int] = {}

    for payload in extract_udp_payloads(data):
        if len(payload) != 5:
            continue

        if payload[:2] != b"\x53\x01" or payload[2] == 0:
            continue

        char = int(payload[2])
        sequence = int.from_bytes(payload[3:5], "little")

        if sequence in characters and characters[sequence] != char:
            raise ValueError(f"Conflicting character at {sequence}")

        characters[sequence] = char

    if not characters:
        raise ValueError("No encoded telemetry characters found")

    positions = sorted(characters)

    if positions != list(range(positions[0], positions[-1] + 1)):
        raise ValueError("Missing character sequence numbers")

    message = bytes(characters[index] for index in positions)
    flag = message.decode("ascii")

    print(f"Start sequence: 0x{positions[0]:04X}")
    print(f"End sequence:   0x{positions[-1]:04X}")
    print(f"Characters:     {len(positions)}")
    print(f"Decoded:        {flag}")

    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError("Invalid flag format")

    print(f"FLAG: {flag}")


if __name__ == "__main__":
    main()

