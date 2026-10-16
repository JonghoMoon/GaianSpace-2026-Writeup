# 705-last-readout

| | |
|---|---|
| **Category** | 07 — Unscheduled Passes |
| **Points** | ? |

## Description

Pilgrim-1 signed its name again, two days after the patch went up. Ines didn't open the champagne. She ordered five full memory readouts instead.

One chip in the old data computer died this month. Chips in the same batch, the same age, under the same radiation, tend to go together. If a second one is starting to fail, the desk wants to know now, while the patch still works, and not after the next safe mode, a light-day away.

The five readouts came home on two passes, each one a fresh read of the whole memory. The link was poor. The receiver loses its grip at the end of every long frame, and the checksum fails on about half the frames. Ade has already diffed the first readout against the golden image and has a list of four hundred dead cells. He wants to send it to engineering.

Find the words that Pilgrim-1 itself has lost.

**Flag format:** `GAIANSPACE{<addresses of the damaged words, three hex digits each, ascending, joined with hyphens>}` — for example `GAIANSPACE{0A1-2F0-7FF}`. Leave out bank 3 lower (`600`–`6FF`); everyone knows about that chip.

### Files

- `readout_frames.log` — the station's log of every readout frame as received
- `readout_notes.md` — the desk's notes, with the readout frame format
- `uplink_2026-10-11.txt` — the patch that went up, exactly as sent
- `fds_golden.img` — the ground's 1977 copy of the memory
- `fds_sim.py` — the ground's bench model of the machine
- `fds_handbook.md` — the instruction set, the memory map and the load history

## Solution

### 1. Restore the frame payloads

`readout_notes.md` defines a six-byte cleartext header: ASCII `P1`, readout number, frame number, and first word address. The payload and its final two-byte checksum are XOR-scrambled with a 16-bit Galois LFSR. The LFSR is initialized to `(readout << 8 | frame) XOR 0x5A5A`, shifted right with feedback polynomial mask `0xB400`, and emits each byte least-significant bit first.

Decode all 130 frames. The payload is 80 big-endian words per normal frame and 48 words in the last frame of each readout. Validate the checksum as the 16-bit sum of the decoded words. Only **69 of 130 frames** pass. Do not treat corrupted frames as evidence of failing spacecraft RAM: the ground receiver loses symbol synchronization near the end of long frames.

### 2. Reconstruct the expected memory, not the 1977 image

The memory image predates the 2026-10-11 uplink. Apply every `ADDR WORD` write in `uplink_2026-10-11.txt` to the 2048-word big-endian golden image. Comparing against the unpatched golden image would incorrectly flag intentional modifications as damage.

The known failed bank `600–6FF` is excluded from the requested answer.

### The 704 relocation and the actual 705 uplink are not byte-identical

Challenge 704 generated a **75-word functional relocation patch** from the 1977 golden image. This challenge separately provides `uplink_2026-10-11.txt`, which is the **actual uplink record** and also contains 75 words. They use **different destination layouts** (for example, the 704 solution places the housekeeping tail at `4F0`, while the 705 uplink uses the `770–788` region for part of its relocation). Therefore, **do not replace the provided 705 uplink with the generated 704 patch** when determining the expected RAM contents. The solver correctly applies the precise supplied 705 uplink.

The two layouts are functionally equivalent in the supplied bench model: when independently applied to the golden memory, both yield the same 114 telemetry words. That behavioural equivalence **does not mean their memory images or patched addresses are identical**. A byte-for-byte comparison against the 704 patch would incorrectly report intended relocation differences as memory faults.

### 3. Distinguish live RAM from persistent faults

The readout captures memory **while the FDS is running**. Some values change legitimately, even in checksum-valid frames. Run the patched memory in the provided `fds_sim.py` and record every address written by the executing program.

The initial static comparison produces false positives at `040`, `3A0`, and `3B1`. The simulator confirms that all three are **runtime-written addresses**, not newly damaged memory cells. In particular, the supposedly free `3A0` region is not safe to treat as unused RAM merely because of the 1977 map.

