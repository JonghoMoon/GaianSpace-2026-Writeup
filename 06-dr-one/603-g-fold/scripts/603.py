
#!/usr/bin/env python3
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

