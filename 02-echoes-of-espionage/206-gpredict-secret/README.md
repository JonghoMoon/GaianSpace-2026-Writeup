# 206-gpredict-secret

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 50 |

## Description

When the attacker left GAIAN-13, they left a second element set behind on the tracking laptop, a saved tracking module, a station file, and a screen grab of a pass. Whoever set it up signed their work, the way a tagger signs a wall. The signature is not written in one place.

The flight-dynamics intern who imaged the laptop is convinced the whole thing is a copy of the operational setup and there is nothing to find. There is something to find. It is broken into pieces and scattered across what the attacker saved, and no single file gives it to you. Collect the pieces and they read like a title.

Put the signature back together.

**Flag format:** `GAIANSPACE{...}` — three fragments joined with underscores, in the order that makes them read as a phrase.

**Attachments:** `gaian-13-relay.tle` — the second element set left on the laptop, `pass_capture.png` — a screen grab of a pass, `relay.mod` — the saved tracking module, `vela.qth` — the station location file

## Solution

### Steps

1. Inspect `gaian-13-relay.tle`. The satellite title carries a nonstandard signature comment `;tag:w4tcher`.
2. Inspect `relay.mod`. The saved tracking module contains `relay-token=0f`.
3. Inspect `pass_capture.png`. Its **Footprint** field displays `note: the_sky`. The solver reads the screenshot with Tesseract OCR and extracts the text following `note:`.
4. Cross-check `vela.qth`: the saved station is **GaianSpace VELA**, latitude **19.48**, longitude **−155.60**. This confirms the context but contributes no fragment.
5. Combine the recovered fragments, preserving digits and underscores, in the order that forms the phrase: `w4tcher` + `0f` + `the_sky`.

### Reproduction

Put `206.py`, `gaian-13-relay.tle`, `relay.mod`, `pass_capture.png` and `vela.qth` in the same directory and run:

```bash
python3 206.py
```

The installation commands for **Pillow**, **pytesseract** and the system **Tesseract OCR executable** are at the top of `206.py`. The script reads all fragments from the supplied files and verifies the station configuration.

Expected relevant output:

```text
[Extracted Fragments]
TLE        : w4tcher
Module     : 0f
Screenshot : the_sky
Station    : VELA (verified)

[FLAG]
GAIANSPACE{w4tcher_0f_the_sky}
```

### Exploit Code

```python
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
```

## Flag

```text
GAIANSPACE{w4tcher_0f_the_sky}
```
