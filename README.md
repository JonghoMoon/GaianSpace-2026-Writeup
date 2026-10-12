# GaianSpace CTF 2026 Writeup

Write-ups and analysis scripts for **GaianSpace CTF 2026** challenges.

This repository documents my solving process as a solo participant, with an emphasis on reproducible analysis of satellite communications, RF signals, orbital mechanics, reverse engineering, embedded systems, and related security challenges.

Each write-up will include the methodology, evidence, analysis scripts, and relevant artifacts used to reach and validate the solution.

## Categories

- [01-welcome](#01-welcome) — 4 challenges
- [02-echoes-of-espionage](#02-echoes-of-espionage) — 7 challenges
- [03-orbital-oops-at-mission-control](#03-orbital-oops-at-mission-control) — 7 challenges
- [04-ai-is-not-sci-fi](#04-ai-is-not-sci-fi) — 4 challenges
- [05-rad-hard-rampage](#05-rad-hard-rampage) — 5 challenges
- [06-dr-one](#06-dr-one) — 4 challenges
- [07-unscheduled-passes](#07-unscheduled-passes) — 4 challenges
- [08-silent-carrier](#08-silent-carrier) — 5 challenges
- [09-dish-wrangler](#09-dish-wrangler) — 5 challenges
- [10-not-yet](#10-not-yet) — placeholder (no challenges yet)
- [11-the-pgm-rush](#11-the-pgm-rush) — 4 challenges
- [12-spectral-forensics](#12-spectral-forensics) — 4 challenges
- [13-night-shift](#13-night-shift) — 5 challenges

## Environment

- Ubuntu 22.04.5(5.15.0-185-generic)
- Python 3.10.12 and challenge-specific libraries
- C / OpenSSL / OpenMP where required
- Wireshark, GNU binutils, SDR/DSP tools, and other challenge-specific utilities

Exact tool versions and dependencies will be documented in the individual challenge write-ups.

Each challenge directory is intended to contain:

- `README.md` — challenge write-up
- Original challenge files and/or description (where redistribution is permitted)
- Analysis scripts and solvers
- Relevant outputs, screenshots, and validation artifacts

## Summary

The table below reflects the **solved challenges visible in the supplied scoreboard screenshots (12 October 2026)**. Category `10-not-yet` is an intentionally empty placeholder.

| Category | Challenges | Listed points |
|---|---:|---:|
| [01-welcome](#01-welcome) | 4 | 51 |
| [02-echoes-of-espionage](#02-echoes-of-espionage) | 7 | 575 |
| [03-orbital-oops-at-mission-control](#03-orbital-oops-at-mission-control) | 7 | 575 |
| [04-ai-is-not-sci-fi](#04-ai-is-not-sci-fi) | 4 | 900 |
| [05-rad-hard-rampage](#05-rad-hard-rampage) | 5 | 425 |
| [06-dr-one](#06-dr-one) | 4 | 350 |
| [07-unscheduled-passes](#07-unscheduled-passes) | 4 | 350 |
| [08-silent-carrier](#08-silent-carrier) | 5 | 450 |
| [09-dish-wrangler](#09-dish-wrangler) | 5 | 450 |
| [10-not-yet](#10-not-yet) | — | — |
| [11-the-pgm-rush](#11-the-pgm-rush) | 4 | 750 |
| [12-spectral-forensics](#12-spectral-forensics) | 4 | 681 |
| [13-night-shift](#13-night-shift) | 5 | 941 |
| **Total** | **58** | **6,498** |

---

## Challenges

Points below are transcribed from the supplied solved-challenge screenshots; they are not necessarily the final values at event close. Individual write-ups and flags will be added as documentation is completed.

### <a id="01-welcome"></a>[01-welcome](./01-welcome/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 100 | [100-well-hello](./01-welcome/100-well-hello/) | 1 | [README](./01-welcome/100-well-hello/README.md) |
| 101 | [101-this-is-gaianspace](./01-welcome/101-this-is-gaianspace/) | 10 | [README](./01-welcome/101-this-is-gaianspace/README.md) |
| 102 | [102-cs-for-gs](./01-welcome/102-cs-for-gs/) | 20 | [README](./01-welcome/102-cs-for-gs/README.md) |
| 103 | [103-parked-birds](./01-welcome/103-parked-birds/) | 20 | [README](./01-welcome/103-parked-birds/README.md) |

### <a id="02-echoes-of-espionage"></a>[02-echoes-of-espionage](./02-echoes-of-espionage/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 201 | [201-uplink-origins](./02-echoes-of-espionage/201-uplink-origins/) | 50 | [README](./02-echoes-of-espionage/201-uplink-origins/README.md) |
| 202 | [202-downlink-deception](./02-echoes-of-espionage/202-downlink-deception/) | 75 | [README](./02-echoes-of-espionage/202-downlink-deception/README.md) |
| 203 | [203-signal-secrets](./02-echoes-of-espionage/203-signal-secrets/) | 100 | [README](./02-echoes-of-espionage/203-signal-secrets/README.md) |
| 204 | [204-payload-unleashed](./02-echoes-of-espionage/204-payload-unleashed/) | 100 | [README](./02-echoes-of-espionage/204-payload-unleashed/README.md) |
| 205 | [205-backdoor-from-space](./02-echoes-of-espionage/205-backdoor-from-space/) | 125 | [README](./02-echoes-of-espionage/205-backdoor-from-space/README.md) |
| 206 | [206-gpredict-secret](./02-echoes-of-espionage/206-gpredict-secret/) | 50 | [README](./02-echoes-of-espionage/206-gpredict-secret/README.md) |
| 207 | [207-lost-signal-to-mars](./02-echoes-of-espionage/207-lost-signal-to-mars/) | 75 | [README](./02-echoes-of-espionage/207-lost-signal-to-mars/README.md) |

### <a id="03-orbital-oops-at-mission-control"></a>[03-orbital-oops-at-mission-control](./03-orbital-oops-at-mission-control/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 301 | [301-email-entrapment](./03-orbital-oops-at-mission-control/301-email-entrapment/) | 50 | [README](./03-orbital-oops-at-mission-control/301-email-entrapment/README.md) |
| 302 | [302-web-wormhole](./03-orbital-oops-at-mission-control/302-web-wormhole/) | 75 | [README](./03-orbital-oops-at-mission-control/302-web-wormhole/README.md) |
| 303 | [303-gerber-grab-crack](./03-orbital-oops-at-mission-control/303-gerber-grab-crack/) | 100 | [README](./03-orbital-oops-at-mission-control/303-gerber-grab-crack/README.md) |
| 304 | [304-pcb-puzzle-probe](./03-orbital-oops-at-mission-control/304-pcb-puzzle-probe/) | 100 | [README](./03-orbital-oops-at-mission-control/304-pcb-puzzle-probe/README.md) |
| 305 | [305-satellite-sabotage-sim](./03-orbital-oops-at-mission-control/305-satellite-sabotage-sim/) | 125 | [README](./03-orbital-oops-at-mission-control/305-satellite-sabotage-sim/README.md) |
| 306 | [306-lora-whisper](./03-orbital-oops-at-mission-control/306-lora-whisper/) | 50 | [README](./03-orbital-oops-at-mission-control/306-lora-whisper/README.md) |
| 307 | [307-descent-diary](./03-orbital-oops-at-mission-control/307-descent-diary/) | 75 | [README](./03-orbital-oops-at-mission-control/307-descent-diary/README.md) |

### <a id="04-ai-is-not-sci-fi"></a>[04-ai-is-not-sci-fi](./04-ai-is-not-sci-fi/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 401 | [401-ai-at-gaian](./04-ai-is-not-sci-fi/401-ai-at-gaian/) | 150 | [README](./04-ai-is-not-sci-fi/401-ai-at-gaian/README.md) |
| 402 | [402-the-cyberiad](./04-ai-is-not-sci-fi/402-the-cyberiad/) | 200 | [README](./04-ai-is-not-sci-fi/402-the-cyberiad/README.md) |
| 403 | [403-altruizine](./04-ai-is-not-sci-fi/403-altruizine/) | 250 | [README](./04-ai-is-not-sci-fi/403-altruizine/README.md) |
| 404 | [404-the-last-kilogram](./04-ai-is-not-sci-fi/404-the-last-kilogram/) | 300 | [README](./04-ai-is-not-sci-fi/404-the-last-kilogram/README.md) |

### <a id="05-rad-hard-rampage"></a>[05-rad-hard-rampage](./05-rad-hard-rampage/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 501 | [501-cosmic-bit-blunder](./05-rad-hard-rampage/501-cosmic-bit-blunder/) | 50 | [README](./05-rad-hard-rampage/501-cosmic-bit-blunder/README.md) |
| 502 | [502-ionized-transistangle](./05-rad-hard-rampage/502-ionized-transistangle/) | 75 | [README](./05-rad-hard-rampage/502-ionized-transistangle/README.md) |
| 503 | [503-degradift](./05-rad-hard-rampage/503-degradift/) | 100 | [README](./05-rad-hard-rampage/503-degradift/README.md) |
| 504 | [504-lunar-latch-up](./05-rad-hard-rampage/504-lunar-latch-up/) | 125 | [README](./05-rad-hard-rampage/504-lunar-latch-up/README.md) |
| 505 | [505-thermal-duty](./05-rad-hard-rampage/505-thermal-duty/) | 75 | [README](./05-rad-hard-rampage/505-thermal-duty/README.md) |

### <a id="06-dr-one"></a>[06-dr-one](./06-dr-one/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 601 | [601-what-is-this-planet](./06-dr-one/601-what-is-this-planet/) | 50 | [README](./06-dr-one/601-what-is-this-planet/README.md) |
| 602 | [602-help-me-fly](./06-dr-one/602-help-me-fly/) | 75 | [README](./06-dr-one/602-help-me-fly/README.md) |
| 603 | [603-g-fold](./06-dr-one/603-g-fold/) | 100 | [README](./06-dr-one/603-g-fold/README.md) |
| 604 | [604-ice-vault](./06-dr-one/604-ice-vault/) | 125 | [README](./06-dr-one/604-ice-vault/README.md) |

### <a id="07-unscheduled-passes"></a>[07-unscheduled-passes](./07-unscheduled-passes/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 701 | [701-one-light-day](./07-unscheduled-passes/701-one-light-day/) | 50 | [README](./07-unscheduled-passes/701-one-light-day/README.md) |
| 702 | [702-concatenated](./07-unscheduled-passes/702-concatenated/) | 75 | [README](./07-unscheduled-passes/702-concatenated/README.md) |
| 703 | [703-lagrange-fix](./07-unscheduled-passes/703-lagrange-fix/) | 100 | [README](./07-unscheduled-passes/703-lagrange-fix/README.md) |
| 704 | [704-dead-chip](./07-unscheduled-passes/704-dead-chip/) | 125 | [README](./07-unscheduled-passes/704-dead-chip/README.md) |

### <a id="08-silent-carrier"></a>[08-silent-carrier](./08-silent-carrier/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 801 | [801-torn-frames](./08-silent-carrier/801-torn-frames/) | 50 | [README](./08-silent-carrier/801-torn-frames/README.md) |
| 802 | [802-sections-in-the-static](./08-silent-carrier/802-sections-in-the-static/) | 75 | [README](./08-silent-carrier/802-sections-in-the-static/README.md) |
| 803 | [803-frames-inside-frames](./08-silent-carrier/803-frames-inside-frames/) | 100 | [README](./08-silent-carrier/803-frames-inside-frames/README.md) |
| 804 | [804-lost-sync](./08-silent-carrier/804-lost-sync/) | 100 | [README](./08-silent-carrier/804-lost-sync/README.md) |
| 805 | [805-the-last-carrier](./08-silent-carrier/805-the-last-carrier/) | 125 | [README](./08-silent-carrier/805-the-last-carrier/README.md) |

### <a id="09-dish-wrangler"></a>[09-dish-wrangler](./09-dish-wrangler/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 901 | [901-twenty-two-kilohertz](./09-dish-wrangler/901-twenty-two-kilohertz/) | 50 | [README](./09-dish-wrangler/901-twenty-two-kilohertz/README.md) |
| 902 | [902-where-was-it-pointing](./09-dish-wrangler/902-where-was-it-pointing/) | 75 | [README](./09-dish-wrangler/902-where-was-it-pointing/README.md) |
| 903 | [903-console-backdoor](./09-dish-wrangler/903-console-backdoor/) | 100 | [README](./09-dish-wrangler/903-console-backdoor/README.md) |
| 904 | [904-gotox-maint](./09-dish-wrangler/904-gotox-maint/) | 100 | [README](./09-dish-wrangler/904-gotox-maint/README.md) |
| 905 | [905-hand-on-the-wheel](./09-dish-wrangler/905-hand-on-the-wheel/) | 125 | [README](./09-dish-wrangler/905-hand-on-the-wheel/README.md) |

### <a id="10-not-yet"></a>[10-not-yet](./10-not-yet/)

*No challenges listed yet.*

### <a id="11-the-pgm-rush"></a>[11-the-pgm-rush](./11-the-pgm-rush/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 110 | [110-m-type](./11-the-pgm-rush/110-m-type/) | 100 | [README](./11-the-pgm-rush/110-m-type/README.md) |
| 111 | [111-short-arc](./11-the-pgm-rush/111-short-arc/) | 150 | [README](./11-the-pgm-rush/111-short-arc/README.md) |
| 113 | [113-touchdown](./11-the-pgm-rush/113-touchdown/) | 250 | [README](./11-the-pgm-rush/113-touchdown/README.md) |
| 117 | [117-the-dark-moonlet](./11-the-pgm-rush/117-the-dark-moonlet/) | 250 | [README](./11-the-pgm-rush/117-the-dark-moonlet/README.md) |

### <a id="12-spectral-forensics"></a>[12-spectral-forensics](./12-spectral-forensics/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 121 | [121-channel-hop](./12-spectral-forensics/121-channel-hop/) | 100 | [README](./12-spectral-forensics/121-channel-hop/README.md) |
| 122 | [122-true-color-is-a-lie](./12-spectral-forensics/122-true-color-is-a-lie/) | 125 | [README](./12-spectral-forensics/122-true-color-is-a-lie/README.md) |
| 123 | [123-isodata-seven](./12-spectral-forensics/123-isodata-seven/) | 204 | [README](./12-spectral-forensics/123-isodata-seven/README.md) |
| 124 | [124-subsidy-claim](./12-spectral-forensics/124-subsidy-claim/) | 252 | [README](./12-spectral-forensics/124-subsidy-claim/README.md) |

### <a id="13-night-shift"></a>[13-night-shift](./13-night-shift/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 131 | [131-two-voices](./13-night-shift/131-two-voices/) | 100 | [README](./13-night-shift/131-two-voices/README.md) |
| 132 | [132-no-name-on-the-door](./13-night-shift/132-no-name-on-the-door/) | 125 | [README](./13-night-shift/132-no-name-on-the-door/README.md) |
| 133 | [133-hopscotch](./13-night-shift/133-hopscotch/) | 192 | [README](./13-night-shift/133-hopscotch/README.md) |
| 134 | [134-repacked](./13-night-shift/134-repacked/) | 237 | [README](./13-night-shift/134-repacked/README.md) |
| 135 | [135-what-they-took](./13-night-shift/135-what-they-took/) | 287 | [README](./13-night-shift/135-what-they-took/README.md) |

---

*Write-ups are being prepared. Challenge links assume each problem is stored in a same-named subdirectory under its category; update relative paths if your local directory names differ.*
