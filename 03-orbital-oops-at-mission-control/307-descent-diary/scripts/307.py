#!/usr/bin/env python3
"""Visualize a hidden message in two magnetometer channels."""

# Dependencies:
#   python3 -m pip install pandas matplotlib

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
print("Saved magnetometer scatter plot to 307_flag.png")
# Reading the text from the image is the final, visual step.
plt.show()
