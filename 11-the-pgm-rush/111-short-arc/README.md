---
render_with_liquid: false
---

# 111-short-arc

| | |
|---|---|
| **Category** | 11 — The PGM Rush |
| **Points** | 150 |

## Description

The rock has a name now. Nobody has seen it in three weeks.

`2041 QM23` was found close, fast, and on a short arc: three nights, then it faded into a crowded patch of sky. Prospector AO-111 leaves next week and needs to know which faint dot is the rock. The desk asked Cerro Tololo to take two exposures of every field where it might be. Their pipeline sent back every moving thing it found. There are dozens.

Kaito has already fitted an orbit on his laptop and picked the closest dot to his prediction. Sunniva has stopped believing laptops that were set up in a hurry.

Name the tracklet that is `2041 QM23`.

**Flag format:** `GAIANSPACE{<tracklet>}` — for example `GAIANSPACE{RTABCDE}`.

### Files

- `2041QM23.obs` — every position measured so far, MPC 80-column format
- `recovery_tracklets.csv` — the moving objects from the recovery night, two positions each
- `station_notes.md` — the desk's follow-up log, including what the stations said

*The PGM Rush is inspired by AstroForge, whose unusually open mission updates show how cheap, autonomous deep-space spacecraft could open the solar system not only to asteroid mining but to faster, cheaper science for everyone.*

## Hints

Two hints were released during the event:

1. **Close company** — At this distance it matters where on Earth each telescope stands.
2. **A good clock** — Not every night in the log deserves the same trust. A position is only as good as the time stamped on it.

## Solution

### Steps

Read the fifteen MPC observations and the station metadata. The `703` observatory reported a timing-server outage; discard its compromised timing measurements rather than treating every astrometric observation as equally trustworthy. The solver fits a two-body heliocentric orbit with station-specific topocentric geometry and finite light time, trying several initial range guesses to reduce short-arc ambiguity. It then predicts the coordinates at the two Cerro Tololo recovery exposure times and ranks observed tracklets by the RMS of their RA/Dec residual components.

The provided execution log yielded a **0.160 arcsec/component** initial observation residual RMS. The best recovery tracklet, `RT39SBA`, has **5.446 arcsec/component**, while the runner-up `RTERXDS` has **99.856 arcsec/component**. These RMS values describe different datasets (initial astrometry versus recovery measurements), so they need not match. The runner-up separation supports the intended choice; the result is not a full N-body orbit solution.

The `ObsCodes.html` catalog and `de440s.bsp` ephemeris are cached reference resources, not original challenge attachments. When absent, the solver downloads station codes; Skyfield must also be able to access the relevant JPL ephemeris. See the source header for dependencies.

### Reproduction

Run the solver from the challenge's working directory, with the input files alongside the script as in the supplied ZIP.

```bash
python3 111.py
```

Expected relevant output:

```text
Initial observation residual RMS/component: 0.160 arcsec
Recovery prediction 2041-10-15T04:10:00+00:00: RA=4.3334353 Dec=8.3794509
Recovery prediction 2041-10-15T04:40:00+00:00: RA=4.3255708 Dec=8.3761361

Top recovery candidates (RMS/component, arcsec):
  RT39SBA         5.446  residuals=[3.54 7.17 3.24 6.65]
  RTERXDS        99.856  residuals=[-103.3    96.34 -113.33   84.19]
  RTS7FDP       218.033  residuals=[ 252.78 -209.06  199.95 -206.32]

BEST CANDIDATE: GAIANSPACE{RT39SBA}
```

### Exploit Code

