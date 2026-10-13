# 131-two-voices

| | |
|---|---|
| **Category** | 13 — Night Shift |
| **Points** | 100 |

## Description

Night shift, GaianSpace MOC. GAIAN-723 dropped off the telemetry console at 01:12 and has not come back. The pass schedule says it is overhead right now.

David Aroz is alone on the SOC desk. Mission control has gone home, and the on-call engineer isn't answering. The ground station modem says nothing is there, but the station's raw recorder never stops, and Aroz pulled the last forty seconds of the band.

The waterfall is not empty. There are two voices in it. One of them is GAIAN-723. The other one is not on any GaianSpace frequency plan, and it is talking to our satellite.

The old frequency sheet pinned above the desk still says 433.000 MHz.

Find out what GAIAN-723 answered when the stranger first called it.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `vela_band_0114.sigmf-data` — the band recorder's raw capture (too large to attach: download it from [Hugging Face](https://huggingface.co/datasets/GaianSpace/ctf-2026-130/tree/main/131))
- `vela_band_0114.sigmf-meta` — the recorder's metadata for that capture
- `desk_notes.md` — Aroz's notes from the same watch; they can be wrong

## Solution

### Steps

Identify two LoRa transmitters in the raw capture rather than assuming the old frequency sheet is correct. Extract the satellite reply as complex IQ and decode with the GNU Radio LoRa receiver. The included `131_A_reply_1.cf32` is an intermediate extraction. Validate the decoded packet CRC.

### Reproduction

Open `lora_RX.grc` in GNU Radio Companion, configure the source to read `131_A_reply_1.cf32`, and run the receiver. The generated `lora_RX.py` is a GNU Radio flowgraph, not a standalone flag-printing script. The decoded output is preserved in `result.txt`.

Expected relevant output:

```text
--------Header--------
Payload length: 46
CRC presence:   1
Coding rate:    1
Header checksum valid!

rx msg: TM,ACK,0,HELLO,GAIANSPACE{tw0_v01c3s_0B0EFE1A}
CRC valid!

******* MESSAGE DEBUG PRINT ********
TM,ACK,0,HELLO,GAIANSPACE{tw0_v01c3s_0B0EFE1A}
************************************
```

### Exploit Code

**`lora_RX.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Lora Rx
# Author: Tapparel Joachim@EPFL,TCL
# GNU Radio version: 3.10.1.1

from gnuradio import blocks
import pmt
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import gnuradio.lora_sdr as lora_sdr




class lora_RX(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Lora Rx", catch_exceptions=True)

        ##################################################
        # Blocks
        ##################################################
        self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(
                interpolation=1,
                decimation=1,
                taps=[],
                fractional_bw=0)
        self.lora_rx_0 = lora_sdr.lora_sdr_lora_rx( bw=125000, cr=2, has_crc=False, impl_head=True, pay_len=64, samp_rate=500000, sf=7, sync_word=[0x00], soft_decoding=False, ldro_mode=2, print_rx=[True,True])
        self.blocks_message_debug_0 = blocks.message_debug(True)
        self.blocks_file_source_0 = blocks.file_source(gr.sizeof_gr_complex*1, '/home/jhmoon/gaianspace/Day 2/132_DL_candidates/132_DL_1_19s.cf32', False, 0, 0)
        self.blocks_file_source_0.set_begin_tag(pmt.PMT_NIL)
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_char*1, '/home/jhmoon/lora_decode.bin', False)
        self.blocks_file_sink_0.set_unbuffered(True)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.lora_rx_0, 'out'), (self.blocks_message_debug_0, 'print'))
        self.connect((self.blocks_file_source_0, 0), (self.rational_resampler_xxx_0, 0))
        self.connect((self.lora_rx_0, 0), (self.blocks_file_sink_0, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.lora_rx_0, 0))





def main(top_block_cls=lora_RX, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
```

## Flag

```text
GAIANSPACE{tw0_v01c3s_0B0EFE1A}
```
