#!/usr/bin/env python3
# Dependencies:
#   python3 -m pip install numpy
"""Solve 701-one-light-day from the supplied frame log and SPICE kernels.

Example:
    python3 701.py

Dependency: NumPy. No downloaded ephemeris or CSPICE installation is needed.
The supplied SPK is evaluated exactly in its degree-3 Hermite representation.
Earth center is the observer because the supplied kernels have no station state.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import posixpath
import re
import struct
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

C_KM_S = 299792.458
J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)

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


def kernel_data(text: str) -> str:
    pieces: list[str] = []
    for part in text.split('\\begindata')[1:]:
        pieces.append(part.split('\\begintext', 1)[0])
    if not pieces:
        raise ValueError('No \\begindata section in text kernel.')
    return '\n'.join(pieces)


def assignment(text: str, name: str) -> str:
    match = re.search(re.escape(name) + r'\s*=\s*(\([^)]*\)|[^\n]+)', text, re.S)
    if match is None:
        raise ValueError(f'Missing kernel variable: {name}')
    return str(match.group(1)).strip()


def numbers(text: str, name: str) -> list[float]:
    expression = assignment(text, name).strip('() \n\r\t')
    return [float(value.replace('D', 'E').replace('d', 'e'))
            for value in expression.replace(',', ' ').split()]


def quotes(text: str, name: str) -> list[str]:
    return [str(value) for value in re.findall(r"'([^']*)'", assignment(text, name))]


def load_kernel_bundle(source: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Resolve the provided meta-kernel without executing or extracting files."""
    archived = zipfile.is_zipfile(source) if source.is_file() else False
    if archived:
        with zipfile.ZipFile(source, 'r') as archive:
            names = [str(n) for n in archive.namelist() if not str(n).endswith('/')]
            choices = [n for n in names if Path(n).name == 'pilgrim.tm']
            if len(choices) != 1:
                raise ValueError('Expected exactly one pilgrim.tm in the kernel ZIP.')
            if sum(int(i.file_size) for i in archive.infolist()) > 128 * 1024 * 1024:
                raise ValueError('The small challenge kernel archive is unexpectedly large.')
            meta_name = choices[0]
            storage = {str(n): archive.read(n) for n in names}
        meta = kernel_data(storage[meta_name].decode('ascii'))
        base = str(posixpath.dirname(meta_name))
        def read_relative(name: str) -> bytes:
            key = str(posixpath.normpath(posixpath.join(base, name)))
            if key.startswith('../') or key.startswith('/'):
                raise ValueError('Unsafe kernel archive path.')
            if key not in storage:
                raise ValueError(f'Missing kernel archive member: {key}')
            return storage[key]
    else:
        if source.is_dir():
            choices = list(source.rglob('pilgrim.tm'))
            if len(choices) != 1:
                raise ValueError('Expected exactly one pilgrim.tm under the kernel directory.')
            meta_path = choices[0]
        else:
            meta_path = source
        meta = kernel_data(meta_path.read_text(encoding='ascii'))
        meta_name = str(meta_path)
        base_path = meta_path.parent
        def read_relative(name: str) -> bytes:
            return (base_path / name).read_bytes()
    symbols, values = quotes(meta, 'PATH_SYMBOLS'), quotes(meta, 'PATH_VALUES')
    if len(symbols) != len(values):
        raise ValueError('PATH_SYMBOLS/PATH_VALUES size mismatch.')
    loaded: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for name in quotes(meta, 'KERNELS_TO_LOAD'):
        for symbol, value in zip(symbols, values):
            name = str(name.replace('$' + symbol, value))
        if '$' in name:
            raise ValueError(f'Unresolved kernel path: {name}')
        content = read_relative(name)
        key = Path(name).name
        if key in loaded:
            raise ValueError(f'Duplicate kernel basename: {key}')
        loaded[key] = content
        hashes[key] = hashlib.sha256(content).hexdigest()
    return loaded, hashes


