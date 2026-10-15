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
