---
render_with_liquid: false
---

# 605 — Black Box

| | |
|---|---|
| **Category** | 06 — DR-ONE |
| **Points** | 300 |

## Description

Two days after the ice find, DR-ONE took off for one more look at the site and never called back. Then something new came down the relay we tap: not telemetry, a file.

The operators had pushed it up to the lander for its fault software to compare against: the black-box card of DR-ONE-Q, their qualification twin. Same airframe, same firmware, same config. They flew it through DR-ONE's last flight in a test hall on Earth, and the twin went down too. The impact pulled its battery, but the card survived, and we caught the image on its way up.

The operators' own note blames the rear servo, and it tested fine.

The mission team wants two things from the twin's card: which swashplate servo quit, and the moment the flight controller lost its gyro, the first sample where the sensor was pinned at the end of its range and the controller was flying blind.

**Flag format:** `GAIANSPACE{S<servo number>-T<tick>}` — `<tick>` is the black box's own `ticks_ms` value of the log block that holds the first clipped gyro sample. For example `GAIANSPACE{S3-T12345678}`.

### Files

- `bbx_sd.img.gz` — the twin's black-box card, as caught on the relay
- `drone_config.md` — DR-ONE's configuration page, as sent with the card
- `hall_notes.md` — the operators' test-hall note for the rerun

## Hints

Two hints were released during the event:

1. **Hint 1** — Last sync. A black box doesn't tell the card about everything it writes the moment it writes it. The card holds more than the file admits, and some of what follows isn't from this flight.
2. **Hint 2** — Pinned. Gravity can't be mounted the wrong way round, and neither can a flight you watched. Find the nose and the way down in the data before you trust a page, or a gyro, that says otherwise.

## Solution

### 1. Recover the black-box log beyond the FAT16 directory size

The compressed SD image contains a FAT16 filesystem. The root directory points to `BBX0007.BIN`, the log for flight 7. However, the battery was disconnected at impact, and the directory's recorded file length is stale. The directory reports **446,090 bytes**, whereas valid BBX records continue beyond that boundary.

The script reads the image, locates `BBX0007.BIN` in the FAT16 root directory, finds the text header's `START` marker, and parses subsequent FIFO (`A5 46`) and temperature (`A5 54`) records. Each FIFO record contains a block `ticks_ms` value, a sample count, and six signed 16-bit sensor values per sample. Crucially, parsing continues past the directory's file-size field.

### 2. Find the first clipped gyro sample

A gyro sample is clipped when any of its three signed 16-bit components equals `-32768` or `32767`. The revised solver searches **all recovered FIFO blocks from the beginning**, rather than skipping everything before a preselected time. The first such sample is found in the block stamped **78758 ms**, at sample index 2:

```text
First clipped gyro block: 78758 ms
Sample index in block: 2
Raw gyro: (13054, -32768, -4215)
Block offset: 476248 bytes
Beyond directory size: True
```

The challenge requests the **block's `ticks_ms`**, not an interpolated per-sample time. Therefore the second half of the flag is `T78758`.

### 3. Identify the failed swashplate servo

The airframe configuration lists three servo positions, clockwise from the nose:

| Servo | Position | Location |
|---|---:|---|
| S1 | 90° | Right |
| S2 | 210° | Rear left |
| S3 | 330° | Front left |

The test-hall notes reveal an important trap: the flight-controller board was replaced after flight 6 and installed to suit its connector, not necessarily in the orientation shown on the original drawing. Consequently, the flight-7 sensor axes cannot be interpreted blindly using the intended installation diagram.

The recorded forward-lean maneuver at 60–65 seconds provides a calibration reference. The script compares the gyro X-axis signal against the rate of change of the accelerometer Y-axis signal, obtaining a strong negative correlation:

```text
Forward-lean gyro/accel correlation: -0.914
Calibrated gyro sign: -1
```

Applying that sign convention to the pre-saturation roll gives:

```text
Onset block: 78700 ms
Onset median gyro: (-923, -2961, -2328)
Estimated tilt bearing: 107.31 deg clockwise from nose
Servo projection scores: {1: 2961.0, 2: -681.1585523069634, 3: -2279.841447693038}
```


The servo bearings are **S1 = 90°**, **S2 = 210°**, and **S3 = 330°**, clockwise from the nose. The known forward-lean maneuver calibrates the sign of the sensor-to-body mapping, and the solver uses the calibrated gyro components to estimate a downward-tilt bearing. The resulting **107.31°** estimate lies closest to **S1 (90°)**; its positive projection score (2961.0) also exceeds the scores of S2 and S3. These are model-based inferences based on the stated mounting/calibration assumptions, not an independent complete reconstruction of the board's attitude.

The estimated downward-tilt direction is nearest **S1 at 90°**, and S1 has the largest projection score. The combined result, **`GAIANSPACE{S1-T78758}`**, was subsequently confirmed as the accepted flag.

