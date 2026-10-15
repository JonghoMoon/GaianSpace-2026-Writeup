#!/usr/bin/env python3
# Dependencies: python3 -m pip install Pillow pytesseract
# System dependency (Ubuntu/Debian): sudo apt install tesseract-ocr

"""
GaianSpace CTF 206 - gpredict-secret

Extract three signature fragments from:
  1. gaian-13-relay.tle
  2. relay.mod
  3. pass_capture.png

Validate the station configuration in vela.qth.
"""

import re
from pathlib import Path

import pytesseract
from PIL import Image


BASE_DIR = Path(".")


def extract_tle_fragment(path: Path) -> str:
    text = path.read_text(encoding="utf-8")

    match = re.search(r";tag:([A-Za-z0-9_]+)", text)
    if match is None:
        raise ValueError("TLE signature tag not found")

    return match.group(1)


def extract_module_fragment(path: Path) -> str:
    text = path.read_text(encoding="utf-8")

    match = re.search(
        r"relay-token\s*=\s*([A-Za-z0-9_]+)",
        text,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError("Relay token not found")

    return match.group(1)


def extract_image_fragment(path: Path) -> str:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        text = pytesseract.image_to_string(
            rgb,
            config="--psm 6",
        )

    print("[OCR Result]")
    print(text)

    match = re.search(
        r"note\s*:\s*([A-Za-z0-9_]+)",
        text,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError("Screenshot signature not found")

    return match.group(1)


def verify_station(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    required = {
        "LOCATION": "GaianSpace VELA",
        "LAT": "19.48",
        "LON": "-155.60",
    }

    for key, expected in required.items():
        match = re.search(
            rf"^{re.escape(key)}\s*=\s*(.+)$",
            text,
            re.MULTILINE,
        )

        if match is None:
            raise ValueError(f"Missing station field: {key}")

        actual = match.group(1).strip()
        if actual != expected:
            raise ValueError(
                f"Unexpected {key}: {actual}"
            )


def main() -> None:
    tle = BASE_DIR / "gaian-13-relay.tle"
    module = BASE_DIR / "relay.mod"
    station = BASE_DIR / "vela.qth"
    screenshot = BASE_DIR / "pass_capture.png"

    verify_station(station)

    part1 = extract_tle_fragment(tle)
    part2 = extract_module_fragment(module)
    part3 = extract_image_fragment(screenshot)

    signature = "_".join((part1, part2, part3))
    flag = f"GAIANSPACE{{{signature}}}"

    print("\n[Extracted Fragments]")
    print(f"TLE        : {part1}")
    print(f"Module     : {part2}")
    print(f"Screenshot : {part3}")
    print("Station    : VELA (verified)")

    print("\n[FLAG]")
    print(flag)


if __name__ == "__main__":
    main()

