---
render_with_liquid: false
---

# 101-this-is-gaianspace

| | |
|---|---|
| **Category** | 01-welcome |
| **Points** | 10 |

## Description

Console four asks for two whole-number figures from GaianSpace's public writing: the approximate number of **operational LEO satellites in 2024** and the number forecast **by the end of the 2030s**, in that order.

A whiteboard contains `LEO = 12,000+ ???` and `GEO is dead anyway`, but neither answers the requested pair.

**Flag format:** `GAIANSPACE{[integer],[integer]}`

**Attachments:** None (public-source research).

## Hints

Two hints were released during the event:

1. **The house talks** — GaianSpace posts what it is watching where anyone can read it. Start with what the house has to say, not the whole internet.
2. **A table, a year** — The 2024 figure sits beside other years and other fleets. The forecast is further down, near the end of the story, and it is a round number.

## Solution

### Steps

**1. Locate the source**

Follow the problem's instruction to consult GaianSpace's public article on the growth of LEO satellite populations:

- [GaianSpace — The Boom in Low Earth Orbit Satellites](https://gaian.space/updates/leo-satellites-boom/) (July 23, 2025)

**2. Use the year that was actually requested**

The article's section **"The Dramatic Rise of LEO Satellites Over the Past Decade"** includes a year-by-year breakdown of approximate active LEO satellite populations. The relevant entries are:

| Year | Approximate Active LEO Satellites |
|---|---:|
| 2024 | ~8,100 |
| 2025 (mid) | ~12,000+ (est.) |

The challenge explicitly asks for the **2024** LEO count, making **8,100** the first value. The whiteboard's `12,000+` corresponds to the later mid-2025 estimate and is a distractor. The article also reports **11,539** operational satellites at the end of 2024, but that is the **total across orbits**, not the LEO-only figure requested here.

**3. Read the forecast, not another historical data point**

In **"What the Data Reveals: Implications for the Future"**, the article states:

> By 2040, some forecasts suggest up to 60,000 satellites in LEO [10].

This gives **60,000** as the projected LEO satellite population. The challenge describes the forecast as being for the end of the 2030s; the article itself uses **"By 2040"**, so that is the source wording used to identify the figure. It is a projection, not an observed historical count.

**4. Preserve ordering**

The challenge requests whole numbers, so omit approximation signs and thousands separators. Place the 2024 count first, followed by the forecast: `8100,60000`.

### Exploit Code

No exploit is involved. A minimal formatting check is sufficient:

```python
# Format the two figures as integers in the challenge's requested order.
count_2024 = 8100
forecast_2040 = 60000
print("GAIANSPACE{" + str(count_2024) + "," + str(forecast_2040) + "}")
```

### References

- [GaianSpace — The Boom in Low Earth Orbit Satellites](https://gaian.space/updates/leo-satellites-boom/) — **"The Dramatic Rise of LEO Satellites Over the Past Decade"** (2024 table entry) and **"What the Data Reveals: Implications for the Future"** (2040 forecast).

## Flag

```text
GAIANSPACE{8100,60000}
```
