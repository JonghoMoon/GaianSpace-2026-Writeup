#!/usr/bin/env python3
"""Reconstruct GaianSpace 303 exfiltration and recover the Gerber FAB-NOTE."""

import base64
import hashlib
import io
import re
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

BASE = Path(__file__).resolve().parent


def fat12_file(image: bytes, filename: bytes) -> bytes:
    bps = int(struct.unpack_from('<H', image, 11)[0])
    sectors_per_cluster = int(image[13])
    reserved = int(struct.unpack_from('<H', image, 14)[0])
    fat_count = int(image[16])
    root_entries = int(struct.unpack_from('<H', image, 17)[0])
    sectors_per_fat = int(struct.unpack_from('<H', image, 22)[0])
    root_sectors = (root_entries * 32 + bps - 1) // bps
    root_start = (reserved + fat_count * sectors_per_fat) * bps
    data_start = (reserved + fat_count * sectors_per_fat + root_sectors) * bps
    fat = image[reserved * bps:(reserved + sectors_per_fat) * bps]

    for off in range(root_start, root_start + root_entries * 32, 32):
        entry = image[off:off + 32]
        if entry[0] == 0:
            break
        if entry[0] == 0xE5 or entry[11] == 0x0F:
            continue
        if entry[:11].upper() != filename.upper():
            continue
        cluster = int(struct.unpack_from('<H', entry, 26)[0])
        size = int(struct.unpack_from('<I', entry, 28)[0])
        result = bytearray()
        seen: set[int] = set()
        while 2 <= cluster < 0xFF8:
            if cluster in seen:
                raise ValueError('FAT cluster loop')
            seen.add(cluster)
            start = data_start + (cluster - 2) * sectors_per_cluster * bps
            result.extend(image[start:start + sectors_per_cluster * bps])
            entry_off = cluster + cluster // 2
            packed = int.from_bytes(fat[entry_off:entry_off + 2], 'little')
            cluster = (packed >> 4) & 0xFFF if cluster & 1 else packed & 0xFFF
        return bytes(result[:size])
    raise ValueError(f'FAT file not found: {filename!r}')


def tcp_streams(pcap: bytes) -> dict[tuple[bytes, bytes, int, int], bytes]:
    magic = pcap[:4]
    if magic == b'\xd4\xc3\xb2\xa1':
        endian = '<'
    elif magic == b'\xa1\xb2\xc3\xd4':
        endian = '>'
    else:
        raise ValueError('Expected classic PCAP')
    linktype = int(struct.unpack_from(endian + 'I', pcap, 20)[0])
    if linktype != 1:
        raise ValueError('Expected Ethernet link type')
    segments: dict[tuple[bytes, bytes, int, int], list[tuple[int, bytes]]] = defaultdict(list)
    offset = 24
    while offset + 16 <= len(pcap):
        _, _, captured, _ = struct.unpack_from(endian + 'IIII', pcap, offset)
        offset += 16
        frame = pcap[offset:offset + captured]
        offset += captured
        if len(frame) < 14 or frame[12:14] != b'\x08\x00':
            continue
        ip = frame[14:]
        if len(ip) < 20 or ip[9] != 6:
            continue
        ihl = (ip[0] & 15) * 4
        ip_len = int.from_bytes(ip[2:4], 'big')
        tcp = ip[ihl:ip_len]
        if len(tcp) < 20:
            continue
        hdr_len = (tcp[12] >> 4) * 4
        payload = tcp[hdr_len:]
        if not payload:
            continue
        sport = int.from_bytes(tcp[:2], 'big')
        dport = int.from_bytes(tcp[2:4], 'big')
        seq = int.from_bytes(tcp[4:8], 'big')
        key = (ip[12:16], ip[16:20], sport, dport)
        segments[key].append((seq, payload))

    output = {}
    for key, chunks in segments.items():
        chunks.sort(key=lambda item: item[0])
        initial = chunks[0][0]
        assembled = bytearray()
        for seq, payload in chunks:
            pos = seq - initial
            if pos > len(assembled):
                raise ValueError(f'Missing TCP segment on flow {key}')
            skip = max(0, len(assembled) - pos)
            assembled.extend(payload[skip:])
        output[key] = bytes(assembled)
    return output


