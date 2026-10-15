# 802-sections-in-the-static

| | |
|---|---|
| **Category** | 08 — Silent Carrier |
| **Points** | 75 |

## Description

The name on the relay was only the letterhead. Under it, Oduya hears a second conversation riding in the same carrier, the way a whisper rides a shout. HALCYON-7 was forwarding someone else’s words. The link faded while it did, and it repeated itself. Some of the repeats came back rotten.

She kept the grab anyway. The crew log is in there, split across the copies that still hold together. Pell has already decided it is the television picture from the rack plate, and he has written a channel number on the tape that belongs to a weather chart from last month.

Pull the crew’s words out of the static. Leave the rotten copies where they fell.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `eumetcast_grab.ts` — the grab, this one continuous
- `mpe_notes.md` — a page from a weather-bird handbook, torn at the corner

## Solution

### Steps

1. Parse the continuous 188-byte MPEG-TS capture and select MPE PID `0x012C`.
2. Extract MPE sections (table ID `0x3E`) and validate MPEG CRC-32.
3. Reject the corrupted repeated sections rather than merging their contents.
4. Decode the IPv4/UDP datagrams inside valid MPE sections.
5. Reassemble `SEG00` through `SEG03` in numeric order.

### Reproduction

Run the supplied Python solver with the original challenge files in the locations expected by its source code.

```bash
python3 802.py
```

Expected relevant output:

```text
Packet 6: CRC FAIL
Packet 11: CRC FAIL
Packet 16: SEG02 = gram_r3a
Packet 21: CRC FAIL
Packet 26: SEG01 = CE{mpe_d
Packet 31: SEG00 = GAIANSPA
Packet 36: CRC FAIL
Packet 41: SEG03 = ssembly}
CRC-valid: 4, rejected: 4
FLAG: GAIANSPACE{mpe_dgram_r3assembly}
```

### Exploit Code

```python
#!/usr/bin/env python3
"""Reassemble CRC-valid DVB MPE sections from a continuous MPEG-TS capture."""
from pathlib import Path
import re

TS_SIZE = 188
MPE_PID = 0x012C

def mpeg_crc32(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for value in data:
        crc ^= int(value) << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
    return crc

def main() -> None:
    data = Path('eumetcast_grab.ts').read_bytes()
    if len(data) % TS_SIZE:
        raise ValueError('Not a complete 188-byte TS capture')
    segments: dict[int, bytes] = {}
    valid_count = 0
    rejected_count = 0
    for packet_index in range(len(data) // TS_SIZE):
        packet = data[packet_index * TS_SIZE:(packet_index + 1) * TS_SIZE]
        if packet[0] != 0x47:
            raise ValueError(f'Missing sync at packet {packet_index}')
        pid = (int(packet[1] & 0x1F) << 8) | int(packet[2])
        if pid != MPE_PID or not (packet[1] & 0x40):
            continue
        adaptation_field_control = (packet[3] >> 4) & 3
        if not adaptation_field_control & 1:
            continue
        offset = 4
        if adaptation_field_control & 2:
            offset += 1 + int(packet[offset])
        pointer = int(packet[offset])
        section_offset = offset + 1 + pointer
        section_length = ((int(packet[section_offset + 1]) & 0x0F) << 8) | int(packet[section_offset + 2])
        section = packet[section_offset:section_offset + 3 + section_length]
        if len(section) != 3 + section_length or section[0] != 0x3E:
            continue
        if mpeg_crc32(section) != 0:
            rejected_count += 1
            print(f'Packet {packet_index}: CRC FAIL')
            continue
        valid_count += 1
        # MPE header occupies 12 bytes; the datagram is IPv4/UDP.
        ip = section[12:-4]
        if len(ip) < 28 or (ip[0] >> 4) != 4 or ip[9] != 17:
            raise ValueError('Unexpected MPE datagram')
        ip_header_size = (int(ip[0]) & 0x0F) * 4
        ip_total_length = int.from_bytes(ip[2:4], 'big')
        udp = ip[ip_header_size:ip_total_length]
        if len(udp) < 8:
            raise ValueError('UDP header truncated')
        udp_length = int.from_bytes(udp[4:6], 'big')
        message = udp[8:udp_length]
        match = re.fullmatch(rb'SEG(\d{2})\|(.+)', message)
        if match is None:
            raise ValueError(f'Unexpected MPE payload: {message!r}')
        seq = int(match.group(1), 10)
        part = match.group(2)
        if seq in segments and segments[seq] != part:
            raise ValueError(f'Conflicting CRC-valid segment {seq}')
        segments[seq] = part
        print(f'Packet {packet_index}: SEG{seq:02d} = {part.decode("ascii")}')
    if not segments or sorted(segments) != list(range(len(segments))):
        raise ValueError('Missing segments')
    flag = b''.join(segments[i] for i in sorted(segments)).decode('ascii')
    if re.fullmatch(r'GAIANSPACE\{[^}]+\}', flag) is None:
        raise ValueError(f'Invalid assembled flag: {flag}')
    print(f'CRC-valid: {valid_count}, rejected: {rejected_count}')
    print('FLAG:', flag)

if __name__ == '__main__':
    main()
```

## Flag

```text
GAIANSPACE{mpe_dgram_r3assembly}
```
