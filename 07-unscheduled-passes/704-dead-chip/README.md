# 704-dead-chip

| | |
|---|---|
| **Category** | 07 — Unscheduled Passes |
| **Points** | 125 |

## Description

The readout came back clean, and it says what everyone feared. One memory chip in the old data computer is gone. Everything Pilgrim-1 says about itself goes through that chip.

A piece of Pilgrim-1's flight data subsystem has stopped holding anything. The routine that lived there builds every telemetry frame, and now the computer falls over every time it calls it. There is no spare chip. All the ground can do is what the engineers who built it would have done: pick the routine up, cut it into pieces, and fit it into whatever corners of memory are still free. Then send that over a link that carries a few words a second, with one pass to get it right.

The desk has the 1977 ground copy of the memory, the handbook, and a bench model of the machine. When the patch is right, the spacecraft will sign its name again.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `fds_golden.img` — the ground's copy of the data computer's memory, 2048 big-endian 16-bit words
- `fds_sim.py` — the ground's bench model of the machine
- `fds_handbook.md` — the instruction set, the 1977 memory map, and the load history

## Solution

### Steps

1. Read the original 2048-word FDS-16 memory image and the instruction-set handbook.
2. Identify the dead memory chip at addresses `0x600–0x6FF` and the telemetry routine that originally occupied it.
3. Build a relocation plan that moves the routine into surviving memory regions, updates control-flow references, and preserves unrelated live data.
4. Generate a patch with no more than the 96-word uplink limit; this solution writes 75 words.
5. Apply the patch to the bench simulator and compare the telemetry output against the healthy reference.
6. Verify zero dead-chip reads and writes, and ensure the thermal-memory region remains intact.

### Reproduction

Required dependencies: Python standard library and the supplied `fds_sim.py`.

Run the solver from the directory containing the original challenge inputs, as in the uploaded working archive.

```bash
python3 704.py
python3 fds_sim.py fds_golden.img 704_solution/fds_patch_704_v1.txt
```

Expected relevant output:

```text
PATCH WORDS: 75/96
PATCHED RUN: 2093 steps, PC=019, 114 telemetry words
DEAD MEMORY ACCESSES: reads=0, writes=0
HEALTHY REFERENCE: 2009 steps; telemetry identical=True
THERMAL REGION: preserved and matches healthy-reference final state
PATCH: 704_solution/fds_patch_704_v1.txt
FLAG: GAIANSPACE{r3l0c4ted_ar0und_a_d34d_ch1p}
```

The solver generates `704_solution/fds_patch_704_v1.txt`; it is an output artifact, not an original challenge attachment.

### Exploit Code

