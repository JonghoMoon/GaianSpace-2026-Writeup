#!/usr/bin/env python3
"""Recover deleted DKR-2 session 12 and measure anchor-induced yaw."""

import argparse
import csv
import gzip
import math
import re
import struct
from pathlib import Path
from statistics import median

CLUSTER_START = 73
GYRO_DPS_PER_COUNT = 0.070
ACCEL_G_PER_COUNT = 0.000732


def u16(data: bytes, offset: int) -> int:
    return int(struct.unpack_from('<H', data, offset)[0])


def u32(data: bytes, offset: int) -> int:
    return int(struct.unpack_from('<I', data, offset)[0])


def recover_card(image_path: Path) -> tuple[bytes, str, dict[str, int]]:
    with gzip.open(image_path, 'rb') as handle:
        image = handle.read()
    bytes_per_sector = u16(image, 11)
    sectors_per_cluster = int(image[13])
    reserved = u16(image, 14)
    fat_count = int(image[16])
    root_entries = u16(image, 17)
    sectors_per_fat = u16(image, 22)
    cluster_size = bytes_per_sector * sectors_per_cluster
    fat_start = reserved * bytes_per_sector
    root_start = (reserved + fat_count * sectors_per_fat) * bytes_per_sector
    root_size = ((root_entries * 32 + bytes_per_sector - 1) // bytes_per_sector) * bytes_per_sector
    data_start = root_start + root_size
    fat = image[fat_start:fat_start + sectors_per_fat * bytes_per_sector]

    entries: dict[str, tuple[int, int]] = {}
    for offset in range(root_start, root_start + root_entries * 32, 32):
        entry = image[offset:offset + 32]
        if entry[0] == 0:
            break
        if entry[11] == 0x0F or (entry[11] & 0x08) != 0:
            continue
        name = entry[:11].decode('latin-1')
        cluster = u16(entry, 26)
        size = u32(entry, 28)
        entries[name] = (cluster, size)

    deleted_name = next((name for name in entries if name[1:] == 'MU0012 BIN' and ord(name[0]) == 0xE5), None)
    if deleted_name is None:
        raise RuntimeError('Deleted IMU0012.BIN directory entry not found')
    first_cluster, imu_size = entries[deleted_name]
    if first_cluster != CLUSTER_START:
        raise RuntimeError(f'Unexpected deleted IMU start cluster: {first_cluster}')
    if 'PWR0012 CSV' not in entries:
        raise RuntimeError('Power log directory entry not found')

    def cluster_bytes(cluster: int) -> bytes:
        offset = data_start + (cluster - 2) * cluster_size
        return image[offset:offset + cluster_size]

    power_start, power_size = entries['PWR0012 CSV']
    power_chain: list[int] = []
    cluster = power_start
    while 2 <= cluster < len(fat) // 2:
        if cluster in power_chain:
            raise RuntimeError('FAT loop in power log')
        power_chain.append(cluster)
        next_cluster = u16(fat, cluster * 2)
        if next_cluster >= 0xFFF8:
            break
        cluster = next_cluster
    power = b''.join(cluster_bytes(c) for c in power_chain)[:power_size]

    required = (imu_size + cluster_size - 1) // cluster_size
    available_clusters = len(image[data_start:]) // cluster_size
    recovered: list[bytes] = []
    used_clusters: list[int] = []
    for cluster in range(first_cluster, available_clusters + 2):
        if u16(fat, cluster * 2) != 0:
            continue
        used_clusters.append(cluster)
        recovered.append(cluster_bytes(cluster))
        if len(recovered) == required:
            break
    if len(recovered) != required:
        raise RuntimeError('Not enough free clusters to reconstruct deleted IMU log')
    imu = b''.join(recovered)[:imu_size]
    if not imu.startswith(b'DKR-2 IMU LOG session 0012'):
        raise RuntimeError('Recovered file has invalid IMU header')
    return imu, power.decode('ascii'), {'size': imu_size, 'clusters': required, 'last_cluster': used_clusters[-1]}


def parse_imu(data: bytes) -> tuple[str, list[tuple[int, tuple[int, ...]]], int, int]:
    marker = b'START\n'
    position = data.index(marker) + len(marker)
    header = data[:position].decode('ascii')
    if 'REG AG 0x10 B8' not in header or 'REG AG 0x1E 38 38 A8' not in header:
        raise RuntimeError('Unexpected IMU register configuration')
    samples: list[tuple[int, tuple[int, ...]]] = []
    fifo_blocks = 0
    temperature_blocks = 0
    while position < len(data):
        if data[position:position + 2] == b'\xA5\x46':
            tick = u32(data, position + 2)
            count = int(data[position + 6])
            position += 7
            for _ in range(count):
                readings = tuple(int(x) for x in struct.unpack_from('<6h', data, position))
                samples.append((tick, readings))
                position += 12
            fifo_blocks += 1
        elif data[position:position + 2] == b'\xA5\x54':
            position += 8
            temperature_blocks += 1
        else:
            raise RuntimeError(f'Invalid IMU block at offset {position}')
    return header, samples, fifo_blocks, temperature_blocks


def power_shots(text: str) -> list[int]:
    lines = csv.DictReader(text.splitlines()[1:])
    points = [(int(row['ticks_ms']), float(row['bus_v'])) for row in lines]
    candidates = [tick for tick, volts in points if volts < 26.0]
    shots: list[int] = []
    for tick in candidates:
        if not shots or tick - shots[-1] > 2000:
            shots.append(tick)
    return shots


def sample_gyro_z(samples: list[tuple[int, tuple[int, ...]]], start: int, end: int) -> list[float]:
    return [float(readings[2]) * GYRO_DPS_PER_COUNT for tick, readings in samples if start <= tick <= end]


def yaw_change(samples: list[tuple[int, tuple[int, ...]]], shot: int, sample_rate: float, rest_window: int = 8000) -> tuple[float, float, float]:
    # Use stable pre/post periods to estimate and interpolate gyro drift.
    pre = sample_gyro_z(samples, shot - rest_window - 2500, shot - 2500)
    post = sample_gyro_z(samples, shot + 3000, shot + 3000 + rest_window)
    if not pre or not post:
        raise RuntimeError('Insufficient rest samples for drift correction')
    bias_pre = float(median(pre))
    bias_post = float(median(post))
    start = shot - 2000
    stop = shot + 3000
    integrated = 0.0
    for tick, readings in samples:
        if start <= tick <= stop:
            fraction = max(0.0, min(1.0, (tick - start) / (stop - start)))
            bias = bias_pre + (bias_post - bias_pre) * fraction
            integrated += (float(readings[2]) * GYRO_DPS_PER_COUNT - bias) / sample_rate
    return -integrated, bias_pre, bias_post


def accel_peak(samples: list[tuple[int, tuple[int, ...]]], shot: int) -> float:
    peak = 0.0
    for tick, readings in samples:
        if shot - 1000 <= tick <= shot + 1500:
            x, y, z = (float(v) * ACCEL_G_PER_COUNT for v in readings[3:])
            peak = max(peak, math.sqrt(x*x + y*y + z*z))
    return peak


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', nargs='?', type=Path, default=Path('dkr2_sd.img.gz'))
    parser.add_argument('--imu-output', type=Path, default=Path('IMU0012_recovered.BIN'))
    args = parser.parse_args()

    imu, power, info = recover_card(args.image)
    args.imu_output.write_bytes(imu)
    header, samples, fifo_count, temp_count = parse_imu(imu)
    shots = power_shots(power)
    if len(shots) != 3:
        raise RuntimeError(f'Expected 3 anchor shots, found {shots}')
    sample_rate = (len(samples) - 1) * 1000.0 / float(samples[-1][0] - samples[0][0])
    print(f"Recovered IMU0012.BIN: {info['size']} bytes, {info['clusters']} clusters")
    print(f"Parsed blocks: {fifo_count + temp_count} (FIFO={fifo_count}, temperature={temp_count})")
    print(f"Samples: {len(samples)}, inferred sample rate: {sample_rate:.3f} Hz")
    print('Sensor scales: gyro 0.070 dps/count, accel 0.000732 g/count')
    print(f'Power-log shot ticks: {shots}')
    print('Anchor  Peak(g)  CW yaw(deg)')
    results: list[tuple[str, float, float]] = []
    for name, tick in zip('CAB', shots):
        peak = accel_peak(samples, tick)
        yaw, _, _ = yaw_change(samples, tick, sample_rate)
        results.append((name, peak, yaw))
        print(f'{name:>6}  {peak:>7.2f}  {yaw:>11.2f}')
    anchor, _, turn = max(results, key=lambda row: abs(row[2]))
    print(f'FLAG: GAIANSPACE{{{anchor}-{round(turn)}}}')


if __name__ == '__main__':
    main()
