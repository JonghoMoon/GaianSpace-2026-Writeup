# 703-lagrange-fix

| | |
|---|---|
| **Category** | 07 — Unscheduled Passes |
| **Points** | 100 |

## Description

Pilgrim-1 does not know what time it is. Before the data computer can be patched, the patch has to be timed, and for that the ground needs to know how wrong the spacecraft's clock is.

Decades ago someone gave Pilgrim-1 a receiver for the Solar System Positioning Service: eight beacons parked at the Lagrange points of the outer planets, each shouting the time into the dark. The receiver has been counting on its own since the 2019 fault. Last night it took three snapshots of what it heard and sent them home.

Engineering needs one number: how far the receiver's clock is from true time.

**Flag format:** `GAIANSPACE{CLK_<receiver clock minus TDB, in whole milliseconds, with sign>}` — for example `GAIANSPACE{CLK_-1234}`.

**Attachments:**

- `ssps_receiver_log.csv` — the receiver's snapshots: its own clock, and the stamp of each beacon's pulse arriving at that moment
- `ssps_almanac.md` — how the service defines a beacon's position, and this month's bulletins

## Solution

### Steps

1. Read the receiver's three snapshots and the almanac for eight outer-planet L4/L5 beacons.
2. Use JPL DE440 ephemerides to compute planetary-system barycentre positions and velocities.
3. Construct each beacon's L4 or L5 location by rotating the heliocentric planet vector ±60° about its orbital angular-momentum axis.
4. Fit receiver position and a shared receiver-clock bias using signal light-time equations.
5. Repeat the fit while excluding each beacon in turn. Reject the outlier `SAT-L5` because excluding it reduces the residual RMS to approximately 0.024 µs.
6. Convert the best-fit clock bias to signed integer milliseconds.

### Reproduction

Required dependencies: NumPy, SciPy, and a local `de440s.bsp` ephemeris file. No ephemeris download is performed automatically.

Run the solver from the directory containing the original challenge inputs, as in the uploaded working archive.

```bash
python3 703.py
```

Expected relevant output:

```text
EXCLUDE (none)  : bias=+2279.907605844 s RMS=0.183916639 s
EXCLUDE JUP-L4  : bias=+2273.578004802 s RMS=0.196391916 s
EXCLUDE JUP-L5  : bias=+2315.569361028 s RMS=0.182582033 s
EXCLUDE NEP-L4  : bias=+2297.412288174 s RMS=0.191655958 s
EXCLUDE NEP-L5  : bias=+2248.580409601 s RMS=0.166727834 s
EXCLUDE SAT-L4  : bias=+2336.543981391 s RMS=0.177951875 s
EXCLUDE SAT-L5  : bias=+2213.481252853 s RMS=2.42029006e-08 s
EXCLUDE URA-L4  : bias=+2278.926003100 s RMS=0.196591499 s
EXCLUDE URA-L5  : bias=+2277.790536511 s RMS=0.196281998 s
SELECTED EXCLUSION: SAT-L5
CLOCK MINUS TDB: +2213.481252853 s
ROUNDED MILLISECONDS: +2213481
RETAINED RMS: 0.024203 us
SNAPSHOT ROUNDING: [2213481, 2213481, 2213481]
FLAG: GAIANSPACE{CLK_+2213481}
```

The `de440s.bsp` file is present in the uploaded working archive, but is not one of the two original challenge attachments.

### Exploit Code

