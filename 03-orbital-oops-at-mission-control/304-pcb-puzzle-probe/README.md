# 304-pcb-puzzle-probe

| | |
|---|---|
| **Category** | 03 — Orbital Oops at Mission Control |
| **Points** | 100 |

## Description

The stolen board is back in our hands, and now the hardware team wants to know what the intruder was so interested in. The review desk will not hand over its assessment until you prove you can actually read the design. Five questions. Answer them from the board itself.

Open the Foundation One Gerber set and look at it the way a reviewer would: how it is stacked, how big it is, what is populated, and what someone left exposed that should not be. The desk checks every answer before it says a word, and it gets suspicious if you guess.

Pass the review to get its assessment.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**
- `foundation_one_gerbers.zip` — the recovered Foundation One board files
- The original description also referenced a review service (`server.py`, `Dockerfile`, `docker-compose.yml`), but these server files are not present in the archived ZIP.

## Solution

### Analysis

The original solver contained the five canonical answers (`2`, `50`, `u2`, `swd`, `6`) as constants. This verifies decryption but does not show how to obtain the answers. The revised solver derives these values from the supplied Gerber ZIP before deriving the unsealing key.

The available Gerber files and the observable evidence are:

| Answer position | Gerber evidence | Recovered answer |
|---|---|---|
| 1 | Front and back copper Gerbers, `F_Cu` and `B_Cu` | `2` |
| 2 | `Edge_Cuts.gbr`: X extent from 0 to 50 mm (Y extent from 0 to 40 mm) | `50` |
| 3 | `F_Silkscreen.gbr`: `U2` reference designator read from rendered vector strokes | `u2` |
| 4 | `F_Silkscreen.gbr`: exposed `SWD` interface marking near connector `J1` | `swd` |
| 5 | `F_Cu.gbr`: 14 flashed pads form footprints of 6, 4, and 4 pads; largest footprint is the six-pad U1 site | `6` |

The Gerber files contain vector drawing instructions rather than ordinary ASCII strings for the silkscreen labels. To recover `U2` and `SWD`, the solver renders the `D01` draw commands into `304_silkscreen.png` and runs OCR on the image. The output can also be checked visually. The third and fourth answers are lowercased for the quiz key derivation.

The script groups front-copper flash coordinates using a short-distance connected-components rule suited to this small board. Its grouping threshold is a layout-specific analysis choice, not a generic footprint classifier. For this dataset the grouping is `[6, 4, 4]`.

**Evidence limitation:** the archived package contains the Gerber ZIP but *not* the referenced `server.py`, `Dockerfile`, or `docker-compose.yml`. The original server's exact question wording and interactive exchange therefore cannot be reproduced from the distributed files. The 29-byte encrypted assessment used in the original solver is retained as a **saved server artifact**, and the code does not imply that this ciphertext was extracted from a Gerber layer. All **five answer values**, however, are now derived from board data.

After computing the answers in the original canonical order, the solver calculates `SHA256("2|50|u2|swd|6")` and constructs a counter-mode keystream from `SHA256(key || uint32_be(counter))`. XOR with the saved encrypted result reveals the flag. This mode is the challenge's custom SHA-256 keystream, not AES-CTR.

### Reproduction

Install OCR dependencies and the OCR executable (Ubuntu example):

```bash
python3 -m pip install Pillow pytesseract
sudo apt-get install tesseract-ocr
python3 304.py
```

Place `foundation_one_gerbers.zip` alongside `304.py`. Expected relevant output:

```text
OCR silkscreen: FOUNDATION ONE / REV C U2 / UL / JA / SWD
Copper layers: 2
Board outline: 50 x 40 mm
Component label: U2
Exposed interface: SWD
Pad groups: [6, 4, 4]
Quiz answers: ['2', '50', 'u2', 'swd', '6']
FLAG: GAIANSPACE{pcb_qu1z_compl3te}
```

OCR's other rendered labels may vary across Tesseract versions. If `U2` or `SWD` is not recognized, inspect the saved `304_silkscreen.png`; the script intentionally raises a clear error rather than silently substituting a known answer.

### Solver Code

