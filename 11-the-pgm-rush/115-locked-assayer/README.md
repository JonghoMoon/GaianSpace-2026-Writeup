# 115 — Locked Assayer

| | |
|---|---|
| **Category** | 11 — The PGM Rush |
| **Points** | 300 |

## Description

AO-111 is down on `2041 QM23` and the assayer has already run three cups. The answer is sitting in the lander, and the company that built the assayer won't let anyone read it.

AsterOre leased the XRF assayer from Orlik Instruments and paid for it in four instalments. Finance held back the last one until the rock proved itself. Overnight Orlik suspended the licence from Brno. The analyser still measures and still keeps every result, but each result leaves the unit sealed, and the seal now needs a seed that Orlik pulled back. Finance will pay once Sunniva signs the ore contract, and Sunniva won't sign without the grade under the anchor.

The lander OBC pulled the assayer's whole controller flash over the debug link, and the mothership logged the lander's beacons all morning. Kaito says the seal is military-grade and the only way in is a cheque.

Sunniva wants the anchor-site result, and its certificate code is the proof that it came off the instrument.

**Flag format:** `GAIANSPACE{<certificate code, exactly as the assayer prints it>}` — for example `GAIANSPACE{XR9-AAAAAA}`.

### Files

- `xrf9_flash.bin` — the assayer controller's whole flash, 4 MiB, read over the lander's debug link
- `lander_link.log` — the mothership's log of the lander's housekeeping beacons
- `lander_icd.md` — the beacon layout and a note on the assayer
- `orlik_notice.md` — Orlik's suspension notice

*The PGM Rush is inspired by AstroForge, whose unusually open mission updates show how cheap, autonomous deep-space spacecraft could open the solar system not only to asteroid mining but to faster, cheaper science for everyone.*

## Hints

Two hints were released during the event:

1. **Close company** — At this distance it matters where on Earth each telescope stands.
2. **A good clock** — Not every night in the log deserves the same trust. A position is only as good as the time stamped on it.

## Solution

### 1. Identify the locked instrument

The Orlik notice states that the last instalment for XRF-9 serial number 0417 was overdue and that licence `OR-7731-B` had been suspended. The instrument continues measuring, but its results are sealed under a licence-dependent seed that has been withdrawn.

According to `lander_icd.md`, the housekeeping beacon starts with `AO` and carries 16-byte unit records. Unit 3 is the XRF-9 assayer; state 3 means *vendor lock*. Decode the CRC-valid hex payloads from `lander_link.log`, using little-endian fields:

```text
Unit:              3 (XRF-9)
State:             3 (vendor lock)
Factory ID on bus: 9f8503e2be0024fd
MicroPython UID:   fd2400bee203859f
```

For this device and capture, reversing the on-bus bytes gives the UID used by the sealing implementation: `fd2400bee203859f`. This byte-order choice is validated by the record decryptions below; it is not a general rule that MicroPython reverses factory identifiers. The UID is part of both the encryption key and IV derivation.

### 2. Recover the withdrawn seed from flash

`xrf9_flash.bin` is a 4 MiB RP2350 controller image. The investigation located a littlefs filesystem beginning at flash offset `0x180000`, including assay records, licence metadata, and the vendor seal module (`/lib/orlik.mpy`).

The current `OR-7731-B` licence JSON says `LOCKED` with `seed: null`. The crucial observation is that littlefs is copy-on-write: an earlier version of the JSON document remains in raw flash even after the current version replaces it. Search the flash for historical licence JSON documents instead of relying only on the current filesystem view.

| Licence | Recovered state | Seed | Flash JSON location |
|---|---|---|---|
| `OR-7731-A` | ACTIVE | `07a0482a255f833b202af0a85c89851d` | `0x2B8000` |
| `OR-7731-B` | Historical ACTIVE | `9e4633db1c7f31896eb7bbb0f5d148ef` | `0x2BB000` |
| `OR-7731-B` | Current LOCKED | `null` | Later copy |

The historical B seed is the key material needed for the three site samples. The A seed also provides a useful independent known-good decryption test.

### 3. Validate the vendor seal algorithm

The controller flash contains the MicroPython vendor module `/lib/orlik.mpy`. A raw-flash inspection around offset `0x2AE000` also reveals its qstr/name strings and literals, including `orlik.py`, `cryptolib`, `machine`, `unique_id`, `sha256`, `aes`, `seal`, `unseal`, `ORLIK/XRF-9/SEAL/2`, and `IV`.

