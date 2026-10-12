
#!/usr/bin/env python3

import re
from pathlib import Path

INPUT_FILE = Path("halcyon_dump.bin")
TS_SIZE = 188
SDT_PID = 0x0011


def extract_service_names(data: bytes) -> list[str]:
    names: list[str] = []

    for offset in range(len(data) - TS_SIZE + 1):
        if data[offset] != 0x47:
            continue

        packet = data[offset:offset + TS_SIZE]

        pid = ((packet[1] & 0x1F) << 8) | packet[2]

        if pid != SDT_PID:
            continue

        # Require a payload unit start indicator.
        if (packet[1] & 0x40) == 0:
            continue

        # Locate the DVB service descriptor (tag 0x48).
        for index in range(4, TS_SIZE - 4):
            if packet[index] != 0x48:
                continue

            descriptor_length = int(packet[index + 1])
            descriptor_end = index + 2 + descriptor_length

            if descriptor_end > TS_SIZE:
                continue

            # Descriptor layout:
            # service_type (1)
            # provider_name_length (1)
            # provider_name (variable)
            # service_name_length (1)
            # service_name (variable)
            provider_length = int(packet[index + 3])
            service_length_offset = index + 4 + provider_length

            if service_length_offset >= descriptor_end:
                continue

            service_length = int(packet[service_length_offset])
            start = service_length_offset + 1
            end = start + service_length

            if end > descriptor_end or service_length < 2:
                continue

            service_bytes = packet[start:end]

            # 0x11 indicates a UTF-16BE service name.
            if service_bytes[0] != 0x11:
                continue

            encoded_name = service_bytes[1:]

            try:
                name = encoded_name.decode("utf-16-be")
            except UnicodeDecodeError:
                continue

            if re.fullmatch(r"GAIANSPACE\{[^}]+\}", name):
                names.append(name)
                break

    return names


def main() -> None:
    data = INPUT_FILE.read_bytes()
    names = extract_service_names(data)

    if not names:
        raise RuntimeError("No SDT service flag found")

    unique_names = sorted(set(names))

    print(f"Recovered SDT entries: {len(names)}")

    for name in unique_names:
        print(f"FLAG: {name}")


if __name__ == "__main__":
    main()
