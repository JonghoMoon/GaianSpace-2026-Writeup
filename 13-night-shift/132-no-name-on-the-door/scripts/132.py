#!/usr/bin/env python3
"""Recover GaianSpace 132 GET HK acknowledgement from LoRa implicit-header IQ.

Requires GNU Radio and gr-lora_sdr installed for the system Python interpreter.
Input: 132_DL_3_32.5s.cf32 (complex64, nominal 500 kS/s).
"""
from __future__ import annotations

import argparse
import binascii
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

WORKER = r'''
import argparse
from gnuradio import blocks, gr, lora_sdr

parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--length', required=True, type=int)
args = parser.parse_args()

class Receiver(gr.top_block):
    def __init__(self):
        super().__init__('GaianSpace 132 decoder')
        source = blocks.file_source(gr.sizeof_gr_complex, args.input, False, 0, 0)
        receiver = lora_sdr.lora_sdr_lora_rx(
            bw=125000, cr=2, has_crc=False, impl_head=True,
            pay_len=args.length, samp_rate=500000, sf=10,
            sync_word=[0x00], soft_decoding=False, ldro_mode=2,
            print_rx=[False, False])
        sink = blocks.file_sink(gr.sizeof_char, args.output, False)
        sink.set_unbuffered(True)
        self.connect(source, receiver, sink)

Receiver().run()
'''

ACK_PATTERN = re.compile(rb'TM,ACK,\d+,GET HK,HK,.*?CO2=(\d+),UP=(\d+)\*([0-9A-Fa-f]{4})')


def decode(iq: Path, length: int, timeout: int) -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory(prefix='gs132_') as dirname:
        directory = Path(dirname)
        worker = directory / 'receiver.py'
        output = directory / 'decoded.bin'
        worker.write_text(WORKER, encoding='utf-8')
        env = os.environ.copy()
        env['PYTHONNOUSERSITE'] = '1'
        cmd = [sys.executable, str(worker), '--input', str(iq.resolve()),
               '--output', str(output), '--length', str(int(length))]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=int(timeout), check=False, env=env)
        log = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        if result.returncode != 0:
            raise RuntimeError(f'Receiver exited with {result.returncode}:\n{log[-2000:]}')
        return (output.read_bytes() if output.exists() else b''), log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('iq', nargs='?', type=Path,
                        default=Path('132_DL_candidates/132_DL_3_32.5s.cf32'))
    parser.add_argument('--length', type=int, default=68,
                        help='Implicit payload length (default: 68 for the 63-byte message plus *XXXX)')
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args()
    if not args.iq.is_file():
        parser.error(f'IQ file not found: {args.iq}')
    data, log = decode(args.iq, int(args.length), int(args.timeout))
    print('RECEIVER:', log.strip() or '(no log)')
    print('DECODED BYTES:', len(data))
    print('PAYLOAD:', data.decode('ascii', errors='backslashreplace'))
    candidates = list(ACK_PATTERN.finditer(data))
    if not candidates:
        print('ERROR: No complete GET HK acknowledgement with *XXXX check field was decoded.', file=sys.stderr)
        print('Try --length 69 or inspect IQ synchronization; no flag is asserted.', file=sys.stderr)
        return 1
    for match in candidates:
        message = match.group(0)
        checksum_text = int(match.group(3).decode('ascii'), 16)
        received_prefix = message.rsplit(b'*', 1)[0]
        calculated = int(binascii.crc_hqx(received_prefix, 0xFFFF))
        print(f'CRC-16/CCITT-FALSE: calculated={calculated:04X}, received={checksum_text:04X}')
        if calculated == checksum_text:
            co2 = int(match.group(1).decode('ascii'))
            uptime = int(match.group(2).decode('ascii'))
            print(f'FLAG: GAIANSPACE{{{co2}_{uptime}}}')
            return 0
    print('ERROR: ACK found but application CRC did not match.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
