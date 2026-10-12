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

## Solution

### Steps

**1. Locate the source**

Follow the problem's instruction to consult GaianSpace's public article on the growth of LEO satellite populations:

- [GaianSpace — LEO Satellites Boom](https://gaian.space/updates/leo-satellites-boom/)

**2. Use the year that was actually requested**

The article's historical series places approximately **8,100** active satellites in LEO in **2024**. The misleading `12,000+` refers to a later population estimate and must not replace the 2024 figure.

**3. Read the forecast, not another historical data point**

The forecast used in the challenge is approximately **60,000** satellites by the end of the 2030s / around 2040. The question asks for rounded whole numbers, not the leading `~` or the comma thousands separators.

**4. Preserve ordering**

Place the 2024 count first, followed by the forecast: `8100,60000`.

### Exploit Code

No exploit is involved. A minimal formatting check is sufficient:

```python
# Format the two figures as integers in the challenge's requested order.
count_2024 = 8100
forecast_end_2030s = 60000
print(f"GAIANSPACE{{{count_2024},{forecast_end_2030s}}}")
```

### References

- [GaianSpace — LEO Satellites Boom](https://gaian.space/updates/leo-satellites-boom/) — challenge source (the original solve relied on its 2024 figures and forecast).

## Flag

```text
GAIANSPACE{8100,60000}
```