```python
#!/usr/bin/env python3
"""Build and verify the relocation patch for 704-dead-chip.

Example:
    python3 solve_704_dead_chip_v1.py --input-dir /path/to/704
    python3 fds_sim.py fds_golden.img 704_solution/fds_patch_704_v1.txt

Dependencies: Python standard library and the supplied fds_sim.py.
The relocation plan is specific to the supplied memory image. Instructions and
ciphertext are copied from that image; the patch and flag are not embedded.
The simulator is imported as trusted challenge code and is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

MEMORY_WORDS = 0x800
DEAD_START = 0x600
DEAD_STOP = 0x700
UPLINK_LIMIT = 96
ADDRESS_OPS = frozenset((1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 26))


@dataclass(frozen=True)
class Block:
    source: int
    destination: int
    size: int
    description: str


BLOCKS = (
    Block(0x600, 0x5D0, 30, 'Return slot and signature body, first part'),
    Block(0x61E, 0x770, 6, 'Signature body, second part'),
    Block(0x624, 0x4F0, 5, 'Housekeeping tail entered by an indirect jump'),
    Block(0x629, 0x4F5, 10, 'Dispatch pointers, constants, and scratch words'),
    Block(0x640, 0x2E0, 21, 'Encrypted signature table, confined to one 32-word page'),
)


def load_simulator(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location('fds_bench_original_704', path)
    if spec is None or spec.loader is None:
        raise ValueError(f'Cannot import the supplied simulator: {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if int(module.MEM) != MEMORY_WORDS or int(module.UPLINK_WORDS) != UPLINK_LIMIT:
        raise ValueError('Simulator memory size or uplink limit differs from this challenge.')
    if set(int(v) for v in module.DEAD) != set(range(DEAD_START, DEAD_STOP)):
        raise ValueError('Simulator fault map differs from this challenge.')
    return module


def load_words(path: Path) -> list[int]:
    content = path.read_bytes()
    if len(content) != MEMORY_WORDS * 2:
        raise ValueError('The golden image must be 2048 big-endian 16-bit words.')
    return [int.from_bytes(content[index:index + 2], 'big')
            for index in range(0, len(content), 2)]


def make_patch(words: list[int]) -> tuple[dict[int, int], dict[int, int], list[dict[str, Any]]]:
    # Guard structural assumptions instead of applying a patch to an unknown image.
    required_words = {
        0x000: 0x4010, 0x004: 0x0624, 0x013: 0x5E00,
        0x043: 0x5BA0, 0x046: 0x6004,
        0x609: 0x7E29, 0x60B: 0x662B,
        0x61C: 0x7E40, 0x622: 0x561A, 0x623: 0x6600,
        0x629: 0x060C, 0x62A: 0x0611, 0x630: 0x0015, 0x632: 0x0640,
    }
    for address, expected in required_words.items():
        if int(words[address]) != int(expected):
            raise ValueError(f'Unexpected word at {address:03X}: '
                             f'{words[address]:04X}, expected {expected:04X}.')
    mapping: dict[int, int] = {}
    for block in BLOCKS:
        for offset in range(block.size):
            source, destination = int(block.source + offset), int(block.destination + offset)
            if source in mapping or destination in mapping.values():
                raise ValueError('Overlapping relocation plan.')
            if not 0 <= destination < MEMORY_WORDS or DEAD_START <= destination < DEAD_STOP:
                raise ValueError('Relocation destination is not healthy memory.')
            if int(words[destination]) != 0:
                raise ValueError(f'Destination {destination:03X} is occupied; refusing to overwrite it.')
            mapping[source] = destination
    if any(0x3A0 <= address <= 0x3DF for address in mapping.values()):
        raise ValueError('The 1998 thermal-correction region must be preserved.')
    if (mapping[0x640] & 0x7E0) != (mapping[0x654] & 0x7E0):
        raise ValueError('The relocated signature table would wrap its 32-word index page.')
    if (mapping[0x629] & 0x7E0) != (mapping[0x62A] & 0x7E0):
        raise ValueError('The relocated dispatch table would wrap its index page.')
    patch: dict[int, int] = {}
    edits: list[dict[str, Any]] = []
    for source, destination in mapping.items():
        old_word = int(words[source])
        new_word = old_word
        reason = 'copy unchanged'
        # Only executable words are decoded as instructions. Data is not code.
        if 0x601 <= source <= 0x628 and int(old_word >> 11) in ADDRESS_OPS:
            operand = int(old_word & 0x7FF)
            if operand in mapping:
                new_word = int((old_word & 0xF800) | mapping[operand])
                reason = 'relocate instruction address operand'
            elif DEAD_START <= operand < DEAD_STOP:
                raise ValueError(f'Unmapped dead-memory instruction operand at {source:03X}.')
        elif source in (0x629, 0x62A):
            new_word = int(mapping[old_word])
            reason = 'relocate full-word indirect dispatch pointer'
        elif source == 0x632:
            # This is a seed/tag, not a live address. Restore the 1977 value.
            new_word = 0x02E0
            reason = 'restore the 1977 signature seed/tag, not an address relocation'
        patch[destination] = int(new_word)
        edits.append(dict(source=f'{source:03X}', destination=f'{destination:03X}',
                          original_word=f'{old_word:04X}', patched_word=f'{new_word:04X}',
                          reason=reason))
    # Housekeeping uses JMPI 004, not JSR 624; update the stored pointer itself.
    patch[0x004] = int(mapping[int(words[0x004])])
    # Update the executive's ordinary subroutine call.
    patch[0x013] = int((int(words[0x013]) & 0xF800) | mapping[int(words[0x013]) & 0x7FF])
    # Preserve fall-through across the split by inserting a one-word bridge.
    bridge = int(mapping[0x61D] + 1)
    if bridge in patch or int(words[bridge]) != 0:
        raise ValueError('The bridge location is not free.')
    patch[bridge] = int((8 << 11) | mapping[0x61E])
    if len(patch) > UPLINK_LIMIT:
        raise ValueError(f'The patch needs {len(patch)} words; the limit is {UPLINK_LIMIT}.')
    for address in patch:
        if DEAD_START <= address < DEAD_STOP or not 0 <= address < MEMORY_WORDS:
            raise ValueError('Patch contains an invalid write address.')
    return patch, mapping, edits


def run_bench(module: ModuleType, words: list[int], fault: bool,
              forbid_dead: bool) -> tuple[dict[str, Any], bytes, list[int]]:
    """Instrument accesses while executing the original simulator's step()."""
    class AuditedFDS(module.FDS):
        def __init__(self, image: list[int], enabled: bool) -> None:
            super().__init__(image, fault=bool(enabled))
            self.read_addresses: set[int] = set()
            self.write_addresses: set[int] = set()
            self.dead_reads = 0
            self.dead_writes = 0

        def rd(self, address: int) -> int:
            address = int(address) & 0x7FF
            self.read_addresses.add(address)
            if DEAD_START <= address < DEAD_STOP:
                self.dead_reads += 1
                if forbid_dead:
                    raise RuntimeError(f'Patched execution read failed memory at {address:03X}.')
            return int(super().rd(address))

        def wr(self, address: int, value: int) -> None:
            address = int(address) & 0x7FF
            self.write_addresses.add(address)
            if DEAD_START <= address < DEAD_STOP:
                self.dead_writes += 1
                if forbid_dead:
                    raise RuntimeError(f'Patched execution wrote failed memory at {address:03X}.')
            super().wr(address, int(value))

    machine = AuditedFDS(words, bool(fault))
    steps = 0
    counts: dict[int, int] = {}
    while steps < int(module.STEP_LIMIT):
        pc_before = int(machine.pc)
        counts[pc_before] = int(counts.get(pc_before, 0) + 1)
        word = int(machine.m[pc_before])
        if not bool(machine.step()):
            if int(word >> 11) != 0:
                raise RuntimeError(f'Unexpected illegal-instruction halt at {pc_before:03X}.')
            break
        steps += 1
    else:
        raise RuntimeError('The patched machine exceeded its instruction limit.')
    telemetry = b''.join(int(value).to_bytes(2, 'big') for value in machine.out)
    stats = dict(steps=int(steps), halt_instruction_address=f'{pc_before:03X}',
                 final_pc=f'{int(machine.pc):03X}', telemetry_words=int(len(machine.out)),
                 telemetry_sha256=hashlib.sha256(telemetry).hexdigest(),
                 dead_reads=int(machine.dead_reads), dead_writes=int(machine.dead_writes),
                 executed_instruction_counts={f'{address:03X}': int(count)
                                              for address, count in sorted(counts.items())},
                 read_addresses=[f'{value:03X}' for value in sorted(machine.read_addresses)],
                 write_addresses=[f'{value:03X}' for value in sorted(machine.write_addresses)])
    return stats, telemetry, [int(value) for value in machine.m]


def disassemble_patch(patch: dict[int, int], mapping: dict[int, int],
                      module: ModuleType) -> str:
    inverse = {destination: source for source, destination in mapping.items()}
    lines = ['# Address  Word  Original  Interpretation']
    for address, word in sorted(patch.items()):
        source = inverse.get(address)
        if source is not None and 0x601 <= source <= 0x628:
            opcode, argument = int(word >> 11), int(word & 0x7FF)
            meaning = f'{module.OPS[opcode]} {argument:03X}'
        elif address == 0x5EE:
            meaning = 'JMP 770 (fall-through bridge)'
        elif address == 0x013:
            meaning = 'JSR 5D0 (executive call)'
        elif address == 0x004:
            meaning = 'indirect entry pointer for JMPI 004'
        else:
            meaning = 'data, constant, pointer, or return slot'
        original = f'{source:03X}' if source is not None else '---'
        lines.append(f'{address:03X}  {word:04X}  {original}       {meaning}')
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=Path('.'))
    parser.add_argument('--image', type=Path)
    parser.add_argument('--sim', type=Path)
    parser.add_argument('--out-dir', type=Path, default=Path('704_solution'))
    args = parser.parse_args()
    image_path = args.image if args.image is not None else args.input_dir / 'fds_golden.img'
    sim_path = args.sim if args.sim is not None else args.input_dir / 'fds_sim.py'
    module = load_simulator(sim_path)
    original = load_words(image_path)
    patch, mapping, edits = make_patch(original)
    patched = original.copy()
    for address, value in patch.items():
        patched[int(address)] = int(value)
    # The no-fault image still contains the historical 1981 seed bug.
    # Fix only that seed to obtain the healthy behavioral reference.
    reference = original.copy()
    reference[0x632] = 0x02E0
    ref_stats, ref_output, ref_memory = run_bench(module, reference, False, False)
    stats, output, final_memory = run_bench(module, patched, True, True)
    if output != ref_output:
        raise RuntimeError('Patched telemetry differs from the corrected healthy reference.')
    if patched[0x3A0:0x3E0] != original[0x3A0:0x3E0]:
        raise RuntimeError('Patch overwrote the thermal routine.')
    if final_memory[0x3A0:0x3E0] != ref_memory[0x3A0:0x3E0]:
        raise RuntimeError('The thermal routine does not match healthy-reference behavior.')
    flag_occurrences = re.findall(rb'GAIANSPACE\{[^}\r\n\x00]{1,200}\}', output)
    flags = sorted(set(value.decode('ascii') for value in flag_occurrences))
    if len(flags) != 1:
        raise RuntimeError('Expected exactly one unique flag in the restored telemetry.')
    flag = str(flags[0])
    report = dict(flag=flag, flag_occurrences=int(len(flag_occurrences)),
                  patch_words=int(len(patch)), uplink_limit=UPLINK_LIMIT,
                  patched_execution=stats, corrected_healthy_reference=ref_stats,
                  output_identical_to_reference=True, thermal_region_preserved=True,
                  original_image_modified=False,
                  blocks=[dict(source=f'{block.source:03X}', destination=f'{block.destination:03X}',
                               words=int(block.size), description=block.description) for block in BLOCKS],
                  relocation_edits=edits,
                  extra_writes={f'{address:03X}': f'{patch[address]:04X}' for address in (4, 0x13, 0x5EE)},
                  input_sha256={image_path.name: hashlib.sha256(image_path.read_bytes()).hexdigest(),
                                sim_path.name: hashlib.sha256(sim_path.read_bytes()).hexdigest()})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    patch_path = args.out_dir / 'fds_patch_704_v1.txt'
    patch_path.write_text('# 704 relocation patch; 75 words generated from the golden image.\n'
                          + ''.join(f'{address:03X} {value:04X}\n' for address, value in sorted(patch.items())),
                          encoding='ascii')
    (args.out_dir / 'fds_patched.img').write_bytes(
        b''.join(int(value).to_bytes(2, 'big') for value in patched))
    (args.out_dir / '704_telemetry.bin').write_bytes(output)
    (args.out_dir / '704_telemetry.txt').write_text(
        output.decode('ascii', errors='backslashreplace') + '\n', encoding='utf-8')
    (args.out_dir / '704_patch_disassembly.txt').write_text(
        disassemble_patch(patch, mapping, module), encoding='ascii')
    (args.out_dir / '704_verified_results.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (args.out_dir / 'flag.txt').write_text(flag + '\n', encoding='ascii')
    # Validate the patch parser too, not just the in-memory patch dictionary.
    parsed = [(int(a), int(v)) for a, v in module.load_patch(str(patch_path))]
    if parsed != sorted(patch.items()):
        raise RuntimeError('The simulator parsed the generated patch differently.')
    print(f'PATCH WORDS: {len(patch)}/{UPLINK_LIMIT}')
    print(f'PATCHED RUN: {stats["steps"]} steps, PC={stats["final_pc"]}, '
          f'{stats["telemetry_words"]} telemetry words')
    print(f'DEAD MEMORY ACCESSES: reads={stats["dead_reads"]}, writes={stats["dead_writes"]}')
    print(f'HEALTHY REFERENCE: {ref_stats["steps"]} steps; telemetry identical=True')
    print('THERMAL REGION: preserved and matches healthy-reference final state')
    print(f'PATCH: {patch_path}')
    print(f'FLAG: {flag}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, ImportError, AttributeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
```

## Flag

```text
GAIANSPACE{r3l0c4ted_ar0und_a_d34d_ch1p}
```
