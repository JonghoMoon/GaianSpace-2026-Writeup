# 904-gotox-maint

| | |
|---|---|
| **Category** | 09 — Dish Wrangler |
| **Points** | 100 |

## Description

The dish unlocked itself with the station’s own maintenance tool. Lindqvist pulled `gotox-maint` off the controller before anyone could be brave about it. The tool will not talk until it is shown a key. The key is not on a sticky note. The tool builds the key while it runs, out of marks it already carries.

A laminated card in the drawer says the night-shift default is `MAINT-0000-0000`. Lindqvist tried it. The tool laughed, in the only way a tool laughs, which is by staying locked.

The token it prints, once it believes you, is what the bridge asked for.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `gotox-maint` — the tool, copied off the controller
- `maint_notes.md` — the drawer card, including the lie

## Solution

### Steps

1. Inspect the Linux x86-64 ELF binary and locate its `MAINT-%04X-%04X` format string.
2. Extract nearby immediate constants loaded into `r8d` and `r9d` from the machine-code bytes, without relying on `objdump` output formatting.
3. Construct candidate maintenance keys and test them by running a temporary copy of the original binary.
4. Recover `MAINT-2189-8A44`, unlock the tool, and read its token.

### Reproduction

The original `904.py` was recovered from the previous working files; this is the machine-code-based version that avoids the earlier `objdump` formatting failure.

Run the supplied solver with the original challenge files in the locations expected by its source code.

```bash
python3 904.py
```

Expected relevant output:

```text
Candidate keys: 1
Recovered key: MAINT-2189-8A44
maintenance mode unlocked
token: GAIANSPACE{m41nt_m0de_unl0cked}
FLAG: GAIANSPACE{m41nt_m0de_unl0cked}
```

### Exploit Code

```python
#!/usr/bin/env python3
"""GaianSpace 904: recover the generated key directly from x86-64 machine code."""

import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

BINARY = Path(__file__).resolve().parent / "gotox-maint"
FORMAT = b"MAINT-%04X-%04X\x00"


def extract_keys(binary: bytes) -> list[str]:
    if not binary.startswith(b"\x7fELF") or binary[4] != 2 or binary[18:20] != b"\x3e\x00":
        raise ValueError("Expected a Linux x86-64 ELF binary")
    if FORMAT not in binary:
        raise ValueError("MAINT key format string was not found")

    # x86-64 encoding: 41 B8 imm32 = mov r8d, imm32;
    #                  41 B9 imm32 = mov r9d, imm32.
    first_values: list[tuple[int, int]] = []
    second_values: list[tuple[int, int]] = []

    for index in range(len(binary) - 5):
        instruction = binary[index:index + 2]
        if instruction not in (b"\x41\xb8", b"\x41\xb9"):
            continue
        value = int(struct.unpack_from("<I", binary, index + 2)[0])
        if value > 0xFFFF:
            continue
        if instruction == b"\x41\xb8":
            first_values.append((index, value))
        else:
            second_values.append((index, value))

    keys: set[str] = set()
    for first_offset, first_value in first_values:
        for second_offset, second_value in second_values:
            # Both arguments are loaded close to the formatting call.
            if abs(first_offset - second_offset) <= 64:
                keys.add(f"MAINT-{first_value:04X}-{second_value:04X}")
    if not keys:
        raise RuntimeError("Could not locate neighboring r8d/r9d immediates")
    return sorted(keys)


def main() -> None:
    if not BINARY.is_file():
        raise FileNotFoundError(BINARY)
    candidates = extract_keys(BINARY.read_bytes())
    print(f"Candidate keys: {len(candidates)}")

    # Run an executable copy instead of modifying the original evidence.
    with tempfile.TemporaryDirectory(prefix="gaian904_") as directory:
        executable = Path(directory) / "gotox-maint"
        shutil.copyfile(BINARY, executable)
        executable.chmod(0o700)
        for key in candidates:
            result = subprocess.run(
                [str(executable), "--unlock", key],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            output = result.stdout + result.stderr
            match = re.search(r"GAIANSPACE\{[^}\r\n]+\}", output)
            if match is None:
                continue
            print(f"Recovered key: {key}")
            print(output.strip())
            print(f"FLAG: {match.group(0)}")
            return

    raise RuntimeError(f"None of the extracted keys unlocked the tool: {candidates}")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{m41nt_m0de_unl0cked}
```
