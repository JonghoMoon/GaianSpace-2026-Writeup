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