### 4. Confirm repeatable bit damage

For each address outside the dead bank and outside the runtime-written set, collect values from **checksum-valid** frames across the five readouts. Require observations from at least three independent checksum-valid readouts. All available valid readouts must agree on the same value, and that value must differ from the patched reference.

| Address | Patched reference | Observed | XOR | Valid readouts |
|---|---|---|---|---|
| `405` | `452D` | `652D` | `2000` | 3, 4, 5 |
| `43E` | `419E` | `619E` | `2000` | 2, 3, 5 |
| `445` | `D743` | `F743` | `2000` | 2, 3, 5 |
| `448` | `4D97` | `6D97` | `2000` | 2, 3, 5 |
| `4BD` | `D5AA` | `F5AA` | `2000` | 2, 4, 5 |

All five words exhibit the same **bit-13 (`0x2000`)** difference. The consistency across multiple checksum-valid readouts distinguishes persistent spacecraft memory damage from link corruption.

### Dead Ends

- Diffing the first raw readout against the 1977 image reports hundreds of spurious differences from the uplink patch, live RAM, and receiver errors.
- Treating checksum-failing frames as valid memory evidence confuses downlink corruption with spacecraft damage.
- Treating the 1977 memory map as a current allocation map incorrectly marks `3A0` and `3B1` as bad cells.
- A single matching discrepancy is insufficient; repeated agreement across independently verified readouts is essential.

<!-- BEGIN CATEGORY07 REVIEW: 705 -->

### Candidate reduction: from 416 discrepancies to five damaged words

Ade's initial raw comparison produced **416 differing addresses**.

However, this comparison used the original 1977 golden image
and did not fully account for the known failed chip, the
2026 uplink patch, or errors introduced during downlink
reception.

The analysis is best understood as two separate phases.

#### Phase A — Re-evaluate the first readout

| Step | Remaining candidates | Explanation |
|---|---:|---|
| Initial raw differences | 416 | Comparison against the 1977 golden image |
| Exclude known failed chip | 160 | Remove addresses in `600–6FF` |
| Apply actual 2026 uplink | 93 | Remove differences caused by intentional memory updates |
| Retain checksum-valid frame evidence | 4 | Remove discrepancies associated with invalid received frames |

The actual uplink contains 75 word writes.

The reduction from 160 to 93 does not imply that the uplink
contained only 67 writes. Only writes overlapping the
remaining candidate differences affect this count.

The four remaining discrepancies are candidates observed
from the first readout.

At this point, they are **not yet confirmed persistent
memory faults**.

#### Phase B — Cross-check all five readouts

The analysis is then expanded to the five independent
memory readouts.

| Step | Remaining candidates | Explanation |
|---|---:|---|
| Discrepancies across all five readouts | 17 | Distinct address candidates from the checksum-valid observations, compared against the patched reference before runtime-write and persistence filtering |
| Exclude runtime-written addresses | 6 | Remove legitimate software modifications |
| Require consistent independent readouts | **5** | Retain persistent discrepancies |

The increase from **4 to 17** is intentional.

It does not represent an increase during a single
candidate-filtering sequence.

Phase A examines the first readout alone, whereas
Phase B considers all five readouts.

#### Why address `7CA` was rejected

Address `7CA` initially appeared to contain an incorrect
memory value.

One checksum-valid readout reported a value different
from the patched reference.

However, two other checksum-valid readouts contained
the expected reference value.

The discrepancy was therefore not persistent across
the available independent readouts.

The observed difference could have resulted from a
transient memory error or another nonpersistent effect.

The available evidence does not establish its precise
cause.

Therefore, `7CA` was excluded from the final list of
persistently damaged words.

#### Exact persistence criterion

The solver does not merely apply a three-readout
majority vote.

For each candidate address, it requires:

1. At least three independent checksum-valid readouts
   must provide observations.
2. **All available checksum-valid readouts** must agree
   on the same observed value.
3. That value must differ from the patched reference.
4. The address must be outside the known failed chip.
5. The address must not be legitimately written during
   normal FDS execution.

