#!/usr/bin/env python3
# Dependencies: Python 3 standard library only (no pip packages required).
"""Reconstruct HTTP TCP streams from PCAP and decrypt the actual C2 reply."""

import base64
import ipaddress
import re
import struct
from collections import defaultdict
from pathlib import Path

INPUT_FILE = Path("ground_c2_traffic.pcap")
Endpoint = tuple[str, int]
Flow = tuple[Endpoint, Endpoint]


def pcap_tcp_segments(path: Path) -> dict[Flow, list[tuple[int, bytes]]]:
    blob = path.read_bytes()
    magic = blob[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        order = "<"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        order = ">"
    else:
        raise ValueError("Expected classic PCAP global header")
    if len(blob) < 24:
        raise ValueError("Truncated PCAP header")
    link_type = int(struct.unpack_from(f"{order}I", blob, 20)[0])
    if link_type != 1:
        raise ValueError("Only Ethernet link-layer PCAP is supported")

    streams: dict[Flow, list[tuple[int, bytes]]] = defaultdict(list)
    cursor = 24
    while cursor < len(blob):
        if cursor + 16 > len(blob):
            raise ValueError("Truncated PCAP packet header")
        _sec, _frac, captured_len, _wire_len = struct.unpack_from(
            f"{order}IIII", blob, cursor
        )
        cursor += 16
        captured_len = int(captured_len)
        packet = blob[cursor:cursor + captured_len]
        if len(packet) != captured_len:
            raise ValueError("Truncated PCAP frame")
        cursor += captured_len

        if len(packet) < 14 or packet[12:14] != b"\x08\x00":
            continue
        ipv4 = packet[14:]
        if len(ipv4) < 20 or ipv4[0] >> 4 != 4 or ipv4[9] != 6:
            continue
        ip_header_len = (ipv4[0] & 15) * 4
        ip_total_len = int.from_bytes(ipv4[2:4], "big")
        flags_frag = int.from_bytes(ipv4[6:8], "big")
        if flags_frag & 0x3FFF:
            raise ValueError("Fragmented TCP over IPv4 is not supported")
        if len(ipv4) < ip_total_len or ip_total_len < ip_header_len + 20:
            raise ValueError("Invalid or truncated IPv4 packet")

        src_ip = str(ipaddress.ip_address(ipv4[12:16]))
        dst_ip = str(ipaddress.ip_address(ipv4[16:20]))
        tcp = ipv4[ip_header_len:ip_total_len]
        sport, dport, seq = struct.unpack_from("!HHI", tcp, 0)
        tcp_header_len = (tcp[12] >> 4) * 4
        if tcp_header_len < 20 or tcp_header_len > len(tcp):
            raise ValueError("Invalid TCP header")
        data = tcp[tcp_header_len:]
        if data:
            flow: Flow = ((src_ip, int(sport)), (dst_ip, int(dport)))
            streams[flow].append((int(seq), data))
    return streams


def reassemble(segments: list[tuple[int, bytes]]) -> bytes:
    ordered = sorted(segments, key=lambda item: item[0])
    if not ordered:
        return b""
    first_seq = int(ordered[0][0])
    assembled = bytearray()
    for seq, payload in ordered:
        start = int(seq) - first_seq
        if start > len(assembled):
            raise ValueError("Missing TCP data in a reconstructed flow")
        overlap = len(assembled) - start
        if overlap >= len(payload):
            if assembled[start:start + len(payload)] != payload:
                raise ValueError("Conflicting retransmitted TCP data")
            continue
        if overlap and assembled[start:] != payload[:overlap]:
            raise ValueError("Conflicting TCP overlap")
        assembled.extend(payload[overlap:])
    return bytes(assembled)


def parse_http(message: bytes) -> tuple[str, dict[str, str], bytes]:
    header, separator, body = message.partition(b"\r\n\r\n")
    if not separator:
        raise ValueError("HTTP header terminator not found")
    lines = header.decode("iso-8859-1").split("\r\n")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, sep, value = line.partition(":")
        if sep:
            headers[name.lower().strip()] = value.strip()
    if "content-length" in headers:
        body_length = int(headers["content-length"])
        if len(body) < body_length:
            raise ValueError("Truncated HTTP body")
        body = body[:body_length]
    return lines[0], headers, body


def rc4_decrypt(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("RC4 requires a nonempty key")
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + int(key[i % len(key)])) % 256
        state[i], state[j] = state[j], state[i]

    i = 0
    j = 0
    output = bytearray()
    for value in data:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        keystream = state[(state[i] + state[j]) % 256]
        output.append(int(value) ^ int(keystream))
    return bytes(output)


def main() -> None:
    raw_flows = pcap_tcp_segments(INPUT_FILE)
    flows = {flow: reassemble(parts) for flow, parts in raw_flows.items()}
    print(f"TCP directional streams: {len(flows)}")

    # Identify exfiltration from the request content, not from a predefined IP,
    # session token, hostname, or encrypted response string.
    candidates: list[tuple[Flow, str, str, str, bytes]] = []
    for flow, raw_request in flows.items():
        if not raw_request.startswith(b"POST "):
            continue
        request_line, request_headers, request_body = parse_http(raw_request)
        if not request_line.startswith("POST /relay/telemetry "):
            continue
        try:
            request_plaintext = base64.b64decode(request_body, validate=True)
        except (ValueError, base64.binascii.Error):
            continue
        if b"exfil=" not in request_plaintext:
            print(f"Skipped benign relay request: {request_headers.get('host', '?')}")
            continue

        session = request_headers.get("x-relay-session")
        if not session:
            raise ValueError("Exfiltration request is missing X-Relay-Session")
        reverse: Flow = (flow[1], flow[0])
        if reverse not in flows:
            raise ValueError("Missing C2 response stream")
        response_line, _response_headers, response_body = parse_http(flows[reverse])
        if not response_line.startswith("HTTP/1.1 200"):
            raise ValueError(f"Unexpected server reply: {response_line}")
        candidates.append((flow, request_headers.get("host", ""), session, request_line, response_body))
        print(f"C2 exfil request: {request_plaintext.decode('ascii')}")

    if len(candidates) != 1:
        raise ValueError(f"Expected one exfiltration flow; found {len(candidates)}")
    flow, hostname, session, request_line, response_body = candidates[0]
    print(f"C2 TCP flow: {flow[0]} -> {flow[1]}")
    print(f"C2 endpoint: {hostname} ({request_line})")
    print(f"Recovered X-Relay-Session: {session}")
    print(f"Base64 response bytes: {len(response_body)}")

    ciphertext = base64.b64decode(response_body, validate=True)
    plaintext = rc4_decrypt(ciphertext, session.encode("ascii"))
    decoded = plaintext.decode("ascii")
    print(decoded)
    flag_match = re.search(r"GAIANSPACE\{[^}]+\}", decoded)
    if flag_match is None:
        raise ValueError("No flag in decrypted C2 response")
    print(f"FLAG: {flag_match.group(0)}")


if __name__ == "__main__":
    main()
