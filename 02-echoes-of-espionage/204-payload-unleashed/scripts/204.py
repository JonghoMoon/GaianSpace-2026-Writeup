#!/usr/bin/env python3
# Dependencies: Python 3 standard library only (no pip packages required).
"""Extract the validation key and encrypted payload using ELF code references."""

import re
import struct
from pathlib import Path

INPUT_FILE = Path("ground_server")


def elf_load_segments(blob: bytes) -> list[tuple[int, int, int, int]]:
    # ELF64 little-endian: identify loadable segments for virtual-address mapping.
    if blob[:5] != b"\x7fELF\x02" or blob[5] != 1:
        raise ValueError("Expected a little-endian ELF64 executable")
    phoff = int(struct.unpack_from("<Q", blob, 0x20)[0])
    phentsize = int(struct.unpack_from("<H", blob, 0x36)[0])
    phnum = int(struct.unpack_from("<H", blob, 0x38)[0])
    segments = []
    for index in range(phnum):
        entry = phoff + index * phentsize
        p_type, _flags, p_offset, p_vaddr, _p_paddr, p_filesz, _p_memsz, _align = (
            struct.unpack_from("<IIQQQQQQ", blob, entry)
        )
        if int(p_type) == 1 and int(p_filesz) > 0:
            segments.append((int(p_vaddr), int(p_offset), int(p_filesz), int(p_type)))
    return segments


def virtual_to_file(segments: list[tuple[int, int, int, int]], addr: int, size: int) -> int:
    for vaddr, offset, filesz, _ in segments:
        if vaddr <= addr and addr + size <= vaddr + filesz:
            return offset + (addr - vaddr)
    raise ValueError(f"ELF address 0x{addr:x} with size {size} is not file-backed")


def rip_target(blob: bytes, instruction_offset: int) -> int:
    # The reference address is RIP following the 7-byte LEA plus signed displacement.
    displacement = int(struct.unpack_from("<i", blob, instruction_offset + 3)[0])
    # In this PIE, code virtual addresses equal their offsets in the text segment.
    segments = elf_load_segments(blob)
    for vaddr, file_offset, filesz, _ in segments:
        if file_offset <= instruction_offset < file_offset + filesz:
            instruction_va = vaddr + (instruction_offset - file_offset)
            return instruction_va + 7 + displacement
    raise ValueError("LEA instruction not in a loadable ELF segment")


def find_key_reference(blob: bytes) -> tuple[int, int, int]:
    # Find LEA RCX,[RIP+disp32] feeding a byte-wise XOR loop.
    for match in re.finditer(re.escape(b"\x48\x8d\x0d"), blob):
        offset = int(match.start())
        window = blob[offset + 7:offset + 75]
        xor = re.search(b"\x83\xf2(.)", window, flags=re.DOTALL)
        count = re.search(b"\x48\x83\xf8(.)", window, flags=re.DOTALL)
        if xor is None or count is None:
            continue
        xor_byte = int(xor.group(1)[0])
        key_length = int(count.group(1)[0])
        if 1 <= key_length <= 64:
            addr = rip_target(blob, offset)
            try:
                key_offset = virtual_to_file(elf_load_segments(blob), addr, key_length)
            except ValueError:
                continue
            return key_offset, xor_byte, key_length
    raise ValueError("Cannot locate the decoded-key loop in ELF code")


def find_payload_reference(blob: bytes, key_offset: int) -> tuple[int, int]:
    # Find a nearby LEA RDI,[RIP+disp32] whose loop bounds the payload length.
    for match in re.finditer(re.escape(b"\x48\x8d\x3d"), blob):
        offset = int(match.start())
        window = blob[offset + 7:offset + 135]
        count = re.search(b"\x48\x83\xfa(.)", window, flags=re.DOTALL)
        if count is None:
            continue
        payload_length = int(count.group(1)[0])
        if not 1 <= payload_length <= 127:
            continue
        addr = rip_target(blob, offset)
        try:
            payload_offset = virtual_to_file(elf_load_segments(blob), addr, payload_length)
        except ValueError:
            continue
        if payload_offset != key_offset:
            return payload_offset, payload_length
    raise ValueError("Cannot locate encrypted payload reference and loop bound")


def main() -> None:
    blob = INPUT_FILE.read_bytes()
    key_offset, xor_byte, key_length = find_key_reference(blob)
    payload_offset, payload_length = find_payload_reference(blob, key_offset)
    encoded_key = blob[key_offset:key_offset + key_length]
    encrypted_payload = blob[payload_offset:payload_offset + payload_length]
    key = bytes(int(value) ^ xor_byte for value in encoded_key)
    decoded = bytes(
        int(value) ^ int(key[index % len(key)])
        for index, value in enumerate(encrypted_payload)
    )

    print(f"Key reference: offset=0x{key_offset:x}, length={key_length}, XOR=0x{xor_byte:02x}")
    print(f"Payload reference: offset=0x{payload_offset:x}, length={payload_length}")
    print(f"Key: {key.decode('ascii')}")
    print(f"FLAG: {decoded.decode('ascii')}")


if __name__ == "__main__":
    main()