**Interpretation note:** The calibration implemented here estimates a sign relationship using the known maneuver; it does not independently solve every degree of freedom of the replacement board's physical mounting. The final S1 identification is supported by the computed direction and by the confirmed challenge flag. This distinction matters when reusing the technique on an unknown aircraft.

### Dead Ends

- **Trusting the FAT directory length:** stops before the accident and misses the clipped sample entirely.
- **Trusting the hall team's rear-servo interpretation:** their S2 hypothesis relies on the wrong sensor mounting assumption.
- **Assigning the servo from uncalibrated gyro signs:** earlier S2 and S3 candidates were incorrect; the known forward-lean maneuver was needed to revisit the sign convention.
- **Using a sample-relative time instead of the BBX block timestamp:** the problem explicitly requests the `ticks_ms` of the containing block.

## Reproduction

Place `605.py` and the original `bbx_sd.img.gz` in the same directory and run:

```bash
python3 605.py bbx_sd.img.gz
```

No third-party Python packages are required.

**Expected relevant output (reproduced with the supplied SD image):**

```text
FAT16 cluster size: 2048 bytes
BBX0007.BIN directory size: 446090 bytes
Forward-lean gyro/accel correlation: -0.914
Calibrated gyro sign: -1
First clipped gyro block: 78758 ms
Sample index in block: 2
Raw gyro: (13054, -32768, -4215)
Block offset: 476248 bytes
Beyond directory size: True
Onset block: 78700 ms
Onset median gyro: (-923, -2961, -2328)
Estimated tilt bearing: 107.31 deg clockwise from nose
Servo projection scores: {1: 2961.0, 2: -681.1585523069634, 3: -2279.841447693038}
FLAG: GAIANSPACE{S1-T78758}
```

## Python Source Code

The standalone recovery and analysis script is also available as [`605.py`](./scripts/605.py).