These strings identify relevant functions and constants, **but qstr entries alone do not disclose the bytecode's complete control flow or prove the number of hash rounds**. This writeup does not document a `.mpy` bytecode disassembly or the tool used to perform one; it therefore does not claim that the precise construction below can be read directly from the strings.

The following **verified decryption implementation** combines the licence seed, device UID, fixed tag, eleven additional SHA-256 rounds, and a per-record IV. Its correctness for the supplied dataset is established by successfully decrypting all four stored records with valid PKCS#7 padding and matching embedded CRC32 checks, rather than by an undocumented disassembly step.

```python
uid = bytes.fromhex("fd2400bee203859f")
seed = bytes.fromhex("9e4633db1c7f31896eb7bbb0f5d148ef")

digest = sha256(b"ORLIK/XRF-9/SEAL/2" + uid + seed)
for i in range(11):
    digest = sha256(digest + bytes([i]) + uid[::-1])
key = digest[:16]

iv = sha256(b"IV" + record_number.to_bytes(4, "little") + uid)[:16]
```

Here `sha256(data)` denotes the raw 32-byte digest. The ciphertext uses **AES-128-CBC**, with PKCS#7 padding. After decrypting, verify the embedded CRC32 trailer (`;crc=XXXXXXXX`) against the plaintext preceding it. The code tries recovered licence seeds and accepts a record only when padding and CRC32 are both valid.

### 4. Identify the anchor-site sample

Four records decrypt successfully: record 0 is the reference sample under licence A, while records 1–3 are site samples under licence B. The requested sample is **record 2**, labelled `QM23-C2` (core from under the anchor).

| Record | Sample | Licence | Pt (g/t) | Pd (g/t) | Rh (g/t) | Certificate |
|---:|---|---|---:|---:|---:|---|
| 0 | CRM ORL-PGM-7 | OR-7731-A | 31.20 | 12.05 | 2.41 | `XR9-736LL7` |
| 1 | QM23-C1 | OR-7731-B | 6.40 | 2.31 | 0.52 | `XR9-KE6U6Y` |
| **2** | **QM23-C2** | **OR-7731-B** | **22.85** | **7.60** | **2.14** | **`XR9-6YYDU6`** |
| 3 | QM23-C3 | OR-7731-B | 0.31 | 0.12 | 0.02 | `XR9-D4D4XJ` |

All four plaintexts pass the embedded CRC32 check. This independently confirms the recovered UID, seeds, record framing, and decryption algorithm.

### Dead Ends and Lessons

- **Using only the current licence file:** the live `OR-7731-B` JSON contains `seed: null`, but the older copy remains in raw flash.
- **Assuming encryption alone makes the results unrecoverable:** AES-CBC was not broken; the key material survived the licence suspension.
- **Using the factory ID in displayed byte order:** the UID is reversed for the sealing routine; using the bus representation directly fails decryption.
- **Choosing a result by grade alone:** the challenge asks for the sample from under the anchor, so the `QM23-C2` label determines the correct record, not the highest platinum reading.

## Reproduction

Run from the `115-locked-assayer/` directory, keeping the repository layout: the solver is in `scripts/` and the original inputs are in `challenges/`. The two Markdown attachments document the protocol and licensing context but are not read by the script.

Install the one external dependency:

```bash
python3 -m pip install cryptography
```

Run:

```bash
python3 scripts/115.py challenges/xrf9_flash.bin challenges/lander_link.log
```

**Expected relevant output:**

