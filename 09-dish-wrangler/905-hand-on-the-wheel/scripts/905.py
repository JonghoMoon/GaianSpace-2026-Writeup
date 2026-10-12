
#!/usr/bin/env python3
import hashlib
import hmac
import json
import re
import struct
import zipfile
from pathlib import Path

LOG_FILE = Path("signed_cmds.log")
ZIP_FILE = Path("service.zip")

STATION_ID = "KESTREL-ARRAY"
EPOCH_DAY = "26278"


def derive_key(epoch: str) -> bytes:
    value = f"{STATION_ID}:{epoch}".encode("utf-8")
    return hashlib.sha256(value).digest()


def canonical_command(command: dict) -> bytes:
    value = (
        f"{command['station_id']}|"
        f"{command['action']}|"
        f"{command['angle_deg']}|"
        f"{command['nonce']}"
    )
    return value.encode("utf-8")


def verify_signature(command: dict, key: bytes) -> bool:
    actual = hmac.new(
        key,
        canonical_command(command),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(actual, str(command["sig"]))


def recover_epoch(commands: list[dict]) -> tuple[str, bytes]:
    # Search fractional epoch lengths from one through five digits.
    for width in range(1, 6):
        for number in range(10 ** width):
            epoch = f"{EPOCH_DAY}.{number:0{width}d}"
            key = derive_key(epoch)

            if not verify_signature(commands[0], key):
                continue

            # Verify every captured command before accepting the key.
            if all(verify_signature(command, key) for command in commands):
                return epoch, key

    raise RuntimeError("Matching epoch not found")


def decrypt_flag(ciphertext: bytes, key: bytes) -> str:
    stream = bytearray()
    counter = 0

    while len(stream) < len(ciphertext):
        block = hmac.new(
            key,
            b"SLEW-CTR" + struct.pack(">I", counter),
            hashlib.sha256,
        ).digest()
        stream.extend(block)
        counter += 1

    plaintext = bytes(
        value ^ stream[index]
        for index, value in enumerate(ciphertext)
    )

    return plaintext.decode("ascii")


def main() -> None:
    commands = []

    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("{"):
            commands.append(json.loads(line))

    if len(commands) < 1:
        raise ValueError("No signed commands found")

    epoch, key = recover_epoch(commands)

    print(f"Recovered epoch: {epoch}")
    print(f"Verified signatures: {len(commands)}")

    with zipfile.ZipFile(ZIP_FILE) as archive:
        ciphertext = archive.read("service/flag.enc")

    flag = decrypt_flag(ciphertext, key)

    if re.fullmatch(r"GAIANSPACE\{[^}]+\}", flag) is None:
        raise ValueError("Invalid decrypted flag")

    print(f"FLAG: {flag}")


if __name__ == "__main__":
    main()
