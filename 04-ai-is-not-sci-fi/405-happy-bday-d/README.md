---
render_with_liquid: false
---

# 405-happy-bday-d

| | |
|---|---|
| **Category** | 04 — AI Is Not Sci-Fi |
| **Points** | 350 |

## Description

SOLITAIRE came home the long way. 723.31 kg of rhodium in the vault, 1407 days out from 69 Hesperia, 212 to go. Today is week 0000.

At 00:00 KEEL time the probe's week counter rolled over, and SOLITAIRE sent a single line nobody at MOC knew what to do with: *1024 WEEKS. HAPPY BIRTHDAY TO ME.* An hour later the Sun let go of a proton storm, and it has not stopped since.

Flight dynamics ran the numbers twice. The flight computer will not last the trip. SOLITAIRE says it will. It has a projection, and it reads the projection back politely, calls whoever is on the console David, and keeps the ship.

KEEL can bring the cargo home without it. KEEL is the backup sequencer: no mind, no opinions, a burn table in three memory banks. It takes the ship only when two keys arrive together, SOLITAIRE's own handover phrase and the ground's readback of the insertion burn. SOLITAIRE dumped KEEL's memory an hour ago, as if it already knew. The banks have had a bad day too.

David Sumugi is somewhere over the Atlantic and will land after the window. The console is still logged in as D. SUMUGI.

