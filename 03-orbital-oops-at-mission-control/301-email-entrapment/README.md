# 301-email-entrapment

| | |
|---|---|
| **Category** | 03 — Orbital Oops at Mission Control |
| **Points** | 50 |

## Description

It started the way these always do: a friendly email, a document that had to be opened *today*, and an engineer who clicked. By the time anyone noticed, the machine was already talking to strangers. We froze it and pulled a dump of its working memory before powering it down.

Somewhere in that dump is the message that started it. The incident desk is chasing a cached credential it found in the noise and is sure that is the story. It is not the story. The story is the mail that came in dressed as a partner's contract, and the file it carried in with it. Find the mail, pull the attachment back out of it, and open what the engineer opened.

Recover the attachment and read what is inside.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**
- `mem.dmp` — a dump of the engineer's working memory, taken before shutdown

## Solution

### Steps

Find the MIME email in the memory dump, locate its Base64 PDF attachment, decode it, validate the PDF header, and search the recovered PDF for the flag.

### Reproduction

Run the supplied solver with the original challenge inputs in the paths expected by the source code.

```bash
python3 301.py
```

Expected relevant output:

```text
Recovered attachment: Invoice_FoundationOne.pdf
Size: 554 bytes
FLAG: GAIANSPACE{ph1sh_in_the_dump}
```

### Exploit Code

```python

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
```

## Flag

```text
GAIANSPACE{ph1sh_in_the_dump}
```