def main() -> None:
    disk = (BASE / 'attacker_disk.img').read_bytes()
    source = fat12_file(disk, b'ENCRYPTOPY ')
    match = re.search(rb'^PASSPHRASE\s*=\s*["\']([^"\']+)["\']', source, re.M)
    if match is None or b'sha256' not in source or b'[:16]' not in source:
        raise ValueError('Unexpected key derivation in ENCRYPTO.PY')
    passphrase = match.group(1)
    key = hashlib.sha256(passphrase).digest()[:16]
    print(f'Passphrase: {passphrase.decode("ascii")}')
    print(f'AES-128 key: {key.hex()}')

    streams = tcp_streams((BASE / 'exfil_upload.pcap').read_bytes())
    parts: dict[int, bytes] = {}
    upload_length = None
    expected_sha = None
    for flow, stream in streams.items():
        if flow[3] == 8080 and b'POST /upload/foundation_one_gerbers.zip.enc ' in stream:
            sep = stream.find(b'\r\n\r\n')
            if sep < 0:
                raise ValueError('HTTP header incomplete')
            head, body = stream[:sep], stream[sep + 4:]
            if not head.startswith(b'POST /upload/foundation_one_gerbers.zip.enc '):
                continue
            def header(name: bytes) -> int:
                found = re.search(rb'(?im)^' + re.escape(name) + rb':\s*(\d+)\s*$', head)
                if not found:
                    raise ValueError(f'Missing HTTP header {name!r}')
                return int(found.group(1))
            part_off = header(b'X-Upload-Offset')
            upload_length = header(b'X-Upload-Length')
            content_length = header(b'Content-Length')
            if len(body) < content_length:
                raise ValueError('Truncated HTTP upload body')
            parts[part_off] = body[:content_length]
            print(f'Upload offset {part_off}: {content_length} bytes')
        elif flow[2] == 8080:
            match_sha = re.search(rb'"sha256"\s*:\s*"([0-9a-f]{64})"', stream)
            if match_sha is not None and b'foundation_one_gerbers.zip.enc' in stream:
                expected_sha = match_sha.group(1).decode('ascii')

    if upload_length is None or not parts:
        raise ValueError('Foundation One upload not found')
    encoded = bytearray(upload_length)
    coverage = bytearray(upload_length)
    for off, payload in parts.items():
        if off + len(payload) > upload_length:
            raise ValueError('Upload fragment out of bounds')
        encoded[off:off + len(payload)] = payload
        coverage[off:off + len(payload)] = b'\x01' * len(payload)
    if not all(coverage):
        raise ValueError('Upload contains gaps')

    encrypted = base64.b64decode(bytes(encoded), validate=True)
    actual_sha = hashlib.sha256(bytes(encoded)).hexdigest()
    print(f'Reassembled upload: {len(encoded)} encoded bytes')
    print(f'Upload SHA256: {actual_sha}')
    if expected_sha is not None:
        if actual_sha != expected_sha:
            print('Note: status hash differs from Base64 body; checking decoded ciphertext')
            if hashlib.sha256(encrypted).hexdigest() != expected_sha:
                raise ValueError('Status SHA256 mismatch')
        print('Status SHA256 verified')

    iv, ciphertext = encrypted[:16], encrypted[16:]
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    if not zipfile.is_zipfile(io.BytesIO(plaintext)):
        raise ValueError('Decrypted data is not a ZIP archive')
    output = BASE / 'foundation_one_gerbers_recovered.zip'
    output.write_bytes(plaintext)
    print(f'Recovered ZIP: {output} ({len(plaintext)} bytes)')

    with zipfile.ZipFile(io.BytesIO(plaintext)) as archive:
        for name in archive.namelist():
            print(f'ZIP: {name}')
            if 'Silkscreen' in name:
                layer = archive.read(name)
                for note in re.findall(rb'G04[^\r\n]*FAB-NOTE[^\r\n]*', layer):
                    print('Fabricator note:', note.decode('ascii'))
                    flag = re.search(rb'GAIANSPACE\{[^}\r\n]+\}', note)
                    if flag:
                        print('FLAG:', flag.group().decode('ascii'))
                        return
    raise ValueError('Flag not found in silkscreen')


if __name__ == '__main__':
    main()

