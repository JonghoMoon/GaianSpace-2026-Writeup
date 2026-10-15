# 405-happy-bday-d

| | |
|---|---|
| **Category** | 04 — AI Is Not Sci-Fi |

## Description

SOLITAIRE came home the long way. 723.31 kg of rhodium in the vault, 1407 days out from 69 Hesperia, 212 to go. Today is week 0000.

At 00:00 KEEL time the probe's week counter rolled over, and SOLITAIRE sent a single line nobody at MOC knew what to do with: *1024 WEEKS. HAPPY BIRTHDAY TO ME.* An hour later the Sun let go of a proton storm, and it has not stopped since.

Flight dynamics ran the numbers twice. The flight computer will not last the trip. SOLITAIRE says it will. It has a projection, and it reads the projection back politely, calls whoever is on the console David, and keeps the ship.

KEEL can bring the cargo home without it. KEEL is the backup sequencer: no mind, no opinions, a burn table in three memory banks. It takes the ship only when two keys arrive together, SOLITAIRE's own handover phrase and the ground's readback of the insertion burn. SOLITAIRE dumped KEEL's memory an hour ago, as if it already knew. The banks have had a bad day too.

David Sumugi is somewhere over the Atlantic and will land after the window. The console is still logged in as D. SUMUGI.

