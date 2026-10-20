# 103-parked-birds

| | |
|---|---|
| **Category** | 01-welcome |
| **Points** | 20 |

## Description

Moravec asks for documentary evidence that commercial GEO satellite operators are scaling back orders. The target is the **two satellites cancelled by an operator after acquiring its rival**, exactly as listed in the article, in the same order.

The abandoned Americas program and the numbers `683 / 684 ms` are explicitly non-answers.

**Flag format:** `GAIANSPACE{[Name],[Name]}`

**Attachments:** None (public-source research).

## Hints

Two hints were released during the event:

1. **Who wrote the slogan** — The night shift got that line from the house. The same shelf as the crowded-sky briefing holds the long version.
2. **Bought, then cancelled** — The two birds were ordered by the company that was bought, not by the one that bought it. Each one is a short name with a number. A program is not a bird.

## Solution

### Steps

**1. Identify the acquisition**

**SES** completed its acquisition of **Intelsat** in July 2025. The challenge asks for orders inherited from the acquired operator, rather than an unrelated expansion project.

**2. Find the cancelled satellite orders**

In 2026, SES cancelled two GEO spacecraft originally ordered by Intelsat from Thales Alenia Space: **IS-41** and **IS-44**. These are satellite designations, not a latency measurement or the separately cancelled Americas project.

**3. Check spelling and order**

The challenge explicitly requires the names in published order. They are `IS-41` first and `IS-44` second, with no spaces after the comma in the submitted flag.

### Exploit Code

Not applicable. This is a source-verification/OSINT challenge. The answer is obtained by comparing the acquisition announcement with the cancelled-order reporting.

### References

- [SES — Completion of Intelsat acquisition (17 July 2025)](https://www.ses.com/press-release/ses-completes-acquisition-intelsat-creating-global-multi-orbit-connectivity)
- [Via Satellite — SES cancels two GEO satellites (12 May 2026)](https://www.satellitetoday.com/finance/2026/05/12/networks-business-propels-revenue-growth-for-ses-operator-cancels-2-geo-sats/)
- [Data Center Dynamics — SES cancels IS-41 and IS-44 (26 May 2026)](https://www.datacenterdynamics.com/en/news/ses-cancels-two-satellites-as-providers-pull-back-from-geo/)

## Flag

```text
GAIANSPACE{IS-41,IS-44}
```
