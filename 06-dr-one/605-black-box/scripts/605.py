#!/usr/bin/env python3
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
        if tick < 76000:
            continue
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
