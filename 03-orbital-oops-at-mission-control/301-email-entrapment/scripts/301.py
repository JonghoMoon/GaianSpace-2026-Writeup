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