For example, an address is rejected if three valid
readouts report an incorrect value but a fourth valid
readout reports the expected value.

This strict consistency requirement distinguishes
persistent memory damage from isolated discrepancies.

#### Final five damaged words

| Address | Expected | Observed | XOR difference |
|---|---|---|---|
| `405` | `452D` | `652D` | `2000` |
| `43E` | `419E` | `619E` | `2000` |
| `445` | `D743` | `F743` | `2000` |
| `448` | `4D97` | `6D97` | `2000` |
| `4BD` | `D5AA` | `F5AA` | `2000` |

All five surviving words exhibit the same bit-13
difference (`0x2000`).

Each was observed consistently across at least three
independent checksum-valid readouts.

The final result is:

    GAIANSPACE{405-43E-445-448-4BD}

The analysis separates persistent spacecraft-memory
corruption from legitimate runtime writes, known failed
memory, and isolated readout discrepancies.

**Counting convention:** The 17 candidates represent distinct memory addresses identified during the separate five-readout diagnostic comparison. They are not a count of frames or individual observations. The diagnostic comparison uses the uplink-corrected reference and checksum-valid frame observations; the runtime-write exclusion and persistence criterion are applied afterward.

**Reproduction scope:** The intermediate counts `416 -> 160 -> 93 -> 4` and `17 -> 6 -> 5` were obtained during a separate diagnostic analysis. The published `705.py` implements checksum validation, runtime-write exclusion, and the final persistence checks, but does not print every intermediate count shown in the candidate-reduction tables.

<!-- END CATEGORY07 REVIEW: 705 -->

### Reproduction

Place `705.py` and the six challenge files in the same directory, then run:

```bash
python3 705.py
```

Expected relevant output:

