
import re
from pathlib import Path

data = Path("mars_downlink.pcap").read_bytes()

# Locate the RTSP session description and its session name.
match = re.search(
    rb"s=(GAIANSPACE\{[^}\r\n]+\})\r?\n"
    rb"i=([^\r\n]+)",
    data,
)

if match is None:
    raise RuntimeError("RTSP session flag not found")

print("Session:", match.group(1).decode("ascii"))
print("Platform:", match.group(2).decode("ascii"))