```text
Unit 3 factory ID: 9f8503e2be0024fd
MicroPython unique_id: fd2400bee203859f
Licence OR-7731-A: latest state=ACTIVE, seed=07a0482a255f833b202af0a85c89851d, copies=1
  Recovered historical seed at 0x2B8000: 07a0482a255f833b202af0a85c89851d
Licence OR-7731-B: latest state=LOCKED, seed=None, copies=2
  Recovered historical seed at 0x2BB000: 9e4633db1c7f31896eb7bbb0f5d148ef
Recovered sealed records: 4
Record 0 (OR-7731-A, CRC32 OK): XRF9 s/n 0417;sample=CRM ORL-PGM-7;Pt=31.20g/t;Pd=12.05g/t;Rh=2.41g/t;Ir=1.88g/t;Ru=2.96g/t;Os=1.12g/t;Fe=88.1%;Ni=9.4%;Co=0.48%;cert=XR9-736LL7;crc=1f3a18d8
Record 1 (OR-7731-B, CRC32 OK): XRF9 s/n 0417;sample=QM23-C1;Pt=6.40g/t;Pd=2.31g/t;Rh=0.52g/t;Ir=0.71g/t;Ru=0.88g/t;Os=0.40g/t;Fe=41.7%;Ni=3.9%;Co=0.19%;cert=XR9-KE6U6Y;crc=35456cbc
Record 2 (OR-7731-B, CRC32 OK): XRF9 s/n 0417;sample=QM23-C2;Pt=22.85g/t;Pd=7.60g/t;Rh=2.14g/t;Ir=3.02g/t;Ru=3.71g/t;Os=1.95g/t;Fe=86.4%;Ni=10.2%;Co=0.55%;cert=XR9-6YYDU6;crc=f9dcf5ae
Record 3 (OR-7731-B, CRC32 OK): XRF9 s/n 0417;sample=QM23-C3;Pt=0.31g/t;Pd=0.12g/t;Rh=0.02g/t;Ir=0.05g/t;Ru=0.07g/t;Os=0.03g/t;Fe=11.3%;Ni=0.8%;Co=0.04%;cert=XR9-D4D4XJ;crc=2c671a66
FLAG: GAIANSPACE{XR9-6YYDU6}
```

## Solver Code

