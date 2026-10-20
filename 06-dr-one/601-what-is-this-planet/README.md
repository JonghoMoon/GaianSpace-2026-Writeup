# 601-what-is-this-planet

| | |
|---|---|
| **Category** | 06 — DR-ONE |
| **Points** | 50 |

## Description

GaianSpace has been quietly listening to a relay that should not exist. Somewhere far from home, a small rotorcraft is flying low over red dust, filming the ground and calling home through a lander. We tapped the downlink. Before anyone argues about what it is or where it is, the stream can answer for itself — it introduces itself every time a client asks to watch.

The capture is the ground relay's view of the link: the little control chatter that keeps the aircraft alive, and the handshake that sets up its camera feed. The engineering team also recovered a design sketch of the thing's eyes — a perception stack that looks at the terrain and guesses what it is seeing and how far away it is. One analyst is adamant this is just a hobby quadcopter on someone's lawn. Watch how the camera feed names itself and decide for yourself.

Identify the platform from its own downlink.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `mars_downlink.pcap` — the ground relay tap (control link + camera setup)
- `perception_stack.drawio` — recovered design sketch of the onboard vision pipeline

## Hints

Two hints were released during the event:

1. **It introduces itself** — The camera feed is set up with a short description exchange before any video flows. Follow that conversation; the stream states what it is.
2. **Read the session** — The description of the feed carries a session name. That name is the answer, wrapper and all.

## Solution

### Steps

1. Read the relay's packet capture and locate the RTSP session-description response.
2. Find the SDP `s=` session name and `i=` information fields.
3. Extract the flag from the session name and corroborate the platform description.

### Reproduction

Run the solver with the original challenge files in the paths expected by the source code.

```bash
python3 601.py
```

Expected relevant output:

```text
Session: GAIANSPACE{m4rs_r0torcraft_scout}
Platform: DR-ONE Mars rotorcraft scout - subsurface survey downlink
```



### Solver Code

```python

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
```

## Flag

```text
GAIANSPACE{m4rs_r0torcraft_scout}
```