class TimeModel:
    """Use the supplied LSK's UTC/TAI/TT/TDB model, including its leap table."""
    def __init__(self, content: bytes) -> None:
        text = kernel_data(content.decode('ascii'))
        self.delta_ta = float(numbers(text, 'DELTET/DELTA_T_A')[0])
        self.k = float(numbers(text, 'DELTET/K')[0])
        self.eb = float(numbers(text, 'DELTET/EB')[0])
        self.m0, self.m1 = [float(v) for v in numbers(text, 'DELTET/M')]
        months = {name: index + 1 for index, name in enumerate(
            ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'))}
        pairs = re.findall(r'(\d+)\s*,\s*@(\d{4})-([A-Za-z]{3})-(\d{1,2})',
                           assignment(text, 'DELTET/DELTA_AT'))
        self.leaps = [(datetime(int(y), int(months[m.upper()]), int(d), tzinfo=timezone.utc), int(n))
                      for n, y, m, d in pairs]
        self.leaps.sort()
        if not self.leaps:
            raise ValueError('No leap-second entries in the LSK.')

    def delta_at(self, utc: datetime) -> int:
        index = bisect.bisect_right([d for d, _ in self.leaps], utc) - 1
        if index < 0:
            raise ValueError('UTC epoch predates the supported LSK leap table.')
        return int(self.leaps[index][1])

    def periodic(self, et: float) -> float:
        m = float(self.m0 + self.m1 * float(et))
        e = float(m + self.eb * math.sin(m))
        return float(self.k * math.sin(e))

    def tt_to_tdb(self, tt: float) -> float:
        et = float(tt)
        for _ in range(6):
            et = float(tt + self.periodic(et))
        return et

    def tdb_to_tt(self, et: float) -> float:
        return float(et - self.periodic(et))

    def utc_to_tdb(self, text: str) -> float:
        # Normalize fractional UTC seconds explicitly for Python-version compatibility.
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})?", text.strip())
        if match is None:
            raise ValueError(f"Invalid UTC timestamp: {text!r}")
        base, fraction, zone = match.groups()
        padded = (fraction or "").ljust(6, "0")
        normalized = f"{base}.{padded}{'+00:00' if zone in (None, 'Z') else zone}"
        utc = datetime.fromisoformat(normalized)
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=timezone.utc)
        utc = utc.astimezone(timezone.utc)
        tt = float((utc - J2000).total_seconds() + self.delta_at(utc) + self.delta_ta)
        return self.tt_to_tdb(tt)

    def tdb_to_utc(self, et: float) -> str:
        base_seconds = float(self.tdb_to_tt(et) - self.delta_ta)
        guess = J2000 + timedelta(seconds=base_seconds)
        for _ in range(4):
            guess = J2000 + timedelta(seconds=float(base_seconds - self.delta_at(guess)))
        return guess.isoformat(timespec='microseconds').replace('+00:00', 'Z')


