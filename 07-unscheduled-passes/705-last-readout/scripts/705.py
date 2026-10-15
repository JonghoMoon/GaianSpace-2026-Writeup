#!/usr/bin/env python3
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
