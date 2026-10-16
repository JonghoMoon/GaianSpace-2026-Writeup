# 112 — Two Clocks

| | |
|---|---|
| **Category** | 11 — The PGM Rush |
| **Points** | 200 |

## Description

16:47 UTC on 4 November 2041. AO-111's lander fires its anchor into `2041 QM23`. Five hundred metres above it, the mothership's hover camera is shooting twenty frames a second.

The core under the anchor is the one that matters, and the geologists want to see where the harpoon went in: metal, or the dark streak beside it. That means the one frame that opened just after the bite. The lander knows the moment of the bite only by its own clock. The camera knows only the mothership's. The two clocks are tied together through the time-transfer pings on the lander link, and the lander kept its radio quiet through the whole anchor sequence.

Kaito has done it the usual way: take each ping's round trip, assume half of it each way, line up the clocks, read off the frame. He is sure. Sunniva wants it done properly before anyone writes a press release about the streak.

Name the frame.

**Flag format:** `GAIANSPACE{<frame number, seven digits, as in the frame index>}` — for example `GAIANSPACE{0400123}`. It is the first frame whose exposure started after the anchor bit.

## Files

- `mothership_tt.log` — the mothership's time-transfer log for the lander link
- `lander_events.log` — the lander OBC's event log around the anchor sequence
- `hover_frames.csv` — the hover camera's frame index for the anchor sequence
- `tt_icd.md` — the time-transfer service, from the AO-111 interface control document

## Solution

### Time-transfer packet structure

The mothership timestamps `T1` at ping TX start and `T4` at reply RX completion. The lander timestamps `t2` at ping RX completion and `t3` at reply TX start. Each 14-byte reply contains the `TT` marker, vehicle ID, sequence, echoed command, and two little-endian 32-bit OBC millisecond timestamps.

The event log contains:

```text
1193532037  anchor BITE: shock peak 27.6 g on unit 4 accelerometer
```

### Asymmetric LoRa airtime

The ICD describes SF10 downlink, but the live TT log explicitly says **SF11** was selected after touchdown. Both links use BW125, coding rate 4/5, explicit headers, payload CRC and eight preamble symbols. The SX1276 airtime formula gives:

| Direction | SF | Payload | Airtime |
|---|---:|---:|---:|
| Uplink | 7 | 5 bytes | **30.976 ms** |
| Downlink | 11 | 14 bytes | **659.456 ms** |

The packet airtimes are dramatically different. The shortcut of assigning half the RTT to each direction does not align `T1` and `t2` correctly.

### Anchor BITE in UTC

Because `t2` is the lander's timestamp for **the end of the uplink packet**, the correct clock correspondence is `t2 ↔ T1 + uplink_airtime`, ignoring the under-2 µs light time. Thus:

```text
UTC_BITE = T1 + 30.976 ms + (BITE_obc_ms - t2)
```

The last ping before the quiet anchor sequence and first ping after it independently yield:

```text
Sequence 4170 bite estimate: 2041-11-04T16:47:18.713083+00:00
Sequence 4171 bite estimate: 2041-11-04T16:47:18.712594+00:00
Estimate disagreement: 0.489 ms
```

### Selecting the frame

| Frame | Exposure start (UTC) | Relation to bite |
|---|---|---|
| `0412376` | 16:47:18.695365 | Before |
| **`0412377`** | **16:47:18.745365** | **First after** |
| `0412378` | 16:47:18.795365 | Later |

The frame index is not renumbered when frames are missing; compare actual exposure timestamps.

### Dead ends

- Assuming `RTT/2` despite unequal radio airtimes and timestamp boundaries.
- Using the outdated SF10 downlink value from the ICD instead of the operational SF11 update.
- Picking the nearest frame rather than the first frame whose exposure starts **after** the bite.

### Consistency check

The two independent time-transfer estimates differ by **0.489 ms**. The camera exposures start every 50 ms, and frame **0412377** is the first exposure after the inferred UTC anchor BITE. The earlier frame 0412376 begins before the bite.

## Reproduction

Put `112.py` and the four original attachments in the same directory and run:

```bash
python3 112.py
```

Expected relevant output:

```text
Uplink ToA: 30.976 ms (SF7, 5 bytes)
Downlink ToA: 659.456 ms (SF11, 14 bytes)
Anchor BITE OBC: 1193532037 ms
Sequence 4170 bite estimate: 2041-11-04T16:47:18.713083+00:00
Sequence 4171 bite estimate: 2041-11-04T16:47:18.712594+00:00
Estimate disagreement: 0.489 ms
Previous frame: 0412376 at 2041-11-04T16:47:18.695365+00:00
First frame after BITE: 0412377 at 2041-11-04T16:47:18.745365+00:00
FLAG: GAIANSPACE{0412377}
```

## Python Source Code

