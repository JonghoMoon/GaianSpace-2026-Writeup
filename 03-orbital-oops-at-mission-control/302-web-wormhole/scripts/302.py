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

