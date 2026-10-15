#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
# Offline mode needs signed_cmds.log and service.zip in the working directory.
# --park additionally requires the supplied local 905 service to be running.

"""Recover the HMAC key and use it to decrypt or authorize a park command."""

import argparse
import hashlib
import hmac
import json
import re
import secrets
import struct
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

LOG_FILE = Path("signed_cmds.log")
ZIP_FILE = Path("service.zip")
EPOCH_DAY = "26278"  # The integer day is explicitly supplied in the challenge.


def derive_key(station_id: str, epoch: str) -> bytes:
    return hashlib.sha256(f"{station_id}:{epoch}".encode("utf-8")).digest()


def canonical_command(command: dict) -> bytes:
    return (
        f"{command['station_id']}|{command['action']}|"
        f"{command['angle_deg']}|{command['nonce']}"
    ).encode("utf-8")


def sign_command(command: dict, key: bytes) -> str:
    return hmac.new(key, canonical_command(command), hashlib.sha256).hexdigest()


def verify_signature(command: dict, key: bytes) -> bool:
    return hmac.compare_digest(sign_command(command, key), str(command["sig"]))


def read_commands() -> list[dict]:
    commands: list[dict] = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("{"):
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("Unexpected signed command record")
            commands.append(record)
    if not commands:
        raise ValueError("No signed commands found")
    stations = {str(record["station_id"]) for record in commands}
    if len(stations) != 1:
        raise ValueError("Captured records have inconsistent station identifiers")
    return commands


def recover_epoch(commands: list[dict]) -> tuple[str, bytes]:
    station_id = str(commands[0]["station_id"])
    for width in range(1, 6):
        for number in range(10**width):
            epoch = f"{EPOCH_DAY}.{number:0{width}d}"
            key = derive_key(station_id, epoch)
            if not verify_signature(commands[0], key):
                continue
            if all(verify_signature(command, key) for command in commands):
                return epoch, key
    raise RuntimeError("Matching epoch not found")


def decrypt_flag(ciphertext: bytes, key: bytes) -> str:
    stream = bytearray()
    counter = 0
    while len(stream) < len(ciphertext):
        stream.extend(
            hmac.new(
                key,
                b"SLEW-CTR" + struct.pack(">I", counter),
                hashlib.sha256,
            ).digest()
        )
        counter += 1
    plaintext = bytes(
        value ^ stream[index]
        for index, value in enumerate(ciphertext)
    )
    return plaintext.decode("ascii")


def read_encrypted_flag() -> bytes:
    with zipfile.ZipFile(ZIP_FILE) as archive:
        return bytes(archive.read("service/flag.enc"))


def forge_park(key: bytes, station_id: str, url: str, nonce: str) -> str:
    # int(0) is used to match the server's canonical string formatting.
    command: dict = {
        "station_id": station_id,
        "action": "park",
        "angle_deg": 0,
        "nonce": nonce,
    }
    command["sig"] = sign_command(command, key)
    request = urllib.request.Request(
        url=f"{url.rstrip('/')}/api/slew",
        data=json.dumps(command).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = int(response.status)
            result = json.load(response)
    except urllib.error.URLError as error:
        raise RuntimeError("Local 905 console is unavailable") from error
    if status != 200 or result.get("status") != "parked":
        raise RuntimeError(f"Park command was rejected: {result}")
    flag = str(result.get("flag", ""))
    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError(f"Unexpected park response: {result}")
    print("[Signed park command]")
    print(json.dumps(command, indent=2))
    print(f"Server status: {result['status']}")
    print(f"Server FLAG: {flag}")
    return flag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--park", action="store_true", help="also send a signed park command")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--nonce", default=None, help="Optional fixed nonce for reproducibility")
    args = parser.parse_args()

    commands = read_commands()
    epoch, key = recover_epoch(commands)
    print(f"Recovered epoch: {epoch}")
    print(f"Verified signatures: {len(commands)}")

    decrypted = decrypt_flag(read_encrypted_flag(), key)
    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", decrypted) is None:
        raise ValueError("Invalid decrypted flag")
    print(f"FLAG: {decrypted}")

    if args.park:
        nonce = str(args.nonce) if args.nonce is not None else secrets.token_hex(8)
        server_flag = forge_park(
            key, str(commands[0]["station_id"]), str(args.url), nonce
        )
        if server_flag != decrypted:
            raise ValueError("Offline and live service flags do not match")
        print("Offline and HTTP methods agree.")


if __name__ == "__main__":
    main()
