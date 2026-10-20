# 204-payload-unleashed

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 100 |

## Description

The malicious frame did not just arrive at the array. It woke something that was already living in the decoder. The station runs an old telemetry decoder called ground_server, and after the frame came down the decoder started answering to a key it should never have accepted.

Forensics pulled the decoder off the array for you. It wants one argument, a key, and it throws back everything that is not the one it is waiting for. Reyes tried the mission id, the callsign, and his own initials, in that order, and got three rejections and a bad mood. Somewhere in the program is the key it actually wants and the thing it hands over when it hears it.

Make the decoder give up what the attacker armed.

**Flag format:** `GAIANSPACE{...}`

**Attachments:** `ground_server` — the station's telemetry decoder (Linux x86-64 ELF)

## Hints

Two hints were released during the event:

1. **It already knows** — The decoder carries the key it is waiting for. It does not store it where a quick glance would find it. The right key is reachable without guessing.
2. **Two coats of paint** — The key is hidden under one simple operation. What it reveals is hidden under the key.

## Solution

### Steps

**1. Inspect the decoder without executing it.**

`ground_server` is a stripped **Linux x86-64 ELF PIE**. The `.text` disassembly shows the key-reconstruction loop and the payload-decryption loop. This can be inspected manually with:

```bash
objdump -d -M intel ground_server
readelf -lW ground_server
```

Relevant instructions from the actual binary include:

```text
1123: lea rcx,[rip+0x2f1e]      # key bytes at virtual address 0x4048
1134: xor edx,0xffffffa7       # each encoded key byte XOR 0xA7
113e: cmp rax,0xd              # 13 key bytes
1158: lea rdi,[rip+0x2ec1]      # payload bytes at virtual address 0x4020
118e: xor al,BYTE PTR [rdi+rdx*1]
1198: cmp rdx,0x23             # 35 payload bytes
```

The integer-multiply/shift sequence around `0x1170` implements indexing by `index % 13` for the repeating key.

**2. Translate virtual addresses into file offsets.**

Because `ground_server` is a PIE, treat the disassembly addresses as **virtual addresses relative to the binary image**, not as assumed disk offsets. Use the ELF `PT_LOAD` program headers to map each referenced virtual address to a file offset:

| Item | Virtual address | File offset | Length |
|---|---:|---:|---:|
| Encoded key | `0x4048` | `0x3048` | 13 bytes |
| Encrypted payload | `0x4020` | `0x3020` | 35 bytes |

**3. Reproduce the embedded decoding loops.**

The updated `204.py` does not embed either file offset, the XOR byte or the data lengths as recovered constants. It scans for the relevant x86-64 RIP-relative `LEA` references and loop instructions, obtains the corresponding virtual addresses, translates them through ELF load segments and extracts the bytes. This pattern-matching method is designed for **this supplied binary**, not as a general-purpose x86 disassembler.

XOR the 13 encoded key bytes with the instruction's `0xA7` constant to obtain `EL06QL-UNLOCK`. XOR the payload with that key repeated over all 35 bytes to recover the flag. The ELF executable itself never needs to be run.

### Reproduction

Put `204.py` and `ground_server` in the same directory and run:

```bash
python3 204.py
```

The script uses only the Python standard library.

Expected output:

```text
Key reference: offset=0x3048, length=13, XOR=0xa7
Payload reference: offset=0x3020, length=35
Key: EL06QL-UNLOCK
FLAG: GAIANSPACE{b4ckd00r_in_the_dec0der}
```

### Solver Code

```python
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
```

## Flag

```text
GAIANSPACE{b4ckd00r_in_the_dec0der}
```