```python
#!/usr/bin/env python3
"""Solve 703-lagrange-fix using DE440 and the supplied SSPS snapshots.

Example:
    python3 solve_703_lagrange_fix_v1.py --input-dir /path/to/703 --ephemeris de440s.bsp

Dependencies: NumPy and SciPy. The 701 spacecraft trajectory is NOT required.
Solve independent receiver positions for all snapshots and one shared clock
bias, then test exclusion of each beacon against the complete residual vector.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import least_squares

C_KM_S = 299792.458
PLANETS = {'JUP': 5, 'SAT': 6, 'URA': 7, 'NEP': 8}

@dataclass(frozen=True)
class SpkSegment:
    target: int
    center: int
    frame: int
    kind: int
    start: float
    stop: float
    words: np.ndarray


class SpkReader:
    """Read the J2000 SPK types used here, not a replacement for CSPICE.

    Supported representations are type 2 (Chebyshev position) and type 13
    with degree 3 (cubic Hermite position/velocity). Unsupported formats fail.
    Reference: https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/spk.html
    """

    def __init__(self, content: bytes, label: str = '<SPK>') -> None:
        self.content = content
        self.label = str(label)
        if len(content) < 1024 or len(content) % 8 != 0:
            raise ValueError(f'{label}: invalid DAF file size.')
        if content[:8] != b'DAF/SPK ':
            raise ValueError(f'{label}: not a DAF/SPK file.')
        formats = {b'LTL-IEEE': '<', b'BIG-IEEE': '>'}
        if content[88:96] not in formats:
            raise ValueError(f'{label}: unsupported binary representation.')
        endian = str(formats[content[88:96]])
        nd, ni = struct.unpack_from(endian + '2i', content, 8)
        if (int(nd), int(ni)) != (2, 6):
            raise ValueError(f'{label}: unsupported SPK summary dimensions.')
        self.words = np.frombuffer(content, dtype=np.dtype(endian + 'f8'))
        self.segments: list[SpkSegment] = []
        record = int(struct.unpack_from(endian + 'i', content, 76)[0])
        visited: set[int] = set()
        while record != 0:
            if record in visited or record < 1 or record * 1024 > len(content):
                raise ValueError(f'{label}: invalid DAF summary chain.')
            visited.add(record)
            start = int((record - 1) * 1024)
            next_record, _, count = struct.unpack_from(endian + '3d', content, start)
            if int(count) != count or not 0 <= int(count) <= 25:
                raise ValueError(f'{label}: invalid DAF summary count.')
            for index in range(int(count)):
                offset = int(start + 24 + index * 40)
                first_et, last_et = struct.unpack_from(endian + '2d', content, offset)
                target, center, frame, kind, first, last = struct.unpack_from(
                    endian + '6i', content, offset + 16)
                if not 1 <= int(first) <= int(last) <= int(self.words.size):
                    raise ValueError(f'{label}: invalid SPK word addresses.')
                self.segments.append(SpkSegment(
                    target=int(target), center=int(center), frame=int(frame),
                    kind=int(kind), start=float(first_et), stop=float(last_et),
                    words=self.words[int(first) - 1:int(last)]))
            record = int(next_record)
        if not self.segments:
            raise ValueError(f'{label}: no SPK segments found.')

    @classmethod
    def from_path(cls, path: Path) -> 'SpkReader':
        return cls(path.read_bytes(), str(path))

    def state(self, target: int, et: float, chain: tuple[int, ...] = ()) -> np.ndarray:
        """Return geometric SSB/J2000 position in km and velocity in km/s."""
        target, et = int(target), float(et)
        if target == 0:
            return np.zeros(6, dtype=np.float64)
        if target in chain:
            raise ValueError('A cycle exists in the SPK center chain.')
        for seg in reversed(self.segments):
            if seg.target != target or not seg.start <= et <= seg.stop:
                continue
            if seg.frame != 1:
                raise ValueError('Only J2000/frame ID 1 is supported.')
            result = self._evaluate(seg, et)
            return result + self.state(seg.center, et, chain + (target,))
        raise ValueError(f'{self.label}: no state for body {target} at ET {et:.9f}.')

    @staticmethod
    def _evaluate(seg: SpkSegment, et: float) -> np.ndarray:
        data = seg.words
        if seg.kind == 2:
            init, interval, record_size, record_count = [float(v) for v in data[-4:]]
            width, count = int(record_size), int(record_count)
            if interval <= 0.0 or width < 5 or (width - 2) % 3 != 0:
                raise ValueError('Invalid SPK type 2 record parameters.')
            if count < 1 or count * width + 4 != int(data.size):
                raise ValueError('Invalid SPK type 2 segment length.')
            index = min(max(int(math.floor((et - init) / interval)), 0), count - 1)
            rec = data[index * width:(index + 1) * width]
            midpoint, radius = float(rec[0]), float(rec[1])
            if radius <= 0.0:
                raise ValueError('Invalid Chebyshev time radius.')
            u = float((et - midpoint) / radius)
            if abs(u) > 1.0 + 1.0e-10:
                raise ValueError('Requested epoch is outside the Chebyshev interval.')
            coeff = rec[2:].reshape(3, -1)
            position = np.asarray([
                float(np.polynomial.chebyshev.chebval(u, row)) for row in coeff
            ], dtype=np.float64)
            velocity = np.asarray([
                float(np.polynomial.chebyshev.chebval(
                    u, np.polynomial.chebyshev.chebder(row))) / radius
                for row in coeff
            ], dtype=np.float64)
            return np.concatenate((position, velocity))
        if seg.kind == 13:
            degree, count = int(data[-2]), int(data[-1])
            if degree != 3 or count < 2:
                raise ValueError('Only degree-3 SPK type 13 is supported.')
            if int(data.size) != 7 * count + (count - 1) // 100 + 2:
                raise ValueError('Invalid SPK type 13 segment length.')
            states = data[:6 * count].reshape(count, 6)
            epochs = data[6 * count:7 * count]
            if not float(epochs[0]) <= et <= float(epochs[-1]):
                raise ValueError('Requested epoch is outside the Hermite state table.')
            index = min(max(int(np.searchsorted(epochs, et, side='right')) - 1, 0), count - 2)
            dt = float(epochs[index + 1] - epochs[index])
            if dt <= 0.0:
                raise ValueError('Non-increasing Hermite epochs.')
            u = float((et - float(epochs[index])) / dt)
            p0, p1 = states[index, :3], states[index + 1, :3]
            v0, v1 = states[index, 3:], states[index + 1, 3:]
            position = ((2.0 * u**3 - 3.0 * u**2 + 1.0) * p0
                        + (u**3 - 2.0 * u**2 + u) * dt * v0
                        + (-2.0 * u**3 + 3.0 * u**2) * p1
                        + (u**3 - u**2) * dt * v1)
            velocity = (((6.0 * u**2 - 6.0 * u) * p0
                         + (-6.0 * u**2 + 6.0 * u) * p1) / dt
                        + (3.0 * u**2 - 4.0 * u + 1.0) * v0
                        + (3.0 * u**2 - 2.0 * u) * v1)
            return np.concatenate((position, velocity))
        raise ValueError(f'Unsupported SPK type {seg.kind}; refusing an approximation.')


@dataclass(frozen=True)
class Observation:
    receiver_clock: float
    beacon: str
    tx_stamp: float
    cn0_dbhz: float


def read_observations(path: Path) -> list[Observation]:
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    result: list[Observation] = []
    for row in rows:
        name = str(row['beacon'])
        parts = name.split('-')
        if len(parts) != 2 or parts[0] not in PLANETS or parts[1] not in ('L4', 'L5'):
            raise ValueError(f'Unknown beacon: {name}')
        values = [float(row[key]) for key in ('rx_clock_s', 'tx_stamp_tdb_s', 'cn0_dbhz')]
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Non-finite observation value.')
        result.append(Observation(values[0], name, values[1], values[2]))
    if not result:
        raise ValueError('The receiver log is empty.')
    pairs = [(row.receiver_clock, row.beacon) for row in result]
    if len(set(pairs)) != len(pairs):
        raise ValueError('Duplicate snapshot/beacon observations.')
    return result


def beacon_position(ephemeris: SpkReader, beacon: str, tx: float) -> np.ndarray:
    """Apply the almanac's exact construction at the stamped TRANSMIT epoch."""
    planet, point = beacon.split('-')
    sun = ephemeris.state(10, float(tx))
    heliocentric = ephemeris.state(int(PLANETS[planet]), float(tx)) - sun
    r, v = heliocentric[:3], heliocentric[3:]
    h = np.cross(r, v)
    norm = float(np.linalg.norm(h))
    if norm == 0.0:
        raise ValueError('The planet orbit normal is undefined.')
    unit = h / norm
    angle = float((1.0 if point == 'L4' else -1.0) * math.pi / 3.0)
    rotated = (r * math.cos(angle) + np.cross(unit, r) * math.sin(angle)
               + unit * float(np.dot(unit, r)) * (1.0 - math.cos(angle)))
    return rotated + sun[:3]


class ClockFit:
    """Use light-seconds for positions so the clock and ranges share units."""
    def __init__(self, observations: list[Observation], positions_km: np.ndarray) -> None:
        self.observations = observations
        self.epochs = sorted(set(float(o.receiver_clock) for o in observations))
        self.group = np.asarray([self.epochs.index(float(o.receiver_clock))
                                 for o in observations], dtype=np.int64)
        self.positions = np.asarray(positions_km, dtype=np.float64) / C_KM_S
        self.pseudoranges = np.asarray([
            float(o.receiver_clock - o.tx_stamp) for o in observations
        ], dtype=np.float64)
        self.count = int(len(self.epochs))

    def residuals(self, x: np.ndarray) -> np.ndarray:
        receivers = x[:-1].reshape(self.count, 3)
        distance = np.linalg.norm(receivers[self.group] - self.positions, axis=1)
        # Positive residual means predicted range+bias exceeds rx_clock-tx_stamp.
        return distance + float(x[-1]) - self.pseudoranges

    def jacobian(self, x: np.ndarray) -> np.ndarray:
        offsets = x[:-1].reshape(self.count, 3)[self.group] - self.positions
        ranges = np.linalg.norm(offsets, axis=1)
        if bool(np.any(ranges == 0.0)):
            raise ValueError('A receiver trial position coincides with a beacon.')
        derivatives = offsets / ranges[:, None]
        jac = np.zeros((len(self.observations), 3 * self.count + 1), dtype=np.float64)
        jac[:, -1] = 1.0
        for index, group in enumerate(self.group):
            first = int(group) * 3
            jac[index, first:first + 3] = derivatives[index]
        return jac

    def initialize(self, keep: np.ndarray) -> np.ndarray:
        positions: list[float] = []
        biases: list[float] = []
        for group in range(self.count):
            indices = np.flatnonzero(keep & (self.group == group))
            if int(indices.size) < 5:
                raise ValueError('Each snapshot needs at least five retained beacons.')
            beacons = self.positions[indices]
            ranges = self.pseudoranges[indices]
            # Subtract the first squared pseudorange equation from all others.
            matrix = np.column_stack((2.0 * (beacons[1:] - beacons[0]),
                                      -2.0 * (ranges[1:] - ranges[0])))
            rhs = (np.sum(beacons[1:]**2, axis=1) - float(np.sum(beacons[0]**2))
                   - ranges[1:]**2 + float(ranges[0]**2))
            solution, _, rank, _ = np.linalg.lstsq(matrix, rhs, rcond=None)
            if int(rank) != 4:
                raise ValueError('Insufficient beacon geometry for initialization.')
            positions.extend(float(value) for value in solution[:3])
            biases.append(float(solution[3]))
        positions.append(float(np.median(np.asarray(biases, dtype=np.float64))))
        return np.asarray(positions, dtype=np.float64)

    def solve(self, excluded: str | None) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
        keep = np.asarray([row.beacon != excluded for row in self.observations], dtype=np.bool_)
        initial = self.initialize(keep)
        fit = least_squares(
            lambda x: self.residuals(x)[keep], initial,
            jac=lambda x: self.jacobian(x)[keep],
            xtol=1.0e-14, ftol=1.0e-14, gtol=1.0e-14, max_nfev=2000)
        residual = self.residuals(fit.x)
        rms = float(np.sqrt(np.mean(residual[keep]**2)))
        summary = dict(
            excluded_beacon=excluded, clock_bias_s=float(fit.x[-1]),
            initial_clock_bias_s=float(initial[-1]), rms_s=rms,
            max_abs_residual_s=float(np.max(np.abs(residual[keep]))),
            retained_observations=int(np.count_nonzero(keep)),
            optimizer_success=bool(fit.success), optimizer_message=str(fit.message),
            function_evaluations=int(fit.nfev),
            jacobian_condition_number=float(np.linalg.cond(fit.jac)))
        return summary, fit.x.copy(), keep


def signed_nearest_ms(seconds: float) -> int:
    value = float(seconds * 1000.0)
    return int(math.floor(value + 0.5)) if value >= 0.0 else -int(math.floor(-value + 0.5))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=Path('.'))
    parser.add_argument('--log', type=Path)
    parser.add_argument('--ephemeris', type=Path, help='Local de440s.bsp (no automatic download).')
    parser.add_argument('--tolerance-us', type=float, default=1.0,
                        help='Maximum accepted RMS for the retained timing observations.')
    parser.add_argument('--out-dir', type=Path, default=Path('703_solution'))
    args = parser.parse_args()
    log = args.log if args.log is not None else args.input_dir / 'ssps_receiver_log.csv'
    bsp = args.ephemeris if args.ephemeris is not None else args.input_dir / 'de440s.bsp'
    if not math.isfinite(float(args.tolerance_us)) or float(args.tolerance_us) <= 0.0:
        raise ValueError('--tolerance-us must be finite and positive.')
    observations = read_observations(log)
    ephemeris = SpkReader.from_path(bsp)
    positions = np.asarray([beacon_position(ephemeris, row.beacon, row.tx_stamp)
                            for row in observations], dtype=np.float64)
    model = ClockFit(observations, positions)
    names = sorted(set(row.beacon for row in observations))
    attempts = [model.solve(excluded) for excluded in [None] + names]
    for summary, _, _ in attempts:
        name = str(summary['excluded_beacon'] or '(none)')
        print(f'EXCLUDE {name:8s}: bias={float(summary["clock_bias_s"]):+.9f} s '
              f'RMS={float(summary["rms_s"]):.9g} s')
    tolerance = float(args.tolerance_us) * 1.0e-6
    if float(attempts[0][0]['rms_s']) <= tolerance:
        chosen = attempts[0]
    else:
        chosen = min(attempts[1:], key=lambda item: float(item[0]['rms_s']))
        plausible = [entry for entry in attempts[1:] if float(entry[0]['rms_s']) <= tolerance]
        if len(plausible) != 1:
            raise RuntimeError('A unique single-beacon exclusion was not established.')
    summary, state, keep = chosen
    if not bool(summary['optimizer_success']) or float(summary['rms_s']) > tolerance:
        raise RuntimeError('The selected timing fit does not satisfy the residual criterion.')
    residual = model.residuals(state)
    bias = float(state[-1])
    milliseconds = signed_nearest_ms(bias)
    # Independently fit each snapshot to check the required millisecond rounding.
    snapshot_checks = []
    for epoch in model.epochs:
        indices = [index for index, row in enumerate(observations)
                   if row.receiver_clock == epoch]
        local = ClockFit([observations[index] for index in indices], positions[indices])
        local_summary, _, _ = local.solve(summary['excluded_beacon'])
        local_ms = signed_nearest_ms(float(local_summary['clock_bias_s']))
        if local_ms != milliseconds:
            raise RuntimeError('Individual snapshots disagree after millisecond rounding.')
        snapshot_checks.append(dict(receiver_clock_s=float(epoch),
                                    clock_bias_s=float(local_summary['clock_bias_s']),
                                    rounded_bias_ms=int(local_ms)))
    flag = f'GAIANSPACE{{CLK_{milliseconds:+d}}}'
    per_row = []
    for index, row in enumerate(observations):
        per_row.append(dict(receiver_clock_s=float(row.receiver_clock), beacon=row.beacon,
                            tx_stamp_tdb_s=float(row.tx_stamp), cn0_dbhz=float(row.cn0_dbhz),
                            retained=bool(keep[index]),
                            predicted_minus_observed_s=float(residual[index])))
    receiver_states = []
    for index, epoch in enumerate(model.epochs):
        receiver_states.append(dict(
            receiver_clock_s=float(epoch), true_receive_tdb_s=float(epoch - bias),
            position_ssb_j2000_km=[float(value * C_KM_S)
                                    for value in state[3 * index:3 * index + 3]]))
    report = dict(flag=flag, clock_bias_definition='receiver clock minus TDB',
                  clock_bias_seconds=bias, rounded_clock_bias_ms=int(milliseconds),
                  selected_fit=summary, exclusion_trials=[entry[0] for entry in attempts],
                  snapshot_checks=snapshot_checks, receiver_states=receiver_states,
                  observations=per_row,
                  model='One common clock bias; independent receiver position per snapshot; '
                        'beacon position evaluated at its transmit stamp; no 701 trajectory used.',
                  residual_definition='predicted_range_seconds + receiver_bias - '
                                      '(receiver_clock - beacon_tx_stamp)',
                  inputs_sha256={log.name: hashlib.sha256(log.read_bytes()).hexdigest(),
                                 bsp.name: hashlib.sha256(bsp.read_bytes()).hexdigest()})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / '703_verified_results.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (args.out_dir / 'flag.txt').write_text(flag + '\n', encoding='ascii')
    print(f'SELECTED EXCLUSION: {summary["excluded_beacon"]}')
    print(f'CLOCK MINUS TDB: {bias:+.9f} s')
    print(f'ROUNDED MILLISECONDS: {milliseconds:+d}')
    print(f'RETAINED RMS: {float(summary["rms_s"])*1.0e6:.6f} us')
    print(f'SNAPSHOT ROUNDING: {[int(item["rounded_bias_ms"]) for item in snapshot_checks]}')
    print(f'FLAG: {flag}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
```

## Flag

```text
GAIANSPACE{CLK_+2213481}
```
