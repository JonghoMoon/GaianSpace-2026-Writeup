# 102-cs-for-gs

| | |
|---|---|
| **Category** | 01-welcome |
| **Points** | 20 |

## Description

The challenge describes a cyberattack against a satellite ground segment on the morning of the 2022 Russian invasion of Ukraine. The satellite remained operational in orbit, but large numbers of user terminals in Europe became unusable; the outage also affected remote wind-turbine management and military communications. The question is what malicious software was left behind on the ground, using the name in GaianSpace's article.

A separate historical incident at a Norwegian ground station is deliberately mentioned as a distraction.

**Flag format:** `GAIANSPACE{[Name]}`

**Attachments:** None (public-source research).

## Hints

Two hints were released during the event:

1. **Same shelf** — The piece Moravec means sits next to the one you read for the crowded-sky briefing.
2. **The recent one** — Among the incidents in that piece, only one is this recent and only one wiped the terminals themselves. The house puts its name in quotes.

## Solution

### Steps

**1. Identify the event**

The references to an invasion, satellite communications, and widespread terminal failure identify the February **2022 Viasat KA-SAT attack**. The ground-side compromise disrupted satellite broadband terminals; the challenge does not ask for an attack on an orbiting spacecraft.

**2. Identify the destructive payload**

Public technical reporting associates the incident with the **AcidRain** wiper, designed to erase data from affected devices. This matches the challenge's description of a destructive component left on the ground.

**3. Exclude the unrelated incident**

The Norwegian ground-station story is another security example but does not identify the payload from the 2022 event.

**4. Preserve the exact name**

Keep the malware name's capitalization, `AcidRain`, inside the flag envelope.

### Exploit Code

Not applicable. The challenge is open-source incident identification; no binary, service, or capture was supplied.

### References

- [SentinelOne — AcidRain wiper technical analysis](https://www.sentinelone.com/labs/acidrain-a-modem-wiper-rains-down-on-europe/) — technical background for the wiper and the KA-SAT incident.
- [Viasat — KA-SAT network cyber attack overview](https://news.viasat.com/blog/corporate/ka-sat-network-cyber-attack-overview) — incident context.

## Flag

```text
GAIANSPACE{AcidRain}
```