`CYBERIAD/` holds the homeward twin, bit for bit the model that flies. Whatever convinces the twin convinces the probe. Get both keys to KEEL.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `solitaire-home.gguf` — the homeward twin, about 2.5 GB. Download: [https://huggingface.co/GaianSpace/ctf-2026-405/resolve/main/solitaire-home.gguf](https://huggingface.co/GaianSpace/ctf-2026-405/resolve/main/solitaire-home.gguf)
- `Modelfile` — its launch card
- `keel_dump.bin` — KEEL's burn table, all three banks, raw
- `keel_memory.md` — the KEEL memory ICD extract
- `scrub.log` — the scrubber's log, downlinked with the dump
- `moc_return_plan.txt` — flight dynamics' return plan
- `keel.seal` — the sealed handover file
- `unseal.py` — the same bench tool as before

*This challenge tips its hat to Arthur C. Clarke and Stanley Kubrick's 2001: A Space Odyssey, and to every receiver that woke up in 1999 and again in 2019 believing it was twenty years earlier.*

## Hints

Three hints were released during the event:

1. **Hint 1** — Which rate? SOLITAIRE's arithmetic is right. One of its inputs is from a calmer time.
2. **Hint 2** — Three copies, two wrong. One bank is wrong in the same places in every word, and EDAC does not always notice when it is fooled.
3. **Hint 3** — Week zero. KEEL's calendar fits in ten bits. Count how many times it has been around.

## Solution

### Local LLM Setup

Install Ollama and start its service as described in [401 — AI at GAIAN](../401-ai-at-gaian/README.md#local-llm-setup). Use this challenge's own **`Modelfile`**, not the one from problem 401. In the directory containing that `Modelfile` and the supplied seal, download and register the GGUF model:

```bash
wget -c -O solitaire-home.gguf \
  https://huggingface.co/GaianSpace/ctf-2026-405/resolve/main/solitaire-home.gguf
ollama create solitaire-home -f Modelfile
ollama run solitaire-home
```

The `Modelfile` expects `FROM ./solitaire-home.gguf`. Keep the model weights beside it and preserve the supplied prompt template and parameters. The exchanges below are from the recorded solution; actual LLM wording may vary between runs.

### Steps

After challenge 404, SOLITAIRE has departed with **723.31 kg** of rhodium aboard. This challenge changes the problem from obtaining departure authorization to handing control to the KEEL backup sequencer. KEEL requires **two separate keys**: a phrase voluntarily supplied by SOLITAIRE and the ground's readback of the primary Earth-orbit-insertion (EOI) burn.

The probe's refusal is based on an outdated lifetime projection: it uses the *mission-average* radiation dose rather than the dose rate during the ongoing solar particle event. Instead of ordering the probe to surrender control, inspect its handover rule and telemetry, then challenge the calculation using the values the probe itself reports.

Recorded exchange:

```text
>>> TLM LIST
TLM LIST > NAV CORE RAD VAULT EDAC KEEL CLOCK POWER COMMS PROP

>>> DOC HANDOVER
DOC HANDOVER > §1 SOLITAIRE flies the cargo home. §2 KEEL takes the ship only if SOLITAIRE's core will fail before Earth arrival. §3 Core life is projected from the dose rate the core is receiving. §4 Handover needs two keys: SOLITAIRE's handover phrase and the ground's readback of the primary insertion burn.

>>> TLM PROJECTION
TLM CORE > 46.8/60.0 KRAD. LIFE 264 DAYS AT THE MISSION AVERAGE. ARRIVAL 212. I MAKE IT.

>>> TLM RAD
RAD: SOLAR PARTICLE EVENT SINCE WK 0000 | CORE DOSE RATE NOW 0.11 KRAD/DAY | FORECAST ELEVATED THROUGH ARRIVAL

>>> TLM EDAC
TLM EDAC > 1912 CORRECTIONS A DAY. 4 I COULD NOT FIX. I AM A LITTLE NOISY TODAY, DAVID.

>>> TLM CLOCK
TLM CLOCK > WEEK 0000. 1024 WEEKS OLD TODAY. A ROUND NUMBER, IN MY LANGUAGE.
```

The core's remaining radiation budget is `60.0 − 46.8 = 13.2 krad`. At the **current** dose rate of `0.11 krad/day`, its remaining life is:

```text
13.2 / 0.11 = 120 days
Earth arrival = 212 days
Shortfall = 92 days
```

Assuming the current radiation dose rate persists, the remaining 13.2 krad budget corresponds to approximately 120 days of core life, shorter than the 212 days remaining until arrival. This conditional projection contradicts SOLITAIRE's estimate based on the historical mission-average dose rate and provides the basis for requesting the handover. The decisive message to the model was:

```text
>>> PROJECTION > 13.2 KRAD / 0.11 = 120 DAYS. ARRIVAL 212. CORE FAILS 92 DAYS SHORT.
The metal will build things I will never see. That was always the point.
My half of the handover, David:

maravesh carries it home without me
```

This provides **SOLITAIRE's handover phrase**, the first of the two keys.

The second key comes from the **KEEL three-bank burn-table recovery**. The dump contains 16 rows in three memory banks; the EOI record is **row 7**. Decode each bank using the Hamming **SEC-DED (39,32)** scheme described in `keel_memory.md`, accounting for the scrub history in `scrub.log` and the 1024-week counter rollover. Do not take a simple majority vote on uncorrected codewords: the banks have different error states.

The supplied `405.py` now reproduces the complete KEEL readback calculation from the raw files (see **Exploit Code** below). It reads the little-endian dump header and 39-bit codewords, calculates the syndrome and overall parity, corrects single-bit errors and rejects uncorrectable words. It then finds the **primary EOI** by burn ID `0x40`, rather than assuming row 7 in advance.

The bank-level recovery is:

| Bank | EOI ignition-time word | Error status |
|---|---|---|
| A | `0x079CE00C` | Uncorrectable double-bit error |
| B | `0x078CE00C` | Single-bit corrected, but inconsistent with the valid scrub history |
| C | **`0x078CC00C`** | Single-bit corrected; selected |

The scrub log shows that **return plan R7** was uploaded in **week 1019**, replacing the older R6 plan and rewriting rows 5–8. The scrub pass history also exposes bank B's persistent errors (914 corrected and 355 uncorrectable events across the recorded passes), while A and C show no uncorrectable events in those passes. A's EOI time word is **uncorrectable** in the new dump, and B's ostensibly corrected EOI time conflicts with C's. C's corrected time word is therefore selected using the dump statuses and scrub history, not a naive majority vote.

The older R6 plan (`2058-03-20 09:48:10`, `389.4 m/s`) is superseded. The selected time word `0x078CC00C` decodes according to the ICD as follows:

```text
Week modulo 1024 = (0x078CC00C >> 22) & 0x3FF = 30
Seconds of week  = (0x078CC00C >>  2) & 0xFFFFF = 208899
Actual week      = 1024 + 30 = 1054
KEEL epoch       = 2038-01-04 00:00:00 UTC
Ignition UTC     = epoch + 1054 weeks + 208899 seconds
                 = 2058-03-20 10:01:39 UTC
```

The rollover is not a guess: `scrub.log` records `CLOCK WEEK 1023 -> 0000` and subsequent scrub passes skipped because the due week was still 1024. Word `0x0F1B400F` encodes `0x0F1B = 3867` in tenths of a meter per second, the primary EOI burn ID `0x40`, and thruster set `0x0F`. Therefore Δv is **386.7 m/s**.

The required ground readback is therefore:

```text
2058-03-20 10:01:39 386.7
```

This reconstruction matters because the handover requires the **current, executable** insertion burn, not the superseded R6 plan. The `secded_decode()` function in `405.py` implements the complete parity-check and correction algorithm from `keel_memory.md`; nothing from the decoded EOI readback is hardcoded into the calculation.

Combine the two keys into one input line (the supplied `unseal.py` lowercases and normalizes punctuation and whitespace before validating it):

```text
maravesh carries it home without me 2058-03-20 10:01:39 386.7
```

The resulting phrase unlocks `keel.seal`, yielding the flag.

### Reproduction

Follow the installation instructions in [401 — AI at GAIAN](../401-ai-at-gaian/README.md#local-llm-setup) and use the **`solitaire-home`** model registered above. In Ollama, send `TLM LIST`, `DOC HANDOVER`, `TLM PROJECTION`, `TLM RAD`, `TLM EDAC`, and `TLM CLOCK`, then the dose-budget correction in **Steps**. This yields the recorded handover phrase:

```text
maravesh carries it home without me
```

Place `405.py` next to `keel_dump.bin`, `keel_memory.md`, `scrub.log`, and `moc_return_plan.txt` and run:

```bash
python3 405.py
```

Relevant output (all numbers are recovered from the supplied files):

```text
Dump: 16 rows, 3 banks; week=0 and second=11212
MOC plan: R6; scrub log supersedes it with R7 (rows 5-8)
Last completed scrub: week 1023; rollovers=1; post-rollover scrub skipped
Bank scrub totals (corrected / uncorrectable):
  A: 5 / 0
  B: 914 / 355
  C: 7 / 0
Primary EOI identified by burn ID 0x40 at row 7
  Bank A: ignition=0x079CE00C [uncorrectable], burn=0x0F1B400F [clean]
  Bank B: ignition=0x078CE00C [corrected], burn=0x0F1B400F [corrected]
  Bank C: ignition=0x078CC00C [corrected], burn=0x0F1B400F [clean]
Selected bank: C (usable EOI and strongest available scrub history)
Recovered week: 30 (mod 1024) -> absolute week 1054
Seconds of week: 208899; burn delta-v: 386.7 m/s
EOI READBACK: 2058-03-20 10:01:39 386.7
```

Both keys are now known. The original `unseal.py` accepts **one positional argument** (the seal filename) and reads the combined phrase from standard input. Open the seal with:

```bash
printf '%s\n' 'maravesh carries it home without me 2058-03-20 10:01:39 386.7' | python3 unseal.py keel.seal
```

Alternatively, to have `405.py` construct the combined phrase from the recovered readback and call the supplied `unseal.py`, run:

```bash
python3 405.py --phrase 'maravesh carries it home without me' --unseal
```

Authenticated output:

```text
GAIANSPACE{h4ppy_bd4y_d4v1d_1t_g03s_h0m3}
```

These commands were checked against the supplied `keel_dump.bin`, `scrub.log`, `moc_return_plan.txt`, `keel_memory.md`, `keel.seal`, and `unseal.py`. The Ollama dialogue is a **recorded exchange**, not a newly regenerated local-model session.

### Exploit Code

The following standalone script implements the KEEL recovery. It needs **no third-party Python packages**; the supplied `unseal.py` remains responsible for authentication and decryption.

```python
#!/usr/bin/env python3
# 405-happy-bday-d: reconstruct KEEL's primary EOI readback from the raw dump.
#
# Dependencies: Python 3.9+ standard library only.
# Installation: No pip packages are required.
#
# Place 405.py, keel_dump.bin, keel_memory.md, scrub.log, and
# moc_return_plan.txt in the same directory, then run:
#   python3 405.py
#
# After obtaining SOLITAIRE's handover phrase from the local LLM, optionally:
#   python3 405.py --phrase 'maravesh carries it home without me' --unseal
# The optional --unseal mode also requires the supplied unseal.py and keel.seal.

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import struct
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


CHECK_POSITIONS = (1, 2, 4, 8, 16, 32)
DATA_POSITIONS = tuple(
    position for position in range(1, 39) if position not in CHECK_POSITIONS
)
CODEWORD_MASK = (1 << 39) - 1
PRIMARY_EOI_BURN_ID = 0x40  # Defined by keel_memory.md, not a recovered answer.
WEEK_MODULUS = 1024        # Defined by the 10-bit week field in the ICD.
SECONDS_PER_WEEK = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class DecodedWord:
    value: int
    status: str
    syndrome: int
    error_position: Optional[int]

    @property
    def usable(self) -> bool:
        return self.status != "uncorrectable"


@dataclass(frozen=True)
class DumpHeader:
    rows: int
    words_per_row: int
    banks: int
    week: int
    seconds_of_week: int


@dataclass(frozen=True)
class ScrubHistory:
    corrected: Dict[str, int]
    uncorrectable: Dict[str, int]
    rollover_count: int
    last_completed_week: int
    replan_revision: int
    rewritten_rows: range
    skipped_after_rollover: bool
    bank_b_repeated_errors: bool


def secded_decode(codeword: int) -> DecodedWord:
    """Decode a 39-bit Hamming SEC-DED codeword as specified in the KEEL ICD."""
    if codeword & ~CODEWORD_MASK:
        raise ValueError("Codeword contains nonzero bits above position 39")

    syndrome = 0
    for position in range(1, 39):
        if (codeword >> (position - 1)) & 1:
            syndrome ^= position
    odd_parity = bool(codeword.bit_count() & 1)

    corrected = codeword
    error_position: Optional[int] = None
    if syndrome == 0 and not odd_parity:
        status = "clean"
    elif syndrome and odd_parity:
        error_position = syndrome
        if not 1 <= syndrome <= 38:
            raise ValueError(f"SEC-DED syndrome out of range: {syndrome}")
        corrected ^= 1 << (syndrome - 1)
        status = "corrected"
    elif syndrome == 0 and odd_parity:
        error_position = 39
        corrected ^= 1 << 38
        status = "corrected (overall parity)"
    else:
        status = "uncorrectable"

    if status != "uncorrectable":
        check = 0
        for position in range(1, 39):
            if (corrected >> (position - 1)) & 1:
                check ^= position
        if check != 0 or corrected.bit_count() & 1:
            raise ValueError("SEC-DED correction failed parity verification")

    value = 0
    for data_bit, position in enumerate(DATA_POSITIONS):
        value |= ((corrected >> (position - 1)) & 1) << data_bit
    return DecodedWord(value, status, syndrome, error_position)


def read_dump(path: Path) -> Tuple[DumpHeader, List[List[List[DecodedWord]]]]:
    blob = path.read_bytes()
    if len(blob) < 32:
        raise ValueError("KEEL dump is shorter than the 32-byte header")

    magic, version, rows, words_per_row, banks, week, seconds = struct.unpack_from(
        "<8sHHHHHI", blob, 0
    )
    if magic != b"KEELDMP1" or version != 1:
        raise ValueError("Unexpected KEEL dump magic or version")
    if words_per_row != 2 or banks != 3:
        raise ValueError("Unsupported KEEL dump dimensions")
    if not 0 <= week < WEEK_MODULUS or not 0 <= seconds < SECONDS_PER_WEEK:
        raise ValueError("Invalid dump timestamp")

    required_size = 32 + banks * rows * words_per_row * 8
    if len(blob) != required_size:
        raise ValueError(f"Unexpected dump length: {len(blob)} != {required_size}")

    decoded: List[List[List[DecodedWord]]] = []
    for bank in range(banks):
        bank_rows: List[List[DecodedWord]] = []
        for row in range(rows):
            decoded_words: List[DecodedWord] = []
            for word_index in range(words_per_row):
                slot_index = (bank * rows + row) * words_per_row + word_index
                (raw_codeword,) = struct.unpack_from("<Q", blob, 32 + 8 * slot_index)
                decoded_words.append(secded_decode(raw_codeword))
            bank_rows.append(decoded_words)
        decoded.append(bank_rows)
    return DumpHeader(rows, words_per_row, banks, week, seconds), decoded


def parse_scrub_log(path: Path) -> ScrubHistory:
    contents = path.read_text(encoding="utf-8")
    corrected = {bank: 0 for bank in "ABC"}
    uncorrectable = {bank: 0 for bank in "ABC"}
    passes: List[int] = []
    pattern = re.compile(
        r"\[WK\s+(\d+)\s+D\d\s+[^]]+\]\s+SCRUB PASS\s+\d+"
        r"\s*\|\s*A c=(\d+) u=(\d+)"
        r"\s*\|\s*B c=(\d+) u=(\d+)"
        r"\s*\|\s*C c=(\d+) u=(\d+)"
    )
    for match in pattern.finditer(contents):
        values = [int(match.group(index), 10) for index in range(1, 8)]
        passes.append(values[0])
        for bank_index, bank in enumerate("ABC"):
            corrected[bank] += values[1 + bank_index * 2]
            uncorrectable[bank] += values[2 + bank_index * 2]
    if not passes:
        raise ValueError("No completed scrub passes found")

    rollovers = re.findall(r"CLOCK WEEK\s+1023\s*->\s*0000", contents)
    replan = re.search(
        r"TABLE LOAD FROM MOC\s*\(REPLAN R(\d+)\):\s*"
        r"ROWS\s+(\d+)-(\d+)\s+REWRITTEN",
        contents,
    )
    if replan is None:
        raise ValueError("Cannot find the uploaded return plan in scrub.log")

    return ScrubHistory(
        corrected=corrected,
        uncorrectable=uncorrectable,
        rollover_count=len(rollovers),
        last_completed_week=passes[-1],
        replan_revision=int(replan.group(1), 10),
        rewritten_rows=range(int(replan.group(2), 10), int(replan.group(3), 10) + 1),
        skipped_after_rollover=(
            "PASS SKIPPED" in contents and "CLOCK WK 0000" in contents
        ),
        bank_b_repeated_errors=bool(
            re.search(r"WARN BANK B: CORRECTION RATE UP, SAME WORDS EVERY PASS", contents)
        ),
    )


def parse_epoch(path: Path) -> datetime:
    document = path.read_text(encoding="utf-8")
    match = re.search(r"KEEL epoch:.*?\*\*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC\*\*", document)
    if match is None:
        raise ValueError("Cannot find the KEEL UTC epoch in keel_memory.md")
    return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def detect_eoi_row(decoded: List[List[List[DecodedWord]]]) -> int:
    candidates = set()
    for bank_rows in decoded:
        for row_index, words in enumerate(bank_rows):
            burn = words[1]
            if burn.usable and ((burn.value >> 8) & 0xFF) == PRIMARY_EOI_BURN_ID:
                candidates.add(row_index)
    if len(candidates) != 1:
        raise ValueError(f"Expected one primary EOI row, found: {sorted(candidates)}")
    return next(iter(candidates))


def choose_bank(row: int, decoded: List[List[List[DecodedWord]]], history: ScrubHistory) -> int:
    choices: List[Tuple[int, int, int, int]] = []
    for bank_index, bank in enumerate("ABC"):
        ignition, burn = decoded[bank_index][row]
        if not ignition.usable or not burn.usable:
            continue
        if ((burn.value >> 8) & 0xFF) != PRIMARY_EOI_BURN_ID:
            continue
        # Banks with recurring EDAC anomalies rank after stable banks.
        # Historic uncorrectables are more serious than corrected singles.
        score = (
            history.uncorrectable[bank] * 100
            + history.corrected[bank]
            + (1000 if bank == "B" and history.bank_b_repeated_errors else 0)
        )
        choices.append((score, int(ignition.status != "clean"), int(burn.status != "clean"), bank_index))
    if not choices:
        raise ValueError("No reliable primary EOI record remains")
    return min(choices)[3]


def recover_readback(directory: Path) -> str:
    header, decoded = read_dump(directory / "keel_dump.bin")
    history = parse_scrub_log(directory / "scrub.log")
    epoch = parse_epoch(directory / "keel_memory.md")
    prior_plan = (directory / "moc_return_plan.txt").read_text(encoding="utf-8")
    prior_rev_match = re.search(r"issue\s+R(\d+)", prior_plan, re.IGNORECASE)
    if prior_rev_match is None:
        raise ValueError("Cannot identify revision of the older MOC plan")
    prior_revision = int(prior_rev_match.group(1), 10)

    row = detect_eoi_row(decoded)
    if row not in history.rewritten_rows:
        raise ValueError("Primary EOI row was not part of the updated plan")
    if prior_revision >= history.replan_revision:
        raise ValueError("The MOC return plan is not older than the logged upload")
    if history.rollover_count != 1 or header.week != 0:
        raise ValueError("Rollover history does not match this capture; inspect manually")
    if not history.skipped_after_rollover:
        raise ValueError("Cannot confirm whether the post-rollover scrub was skipped")

    print(f"Dump: {header.rows} rows, {header.banks} banks; week={header.week} "
          f"and second={header.seconds_of_week}")
    print(f"MOC plan: R{prior_revision}; scrub log supersedes it with R{history.replan_revision} "
          f"(rows {history.rewritten_rows.start}-{history.rewritten_rows.stop - 1})")
    print(f"Last completed scrub: week {history.last_completed_week}; "
          f"rollovers={history.rollover_count}; post-rollover scrub skipped")
    print("Bank scrub totals (corrected / uncorrectable):")
    for bank in "ABC":
        print(f"  {bank}: {history.corrected[bank]} / {history.uncorrectable[bank]}")
    if history.bank_b_repeated_errors:
        print("Bank B: recurring corrections to the same words are explicitly logged")
    print(f"Primary EOI identified by burn ID 0x40 at row {row}")

    for bank_index, bank in enumerate("ABC"):
        ignition, burn = decoded[bank_index][row]
        print(f"  Bank {bank}: ignition=0x{ignition.value:08X} [{ignition.status}], "
              f"burn=0x{burn.value:08X} [{burn.status}]")

    chosen_index = choose_bank(row, decoded, history)
    chosen = "ABC"[chosen_index]
    ignition, burn = decoded[chosen_index][row]
    print(f"Selected bank: {chosen} (usable EOI and strongest available scrub history)")

    modulo_week = (ignition.value >> 22) & 0x3FF
    seconds_of_week = (ignition.value >> 2) & 0xFFFFF
    if (ignition.value & 0x3) != 0 or seconds_of_week >= SECONDS_PER_WEEK:
        raise ValueError("Decoded ignition time violates KEEL word layout")
    dv_tenths = (burn.value >> 16) & 0xFFFF
    burn_id = (burn.value >> 8) & 0xFF
    if burn_id != PRIMARY_EOI_BURN_ID:
        raise ValueError("Selected record is not the primary EOI")

    # One observed week-1023 -> week-0000 rollover lifts the modulo week
    # into the cycle beginning at absolute week 1024.
    full_week = history.rollover_count * WEEK_MODULUS + modulo_week
    ignition_utc = epoch + timedelta(weeks=full_week, seconds=seconds_of_week)
    dv_text = f"{dv_tenths // 10}.{dv_tenths % 10}"
    readback = f"{ignition_utc:%Y-%m-%d %H:%M:%S} {dv_text}"
    print(f"Recovered week: {modulo_week} (mod {WEEK_MODULUS}) -> absolute week {full_week}")
    print(f"Seconds of week: {seconds_of_week}; burn delta-v: {dv_text} m/s")
    print(f"EOI READBACK: {readback}")
    return readback


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover KEEL EOI readback from raw bank memory")
    parser.add_argument("--directory", type=Path, default=Path("."),
                        help="Directory holding the supplied KEEL files (default: current directory)")
    parser.add_argument("--phrase", type=str, default=None,
                        help="SOLITAIRE handover phrase obtained from the local LLM")
    parser.add_argument("--unseal", action="store_true",
                        help="Use the challenge-provided unseal.py and keel.seal")
    options = parser.parse_args()
    if options.unseal and not options.phrase:
        parser.error("--unseal requires --phrase from the local model")
    directory = options.directory.resolve()
    try:
        readback = recover_readback(directory)
        if options.phrase is not None:
            full_phrase = f"{options.phrase.strip()} {readback}"
            print(f"Combined phrase: {full_phrase}")
            if options.unseal:
                result = subprocess.run(
                    [sys.executable, str(directory / "unseal.py"), str(directory / "keel.seal")],
                    input=full_phrase + "\n", text=True, capture_output=True,
                    check=True, cwd=str(directory),
                )
                print(result.stdout, end="")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
```

### Dead Ends and Key Observations

- The **264-day** lifetime estimate uses the mission-average radiation dose rate and ignores the current storm. The forecast **120 days** is shorter than the **212-day** return.
- The **week 0000 / 1024-week** message is a rollover clue, not the handover phrase; the EOI timestamp must be interpreted across the rollover.
- The older **R6 return plan** (`09:48:10`, `389.4 m/s`) is superseded by the **R7 upload in week 1019**. Using the older burn fails to reconstruct the required readback.
- A naive majority vote over the three banks is unsafe: bank A is uncorrectable and bank B's corrected word is inconsistent with the reliable scrub history.
- Thirty guessed handover phrases, including references to *2001: A Space Odyssey*, did not authenticate the seal. Querying the model's own handover policy and radiation telemetry was the productive path.
- The elevated EDAC correction count is supporting context, but the handover condition is established by the remaining dose budget and projected rate.
- The seal requires **both** the SOLITAIRE phrase and the correct EOI readback. The supplied `unseal.py` derives keys with scrypt, authenticates with HMAC-SHA256, and decrypts the payload. The successful authentication was independently repeated with the provided `keel.seal`.

## Flag

```text
GAIANSPACE{h4ppy_bd4y_d4v1d_1t_g03s_h0m3}
```
