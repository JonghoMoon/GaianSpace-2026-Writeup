
from datetime import datetime, timezone
from skyfield.api import EarthSatellite, load, wgs84

sites = {
    "GDSN": (35.42667, -116.89000),
    "MDSN": (40.43194, -4.24917),
    "CDSN": (-35.40139, 148.98167),
    "CAPE": (28.53830, -81.37920),
    "VELA": (19.48000, -155.60000),
}

with open("gaian-13.tle", encoding="utf-8") as f:
    lines = [s.replace("\u00a0", " ").strip() for s in f if s.strip()]

line1 = next(s for s in lines if s.startswith("1 "))
line2 = next(s for s in lines if s.startswith("2 "))

ts = load.timescale()
sat = EarthSatellite(line1, line2, "GAIAN-13", ts)
t = ts.from_datetime(
    datetime(2025, 6, 12, 19, 15, 0, tzinfo=timezone.utc)
)

for callsign, (lat, lon) in sites.items():
    observer = wgs84.latlon(lat, lon)
    alt, az, distance = (sat - observer).at(t).altaz()
    print(
        f"{callsign}: elevation={alt.degrees:+.4f} deg, "
        f"visible={alt.degrees > 0.0}"
    )