```python
#!/usr/bin/env python3
"""Derive the PCB quiz answers from Gerber data and unseal the saved result."""

# Dependencies:
#   python3 -m pip install Pillow pytesseract
#   sudo apt-get install tesseract-ocr
# The quiz server is not included in the published challenge archive.
# ENCRYPTED_RESULT is a saved server artifact, not derivable from Gerbers.

import hashlib
import math
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw
import pytesseract

GERBER_ZIP = Path("foundation_one_gerbers.zip")
OUTPUT_IMAGE = Path("304_silkscreen.png")

# Fixed ciphertext recovered during the original interactive quiz.
# This is not a Gerber-derived intermediate answer.
ENCRYPTED_RESULT = bytes.fromhex(
    "eb6db0ec34531efa33556c0025c2bb98"
    "67348c6c9e287d2217e6637a68"
)


def gerber_coordinates(layer: str, operation: int) -> list[tuple[float, float]]:
    # FSLAX45Y45 specifies four integer and five fractional digits.
    if "%FSLAX45Y45*%" not in layer or "%MOMM*%" not in layer:
        raise ValueError("This solver expects 4.5 Gerber coordinates in mm")
    pattern = rf"X(-?\d+)Y(-?\d+)D0{operation}\*"
    return [(int(x) / 100000.0, int(y) / 100000.0)
            for x, y in re.findall(pattern, layer)]


def draw_silkscreen(layer: str, width_mm: float, height_mm: float) -> Image.Image:
    scale = 35
    image = Image.new("L", (round(width_mm * scale), round(height_mm * scale)), 255)
    painter = ImageDraw.Draw(image)
    cursor = None
    for x_text, y_text, mode in re.findall(r"X(-?\d+)Y(-?\d+)D0([123])\*", layer):
        x = int(x_text) / 100000.0
        y = int(y_text) / 100000.0
        point = (round(x * scale), round((height_mm - y) * scale))
        if mode == "2":
            cursor = point
        elif mode == "1":
            if cursor is not None:
                painter.line([cursor, point], fill=0, width=max(2, round(scale * 0.11)))
            cursor = point
        elif mode == "3":
            radius = max(2, round(scale * 0.3))
            painter.ellipse((point[0] - radius, point[1] - radius,
                             point[0] + radius, point[1] + radius), fill=0)
    return image


def pad_group_sizes(pads: list[tuple[float, float]]) -> list[int]:
    # The six-pad IC and two four-pad footprints form distinct spatial groups.
    # The grouping threshold is determined by the sparse footprint spacing
    # on this simple board, not by the expected quiz answer.
    neighbor_distance_mm = 9.5
    unseen = set(range(len(pads)))
    groups = []
    while unseen:
        seed = unseen.pop()
        pending = [seed]
        count = 0
        while pending:
            current = pending.pop()
            count += 1
            neighbors = {other for other in unseen
                         if math.dist(pads[current], pads[other]) < neighbor_distance_mm}
            pending.extend(neighbors)
            unseen.difference_update(neighbors)
        groups.append(count)
    return sorted(groups, reverse=True)


def answer_from_gerbers() -> list[str]:
    with zipfile.ZipFile(GERBER_ZIP) as archive:
        layers = {name: archive.read(name).decode("ascii")
                  for name in archive.namelist() if name.endswith(".gbr")}
    copper = [name for name in layers if name.endswith(("-F_Cu.gbr", "-B_Cu.gbr"))]
    if not copper:
        raise ValueError("Copper layers not found")
    edge = next(text for name, text in layers.items() if name.endswith("-Edge_Cuts.gbr"))
    perimeter = gerber_coordinates(edge, 1) + gerber_coordinates(edge, 2)
    if not perimeter:
        raise ValueError("No board outline coordinates found")
    xs = [point[0] for point in perimeter]
    ys = [point[1] for point in perimeter]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)

    silk = next(text for name, text in layers.items() if name.endswith("-F_Silkscreen.gbr"))
    image = draw_silkscreen(silk, width, height)
    image.save(OUTPUT_IMAGE)
    ocr_text = pytesseract.image_to_string(image, config="--psm 6").upper()
    print("OCR silkscreen:", " / ".join(ocr_text.splitlines()))
    # Select reference designators read from the drawing, not from a constant.
    components = sorted(set(re.findall(r"\bU\d+\b", ocr_text)))
    interfaces = sorted(set(re.findall(r"\b(?:SWD|JTAG)\b", ocr_text)))
    if len(components) != 1 or len(interfaces) != 1:
        raise ValueError(f"Ambiguous silkscreen OCR: {components}, {interfaces}")

    front_copper = next(text for name, text in layers.items() if name.endswith("-F_Cu.gbr"))
    pads = gerber_coordinates(front_copper, 3)
    pad_groups = pad_group_sizes(pads)
    if not pad_groups:
        raise ValueError("No flashed pads found")

    print(f"Copper layers: {len(copper)}")
    print(f"Board outline: {width:g} x {height:g} mm")
    print(f"Component label: {components[0]}")
    print(f"Exposed interface: {interfaces[0]}")
    print(f"Pad groups: {pad_groups}")
    answers = [str(len(copper)), f"{width:g}", components[0].lower(),
               interfaces[0].lower(), str(max(pad_groups))]
    print("Quiz answers:", answers)
    return answers


def main() -> None:
    answers = answer_from_gerbers()
    key = hashlib.sha256("|".join(answers).encode("ascii")).digest()
    stream = bytearray()
    counter = 0
    while len(stream) < len(ENCRYPTED_RESULT):
        stream.extend(hashlib.sha256(key + counter.to_bytes(4, "big")).digest())
        counter += 1
    decrypted = bytes(value ^ stream[index]
                      for index, value in enumerate(ENCRYPTED_RESULT))
    text = decrypted.decode("ascii")
    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", text) is None:
        raise ValueError("Unsealed result is not a valid flag")
    print("FLAG:", text)


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{pcb_qu1z_compl3te}
```