{% raw %}
```python
#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
"""Recover clipped gyro time and calibrate servo direction from a known maneuver."""

import argparse
import gzip
import math
import struct
from pathlib import Path


SERVO_ANGLES = {1: 90.0, 2: 210.0, 3: 330.0}


def read_image(path: Path) -> bytes:
    with gzip.open(path, "rb") as source:
        return source.read()


def locate_flight(image: bytes) -> tuple[int, int, int]:
    """Locate BBX0007.BIN using the FAT16 boot sector and root directory."""
    bytes_per_sector = struct.unpack_from("<H", image, 11)[0]
    sectors_per_cluster = int(image[13])
    reserved_sectors = struct.unpack_from("<H", image, 14)[0]
    fat_count = int(image[16])
    root_entries = struct.unpack_from("<H", image, 17)[0]
    sectors_per_fat = struct.unpack_from("<H", image, 22)[0]

    root_offset = (
        reserved_sectors + fat_count * sectors_per_fat
    ) * bytes_per_sector
    root_sectors = (root_entries * 32 + bytes_per_sector - 1) // bytes_per_sector
    data_offset = root_offset + root_sectors * bytes_per_sector
    cluster_bytes = bytes_per_sector * sectors_per_cluster

    for index in range(root_entries):
        entry = root_offset + index * 32
        record = image[entry:entry + 32]
        if record[0] == 0:
            break
        if record[0] == 0xE5 or (record[11] & 0x08) != 0:
            continue
        if record[:11] == b"BBX0007 BIN":
            first_cluster = struct.unpack_from("<H", image, entry + 26)[0]
            file_size = struct.unpack_from("<I", image, entry + 28)[0]
            offset = data_offset + (first_cluster - 2) * cluster_bytes
            return offset, file_size, cluster_bytes

    raise ValueError("BBX0007.BIN was not found")


def read_blocks(image: bytes, start: int):
    """Parse contiguous BBX records beyond the stale FAT directory size."""
    header_end = image.find(b"START\n", start, start + 4096)
    if header_end < 0:
        raise ValueError("BBX START marker was not found")

    cursor = header_end + len(b"START\n")
    while cursor + 8 <= len(image):
        record_type = image[cursor:cursor + 2]

        if record_type == b"\xA5\x54":
            cursor += 8
            continue

        if record_type != b"\xA5\x46":
            break

        tick = struct.unpack_from("<I", image, cursor + 2)[0]
        count = int(image[cursor + 6])
        if not 1 <= count <= 20:
            break

        end = cursor + 7 + count * 12
        if end > len(image):
            break

        samples = [
            struct.unpack_from("<6h", image, cursor + 7 + index * 12)
            for index in range(count)
        ]
        yield cursor - start, tick, samples
        cursor = end


def calibrate_gyro_sign(blocks):
    """Calibrate the gyro sign using the known forward-lean maneuver."""
    import statistics

    rows = [
        (tick, float(statistics.median(sample[0] for sample in samples)),
         float(statistics.median(sample[4] for sample in samples)))
        for _, tick, samples in blocks
        if 60000 <= tick <= 65000
    ]

    window = 11
    pairs = []
    for index in range(window, len(rows) - window):
        before = rows[index - window]
        after = rows[index + window]
        dt = float(after[0] - before[0])
        if dt > 0.0:
            pairs.append((rows[index][1], (after[2] - before[2]) / dt))

    if len(pairs) < 10:
        raise RuntimeError("Not enough forward-lean calibration samples")

    mx = statistics.mean(pair[0] for pair in pairs)
    my = statistics.mean(pair[1] for pair in pairs)
    numerator = sum((x - mx) * (y - my) for x, y in pairs)
    dx = sum((x - mx) ** 2 for x, _ in pairs)
    dy = sum((y - my) ** 2 for _, y in pairs)
    correlation = numerator / ((dx * dy) ** 0.5)
    if abs(correlation) < 0.5:
        raise RuntimeError("Gyro sign calibration is inconclusive")
    return (1 if correlation > 0.0 else -1), correlation


def choose_servo(gyro, gyro_sign):
    """Project calibrated gyro rates into body-frame downward tilt."""
    gyro_x, gyro_y, _ = gyro

    # Controlled forward lean identifies sensor +Y as forward, +X as right.
    # In the body frame: omega_forward = gyro_y; omega_left = -gyro_x.
    # Tilt velocity is (forward = omega_left, left = -omega_forward).
    forward = float(-gyro_sign * gyro_x)
    left = float(-gyro_sign * gyro_y)

    scores = {}
    for servo, angle in SERVO_ANGLES.items():
        radians = math.radians(angle)
        servo_forward = math.cos(radians)
        servo_left = -math.sin(radians)
        scores[servo] = forward * servo_forward + left * servo_left

    bearing = (math.degrees(math.atan2(-left, forward)) + 360.0) % 360.0
    return max(scores, key=scores.get), scores, bearing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", default="bbx_sd.img.gz")
    args = parser.parse_args()

    image = read_image(Path(args.image))
    start, directory_size, cluster_size = locate_flight(image)
    print(f"FAT16 cluster size: {cluster_size} bytes")
    print(f"BBX0007.BIN directory size: {directory_size} bytes")

    blocks = list(read_blocks(image, start))
    gyro_sign, correlation = calibrate_gyro_sign(blocks)
    print(f"Forward-lean gyro/accel correlation: {correlation:+.3f}")
    print(f"Calibrated gyro sign: {gyro_sign:+d}")

    first_clip = None
    preceding_blocks = []
    for relative_offset, tick, samples in blocks:
        preceding_blocks.append((tick, samples))
        if len(preceding_blocks) > 20:
            preceding_blocks.pop(0)

        for sample_index, sample in enumerate(samples):
            if any(value in (-32768, 32767) for value in sample[:3]):
                first_clip = (relative_offset, tick, sample_index, sample)
                break
        if first_clip is not None:
            break

    if first_clip is None:
        raise RuntimeError("No clipped gyro sample found")

    relative_offset, tick, sample_index, sample = first_clip
    print(f"First clipped gyro block: {tick} ms")
    print(f"Sample index in block: {sample_index}")
    print(f"Raw gyro: {sample[:3]}")
    print(f"Block offset: {relative_offset} bytes")
    print(f"Beyond directory size: {relative_offset >= directory_size}")

    # Use the beginning of the uncontrolled roll, before gyro saturation.
    onset = [
        (block_tick, values)
        for block_tick, values in preceding_blocks
        if tick - 100 <= block_tick < tick
        and abs(float(sorted(row[1] for row in values)[len(values) // 2])) > 2000.0
    ]
    if not onset:
        raise RuntimeError("No pre-clipping failure onset found")

    onset_tick, onset_samples = onset[0]
    gyro = tuple(
        int(sorted(row[column] for row in onset_samples)[len(onset_samples) // 2])
        for column in range(3)
    )
    servo, scores, direction = choose_servo(gyro, gyro_sign)
    print(f"Onset block: {onset_tick} ms")
    print(f"Onset median gyro: {gyro}")
    print(f"Estimated tilt bearing: {direction:.2f} deg clockwise from nose")
    print(f"Servo projection scores: {scores}")
    print(f"FLAG: GAIANSPACE{{S{servo}-T{tick}}}")


if __name__ == "__main__":
    main()
```
{% endraw %}

## Tools and References

- Python 3 standard library: `argparse`, `gzip`, `math`, `struct`, `statistics`, `pathlib`
- `drone_config.md`: servo geometry, IMU mounting diagram, and logger information
- `hall_notes.md`: flight sequence, forward-lean calibration maneuver, and board replacement
- FAT16 boot sector and root-directory layout; BBX FIFO record parsing

## Flag

```text
GAIANSPACE{S1-T78758}
```
