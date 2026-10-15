#!/usr/bin/env python3
# Dependencies (install if needed):
#   python3 -m pip install numpy Pillow
"""Recover the AgriLink delivery stamp from the LoRa mast journal."""

import argparse
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

PACKET_PATTERN = re.compile(
    r"^\S+\s+\S+\s+-?\d+\s+[+-]?\d+(?:\.\d+)?\s+"
    r"(OK|BAD)\s+(\d+)\s+([0-9a-fA-F]+)\s*$"
)
BANDS = ("B02", "B03", "B04", "B08", "B11")
IMAGE_SIZE = 128


def read_packets(path: Path) -> tuple[np.ndarray, list[tuple[int, int]], str]:
    cube = np.zeros((len(BANDS), IMAGE_SIZE, IMAGE_SIZE), dtype=np.uint8)
    received: set[tuple[int, int]] = set()
    duplicate_rows: list[tuple[int, int]] = []
    metadata = ""
    count = 0

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        match = PACKET_PATTERN.match(line)
        if match is None:
            raise ValueError(f"Invalid log line {line_number}")
        crc_status, length_text, hex_text = match.groups()
        payload = bytes.fromhex(hex_text)
        if len(payload) != int(length_text, 10):
            raise ValueError(f"Length mismatch on line {line_number}")
        if crc_status != "OK":
            continue
        if len(payload) < 6 or payload[:5] != b"AL\x02\x04\x07":
            raise ValueError(f"Unexpected frame header on line {line_number}")
        packet_type = payload[5]
        count += 1
        if packet_type == ord("M"):
            metadata = payload[6:].decode("ascii")
        elif packet_type == ord("D"):
            if len(payload) != 8 + IMAGE_SIZE:
                raise ValueError(f"Unexpected image packet size on line {line_number}")
            channel = int(payload[6])
            row_index = int(payload[7])
            if not (0 <= channel < len(BANDS) and 0 <= row_index < IMAGE_SIZE):
                raise ValueError(f"Invalid channel/row on line {line_number}")
            key = (channel, row_index)
            if key in received:
                if cube[channel, row_index].tobytes() != payload[8:]:
                    raise ValueError(f"Conflicting duplicate at channel={channel}, row={row_index}")
                duplicate_rows.append(key)
            else:
                cube[channel, row_index] = np.frombuffer(payload[8:], dtype=np.uint8)
                received.add(key)
        elif packet_type != ord("E"):
            raise ValueError(f"Unexpected packet type {packet_type:#x}")

    missing = [(channel, row) for channel in range(len(BANDS))
               for row in range(IMAGE_SIZE) if (channel, row) not in received]
    print(f"Accepted packets: {count}")
    print(f"Unique image rows: {len(received)}")
    print(f"Duplicate rows: {len(duplicate_rows)}")
    print(f"Missing rows: {missing}")
    print(f"Metadata: {metadata}")
    if any(channel == 3 for channel, _ in missing):
        raise ValueError("The B08 band is incomplete")
    return cube, missing, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", type=Path, default=Path("mast_rx_0540.log"))
    parser.add_argument("--output", type=Path, default=Path("121_output"))
    args = parser.parse_args()

    cube, _, _ = read_packets(args.log)
    args.output.mkdir(parents=True, exist_ok=True)

    for channel, band in enumerate(BANDS):
        image = Image.fromarray(cube[channel], mode="L")
        image.save(args.output / f"{band}_raw.png")
        image.resize((768, 768), Image.Resampling.NEAREST).save(
            args.output / f"{band}_enlarged.png"
        )

    # The delivery stamp is visible in the B08 (near-infrared) channel.
    b08 = Image.fromarray(cube[3], mode="L")
    crop = b08.crop((30, 44, 101, 82))
    crop = crop.resize((994, 532), Image.Resampling.NEAREST)
    enhanced = ImageEnhance.Contrast(crop).enhance(2.2)
    enhanced.save(args.output / "delivery_stamp.png")

    print(f"Saved: {args.output / 'delivery_stamp.png'}")
    print("Read the three lines in the saved B08 image and join them without newlines.")


if __name__ == "__main__":
    main()
