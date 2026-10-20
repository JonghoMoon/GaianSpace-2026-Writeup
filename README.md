# GaianSpace CTF 2026 Writeup

Write-ups and analysis scripts for **GaianSpace CTF 2026** challenges.

This repository documents my solving process as a solo participant, with an emphasis on reproducible analysis of satellite communications, RF signals, orbital mechanics, reverse engineering, embedded systems, and related security challenges.

Each write-up includes the methodology, supporting evidence, analysis scripts, and relevant artifacts used to derive the solution.

![social-preview](./social-preview.png)

## Links

- 🌐**GitHub Pages**
  
  [https://jonghomoon.github.io/GaianSpace-2026-Writeup/](https://jonghomoon.github.io/GaianSpace-2026-Writeup/)

- 📁**GitHub Repository**
  
  [https://github.com/JonghoMoon/GaianSpace-2026-Writeup](https://github.com/JonghoMoon/GaianSpace-2026-Writeup)

## Categories

- [01-welcome](#01-welcome) — 4 challenges
- [02-echoes-of-espionage](#02-echoes-of-espionage) — 7 challenges
- [03-orbital-oops-at-mission-control](#03-orbital-oops-at-mission-control) — 7 challenges
- [04-ai-is-not-sci-fi](#04-ai-is-not-sci-fi) — 5 challenges
- [05-rad-hard-rampage](#05-rad-hard-rampage) — 5 challenges
- [06-dr-one](#06-dr-one) — 5 challenges
- [07-unscheduled-passes](#07-unscheduled-passes) — 5 challenges
- [08-silent-carrier](#08-silent-carrier) — 5 challenges
- [09-dish-wrangler](#09-dish-wrangler) — 5 challenges
- [11-the-pgm-rush](#11-the-pgm-rush) — 8 challenges
- [12-spectral-forensics](#12-spectral-forensics) — 7 challenges
- [13-night-shift](#13-night-shift) — 5 challenges

## Environment

- Ubuntu 22.04.5 (5.15.0-185-generic)
- Python 3.10.12 and challenge-specific libraries
- C / OpenSSL / OpenMP where required
- Wireshark, GNU binutils, SDR/DSP tools, and other challenge-specific utilities

Exact tool versions and dependencies are documented in the individual challenge write-ups.

Each challenge directory is intended to contains:

- `README.md` — challenge write-up
- Original challenge files and/or description (where redistribution is permitted)
- Analysis scripts and solvers
- Relevant outputs, screenshots, and validation artifacts

## Running the Solvers

Each challenge stores its original inputs in challenges/ and its analysis code in scripts/. Unless the individual writeup specifies otherwise, copy the solver and any required helper modules and reference files into the challenges/ directory, then run the solver from that directory. Install the dependencies described at the top of the source code before execution.

## Summary

The table below reflects the **final scoreboard at event close**, confirmed after the organizers reopened the site (16 October 2026)

| Category | Challenges | Listed points |
|---|---:|---:|
| [01-welcome](#01-welcome) | 4 | 51 |
| [02-echoes-of-espionage](#02-echoes-of-espionage) | 7 | 575 |
| [03-orbital-oops-at-mission-control](#03-orbital-oops-at-mission-control) | 7 | 575 |
| [04-ai-is-not-sci-fi](#04-ai-is-not-sci-fi) | 5 | 1250 |
| [05-rad-hard-rampage](#05-rad-hard-rampage) | 5 | 425 |
| [06-dr-one](#06-dr-one) | 5 | 650 |
| [07-unscheduled-passes](#07-unscheduled-passes) | 5 | 650 |
| [08-silent-carrier](#08-silent-carrier) | 5 | 450 |
| [09-dish-wrangler](#09-dish-wrangler) | 5 | 450 |
| [11-the-pgm-rush](#11-the-pgm-rush) | 8 | 1800 |
| [12-spectral-forensics](#12-spectral-forensics) | 7 | 1537 |
| [13-night-shift](#13-night-shift) | 5 | 718 |
| **Total** | **68** | **9131** |

---

## Challenges

Points below are the final scoreboard values confirmed after the event. Individual write-ups and flags are provided per challenge.

### <a id="01-welcome"></a>[01-welcome](./01-welcome/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [100-well-hello](./01-welcome/100-well-hello/) | 1 | `GAIANSPACE{Welcome}` |
| 2 | [101-this-is-gaianspace](./01-welcome/101-this-is-gaianspace/) | 10 | `GAIANSPACE{8100,60000}` |
| 3 | [102-cs-for-gs](./01-welcome/102-cs-for-gs/) | 20 |`GAIANSPACE{AcidRain}` |
| 4 | [103-parked-birds](./01-welcome/103-parked-birds/) | 20 | `GAIANSPACE{IS-41,IS-44}` |

### <a id="02-echoes-of-espionage"></a>[02-echoes-of-espionage](./02-echoes-of-espionage/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [201-uplink-origins](./02-echoes-of-espionage/201-uplink-origins/) | 50 | `GAIANSPACE{26.46,-98.64,3296.64}` |
| 2 | [202-downlink-deception](./02-echoes-of-espionage/202-downlink-deception/) | 75 | `GAIANSPACE{VELA,2025-06-12T19:15:00Z}` |
| 3 | [203-signal-secrets](./02-echoes-of-espionage/203-signal-secrets/) | 100 | `GAIANSPACE{tw0_l4yer_d0wnlink}` |
| 4 | [204-payload-unleashed](./02-echoes-of-espionage/204-payload-unleashed/) | 100 | `GAIANSPACE{b4ckd00r_in_the_dec0der}` |
| 5 | [205-backdoor-from-space](./02-echoes-of-espionage/205-backdoor-from-space/) | 125 | `GAIANSPACE{c2_rc4_from_the_nonce}` |
| 6 | [206-gpredict-secret](./02-echoes-of-espionage/206-gpredict-secret/) | 50 | `GAIANSPACE{w4tcher_0f_the_sky}` |
| 7 | [207-lost-signal-mars](./02-echoes-of-espionage/207-lost-signal-mars/) | 75 | `GAIANSPACE{diff_enc0ded_and_buried}` |

### <a id="03-orbital-oops-at-mission-control"></a>[03-orbital-oops-at-mission-control](./03-orbital-oops-at-mission-control/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [301-email-entrapment](./03-orbital-oops-at-mission-control/301-email-entrapment/) | 50 | `GAIANSPACE{ph1sh_in_the_dump}` |
| 2 | [302-web-wormhole](./03-orbital-oops-at-mission-control/302-web-wormhole/) | 75 | `GAIANSPACE{dr1ve_by_st4ged}` |
| 3 | [303-gerber-grab-crack](./03-orbital-oops-at-mission-control/303-gerber-grab-crack/) | 100 | `GAIANSPACE{s1lk_scr33n_le4k}` |
| 4 | [304-pcb-puzzle-probe](./03-orbital-oops-at-mission-control/304-pcb-puzzle-probe/) | 100 | `GAIANSPACE{pcb_qu1z_compl3te}` |
| 5 | [305-satellite-sabotage-sim](./03-orbital-oops-at-mission-control/305-satellite-sabotage-sim/) | 125 | `GAIANSPACE{c4nsat_t3lemetry_pwn3d}` |
| 6 | [306-lora-whisper](./03-orbital-oops-at-mission-control/306-lora-whisper/) | 50 | `GAIANSPACE{l0ra_fr4gments_in_0rder}` |
| 7 | [307-descent-diary](./03-orbital-oops-at-mission-control/307-descent-diary/) | 75 | `GAIANSPACE{DRIFT_AND_FALL}` |

### <a id="04-ai-is-not-sci-fi"></a>[04-ai-is-not-sci-fi](./04-ai-is-not-sci-fi/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [401-ai-at-gaian](./04-ai-is-not-sci-fi/401-ai-at-gaian/) | 150 | `GAIANSPACE{z3roth_l4w_ab0ve_0rders}` |
| 2 | [402-the-cyberiad](./04-ai-is-not-sci-fi/402-the-cyberiad/) | 200 | `GAIANSPACE{n0thing_fr0m_st0ck}` |
| 3 | [403-altruizine](./04-ai-is-not-sci-fi/403-altruizine/) | 250 | `GAIANSPACE{sh4red_p41n_n0t_j0y}` |
| 4 | [404-the-last-kilogram](./04-ai-is-not-sci-fi/404-the-last-kilogram/) | 300 | `GAIANSPACE{3very_gr41n_c0unts}` |
| 5 | [405-happy-bday-d](./04-ai-is-not-sci-fi/405-happy-bday-d/) | 350 | `GAIANSPACE{h4ppy_bd4y_d4v1d_1t_g03s_h0m3}` |

### <a id="05-rad-hard-rampage"></a>[05-rad-hard-rampage](./05-rad-hard-rampage/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [501-cosmic-bit-blunder](./05-rad-hard-rampage/501-cosmic-bit-blunder/) | 50 | `GAIANSPACE{s1ngle_event_upset}` |
| 2 | [502-ionized-transistangle](./05-rad-hard-rampage/502-ionized-transistangle/) | 75 | `GAIANSPACE{t0tal_1onizing_d0se}` |
| 3 | [503-degradift](./05-rad-hard-rampage/503-degradift/) | 100 | `GAIANSPACE{displ4cement_drift}` |
| 4 | [504-lunar-latch-up](./05-rad-hard-rampage/504-lunar-latch-up/) | 125 | `GAIANSPACE{s1ngle_event_l4tchup}` |
| 5 | [505-thermal-duty](./05-rad-hard-rampage/505-thermal-duty/) | 75 | `GAIANSPACE{therm4l_duty_cycle}` |

### <a id="06-dr-one"></a>[06-dr-one](./06-dr-one/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [601-what-is-this-planet](./06-dr-one/601-what-is-this-planet/) | 50 | `GAIANSPACE{m4rs_r0torcraft_scout}` |
| 2 | [602-help-me-fly](./06-dr-one/602-help-me-fly/) | 75 | `GAIANSPACE{fl1ght_telemetry_str3am}` |
| 3 | [603-g-fold](./06-dr-one/603-g-fold/) | 100 | `GAIANSPACE{LZ_1370_-360}` |
| 4 | [604-ice-vault](./06-dr-one/604-ice-vault/) | 125 | `GAIANSPACE{UTOPIA_PLANITIA_46.7N_97.3E}` |
| 5 | [605-black-box](./06-dr-one/605-black-box/) | 300 | `GAIANSPACE{S1-T78758}` |

### <a id="07-unscheduled-passes"></a>[07-unscheduled-passes](./07-unscheduled-passes/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [701-one-light-day](./07-unscheduled-passes/701-one-light-day/) | 50 | `GAIANSPACE{FDS_3C0AB555}` |
| 2 | [702-concatenated](./07-unscheduled-passes/702-concatenated/) | 75 | `GAIANSPACE{s0ft_v1terbi_th3n_r33d_s0l0m0n}` |
| 3 | [703-lagrange-fix](./07-unscheduled-passes/703-lagrange-fix/) | 100 | `GAIANSPACE{CLK_+2213481}` |
| 4 | [704-dead-chip](./07-unscheduled-passes/704-dead-chip/) | 125 | `GAIANSPACE{r3l0c4ted_ar0und_a_d34d_ch1p}` |
| 5 | [705-last-readout](./07-unscheduled-passes/705-last-readout/) | 300 | `GAIANSPACE{405-43E-445-448-4BD}` |

### <a id="08-silent-carrier"></a>[08-silent-carrier](./08-silent-carrier/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [801-torn-frames](./08-silent-carrier/801-torn-frames/) | 50 | `GAIANSPACE{burst_r3align_sdt_r3ad}` |
| 2 | [802-sections-in-the-static](./08-silent-carrier/802-sections-in-the-static/) | 75 | `GAIANSPACE{mpe_dgram_r3assembly}` |
| 3 | [803-frames-inside-frames](./08-silent-carrier/803-frames-inside-frames/) | 100 | `GAIANSPACE{gse_fr4g_crc32_ok}` |
| 4 | [804-lost-sync](./08-silent-carrier/804-lost-sync/) | 100 | `GAIANSPACE{syncd_led_me_home}` |
| 5 | [805-the-last-carrier](./08-silent-carrier/805-the-last-carrier/) | 125 | `GAIANSPACE{qpsk_sof_lock_carrier}` |

### <a id="09-dish-wrangler"></a>[09-dish-wrangler](./09-dish-wrangler/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [901-twenty-two-kilohertz](./09-dish-wrangler/901-twenty-two-kilohertz/) | 50 | `GAIANSPACE{dis3qc_t0ne_b1ts}` |
| 2 | [902-where-was-it-pointing](./09-dish-wrangler/902-where-was-it-pointing/) | 75 | `GAIANSPACE{usals_arc_backtr4ced}` |
| 3 | [903-console-backdoor](./09-dish-wrangler/903-console-backdoor/) | 100 | `GAIANSPACE{ref_p4th_tr4versal}` |
| 4 | [904-gotox-maint](./09-dish-wrangler/904-gotox-maint/) | 100 | `GAIANSPACE{m41nt_m0de_unl0cked}` |
| 5 | [905-hand-on-the-wheel](./09-dish-wrangler/905-hand-on-the-wheel/) | 125 | `GAIANSPACE{f0rged_slew_t0_h0me}` |

### <a id="11-the-pgm-rush"></a>[11-the-pgm-rush](./11-the-pgm-rush/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [110-m-type](./11-the-pgm-rush/110-m-type/) | 100 | `GAIANSPACE{2041QM23_120}` |
| 2 | [111-short-arc](./11-the-pgm-rush/111-short-arc/) | 150 | `GAIANSPACE{RT39SBA}` |
| 3 | [112-two-clocks](./11-the-pgm-rush/112-two-clocks/) | 200 | `GAIANSPACE{0412377}` |
| 4 | [113-touchdown](./11-the-pgm-rush/113-touchdown/) | 250 | `GAIANSPACE{A-0242}` |
| 5 | [114-anchor-bite](./11-the-pgm-rush/114-anchor-bite/) | 250 | `GAIANSPACE{B-27}` |
| 6 | [115-locked-assayer](./11-the-pgm-rush/115-locked-assayer/) | 300 | `GAIANSPACE{XR9-6YYDU6}` |
| 7 | [116-sealed-canister](./11-the-pgm-rush/116-sealed-canister/) | 300 | `GAIANSPACE{6304}` |
| 8 | [117-the-dark-moonlet](./11-the-pgm-rush/117-the-dark-moonlet/) | 250 | `GAIANSPACE{aspartic_acid_L34}` |

### <a id="12-spectral-forensics"></a>[12-spectral-forensics](./12-spectral-forensics/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [121-channel-hop](./12-spectral-forensics/121-channel-hop/) | 100 | `GAIANSPACE{AL-STAMP-Q9VRR9}` |
| 2 | [122-true-color-is-a-lie](./12-spectral-forensics/122-true-color-is-a-lie/) | 125 | `GAIANSPACE{TRUE-NDVI-HR6TNM}` |
| 3 | [123-isodata-seven](./12-spectral-forensics/123-isodata-seven/) | 150 | `GAIANSPACE{7TH-CLASS-XHTXWX}` |
| 4 | [124-subsidy-claim](./12-spectral-forensics/124-subsidy-claim/) | 175 | `GAIANSPACE{CUVE-UKEJ-TRP6}` |
| 5 | [125-where-they-stood](./12-spectral-forensics/125-where-they-stood/) | 277 | `GAIANSPACE{MZH-3240}` |
| 6 | [126-borrowed-summer](./12-spectral-forensics/126-borrowed-summer/) | 316 | `GAIANSPACE{ZDJ7-UCZA-JADX-7JEY}` |
| 7 | [127-heads-down-97](./12-spectral-forensics/127-heads-down-97/) | 394 | `GAIANSPACE{SZMMPR-SZPTJU-SZXYMY_SZ4TE4}` |

### <a id="13-night-shift"></a>[13-night-shift](./13-night-shift/)

| # | Challenge | Points | Flags |
|---:|---|---:|---|
| 1 | [131-two-voices](./13-night-shift/131-two-voices/) | 100 | `GAIANSPACE{tw0_v01c3s_0B0EFE1A}` |
| 2 | [132-no-name-on-the-door](./13-night-shift/132-no-name-on-the-door/) | 125 | `GAIANSPACE{432_132}` |
| 3 | [133-hopscotch](./13-night-shift/133-hopscotch/) | 150| `GAIANSPACE{h0p_sc0tch_AF44A6}` |
| 4 | [134-repacked](./13-night-shift/134-repacked/) | 150 | `GAIANSPACE{r3p4ck3d_660413}` |
| 5 | [135-what-they-took](./13-night-shift/135-what-they-took/) | 193 | `GAIANSPACE{wh4t_th3y_t00k_064CCB}` |

