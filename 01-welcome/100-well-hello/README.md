# 100-well-hello

| | |
|---|---|
| **Category** | 01-welcome |
| **Points** | 1 |

## Description

At 21:00 UTC, the new operator checks in at console four. The watch lead, Ilse Moravec, indicates that the check-in word is **Welcome** and that every message uses the same flag envelope. A note explicitly warns that `PASSWORD123` does not work.

**Flag format:** `GAIANSPACE{[Welcome]}`

**Attachments:** None.

## Hints

Two hints were released during the event:

1. **The patch, not the stitching** — Moravec says the brackets on the card are where the word goes. They are not part of the word.
2. **Still on the pad** — Copy it almost exactly. The console is fussy about capital letters and does not forgive stray spaces.

## Solution

### Steps

**1. Identify the check-in phrase**

The challenge text directly gives the word `Welcome`. There is no connection endpoint or file to inspect for this introductory challenge.

**2. Apply the submission envelope**

The competition uses `GAIANSPACE{...}` for flags. The square brackets in the example mark replaceable text and must not be submitted literally. Case is significant, so retain the capital `W`.

**3. Ignore the decoy**

`PASSWORD123` is explicitly rejected in the story; it is not a password to crack or a valid flag.

### Solver Code

Not applicable. This is a flag-format and reading-comprehension check; no tool or code is needed.

## Flag

```text
GAIANSPACE{Welcome}
```
