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