```text
Frames: 130; checksum-valid: 69
405: expected=452D observed=652D XOR=2000 valid_readouts=[3, 4, 5]
43E: expected=419E observed=619E XOR=2000 valid_readouts=[2, 3, 5]
445: expected=D743 observed=F743 XOR=2000 valid_readouts=[2, 3, 5]
448: expected=4D97 observed=6D97 XOR=2000 valid_readouts=[2, 3, 5]
4BD: expected=D5AA observed=F5AA XOR=2000 valid_readouts=[2, 4, 5]
Excluded runtime-written addresses: 040, 0C0, 0E0, 0E1, 0E3, 0E4, 0E6, 3A0, 3B1, 5D0, 772, 778
Damaged words: 5
FLAG: GAIANSPACE{405-43E-445-448-4BD}
```

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies: Python 3 standard library and challenge-supplied fds_sim.py.
# No pip installation is required.
"""Recover persistent FDS-16 memory damage from five noisy readouts."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import fds_sim

MEMORY_WORDS = 2048
FRAME_WORDS = 80
DEAD_RANGE = range(0x600, 0x700)


def descramble(data: bytes, readout: int, frame: int) -> bytes:
    """Undo the bytewise Galois LFSR scrambler from readout_notes.md."""
    state = (((readout << 8) | frame) ^ 0x5A5A) & 0xFFFF
    result = bytearray()
    for value in data:
        mask = 0
        for bit_index in range(8):
            output_bit = state & 1
            mask |= output_bit << bit_index
            state >>= 1
            if output_bit:
                state ^= 0xB400
        result.append(value ^ mask)
    return bytes(result)


def parse_frames(path: Path):
    """Decode and checksum every frame without silently repairing bad frames."""
    parsed = []
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f'Line {line_number}: unexpected frame log format')
        station, ert, snr, declared_length, raw_hex = fields
        raw = bytes.fromhex(raw_hex)
        if len(raw) != int(declared_length) or raw[:2] != b'P1':
            raise ValueError(f'Line {line_number}: invalid frame length or sync')
        readout = int(raw[2])
        frame = int(raw[3])
        start = int.from_bytes(raw[4:6], 'big')
        body = descramble(raw[6:], readout, frame)
        if (len(body) - 2) % 2:
            raise ValueError(f'Line {line_number}: odd word data size')
        words = [int.from_bytes(body[offset:offset + 2], 'big')
                 for offset in range(0, len(body) - 2, 2)]
        checksum = int.from_bytes(body[-2:], 'big')
        valid = (sum(words) & 0xFFFF) == checksum
        if not 1 <= readout <= 5 or start + len(words) > MEMORY_WORDS:
            raise ValueError(f'Line {line_number}: invalid readout/address')
        parsed.append((readout, frame, start, words, valid, station, ert))
    return parsed


def expected_memory(image_path: Path, patch_path: Path) -> list[int]:
    """Apply the actual uplink to the ground image before comparing values."""
    raw = image_path.read_bytes()
    if len(raw) != MEMORY_WORDS * 2:
        raise ValueError('Expected 2048 big-endian 16-bit words')
    memory = [int.from_bytes(raw[i:i + 2], 'big') for i in range(0, len(raw), 2)]
    for line in patch_path.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        address_text, word_text = line.split()[:2]
        address = int(address_text, 16)
        word = int(word_text, 16)
        if not 0 <= address < MEMORY_WORDS or not 0 <= word <= 0xFFFF:
            raise ValueError(f'Invalid patch line: {line}')
        memory[address] = word
    return memory


def runtime_written_addresses(memory: list[int]) -> set[int]:
    """Run the supplied bench model and record addresses modified by software."""
    machine = fds_sim.FDS(memory, fault=True)
    written: set[int] = set()
    original_write = machine.wr

    def tracked_write(address: int, value: int) -> None:
        written.add(address & 0x7FF)
        original_write(address, value)

    machine.wr = tracked_write
    for _ in range(fds_sim.STEP_LIMIT):
        if not machine.step():
            break
    else:
        raise RuntimeError('Bench model reached the step limit')
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    parser.add_argument('--frames', type=Path, default=root / 'readout_frames.log')
    parser.add_argument('--golden', type=Path, default=root / 'fds_golden.img')
    parser.add_argument('--patch', type=Path, default=root / 'uplink_2026-10-11.txt')
    args = parser.parse_args()
    expected = expected_memory(args.golden, args.patch)
    mutable = runtime_written_addresses(expected)
    frames = parse_frames(args.frames)
    verified = [entry for entry in frames if entry[4]]
    print(f'Frames: {len(frames)}; checksum-valid: {len(verified)}')

    observations = defaultdict(list)
    for readout, frame, start, words, valid, station, ert in verified:
        for offset, value in enumerate(words):
            observations[start + offset].append((readout, value))

    damaged = []
    for address in sorted(observations):
        if address in DEAD_RANGE or address in mutable:
            continue
        readings = observations[address]
        by_readout = {readout: value for readout, value in readings}
        if len(by_readout) < 3:
            continue
        counts = Counter(by_readout.values())
        value, count = counts.most_common(1)[0]
        if count < 3 or value == expected[address]:
            continue
        # Reject mutable RAM: a genuine persistent fault must be repeatable.
        if len(counts) != 1:
            continue
        damaged.append(address)
        print(f'{address:03X}: expected={expected[address]:04X} '
              f'observed={value:04X} XOR={expected[address] ^ value:04X} '
              f'valid_readouts={sorted(by_readout)}')

    print('Excluded runtime-written addresses:', ', '.join(f'{addr:03X}' for addr in sorted(mutable)))
    print(f'Damaged words: {len(damaged)}')
    print('FLAG: GAIANSPACE{' + '-'.join(f'{addr:03X}' for addr in damaged) + '}')


if __name__ == '__main__':
    main()
```

### Tools and References

- Python 3 standard library (`argparse`, `collections`, `pathlib`)
- Provided `fds_sim.py` to identify legitimate runtime writes
- Provided `readout_notes.md` for LFSR framing and checksum
- Provided `fds_handbook.md` for FDS memory architecture and load history

## Flag

```text
GAIANSPACE{405-43E-445-448-4BD}
```
