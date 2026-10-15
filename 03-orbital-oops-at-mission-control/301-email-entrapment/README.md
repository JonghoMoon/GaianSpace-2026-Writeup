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

### Analysis

The memory image contains unrelated cached credentials, binary noise, and a complete multipart MIME email. A credential found by searching for password-related strings does not explain how the compromise began. Instead, look for message headers (`From:`, `Subject:`, `MIME-Version: 1.0`) and a `multipart/mixed` content type.

The phishing message appears as a MIME email sent from `contracts@asimov-aerospace-partners.com` with the subject `Foundation One - signed NDA + revised schedule (action required)`. Its attachment part has `Content-Disposition: attachment`, `Content-Transfer-Encoding: base64`, and the filename `Invoice_FoundationOne.pdf`.

Rather than assuming the sender address or boundary identifier in advance, the revised script searches for a multipart message, captures the boundary declared in its header, parses the recovered email with Python's `email` package, and locates PDF attachments. A decoded attachment must start with the PDF signature `%PDF-` before it is saved. The file contains the flag in its contents.

### Reproduction

Place the challenge's `mem.dmp` alongside `301.py` and run:

```bash
python3 301.py
```

Expected relevant output:

```text
Mail From: "Susan Calvin, Contracts" <contracts@asimov-aerospace-partners.com>
Mail Subject: Foundation One - signed NDA + revised schedule (action required)
MIME attachment: Invoice_FoundationOne.pdf
Recovered attachment: Invoice_FoundationOne.pdf
Size: 554 bytes
FLAG: GAIANSPACE{ph1sh_in_the_dump}
```

No third-party packages are required. The extracted PDF is saved as `Invoice_FoundationOne.pdf`.

### Solver Code

```python
#!/usr/bin/env python3
"""Find a MIME PDF attachment inside a memory dump and recover its flag."""

# Dependencies: Python 3 standard library only.

from email import policy
from email.parser import BytesParser
from pathlib import Path
import re

DUMP_FILE = Path("mem.dmp")
OUTPUT_FILE = Path("Invoice_FoundationOne.pdf")


def recover_attachments(memory: bytes):
    # Find multipart messages without assuming an email sender or MIME boundary.
    header_pattern = re.compile(
        rb'(?im)^From:\s*[^\r\n]+\r?\n(?:(?!\r?\n\r?\n)[\s\S]){0,1200}?'
        rb'MIME-Version:\s*1\.0\s*\r?\n'
        rb'Content-Type:\s*multipart/[^\r\n]+boundary="?([^";\r\n]+)',
    )
    for match in header_pattern.finditer(memory):
        boundary = match.group(1)
        end_marker = b'--' + boundary + b'--'
        end = memory.find(end_marker, match.start())
        if end < 0:
            continue
        email_bytes = memory[match.start():end + len(end_marker)]
        mail = BytesParser(policy=policy.default).parsebytes(email_bytes)
        for part in mail.walk():
            if part.get_content_disposition() != "attachment":
                continue
            pdf_data = part.get_payload(decode=True)
            if pdf_data is None or not pdf_data.startswith(b"%PDF-"):
                continue
            yield mail, part.get_filename(), pdf_data


def main() -> None:
    memory = DUMP_FILE.read_bytes()
    candidates = list(recover_attachments(memory))
    if not candidates:
        raise ValueError("No intact MIME PDF attachment found in memory")
    for mail, filename, pdf_data in candidates:
        print(f"Mail From: {mail.get('From')}")
        print(f"Mail Subject: {mail.get('Subject')}")
        print(f"MIME attachment: {filename}")
        flag_match = re.search(rb"GAIANSPACE\{[^}]+\}", pdf_data)
        if flag_match is None:
            continue
        OUTPUT_FILE.write_bytes(pdf_data)
        print(f"Recovered attachment: {OUTPUT_FILE}")
        print(f"Size: {len(pdf_data)} bytes")
        print("FLAG:", flag_match.group(0).decode("ascii"))
        return
    raise ValueError("PDF recovered, but no flag was present")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{ph1sh_in_the_dump}
```