```python
#!/usr/bin/env python3
# Dependencies: pip install numpy scipy skyfield
# Runtime data: MPC ObsCodes.html and JPL de440s.bsp (download if absent).
"""GaianSpace 111: orbit-fit MPC astrometry and rank recovery tracklets.

Dependencies: numpy, scipy, skyfield. Internet is needed once for the
DE440s ephemeris and MPC observatory catalog if they are not cached.

This is a two-body, topocentric orbit determination model, not a full
N-body precision orbit determination system. Check the fitted RMS and
runner-up separation before treating a tracklet as established.
"""

import argparse
import csv
import math
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares
from skyfield.api import load
from skyfield.framelib import itrs

AU_KM = 149597870.700
EARTH_EQUATORIAL_RADIUS_KM = 6378.137
GAUSSIAN_K = 0.01720209895
MU_SUN = GAUSSIAN_K ** 2
C_AU_PER_DAY = 173.144632674240
SECONDS_PER_DAY = 86400.0
ARCSEC_PER_RAD = 180.0 / math.pi * 3600.0


@dataclass(frozen=True)
class Observation:
    utc: datetime
    ra_deg: float
    dec_deg: float
    station: str


def parse_mpc_observations(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    for line in path.read_text(encoding="ascii").splitlines():
        if len(line) < 80:
            raise ValueError(f"Expected 80-column MPC record: {line!r}")
        date_fields = line[15:32].split()
        year, month = int(date_fields[0]), int(date_fields[1])
        day_fraction = float(date_fields[2])
        day_number = int(day_fraction)
        utc = datetime(year, month, day_number, tzinfo=timezone.utc)
        utc += timedelta(days=day_fraction - float(day_number))

        ra = line[32:44].split()
        dec = line[44:56].split()
        if len(ra) != 3 or len(dec) != 3:
            raise ValueError(f"Invalid RA/Dec in {line!r}")
        ra_deg = 15.0 * (float(ra[0]) + float(ra[1]) / 60.0 + float(ra[2]) / 3600.0)
        sign = -1.0 if dec[0].startswith("-") else 1.0
        dec_deg = sign * (abs(float(dec[0])) + float(dec[1]) / 60.0 + float(dec[2]) / 3600.0)
        observations.append(Observation(utc, ra_deg, dec_deg, line[77:80]))
    return observations


def get_mpc_stations(path: Path) -> dict[str, tuple[float, float, float]]:
    if not path.exists():
        url = "https://www.minorplanetcenter.net/iau/lists/ObsCodes.html"
        print(f"Downloading MPC station codes: {url}", flush=True)
        urllib.request.urlretrieve(url, path)
    text_data = path.read_text(encoding="latin-1")
    result: dict[str, tuple[float, float, float]] = {}
    for line in text_data.splitlines():
        line = re.sub(r"<[^>]*>", "", line)
        if len(line) < 30:
            continue
        code = line[:3].strip()
        if len(code) != 3:
            continue
        try:
            longitude_deg = float(line[4:13])
            rho_cos = float(line[13:21])
            rho_sin = float(line[21:30])
        except ValueError:
            continue
        result[code] = (longitude_deg, rho_cos, rho_sin)
    return result


def ra_dec_unit(ra_deg: float, dec_deg: float) -> np.ndarray:
    a = math.radians(ra_deg)
    d = math.radians(dec_deg)
    return np.array([math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d)])


def sky_position(unit: np.ndarray) -> tuple[float, float]:
    unit = unit / np.linalg.norm(unit)
    return (math.degrees(math.atan2(float(unit[1]), float(unit[0]))) % 360.0,
            math.degrees(math.asin(float(unit[2]))))


def ang_residual(predicted: np.ndarray, target: np.ndarray) -> np.ndarray:
    # The cross-product is a stable tangent-plane angular residual.
    ra, dec = sky_position(target)
    a = math.radians(ra)
    d = math.radians(dec)
    east = np.array([-math.sin(a), math.cos(a), 0.0])
    north = np.array([-math.sin(d) * math.cos(a), -math.sin(d) * math.sin(a), math.cos(d)])
    return np.array([float((predicted - target) @ east), float((predicted - target) @ north)]) * ARCSEC_PER_RAD


class OrbitModel:
    def __init__(self, all_dates: list[datetime], stations: dict[str, tuple[float, float, float]]):
        self.ts = load.timescale()
        self.eph = load("de440s.bsp")
        self.sun = self.eph["sun"]
        self.earth = self.eph["earth"]
        self.stations = stations
        self.t0 = min(all_dates)
        self.t0_sf = self.ts.from_datetime(self.t0)
        self.sun0 = np.asarray(self.sun.at(self.t0_sf).position.au, dtype=float)
        self.earth0 = np.asarray(self.earth.at(self.t0_sf).position.au, dtype=float)

    def t_days(self, utc: datetime) -> float:
        return (utc - self.t0).total_seconds() / SECONDS_PER_DAY

    def observer_helio(self, utc: datetime, station: str) -> np.ndarray:
        sf = self.ts.from_datetime(utc)
        earth_helio = (np.asarray(self.earth.at(sf).position.au, dtype=float)
                       - np.asarray(self.sun.at(sf).position.au, dtype=float))
        longitude_deg, rho_cos, rho_sin = self.stations[station]
        lon = math.radians(longitude_deg)
        scale = EARTH_EQUATORIAL_RADIUS_KM / AU_KM
        ecef = scale * np.array([rho_cos * math.cos(lon), rho_cos * math.sin(lon), rho_sin])
        # Skyfield's ITRS frame matrix rotates inertial vectors to Earth-fixed.
        station_inertial = itrs.rotation_at(sf).T @ ecef
        return earth_helio + station_inertial

    def observer_velocity(self, utc: datetime, station: str) -> np.ndarray:
        delta = timedelta(seconds=20)
        return (self.observer_helio(utc + delta, station)
                - self.observer_helio(utc - delta, station)) / (40.0 / SECONDS_PER_DAY)


def propagate(state: np.ndarray, dt_days: float) -> np.ndarray:
    if abs(dt_days) < 1.0e-13:
        return state[:3]

    def deriv(_t: float, y: np.ndarray) -> np.ndarray:
        r = y[:3]
        norm = float(np.linalg.norm(r))
        if norm < 0.1:
            raise ValueError("Orbit reached an implausible solar distance")
        return np.concatenate((y[3:], -MU_SUN * r / norm**3))

    sol = solve_ivp(deriv, (0.0, dt_days), state, rtol=3e-9, atol=3e-11)
    if not sol.success:
        raise ValueError(sol.message)
    return sol.y[:3, -1]


def predicted_direction(state: np.ndarray, time_days: float, observer: np.ndarray) -> np.ndarray:
    # Iterate light travel time for topocentric astrometric position.
    emission = time_days
    for _ in range(3):
        pos = propagate(state, emission)
        diff = pos - observer
        emission = time_days - float(np.linalg.norm(diff)) / C_AU_PER_DAY
    diff = propagate(state, emission) - observer
    return diff / np.linalg.norm(diff)


def fit_orbit(model: OrbitModel, initial: list[Observation]) -> tuple[np.ndarray, float]:
    # Exclude station 703 due to the documented loss of time synchronization.
    selected = [o for o in initial if o.station != "703"]
    if len(selected) < 6:
        raise ValueError("Not enough reliable observations")
    obs_units = [ra_dec_unit(o.ra_deg, o.dec_deg) for o in selected]
    observers = [model.observer_helio(o.utc, o.station) for o in selected]
    td = [model.t_days(o.utc) for o in selected]
    first = selected[0]
    direction0 = obs_units[0]
    pos0 = observers[0]
    vel0 = model.observer_velocity(first.utc, first.station)

    # Estimate sky-plane angular velocity from the first night's short arc.
    first_night = [i for i, o in enumerate(selected) if o.station == first.station]
    i_last = first_night[-1]
    span = td[i_last] - td[0]
    direction_rate = (obs_units[i_last] - direction0) / span
    direction_rate -= direction0 * float(direction_rate @ direction0)

    # Six free heliocentric state coordinates, expressed as position AU and
    # velocity AU/day. Range/range-rate multistart limits short-arc degeneracy.
    def objective(state: np.ndarray) -> np.ndarray:
        try:
            return np.concatenate([
                ang_residual(predicted_direction(state, t, observer), observed)
                for t, observer, observed in zip(td, observers, obs_units)
            ])
        except (ValueError, OverflowError):
            return np.full(2 * len(td), 1.0e6)

    best_state: np.ndarray | None = None
    best_score = float("inf")
    for rho in (0.003, 0.01, 0.03, 0.08):
        for radial_rate in (-0.005, 0.0, 0.005):
            guess = np.concatenate((pos0 + rho * direction0,
                                    vel0 + rho * direction_rate + radial_rate * direction0))
            result = least_squares(objective, guess, max_nfev=130,
                                   x_scale=np.array([1, 1, 1, .02, .02, .02]),
                                   loss="soft_l1", f_scale=1.0)
            residual = objective(result.x)
            score = float(np.sqrt(np.mean(residual**2)))
            if score < best_score:
                best_score = score
                best_state = result.x
                print(f"Fit: RMS/component={score:.3f} arcsec, starting rho={rho}", flush=True)
    if best_state is None:
        raise RuntimeError("Failed to fit orbit")
    return best_state, best_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--obs", type=Path, default=Path("2041QM23.obs"))
    parser.add_argument("--tracklets", type=Path, default=Path("recovery_tracklets.csv"))
    parser.add_argument("--sites", type=Path, default=Path("ObsCodes.html"))
    args = parser.parse_args()

    observations = parse_mpc_observations(args.obs)
    with args.tracklets.open(encoding="utf-8", newline="") as file:
        tracklets = list(csv.DictReader(file))
    if not tracklets:
        raise ValueError("No recovery tracklets")
    required_sites = {o.station for o in observations} | {"807"}
    sites = get_mpc_stations(args.sites)
    missing = required_sites - set(sites)
    if missing:
        raise ValueError(f"MPC observatory codes unavailable: {sorted(missing)}")

    recovery_times = [datetime.strptime(tracklets[0][f"t{i}_utc"], "%Y-%m-%d %H:%M:%S")
                      .replace(tzinfo=timezone.utc) for i in (1, 2)]
    model = OrbitModel([o.utc for o in observations] + recovery_times, sites)
    state, rms = fit_orbit(model, observations)
    print(f"Initial observation residual RMS/component: {rms:.3f} arcsec")

    predicted = []
    for utc in recovery_times:
        observed_pos = model.observer_helio(utc, "807")
        direction = predicted_direction(state, model.t_days(utc), observed_pos)
        ra, dec = sky_position(direction)
        predicted.append(direction)
        print(f"Recovery prediction {utc.isoformat()}: RA={ra:.7f} Dec={dec:.7f}")

    rows = []
    for row in tracklets:
        residual = np.concatenate([
            ang_residual(predicted[i], ra_dec_unit(float(row[f"ra{i+1}_deg"]),
                                                       float(row[f"dec{i+1}_deg"])))
            for i in range(2)
        ])
        score = float(np.sqrt(np.mean(residual**2)))
        rows.append((score, row["tracklet"], residual))
    rows.sort(key=lambda item: item[0])
    print("\nTop recovery candidates (RMS/component, arcsec):")
    for score, name, residual in rows[:10]:
        print(f"  {name:10s} {score:10.3f}  residuals={np.round(residual, 2)}")
    print(f"\nBEST CANDIDATE: GAIANSPACE{{{rows[0][1]}}}")
    if rms > 2.0:
        print("WARNING: orbit-fit residual is large. Do not trust rank without refining model.")
    if len(rows) > 1 and rows[1][0] < 2.0 * rows[0][0]:
        print("WARNING: top two candidates are close. Additional orbit fitting needed.")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{RT39SBA}
```