class SpacecraftClock:
    """Interpret the provided type-1 clock kernel; the subfield is a tick count."""
    def __init__(self, content: bytes, time: TimeModel, spacecraft: int = -901) -> None:
        text = kernel_data(content.decode('ascii'))
        code = str(abs(int(spacecraft)))
        if int(numbers(text, 'SCLK_DATA_TYPE_' + code)[0]) != 1:
            raise ValueError('Only type-1 SCLK kernels are supported.')
        if int(numbers(text, 'SCLK01_N_FIELDS_' + code)[0]) != 2:
            raise ValueError('Expected a two-field SCLK.')
        self.moduli = [int(v) for v in numbers(text, 'SCLK01_MODULI_' + code)]
        if any(float(v) != 0.0 for v in numbers(text, 'SCLK01_OFFSETS_' + code)):
            raise ValueError('This challenge reader requires zero SCLK field offsets.')
        self.starts = numbers(text, 'SCLK_PARTITION_START_' + code)
        self.ends = numbers(text, 'SCLK_PARTITION_END_' + code)
        if len(self.starts) != len(self.ends):
            raise ValueError('SCLK partition count mismatch.')
        self.prefix = [0.0]
        for start, stop in zip(self.starts, self.ends):
            self.prefix.append(float(self.prefix[-1] + stop - start))
        self.coeff = np.asarray(numbers(text, 'SCLK01_COEFFICIENTS_' + code), dtype=np.float64).reshape(-1, 3)
        self.system = int(numbers(text, 'SCLK01_TIME_SYSTEM_' + code)[0])
        if self.system not in (1, 2):
            raise ValueError('Unsupported SCLK parallel time system.')
        self.time = time

    def encode(self, text: str) -> float:
        match = re.fullmatch(r'(\d+)/(\d+)[.:](\d+)', text.strip())
        if match is None:
            raise ValueError(f'Invalid SCLK: {text}')
        partition, major, minor = [int(value) for value in match.groups()]
        if not 1 <= partition <= len(self.starts):
            raise ValueError('SCLK partition outside the supplied kernel.')
        if not 0 <= major < self.moduli[0] or not 0 <= minor < self.moduli[1]:
            raise ValueError('SCLK subfield is a tick count, not decimal milliseconds.')
        local = float(major * self.moduli[1] + minor)
        index = int(partition - 1)
        if not self.starts[index] <= local <= self.ends[index]:
            raise ValueError('SCLK outside its partition interval.')
        return float(self.prefix[index] + local - self.starts[index])

    def ticks_to_tdb(self, ticks: float) -> float:
        index = int(np.searchsorted(self.coeff[:, 0], ticks, side='right')) - 1
        if index < 0:
            raise ValueError('SCLK predates the first correlation coefficient.')
        tick0, epoch0, rate = [float(v) for v in self.coeff[index]]
        parallel = float(epoch0 + (ticks - tick0) * rate / float(self.moduli[1]))
        return self.time.tt_to_tdb(parallel) if self.system == 2 else parallel

    def tdb_to_ticks(self, et: float) -> float:
        parallel = self.time.tdb_to_tt(et) if self.system == 2 else float(et)
        index = int(np.searchsorted(self.coeff[:, 1], parallel, side='right')) - 1
        if index < 0:
            raise ValueError('Epoch predates the first SCLK correlation coefficient.')
        tick0, epoch0, rate = [float(v) for v in self.coeff[index]]
        return float(tick0 + (parallel - epoch0) * float(self.moduli[1]) / rate)

    def describe(self, ticks: float) -> dict[str, object]:
        index = min(bisect.bisect_right(self.prefix, ticks) - 1, len(self.starts) - 1)
        if index < 0 or ticks > self.prefix[-1]:
            raise ValueError('Epoch outside the SCLK partition coverage.')
        local = float(ticks - self.prefix[index] + self.starts[index])
        rounded = int(math.floor(local + 0.5))
        major, minor = divmod(rounded, int(self.moduli[1]))
        return dict(partition=int(index + 1),
                    sclk=f'{index + 1}/{major:010d}.{minor:03d}',
                    local_seconds=float(local / float(self.moduli[1])),
                    subsecond_tick_size_s=float(1.0 / float(self.moduli[1])))


def find_event(path: Path) -> str:
    matches = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if 'carrier frequency step' in line.lower():
            value = line.split()[0]
            matches.append(str(value))
    if len(matches) != 1:
        raise ValueError('Expected one carrier-frequency step; use --event-utc to disambiguate.')
    return str(matches[0])


