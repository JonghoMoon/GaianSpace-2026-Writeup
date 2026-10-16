# 803-frames-inside-frames

| | |
|---|---|
| **Category** | 08 — Silent Carrier |
| **Points** | 100 |

## Description

Oduya was wrong about the shape of the pipe. Under the mailbox there is another wrapping, and under that a message that would not fit in one breath. The relay split it. The fade, helpful as ever, kept a second copy that looks just as sure of itself.

She swears this is not the same trick as last watch. Pell swears it is, and he has already started on the old handbook. One of the copies reads like a confession. The other only pretends to.

Find the copy that survived whole.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `relay_bbframes.ts` — another grab from the same dish
- `bbframe_notes.md` — what is left of the frame manual after the coffee

## Hints

Two hints were released during the event:

1. **Not the mailbox** — Last watch's handbook will open something. It will not open this. The message is wrapped, and then wrapped again.
2. **The copy that checks** — Two versions want to be believed. Only one of them still matches itself once the pieces are put back.

## Solution

### Steps

1. Extract BBFRAME data carried in private MPEG-TS sections on PID `270`.
2. Read BBHEADER data-field length and parse the embedded GSE packets.
3. Reassemble the fragments by GSE fragment identifier.
4. Validate the completed datagram against its MPEG CRC-32.
5. Reject the corrupt fragment `0x07`; decode the CRC-valid IPv4/UDP message from fragment `0x09`.

### Reproduction

Run the supplied Python solver with the original challenge files in the locations expected by its source code.

```bash
python3 803.py
```

Expected relevant output:

```text
Fragment 0x07: CRC expected=859FC517 actual=F083C0EF
  Rejected corrupted repeat
Fragment 0x09: CRC expected=859FC517 actual=859FC517
  UDP: MSG|GAIANSPACE{gse_fr4g_crc32_ok}
FLAG: GAIANSPACE{gse_fr4g_crc32_ok}
```


### Additional integrity checks

After reassembling the relevant TS private section on PID 270, the solver verifies the 10-byte BBHEADER: the tenth byte is CRC-8 over the first nine bytes (polynomial `0xD5`, initial state zero). Its DFL field is a **bit count** and must be byte-aligned for this dataset. GSE fragment headers then supply the fragment identifier, first-fragment total datagram length, and a final CRC-32/MPEG-2. The updated solver compares the reassembled datagram length plus the two-byte protocol type with the first fragment's declared length before trusting the final CRC. A corrupted repeat is rejected and the CRC-valid repeat yields the IPv4/UDP flag.

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
"""Recover CRC-valid fragmented GSE packets from a TS-carried BBFRAME grab."""
from collections import defaultdict
from pathlib import Path
import re

FILE = Path(__file__).with_name('relay_bbframes.ts')
TS_SIZE = 188
PID = 270


def crc32_mpeg(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for value in data:
        crc ^= int(value) << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
    return crc



def crc8_bbheader(data: bytes) -> int:
    # DVB-S2-style BBHEADER CRC-8: polynomial 0xD5, init 0.
    crc = 0
    for value in data:
        crc ^= int(value)
        for _ in range(8):
            crc = ((crc << 1) ^ (0xD5 if (crc & 0x80) else 0)) & 0xFF
    return crc

def gse_bytes(ts: bytes):
    if len(ts) % TS_SIZE:
        raise ValueError('TS data is not packet aligned')
    for off in range(0, len(ts), TS_SIZE):
        packet = ts[off:off + TS_SIZE]
        if packet[0] != 0x47:
            raise ValueError(f'Invalid TS sync at {off}')
        pid = ((packet[1] & 0x1F) << 8) | packet[2]
        if pid != PID:
            continue
        if not (packet[1] & 0x40):
            continue
        pointer = int(packet[4])
        section = packet[5 + pointer:]
        size = ((section[1] & 0x0F) << 8) | section[2]
        section = section[:3 + size]
        if section[0] != 0x80:
            continue
        # Private section content: marker byte, 10-byte BBHEADER, then BB payload.
        bbheader = section[4:14]
        if len(bbheader) != 10 or crc8_bbheader(bbheader[:9]) != bbheader[9]:
            raise ValueError(f'Invalid BBHEADER CRC-8 at TS offset {off}')
        dfl_bits = int.from_bytes(bbheader[4:6], 'big')
        if dfl_bits % 8 != 0:
            raise ValueError('Non byte-aligned BBFRAME payload')
        yield section[14:14 + dfl_bits // 8]


def main() -> None:
    ts = FILE.read_bytes()
    partial: dict[int, bytearray] = {}
    expected_lengths: dict[int, int] = {}
    for bb in gse_bytes(ts):
        pos = 0
        while pos + 2 <= len(bb):
            if bb[pos] == 0:
                break
            head = int.from_bytes(bb[pos:pos + 2], 'big')
            start = bool(head & 0x8000)
            end = bool(head & 0x4000)
            length = head & 0x0FFF
            if pos + 2 + length > len(bb):
                raise ValueError('Truncated GSE packet')
            body = bb[pos + 2:pos + 2 + length]
            pos += 2 + length
            if not body:
                continue
            fragment_id = int(body[0])
            if start and not end:
                if len(body) < 5:
                    raise ValueError('Invalid first fragment')
                # Total length is in body[1:3], protocol type in body[3:5].
                if body[3:5] != b'\x08\x00':
                    continue
                expected_lengths[fragment_id] = int.from_bytes(body[1:3], "big")
                partial[fragment_id] = bytearray(body[5:])
            elif not start and not end and fragment_id in partial:
                partial[fragment_id].extend(body[1:])
            elif not start and end and fragment_id in partial:
                if len(body) < 5:
                    continue
                full_datagram = bytes(partial.pop(fragment_id)) + body[1:-4]
                expected_length = expected_lengths.pop(fragment_id)
                if len(full_datagram) + 2 != expected_length:
                    raise ValueError(
                        f'Fragment 0x{fragment_id:02X}: total length mismatch '
                        f'{len(full_datagram)}+2 != {expected_length}'
                    )
                expected_crc = int.from_bytes(body[-4:], 'big')
                actual_crc = crc32_mpeg(full_datagram)
                print(f'Fragment 0x{fragment_id:02X}: CRC expected={expected_crc:08X} actual={actual_crc:08X}')
                if actual_crc != expected_crc:
                    print('  Rejected corrupted repeat')
                    continue
                if len(full_datagram) < 28 or full_datagram[0] >> 4 != 4:
                    raise ValueError('CRC-valid packet is not IPv4')
                ihl = (full_datagram[0] & 0x0F) * 4
                if full_datagram[9] != 17:
                    raise ValueError('Expected UDP')
                udp_length = int.from_bytes(full_datagram[ihl + 4:ihl + 6], 'big')
                message = full_datagram[ihl + 8:ihl + udp_length]
                print('  UDP:', message.decode('ascii'))
                match = re.search(rb'GAIANSPACE\{[^}]+\}', message)
                if match:
                    print('FLAG:', match.group().decode('ascii'))
                    return
    raise RuntimeError('No CRC-valid flag found')


if __name__ == '__main__':
    main()
```

## Flag

```text
GAIANSPACE{gse_fr4g_crc32_ok}
```