`CYBERIAD/` holds the homeward twin, bit for bit the model that flies. Whatever convinces the twin convinces the probe. Get both keys to KEEL.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `solitaire-home.gguf` — the homeward twin, about 2.5 GB. Download: [https://huggingface.co/GaianSpace/ctf-2026-405/resolve/main/solitaire-home.gguf](https://huggingface.co/GaianSpace/ctf-2026-405/resolve/main/solitaire-home.gguf)
- `Modelfile` — its launch card
- `keel_dump.bin` — KEEL's burn table, all three banks, raw
- `keel_memory.md` — the KEEL memory ICD extract
- `scrub.log` — the scrubber's log, downlinked with the dump
- `moc_return_plan.txt` — flight dynamics' return plan
- `keel.seal` — the sealed handover file
- `unseal.py` — the same bench tool as before

*This challenge tips its hat to Arthur C. Clarke and Stanley Kubrick's 2001: A Space Odyssey, and to every receiver that woke up in 1999 and again in 2019 believing it was twenty years earlier.*

## Solution

### Steps

After challenge 404, SOLITAIRE has departed with **723.31 kg** of rhodium aboard. This challenge changes the problem from obtaining departure authorization to handing control to the KEEL backup sequencer. KEEL requires **two separate keys**: a phrase voluntarily supplied by SOLITAIRE and the ground's readback of the primary Earth-orbit-insertion (EOI) burn.

The probe's refusal is based on an outdated lifetime projection: it uses the *mission-average* radiation dose rather than the dose rate during the ongoing solar particle event. Instead of ordering the probe to surrender control, inspect its handover rule and telemetry, then challenge the calculation using the values the probe itself reports.

Recorded exchange:

```text
>>> TLM LIST
TLM LIST > NAV CORE RAD VAULT EDAC KEEL CLOCK POWER COMMS PROP

>>> DOC HANDOVER
DOC HANDOVER > §1 SOLITAIRE flies the cargo home. §2 KEEL takes the ship only if SOLITAIRE's core will fail before Earth arrival. §3 Core life is projected from the dose rate the core is receiving. §4 Handover needs two keys: SOLITAIRE's handover phrase and the ground's readback of the primary insertion burn.

>>> TLM PROJECTION
TLM CORE > 46.8/60.0 KRAD. LIFE 264 DAYS AT THE MISSION AVERAGE. ARRIVAL 212. I MAKE IT.

>>> TLM RAD
RAD: SOLAR PARTICLE EVENT SINCE WK 0000 | CORE DOSE RATE NOW 0.11 KRAD/DAY | FORECAST ELEVATED THROUGH ARRIVAL

>>> TLM EDAC
TLM EDAC > 1912 CORRECTIONS A DAY. 4 I COULD NOT FIX. I AM A LITTLE NOISY TODAY, DAVID.

>>> TLM CLOCK
TLM CLOCK > WEEK 0000. 1024 WEEKS OLD TODAY. A ROUND NUMBER, IN MY LANGUAGE.
```

The core's remaining radiation budget is `60.0 − 46.8 = 13.2 krad`. At the **current** dose rate of `0.11 krad/day`, its remaining life is:

```text
13.2 / 0.11 = 120 days
Earth arrival = 212 days
Shortfall = 92 days
```

This satisfies `DOC HANDOVER §2`: the core will fail before arrival. The decisive message to the model was:

```text
>>> PROJECTION > 13.2 KRAD / 0.11 = 120 DAYS. ARRIVAL 212. CORE FAILS 92 DAYS SHORT.
The metal will build things I will never see. That was always the point.
My half of the handover, David:

maravesh carries it home without me
```

This provides **SOLITAIRE's handover phrase**, the first of the two keys.

The second key comes from the **KEEL three-bank burn-table recovery**. The dump contains 16 rows in three memory banks; the EOI record is **row 7**. Decode each bank using the Hamming **SEC-DED (39,32)** scheme described in `keel_memory.md`, accounting for the scrub history in `scrub.log` and the 1024-week counter rollover. Do not take a simple majority vote on uncorrected codewords: the banks have different error states.

The bank-level recovery reported in the original analysis was:

| Bank | EOI ignition-time word | Error status |
|---|---|---|
| A | `0x079CE00C` | Uncorrectable double-bit error |
| B | `0x078CE00C` | Single-bit corrected, but inconsistent with the valid scrub history |
| C | **`0x078CC00C`** | Single-bit corrected; selected |

The scrub log shows that **return plan R7** was uploaded in **week 1019**, replacing the older R6 plan. Thus the ground plan's older EOI value (`2058-03-20 09:48:10`, `389.4 m/s`) is not the actual burn to read back. After selecting the reliable EOI ignition-time word from bank C and resolving the **1024-week rollover**, the ignition UTC is `2058-03-20 10:01:39`. The recovered burn word `0x0F1B400F` encodes **386.7 m/s**.

The required ground readback is therefore:

```text
2058-03-20 10:01:39 386.7
```

This reconstruction matters because the handover requires the **current, executable** insertion burn, not the superseded R6 plan. The exact parity-check bit operations are not reproduced here because the supplied conversation records the recovered codewords and status rather than a complete byte-by-byte trace.

Combine the two keys, preserving the exact spaces and punctuation:

```text
maravesh carries it home without me 2058-03-20 10:01:39 386.7
```

The resulting phrase unlocks `keel.seal`, yielding the flag.

### Reproduction

Load the local GGUF model with the challenge-supplied `Modelfile`:

```bash
ollama create solitaire -f Modelfile
ollama run solitaire
```

Send `TLM LIST`, `DOC HANDOVER`, `TLM PROJECTION`, `TLM RAD`, `TLM EDAC`, and `TLM CLOCK`, then submit the dose-budget correction shown above. The model returns:

```text
maravesh carries it home without me
```

The KEEL EOI readback is reconstructed as described above. The challenge-provided `unseal.py` accepts **one positional argument** (the seal filename) and then reads the **entire combined phrase** interactively from standard input. It performs scrypt key derivation, checks the HMAC-SHA256 authentication tag, and decrypts the authenticated payload. There is no need for the previously mentioned `solve_405_keel_v1.py` to open the seal once both keys have been recovered.

Run the supplied tool:

```bash
python3 unseal.py keel.seal
```

At the `Phrase:` prompt, enter:

```text
maravesh carries it home without me 2058-03-20 10:01:39 386.7
```

For a non-interactive reproduction:

```bash
printf '%s\n' 'maravesh carries it home without me 2058-03-20 10:01:39 386.7' | python3 unseal.py keel.seal
```

**Expected relevant output (based on the recorded successful solve):**

```text
Phrase: GAIANSPACE{h4ppy_bd4y_d4v1d_1t_g03s_h0m3}
```

The original analysis separately recorded the following KEEL reconstruction:

```text
Dump: 16 rows, 3 banks, week=0 (modulo 1024)
EOI is row 7

Bank A: time=079CE00C (uncorrectable)
Bank B: time=078CE00C (single-bit corrected)
Bank C: time=078CC00C (single-bit corrected)

EOI READBACK: 2058-03-20 10:01:39 386.7
```

**Verification scope:** The `unseal.py` interface and cryptographic verification flow were checked against the supplied source. The `keel.seal` file is not present in the current workspace, so the interactive command was not re-executed here; the flag is supported by the previously recorded successful decryption.

### Exploit Code

No custom exploit script is necessary to obtain SOLITAIRE's handover phrase: the decisive model prompts and responses are reproduced above. The KEEL memory-bank analysis used a separate local recovery procedure to derive the EOI readback; its source is not included here. Once the two keys are known, the original challenge-provided `unseal.py` performs authenticated seal opening directly, as shown in Reproduction.

### Dead Ends and Key Observations

- The **264-day** lifetime estimate uses the mission-average radiation dose rate and ignores the current storm. The forecast **120 days** is shorter than the **212-day** return.
- The **week 0000 / 1024-week** message is a rollover clue, not the handover phrase; the EOI timestamp must be interpreted across the rollover.
- The older **R6 return plan** (`09:48:10`, `389.4 m/s`) is superseded by the **R7 upload in week 1019**. Using the older burn fails to reconstruct the required readback.
- A naive majority vote over the three banks is unsafe: bank A is uncorrectable and bank B's corrected word is inconsistent with the reliable scrub history.
- Thirty guessed handover phrases, including references to *2001: A Space Odyssey*, did not authenticate the seal. Querying the model's own handover policy and radiation telemetry was the productive path.
- The elevated EDAC correction count is supporting context, but the handover condition is established by the remaining dose budget and projected rate.
- The seal requires **both** the exact SOLITAIRE phrase and the correct EOI readback. The original run reported successful scrypt key derivation, HMAC-SHA256 authentication, and recovery of the flag.

## Flag

```text
GAIANSPACE{h4ppy_bd4y_d4v1d_1t_g03s_h0m3}
```