def choose_suffix(loaded: dict[str, bytes], suffix: str) -> tuple[str, bytes]:
    choices = [(name, content) for name, content in loaded.items() if name.endswith(suffix)]
    if len(choices) != 1:
        raise ValueError(f'Expected exactly one {suffix} kernel in pilgrim.tm.')
    return choices[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=Path('.'))
    parser.add_argument('--frames', type=Path)
    parser.add_argument('--events', type=Path)
    parser.add_argument('--kernels', type=Path, help='kernels.zip, a kernel directory, or pilgrim.tm')
    parser.add_argument('--event-utc', help='Optional ERT override, in UTC ISO format.')
    parser.add_argument('--out-dir', type=Path, default=Path('701_solution'))
    args = parser.parse_args()
    frames = args.frames if args.frames is not None else args.input_dir / 'frame_log.csv'
    events = args.events if args.events is not None else args.input_dir / 'station_events.log'
    kernels = args.kernels if args.kernels is not None else args.input_dir / 'kernels.zip'
    loaded, hashes = load_kernel_bundle(kernels)
    _, lsk = choose_suffix(loaded, '.tls')
    _, sclk = choose_suffix(loaded, '.tsc')
    spk_name, bsp = choose_suffix(loaded, '.bsp')
    time = TimeModel(lsk)
    clock = SpacecraftClock(sclk, time)
    ephemeris = SpkReader(bsp, spk_name)
    utc_received = str(args.event_utc) if args.event_utc else find_event(events)
    received = float(time.utc_to_tdb(utc_received))
    earth = ephemeris.state(399, received)[:3]
    light_time = 0.0
    for iteration in range(1, 31):
        spacecraft = ephemeris.state(-901, received - light_time)[:3]
        updated = float(np.linalg.norm(spacecraft - earth) / C_KM_S)
        difference = float(abs(updated - light_time))
        light_time = updated
        if difference < 1.0e-9:
            break
    else:
        raise RuntimeError('The reception light-time equation did not converge.')
    event = float(received - light_time)
    ticks = float(clock.tdb_to_ticks(event))
    with frames.open('r', encoding='utf-8-sig', newline='') as handle:
        records = list(csv.DictReader(handle))
    values = np.asarray([clock.encode(str(row['sclk'])) for row in records], dtype=np.float64)
    if int(values.size) < 2 or bool(np.any(np.diff(values) <= 0.0)):
        raise ValueError('Frame SCLK values must be strictly increasing.')
    index = int(np.searchsorted(values, ticks, side='right')) - 1
    if not 0 <= index < len(records) - 1:
        raise ValueError('The event is not bracketed by two logged frame starts.')
    current, following = records[index], records[index + 1]
    word = str(current['fds_word'])
    if re.fullmatch(r'[0-9A-Fa-f]{8}', word) is None:
        raise ValueError('The selected FDS status word is not eight hexadecimal digits.')
    event_clock = clock.describe(ticks)
    frame_start = float(clock.ticks_to_tdb(float(values[index])))
    next_start = float(clock.ticks_to_tdb(float(values[index + 1])))
    if not frame_start <= event < next_start:
        raise RuntimeError('SCLK and ephemeris-time frame selection disagree.')
    flag = 'GAIANSPACE{FDS_' + word + '}'
    report = dict(
        flag=flag, reception_utc=utc_received, reception_tdb_s=received,
        event_utc=time.tdb_to_utc(event), event_tdb_s=event,
        one_way_light_time_s=light_time, iterations=int(iteration),
        observer='Earth center (399), as represented by the supplied SPK',
        event_sclk=event_clock, encoded_sclk_ticks=ticks,
        selected_frame=current, next_frame=following,
        elapsed_sclk_seconds=float((ticks - values[index]) / clock.moduli[1]),
        elapsed_tdb_seconds=float(event - frame_start),
        seconds_to_next_frame_tdb=float(next_start - event),
        kernel_sha256=hashes,
        frame_log_sha256=hashlib.sha256(frames.read_bytes()).hexdigest())
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / '701_verified_results.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (args.out_dir / 'flag.txt').write_text(flag + '\n', encoding='ascii')
    print(f'ERT UTC: {utc_received}')
    print(f'ONE-WAY LIGHT TIME: {light_time:.9f} s')
    print(f'EVENT UTC: {report["event_utc"]}')
    print(f'SCLK: {event_clock["sclk"]} (subfield counts 1/256-second ticks)')
    print(f'SCLK local seconds: {float(event_clock["local_seconds"]):.9f}')
    print(f'FRAME: {current["frame"]}, starts at {current["sclk"]}')
    print(f'ELAPSED IN FRAME: {float(report["elapsed_sclk_seconds"]):.9f} SCLK seconds')
    print(f'FLAG: {flag}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
