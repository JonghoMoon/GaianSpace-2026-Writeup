
#!/usr/bin/env python3
import base64
import re
from pathlib import Path

DUMP_FILE = Path("mem.dmp")
OUTPUT_FILE = Path("Invoice_FoundationOne.pdf")

data = DUMP_FILE.read_bytes()

# Locate the phishing email in the memory dump.
start = data.find(b'From: "Susan Calvin, Contracts"')
if start < 0:
    raise ValueError("Phishing email not found")

boundary = b"--=_gaian_7f2a_boundary--"
end = data.find(boundary, start)
if end < 0:
    raise ValueError("MIME boundary not found")

email_data = data[start:end]

# Recover the base64-encoded MIME attachment.
pattern = (
    rb'Content-Disposition:\s*attachment;\s*'
    rb'filename="([^"]+)"\r?\n\r?\n'
    rb'([A-Za-z0-9+/\r\n=]+)'
)

match = re.search(pattern, email_data)
if match is None:
    raise ValueError("MIME attachment not found")

pdf_data = base64.b64decode(match.group(2), validate=False)

if not pdf_data.startswith(b"%PDF-"):
    raise ValueError("Invalid PDF header")

OUTPUT_FILE.write_bytes(pdf_data)

# Search the recovered PDF for the embedded flag.
flag_match = re.search(rb"GAIANSPACE\{[^}]+\}", pdf_data)
if flag_match is None:
    raise ValueError("Flag not found")

flag = flag_match.group(0).decode("ascii")

print(f"Recovered attachment: {OUTPUT_FILE}")
print(f"Size: {len(pdf_data)} bytes")
print(f"FLAG: {flag}")

