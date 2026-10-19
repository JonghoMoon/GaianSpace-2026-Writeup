---
render_with_liquid: false
---

# 603-g-fold

| | |
|---|---|
| **Category** | 06 — DR-ONE |
| **Points** | 100 |

## Description

The rotorcraft cannot just drop onto a survey site — the air is too thin to glide and the ground is unforgiving. Its guidance computer runs a powered-descent solution (the g-FOLD family): a thrust plan that flies it from release down to a controlled touchdown. We recovered the thrust plan it used for one descent, along with the state it started from. Mission wants to know exactly where that plan puts it on the ground.

You have the computed thrust-acceleration plan, step by step, and the release state. Gravity out there is not Earth's. Fly the plan forward from the release point under the local gravity and see where it sets down. The on-call engineer keeps eyeballing the horizontal thrust and guessing a spot; the only way to know is to integrate it.

Compute the landing site.

**Flag format:** `GAIANSPACE{LZ_<x>_<y>}` — x and y in metres, each rounded to the nearest 10 m (negative allowed). For example `GAIANSPACE{LZ_120_-40}`.

**Attachments:**

- `descent_profile.csv` — the guidance thrust-acceleration plan (inertial frame)
- `gfold_notes.md` — release state, constants, and how to integrate

## Hints

Two hints were released during the event:

1. **Thin air, hard ground** — This is not Earth. Use the gravity in the notes, not 9.81.
2. **Fly the plan** — Add gravity to each thrust sample, step the velocity then the position, and stop when it reaches the ground. The horizontal position there is the site.

## Solution

### Steps

1. Read the thrust acceleration for each 0.1-second time step.
2. Combine the inertial thrust acceleration with local gravitational acceleration (3.711 m/s² downward).
3. Apply semi-implicit Euler integration: update velocity, then position.
4. Stop when altitude becomes non-positive and round the horizontal landing coordinates to the nearest 10 m.

### Reproduction

Run the solver with the original challenge files in the paths expected by the source code.

```bash
python3 603.py
```

Expected relevant output:

```text
Steps: 203
Time: 20.3 s
Position: (1374.354000, -359.118000, -2.889660) m
Velocity: [-21.729999999999716, 3.9100000000000095, -81.22329999999988] m/s
FLAG: GAIANSPACE{LZ_1370_-360}
```



### Exploit Code

```python

#!/usr/bin/env python3
# Dependencies: Python 3 standard library only.
import csv
from pathlib import Path

INPUT_FILE = Path("descent_profile.csv")

DT = 0.1
GRAVITY = 3.711

# Initial position and velocity in the inertial frame.
position = [2000.0, -500.0, 1500.0]
velocity = [-40.0, 10.0, -60.0]


def main() -> None:
    with INPUT_FILE.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for step, row in enumerate(reader, start=1):
            acceleration = [
                float(row["thr_ax"]),
                float(row["thr_ay"]),
                float(row["thr_az"]) - GRAVITY,
            ]

            # Semi-implicit Euler: update velocity before position.
            for axis in range(3):
                velocity[axis] += acceleration[axis] * DT
                position[axis] += velocity[axis] * DT

            if position[2] <= 0.0:
                x, y, z = position

                # Round the landing coordinates to the nearest 10 m.
                landing_x = round(x / 10.0) * 10
                landing_y = round(y / 10.0) * 10

                print(f"Steps: {step}")
                print(f"Time: {step * DT:.1f} s")
                print(f"Position: ({x:.6f}, {y:.6f}, {z:.6f}) m")
                print(f"Velocity: {velocity} m/s")
                print(
                    f"FLAG: GAIANSPACE{{LZ_{landing_x}_{landing_y}}}"
                )
                return

    raise RuntimeError("Vehicle did not reach the ground")


if __name__ == "__main__":
    main()
```

## Flag

```text
GAIANSPACE{LZ_1370_-360}
```
