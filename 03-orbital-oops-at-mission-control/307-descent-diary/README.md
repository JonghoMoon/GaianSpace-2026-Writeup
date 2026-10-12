# 307-descent-diary

| | |
|---|---|
| **Category** | 03 — Orbital Oops at Mission Control |
| **Points** | 75 |

## Description

Foundation One logged every sensor it had, all the way down. The recovery team pulled the card after landing and handed over the whole diary of the fall. The flight lead wants to know if the CanSat recorded anything it was not supposed to.

The barometer tells a tidy story — a clean fall from a kilometre up to a hard stop in the dirt — and that tidy story is what everyone keeps staring at. It is not where the surprise is. The CanSat carried more than one instrument, and one of them was not watching the sky at all. Let that instrument draw its own picture and it stops looking like noise.

Read what the descent diary was hiding.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**
- `descent_log.csv` — the full sensor diary of the descent

## Solution

### Steps

Plot magnetometer X against magnetometer Y as a scatter plot rather than against time; read the resulting hidden message from the generated figure.

### Reproduction

Run the supplied solver with the original challenge inputs in the paths expected by the source code.

```bash
python3 307.py
```

The solver generates `flag.png` and displays a scatter plot. The flag is read visually from the plot; it is not printed by the script.

Expected relevant output:

![flag](./images/flag.png)

### Exploit Code

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("descent_log.csv")

# Plot magnetometer readings as XY coordinates.
fig, ax = plt.subplots(figsize=(17, 4.5))

ax.scatter(
    df["mag_x_uT"],
    df["mag_y_uT"],
    s=0.8,
    linewidths=0,
)

ax.set_xlabel("Magnetometer X (uT)")
ax.set_ylabel("Magnetometer Y (uT)")
ax.set_title("Foundation One - Hidden Magnetometer Message")
ax.grid(alpha=0.15)

plt.tight_layout()
plt.savefig("307_flag.png", dpi=200)
plt.show()
```

## Flag

```text
GAIANSPACE{DRIFT_AND_FALL}
```
