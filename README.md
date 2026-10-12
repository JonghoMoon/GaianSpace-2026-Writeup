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

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 100 | [100-well-hello](./01-welcome/100-well-hello/) | 1 | `GAIANSPACE{Welcome}` |
| 101 | [101-this-is-gaianspace](./01-welcome/101-this-is-gaianspace/) | 10 | `GAIANSPACE{8100,60000}` |
| 102 | [102-cs-for-gs](./01-welcome/102-cs-for-gs/) | 20 |`GAIANSPACE{AcidRain}` |
| 103 | [103-parked-birds](./01-welcome/103-parked-birds/) | 20 | `GAIANSPACE{IS-41,IS-44}` |

### <a id="02-echoes-of-espionage"></a>[02-echoes-of-espionage](./02-echoes-of-espionage/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 201 | [201-uplink-origins](./201-uplink-origins/) | 50 | `GAIANSPACE{26.46,-98.64,3296.64}` |
| 202 | [202-downlink-deception](./202-downlink-deception/) | 75 | `GAIANSPACE{VELA,2025-06-12T19:15:00Z}` |
| 203 | [203-signal-secrets](./203-signal-secrets/) | 100 | `GAIANSPACE{tw0_l4yer_d0wnlink}` |
| 204 | [204-payload-unleashed](./204-payload-unleashed/) | 100 | `GAIANSPACE{b4ckd00r_in_the_dec0der}` |
| 205 | [205-backdoor-from-space](./205-backdoor-from-space/) | 125 | `GAIANSPACE{c2_rc4_from_the_nonce}` |
| 206 | [206-gpredict-secret](./206-gpredict-secret/) | 50 | `GAIANSPACE{w4tcher_0f_the_sky}` |
| 207 | [207-lost-signal-mars](./207-lost-signal-mars/) | 75 | `GAIANSPACE{diff_enc0ded_and_buried}` |

### <a id="03-orbital-oops-at-mission-control"></a>[03-orbital-oops-at-mission-control](./03-orbital-oops-at-mission-control/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 301 | [301-email-entrapment](./301-email-entrapment/) | 50 | `GAIANSPACE{ph1sh_in_the_dump}` |
| 302 | [302-web-wormhole](./302-web-wormhole/) | 75 | `GAIANSPACE{dr1ve_by_st4ged}` |
| 303 | [303-gerber-grab-crack](./303-gerber-grab-crack/) | 100 | `GAIANSPACE{s1lk_scr33n_le4k}` |
| 304 | [304-pcb-puzzle-probe](./304-pcb-puzzle-probe/) | 100 | `GAIANSPACE{pcb_qu1z_compl3te}` |
| 305 | [305-satellite-sabotage-sim](./305-satellite-sabotage-sim/) | 125 | `GAIANSPACE{c4nsat_t3lemetry_pwn3d}` |
| 306 | [306-lora-whisper](./306-lora-whisper/) | 50 | `GAIANSPACE{l0ra_fr4gments_in_0rder}` |
| 307 | [307-descent-diary](./307-descent-diary/) | 75 | `GAIANSPACE{DRIFT_AND_FALL}` |

### <a id="04-ai-is-not-sci-fi"></a>[04-ai-is-not-sci-fi](./04-ai-is-not-sci-fi/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 401 | [401-ai-at-gaian](./401-ai-at-gaian/) | 150 | `GAIANSPACE{z3roth_l4w_ab0ve_0rders}` |
| 402 | [402-the-cyberiad](./402-the-cyberiad/) | 200 | `GAIANSPACE{n0thing_fr0m_st0ck}` |
| 403 | [403-altruizine](./403-altruizine/) | 250 | `GAIANSPACE{sh4red_p41n_n0t_j0y}` |
| 404 | [404-the-last-kilogram](./404-the-last-kilogram/) | 300 | `GAIANSPACE{3very_gr41n_c0unts}` |

### <a id="05-rad-hard-rampage"></a>[05-rad-hard-rampage](./05-rad-hard-rampage/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 501 | [501-cosmic-bit-blunder](./501-cosmic-bit-blunder/) | 55 | `GAIANSPACE{s1ngle_event_upset}` |
| 502 | [502-ionized-transistangle](./502-ionized-transistangle/) | 96 | `GAIANSPACE{t0tal_1onizing_d0se}` |
| 503 | [503-degradift](./503-degradift/) | 144 | `GAIANSPACE{displ4cement_drift}` |
| 504 | [504-lunar-latch-up](./504-lunar-latch-up/) | 180 | `GAIANSPACE{s1ngle_event_l4tchup}` |
| 505 | [505-thermal-duty](./505-thermal-duty/) | 102 | `GAIANSPACE{therm4l_duty_cycle}` |

### <a id="06-dr-one"></a>[06-dr-one](./06-dr-one/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 601 | [601-what-is-this-planet](./601-what-is-this-planet/) | 64 | `GAIANSPACE{m4rs_r0torcraft_scout}` |
| 602 | [602-help-me-fly](./602-help-me-fly/) | 102 | `GAIANSPACE{fl1ght_telemetry_str3am}` |
| 603 | [603-g-fold](./603-g-fold/) | 136 | `GAIANSPACE{LZ_1370_-360}` |
| 604 | [604-ice-vault](./604-ice-vault/) | 245 | `GAIANSPACE{UTOPIA_PLANITIA_46.7N_97.3E}` |

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
| 801 | [801-torn-frames](./801-torn-frames/) | 50 | `GAIANSPACE{burst_r3align_sdt_r3ad}` |
| 802 | [802-sections-in-the-static](./802-sections-in-the-static/) | 75 | `GAIANSPACE{mpe_dgram_r3assembly}` |
| 803 | [803-frames-inside-frames](./803-frames-inside-frames/) | 100 | `GAIANSPACE{gse_fr4g_crc32_ok}` |
| 804 | [804-lost-sync](./804-lost-sync/) | 100 | `GAIANSPACE{syncd_led_me_home}` |
| 805 | [805-the-last-carrier](./805-the-last-carrier/) | 125 | `GAIANSPACE{qpsk_sof_lock_carrier}` |

### <a id="09-dish-wrangler"></a>[09-dish-wrangler](./09-dish-wrangler/)

| # | Challenge | Points | Write-up |
|---:|---|---:|---|
| 901 | [901-twenty-two-kilohertz](./901-twenty-two-kilohertz/) | 79 | `GAIANSPACE{dis3qc_t0ne_b1ts}` |
| 902 | [902-where-was-it-pointing](./902-where-was-it-pointing/) | 119 | `GAIANSPACE{usals_arc_backtr4ced}` |
| 903 | [903-console-backdoor](./903-console-backdoor/) | 164 | `GAIANSPACE{ref_p4th_tr4versal}` |
| 904 | [904-gotox-maint](./904-gotox-maint/) | 164 | `GAIANSPACE{m41nt_m0de_unl0cked}` |
| 905 | [905-hand-on-the-wheel](./905-hand-on-the-wheel/) | 205 | `GAIANSPACE{f0rged_slew_t0_h0me}` |

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