```python
#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
"""Recover the first hover-camera frame after the lander's anchor bite."""

import argparse
import csv
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def lora_airtime_ms(sf: int, payload_bytes: int, bw_hz: int = 125000) -> float:
    """Compute SX1276 explicit-header, CRC-on, CR 4/5 time-on-air."""
    symbol_ms = (2 ** sf) * 1000.0 / float(bw_hz)
    low_data_rate = 1 if symbol_ms > 16.0 else 0
    numerator = 8 * payload_bytes - 4 * sf + 28 + 16
    denominator = 4 * (sf - 2 * low_data_rate)
    payload_symbols = 8 + max(math.ceil(numerator / denominator) * 5, 0)
    return (8 + 4.25 + payload_symbols) * symbol_ms


def read_transfers(path: Path):
    """Read transfer records, including the post-touchdown SF11 update."""
    downlink_sf = None
    transfers = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if "link config:" in line:
            match = re.search(r"downlink SF(\d+)", line)
            if match:
                downlink_sf = int(match.group(1))
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 7 or parts[5] != "ok":
            continue
        seq = int(parts[0])
        payload = bytes.fromhex(parts[6])
        if len(payload) != 14 or payload[:2] != b"TT":
            raise ValueError(f"Invalid TT reply for sequence {seq}")
        reply_seq = int.from_bytes(payload[3:5], "little")
        if reply_seq != seq:
            raise ValueError(f"Sequence mismatch: {seq} vs {reply_seq}")
        transfers.append({
            "seq": seq,
            "t1": parse_utc(parts[1]),
            "t4": parse_utc(parts[2]),
            "command": int(payload[5]),
            "t2": int.from_bytes(payload[6:10], "little"),
            "t3": int.from_bytes(payload[10:14], "little"),
        })
    if downlink_sf is None:
        raise ValueError("Missing live downlink SF configuration")
    return transfers, downlink_sf


def read_bite(path: Path) -> int:
    """Read the anchor-bite event in lander OBC milliseconds."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if "anchor BITE:" in line:
            return int(line.split()[0])
    raise ValueError("Anchor BITE event not found")


def estimate_bite(record: dict, bite_ms: int, uplink_ms: float) -> datetime:
    """Map OBC time to UTC using the corrected uplink receive instant."""
    utc_at_t2 = record["t1"] + timedelta(milliseconds=uplink_ms)
    return utc_at_t2 + timedelta(milliseconds=bite_ms - record["t2"])


def read_frames(path: Path):
    """Load exposure start times without renumbering missing frames."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [(row["frame"], parse_utc(row["exposure_start_utc"])) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tt", type=Path, default=Path("mothership_tt.log"))
    parser.add_argument("--events", type=Path, default=Path("lander_events.log"))
    parser.add_argument("--frames", type=Path, default=Path("hover_frames.csv"))
    args = parser.parse_args()

    transfers, downlink_sf = read_transfers(args.tt)
    bite_ms = read_bite(args.events)
    uplink_ms = lora_airtime_ms(7, 5)
    downlink_ms = lora_airtime_ms(downlink_sf, 14)
    print(f"Uplink ToA: {uplink_ms:.3f} ms (SF7, 5 bytes)")
    print(f"Downlink ToA: {downlink_ms:.3f} ms (SF{downlink_sf}, 14 bytes)")
    print(f"Anchor BITE OBC: {bite_ms} ms")

    # Select the last transfer before the bite and the first one after it.
    before = max((item for item in transfers if item["t2"] <= bite_ms), key=lambda item: item["t2"])
    after = min((item for item in transfers if item["t2"] > bite_ms), key=lambda item: item["t2"])
    first_estimate = estimate_bite(before, bite_ms, uplink_ms)
    second_estimate = estimate_bite(after, bite_ms, uplink_ms)
    print(f"Sequence {before['seq']} bite estimate: {first_estimate.isoformat()}")
    print(f"Sequence {after['seq']} bite estimate: {second_estimate.isoformat()}")
    print(f"Estimate disagreement: {abs((first_estimate - second_estimate).total_seconds()) * 1000.0:.3f} ms")

    frames = read_frames(args.frames)
    first = next(((frame, start) for frame, start in frames if start > first_estimate), None)
    if first is None:
        raise RuntimeError("No recorded exposure starts after the bite")
    frame, start = first
    prior = [(name, stamp) for name, stamp in frames if stamp <= first_estimate]
    if prior:
        print(f"Previous frame: {prior[-1][0]} at {prior[-1][1].isoformat()}")
    print(f"First frame after BITE: {frame} at {start.isoformat()}")
    print(f"FLAG: GAIANSPACE{{{frame}}}")


if __name__ == "__main__":
    main()
```

## Tools and References

- Python 3 standard library: `datetime`, `csv`, `math`, `re`, `pathlib`
- Supplied `tt_icd.md` for the packet format and timestamp definitions
- Supplied `mothership_tt.log` for the live SF11 update
- Semtech SX1276 time-on-air formula (cited by the ICD)

## Flag

```text
GAIANSPACE{0412377}
```