{% raw %}
```python
#!/usr/bin/env python3
# Dependencies: pip install cryptography
"""Recover XRF-9 sealed assay certificates from its flash and lander beacons.

Usage: python3 115.py xrf9_flash.bin lander_link.log
Requires: pip install cryptography
"""

import argparse
import hashlib
import json
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

TAG = b"ORLIK/XRF-9/SEAL/2"
FLASH_START = 0x180000
RECORD_MAGIC = b"XR"
RECORD_HEADER_SIZE = 12


@dataclass(frozen=True)
class SealedRecord:
    number: int
    offset: int
    timestamp: int
    ciphertext: bytes


def find_unit_uid(log_path: Path, unit_number: int = 3) -> tuple[bytes, bytes]:
    """Extract the 64-bit factory ID from an AO housekeeping beacon."""
    for line in log_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[-3] != "ok":
            continue
        try:
            payload = bytes.fromhex(parts[-1])
        except ValueError:
            continue
        if len(payload) < 10 or payload[:2] != b"AO":
            continue
        count = int(payload[9])
        if len(payload) != 10 + 16 * count:
            continue
        for index in range(count):
            start = 10 + index * 16
            record = payload[start:start + 16]
            if int(record[0]) != unit_number:
                continue
            factory_id_le = record[8:16]
            factory_id_display = factory_id_le
            # machine.unique_id() uses the byte-reversed on-bus factory ID.
            return factory_id_display, factory_id_le[::-1]
    raise ValueError("Unit 3 factory ID not found in any valid AO beacon")


def recover_licences(flash: bytes) -> dict[str, list[dict[str, object]]]:
    """Carve both active and superseded licence JSON documents from flash."""
    licences: dict[str, list[dict[str, object]]] = {}
    for match in re.finditer(rb"\{[^{}\x00]{0,1200}\}", flash[FLASH_START:]):
        try:
            item = json.loads(match.group().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(item, dict):
            continue
        licence = item.get("lic")
        if not isinstance(licence, str) or not licence.startswith("OR-7731-"):
            continue
        item["_offset"] = int(FLASH_START + match.start())
        licences.setdefault(licence, []).append(item)
    if not licences:
        raise RuntimeError("No licence JSON documents recovered")
    return licences


def recover_sealed_records(flash: bytes) -> dict[int, SealedRecord]:
    """Find the latest copy of each 160-byte encrypted assay record."""
    records: dict[int, SealedRecord] = {}
    for match in re.finditer(re.escape(RECORD_MAGIC), flash[FLASH_START:]):
        offset = int(FLASH_START + match.start())
        if offset + RECORD_HEADER_SIZE > len(flash):
            continue
        magic, number, length, version, timestamp = struct.unpack_from(
            "<2sHHHI", flash, offset
        )
        if magic != RECORD_MAGIC or number > 255 or version != 1:
            continue
        if length < 16 or length > 4096 or length % 16 != 0:
            continue
        end = offset + RECORD_HEADER_SIZE + int(length)
        if end > len(flash):
            continue
        records[int(number)] = SealedRecord(
            number=int(number),
            offset=offset,
            timestamp=int(timestamp),
            ciphertext=flash[offset + RECORD_HEADER_SIZE:end],
        )
    if not records:
        raise RuntimeError("No sealed assay records found")
    return records


def derive_key(uid: bytes, seed: bytes) -> bytes:
    """Reproduce the vendor seal-module key derivation."""
    digest = hashlib.sha256(TAG + uid + seed).digest()
    for index in range(11):
        digest = hashlib.sha256(digest + bytes([index]) + uid[::-1]).digest()
    return digest[:16]


def decrypt_record(record: SealedRecord, uid: bytes, seed: bytes) -> str | None:
    """Decrypt and validate PKCS#7 padding and the embedded CRC32 trailer."""
    key = derive_key(uid, seed)
    iv = hashlib.sha256(
        b"IV" + int(record.number).to_bytes(4, "little") + uid
    ).digest()[:16]
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(record.ciphertext) + decryptor.finalize()
    if not padded:
        return None
    padding = int(padded[-1])
    if not 1 <= padding <= 16 or padded[-padding:] != bytes([padding]) * padding:
        return None
    try:
        plaintext = padded[:-padding].decode("ascii")
    except UnicodeDecodeError:
        return None
    match = re.fullmatch(r"(.*);crc=([0-9a-fA-F]{8})", plaintext)
    if match is None:
        return None
    actual = zlib.crc32(match.group(1).encode("ascii")) & 0xFFFFFFFF
    expected = int(match.group(2), 16)
    if actual != expected:
        return None
    return plaintext


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flash", nargs="?", type=Path, default=Path("xrf9_flash.bin"))
    parser.add_argument("link", nargs="?", type=Path, default=Path("lander_link.log"))
    args = parser.parse_args()

    flash = args.flash.read_bytes()
    factory_id, uid = find_unit_uid(args.link)
    print(f"Unit 3 factory ID: {factory_id.hex()}")
    print(f"MicroPython unique_id: {uid.hex()}")

    licences = recover_licences(flash)
    seeds: dict[str, bytes] = {}
    for name, entries in sorted(licences.items()):
        latest = max(entries, key=lambda item: int(item["_offset"]))
        print(
            f"Licence {name}: latest state={latest.get('state')}, "
            f"seed={latest.get('seed')}, copies={len(entries)}"
        )
        historical = [
            item for item in entries
            if isinstance(item.get("seed"), str)
            and re.fullmatch(r"[0-9a-fA-F]{32}", str(item["seed"]))
        ]
        if historical:
            recovered = max(historical, key=lambda item: int(item["_offset"]))
            seeds[name] = bytes.fromhex(str(recovered["seed"]))
            print(
                f"  Recovered historical seed at 0x{int(recovered['_offset']):X}: "
                f"{seeds[name].hex()}"
            )

    records = recover_sealed_records(flash)
    print(f"Recovered sealed records: {len(records)}")
    plaintexts: dict[int, str] = {}
    for number, record in sorted(records.items()):
        valid = []
        for name, seed in seeds.items():
            result = decrypt_record(record, uid, seed)
            if result is not None:
                valid.append((name, result))
        if len(valid) != 1:
            raise RuntimeError(
                f"Record {number}: expected one CRC-verified licence, found {len(valid)}"
            )
        licence, plaintext = valid[0]
        plaintexts[number] = plaintext
        print(f"Record {number} ({licence}, CRC32 OK): {plaintext}")

    anchor_records = [
        text for text in plaintexts.values() if "sample=QM23-C2;" in text
    ]
    if len(anchor_records) != 1:
        raise RuntimeError("Expected one verified anchor-core assay")
    certificate = re.search(r";cert=(XR9-[A-Z0-9]+);", anchor_records[0])
    if certificate is None:
        raise RuntimeError("No certificate code in anchor-core assay")
    print(f"FLAG: GAIANSPACE{{{certificate.group(1)}}}")


if __name__ == "__main__":
    main()
```
{% endraw %}

## Tools and References

- Python 3 (`argparse`, `hashlib`, `json`, `re`, `struct`, `zlib`)
- `cryptography` Python package (AES-CBC)
- `lander_icd.md` — AO housekeeping format and unit state definitions
- `lander_link.log` — Unit 3 factory ID
- `orlik_notice.md` — licence suspension context
- Raw RP2350 flash and historical littlefs metadata
- Flash-visible vendor-module qstr strings and the four independently CRC32-validated decrypted records

## Flag

```text
GAIANSPACE{XR9-6YYDU6}
```
