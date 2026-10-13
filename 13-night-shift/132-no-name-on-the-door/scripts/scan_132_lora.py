#!/usr/bin/env python3
"""Batch-test gr-lora_sdr implicit-header LoRa settings against IQ files."""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

WORKER = r'''
import argparse
from gnuradio import blocks, gr
from gnuradio import lora_sdr

parser = argparse.ArgumentParser()
for flag in ('input', 'output'):
    parser.add_argument('--' + flag, required=True)
for flag in ('sf', 'cr', 'length', 'bw', 'rate', 'crc'):
    parser.add_argument('--' + flag, type=int, required=True)
args = parser.parse_args()

class Receiver(gr.top_block):
    def __init__(self):
        super().__init__('LoRa batch receiver')
        source = blocks.file_source(gr.sizeof_gr_complex, args.input, False, 0, 0)
        rx = lora_sdr.lora_sdr_lora_rx(
            bw=args.bw, cr=args.cr, has_crc=bool(args.crc), impl_head=True,
            pay_len=args.length, samp_rate=args.rate, sf=args.sf,
            sync_word=[0x00], soft_decoding=False,
            ldro_mode=2, print_rx=[False, False])
        sink = blocks.file_sink(gr.sizeof_char, args.output, False)
        sink.set_unbuffered(True)
        self.connect(source, rx)
        self.connect(rx, sink)

receiver = Receiver()
receiver.run()
'''


def score(data: bytes) -> tuple[float, int, str]:
    if not data:
        return 0.0, 0, ''
    good = sum(32 <= x <= 126 or x in (9, 10, 13) for x in data)
    preview = data[:180].decode('ascii', errors='replace')
    return good / len(data), len(data), preview


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('iq', nargs='+', help='Complex float32 IQ files (500 kS/s)')
    parser.add_argument('--sf', type=int, nargs='+', default=[7, 8, 9, 10])
    parser.add_argument('--cr', type=int, nargs='+', default=[1, 2, 3, 4])
    parser.add_argument('--length', type=int, nargs='+', default=[32, 48, 64, 96, 128, 165, 192, 208])
    parser.add_argument('--crc', type=int, choices=[0, 1], default=0)
    parser.add_argument('--bw', type=int, default=125000)
    parser.add_argument('--rate', type=int, default=500000)
    parser.add_argument('--timeout', type=int, default=12)
    parser.add_argument('--out', default='scan132_results.jsonl')
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix='scan132_') as temp_dir:
        worker = pathlib.Path(temp_dir, 'worker.py')
        worker.write_text(WORKER, encoding='utf-8')
        output = pathlib.Path(temp_dir, 'decoded.bin')
        number = 0
        with open(args.out, 'w', encoding='utf-8') as records:
            for filename in args.iq:
                if not pathlib.Path(filename).is_file():
                    print(f'ERROR: missing input {filename}', file=sys.stderr)
                    continue
                for sf in args.sf:
                    for cr in args.cr:
                        for length in args.length:
                            number += 1
                            output.write_bytes(b'')
                            command = [sys.executable, str(worker), '--input', str(pathlib.Path(filename).resolve()),
                                       '--output', str(output), '--sf', str(sf), '--cr', str(cr),
                                       '--length', str(length), '--bw', str(args.bw),
                                       '--rate', str(args.rate), '--crc', str(args.crc)]
                            env = dict(os.environ)
                            env['PYTHONNOUSERSITE'] = '1'
                            try:
                                proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                      timeout=args.timeout, check=False, env=env)
                                log = (proc.stdout + proc.stderr).decode('utf-8', errors='replace')
                                data = output.read_bytes()
                                fraction, size, preview = score(data)
                                valid = 'CRC valid!' in log and 'CRC invalid' not in log
                                record = dict(iq=filename, sf=sf, cr=cr, length=length, crc=args.crc,
                                              bytes=size, printable=round(fraction, 5), valid_crc=valid,
                                              preview=preview, returncode=proc.returncode,
                                              log_tail=log[-500:])
                                records.write(json.dumps(record, ensure_ascii=False) + '\n')
                                records.flush()
                                if valid or (size and fraction > 0.85):
                                    print(f'[{number}] {filename} SF{sf} CR{cr} len={length} '
                                          f'bytes={size} printable={fraction:.1%} CRC={valid} {preview[:100]!r}',
                                          flush=True)
                            except subprocess.TimeoutExpired:
                                records.write(json.dumps(dict(iq=filename, sf=sf, cr=cr,
                                                              length=length, error='timeout')) + '\n')
                                records.flush()
            print(f'Finished {number} trials. Results: {args.out}')


if __name__ == '__main__':
    main()
