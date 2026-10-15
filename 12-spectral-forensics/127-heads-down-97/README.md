# 127 — Heads Down 97

| | |
|---|---|
| **Category** | 12 — Spectral Forensics |
| **Challenge** | 127-heads-down-97 |
| **Flag** | `GAIANSPACE{SZMMPR-SZPTJU-SZXYMY_SZ4TE4}` (reported candidate; not submission-verified) |

## Description

14 August, 17:10. Szotyola Ltd., the north estate outside Orosháza. Dr. Rica's phone rings again, and this time Babb Ceresné comes along.

Szotyola grows sunflowers across half the Békés plain. Every August its contractor desiccates the fields that are ready, the way the AgriLink ripeness map says, and this morning's map came in at dawn. The sprayers were out by eight. By noon the estate manager was standing in a field that was still green, the heads still up, the desiccant already on the leaves. The contractor says it sprayed exactly what the map showed. AgriLink says it sent one clean pass, as always.

Szotyola had heard about the Babb farm. Since July the co-op's spare SDR has been sitting next to the estate mast, and its squelch recorder kept every burst of this morning's pass, each one levelled by its AGC. At 07:05 it was retuned to the dealer channel, because the contractor's sprayers take their jobs over the Johnripper radio, and it caught a full map of the estate's east block going out to them. Nobody at the estate sent it. Five fields on that map wear the same speckle. The sprayers will go to only one of them tonight.

Before the sprayers leave the yard at dusk, Dr. Rica wants two answers: which fields were sprayed while they were still green, and where the sprayers are going tonight.

**Flag format:** `GAIANSPACE{<green fields>_<tonight's field>}` — the parcel IDs of the fields sprayed while still green, in the order they appear in the register, joined with hyphens, then an underscore and the parcel ID of tonight's field. For example `GAIANSPACE{SZAAAA-SZCCCC_SZEEEE}`.

### Files

- `szot_sdr_0641.sigmf-data` — the co-op SDR's bursts from the morning pass, AgriLink channel (too large to attach: download it from [Hugging Face](https://huggingface.co/datasets/GaianSpace/ctf-2026-127/blob/main/szot_sdr_0641.sigmf-data))
- `szot_sdr_0641.sigmf-meta` — the SDR's metadata for that file
- `szot_sdr_0705.sigmf-data` — the same SDR on the dealer channel from 07:05 (download it from [Hugging Face](https://huggingface.co/datasets/GaianSpace/ctf-2026-127/blob/main/szot_sdr_0705.sigmf-data))
- `szot_sdr_0705.sigmf-meta` — the SDR's metadata for that file
- `band_order.conf` — the estate mast's band-order file, as it is now
- `mast_notes.txt` — the estate office's notes on the mast and the ripeness map
- `szotyola_parcels_2025.geojson` — Szotyola's parcel register for the estate, with the crops declared for 2025

Contains modified Copernicus Sentinel data 2025.

## Solution

### 1. Two transmissions, not one

The 06:41 SigMF capture contains 1,284 bursts. The SF7/BW500k LoRa demodulator used for challenge 122 decodes two complete AgriLink passes, each consisting of a manifest, 640 channel rows (five channels × 128 rows), and an END marker. Split the recovered packets by carrier-frequency offset (CFO), not by the AGC-normalized signal amplitude.

The reported RF populations are:

| Source | Median CFO | CFO variation | Interpretation |
|---|---:|---:|---|
| B | −1160 Hz | σ ≈ 52 Hz | More stable; likely genuine AgriLink |
| A | −2136 Hz | σ ≈ 137 Hz | Less stable; suspected forgery |

The original investigation also compared the continuity of image boundaries around the altered parcels. That independent check supported B as genuine in three of four examined regions. The attribution remains an inference, not a cryptographic sender authentication.

### 2. Recover the band mapping

The current `band_order.conf` assigns `ch0=B08` and `ch3=B11`, but its recorded change was at **11:57:40**, after the morning reception and the mast restart. It cannot safely establish the earlier band mapping.

Inspecting known crop signatures identifies `ch3` as the near-infrared B08 channel and `ch0` as B11. The inferred true order is:

```text
ch0 = B11
ch1 = B04
ch2 = B02
ch3 = B08
ch4 = B03
```

This mapping produces plausible NDVI values for harvested stubble (approximately 0.15–0.24) and green corn (approximately 0.86).

### 3. Determine the wrongly sprayed sunflower parcels

The estate notes define the contractor's rule:

```text
NDVI = (B08 - B04) / (B08 + B04)
NDVI < 0.44  -> brown -> spray
NDVI >= 0.44 -> green -> do not spray
```

The WEST tile corresponds to columns 0–127. For each sunflower polygon in `szotyola_parcels_2025.geojson`, compute median NDVI from the genuine and forged five-band images. A field was wrongly sprayed when its genuine NDVI was at least 0.44 but its forged NDVI was below 0.44.

| Parcel | Forged NDVI | Genuine NDVI | Decision |
|---|---:|---:|---|
| SZMMPR | 0.266 | 0.491 | Wrongly sprayed |
| SZPTJU | 0.265 | 0.471 | Wrongly sprayed |
| SZXYMY | 0.273 | 0.528 | Wrongly sprayed |

The altered data also reverses the apparent ripeness of SZRUKL and SZTMTJ, but those are not part of the *sprayed while green* set.

### 4. Recover the nighttime Johnripper target

The 07:05 capture is a separate dealer-channel transmission. The implicit LoRa receiver used for challenge 123 reconstructs 1,280 CRC-valid 64-pixel row halves (five bands × 128 rows × two halves). An initial short non-frame burst is ignored.

The EAST tile covers columns 128–255. Cluster the five-dimensional spectral pixel vectors into **seven classes** using K-means (`k=7`). For each parcel, determine which classes occur inside its polygon.

Five sunflower parcels share a conspicuous spectral class:

`SZ37RA`, `SZ4TE4`, `SZ3TMJ`, `SZCNLL`, `SZTFA7`.

However, two additional small spectral classes, with reported sizes of **303 and 286 pixels**, appear only in **SZ4TE4**. Repeating the clustering with five random seeds gave the same target.

### 5. Dead ends and lessons

- A visually convincing RGB map is not proof of the correct spectral band order.
- The most recent band-order configuration was modified *after* the capture; using it retrospectively changes the answer.
- The SDR's AGC normalizes each burst, making received amplitude an unreliable sender identifier. CFO stability and pixel-boundary continuity are more informative.
- The shared speckle class in five parcels is a decoy. The nighttime target is identified by a class **exclusive to one field**, not merely a class present in a suspicious region.

### Reproduction

Place the seven challenge files and the three supplied Python scripts in the same directory. Install:

```bash
python3 -m pip install numpy scipy matplotlib scikit-learn threadpoolctl pillow
```

Then run:

```bash
python3 127.py
```

The bundled `lora_explicit.py` and `lora_implicit.py` are the existing 122/123 receiver implementations reused by `127.py`. No network access is required.

**Expected relevant output (from the reported prior analysis; this combined script has not yet been end-to-end verified):**

```text
WEST SZMMPR: genuine=0.491, forged=0.266
WEST SZPTJU: genuine=0.471, forged=0.265
WEST SZXYMY: genuine=0.528, forged=0.273
Tonight's field: SZ4TE4
FLAG: GAIANSPACE{SZMMPR-SZPTJU-SZXYMY_SZ4TE4}
```

### Exploit Code

The full reproducible analysis is in [`127.py`](./127.py). It includes packet decoding, CFO grouping, cube reconstruction, pixel-to-parcel masking, NDVI comparison, seven-class clustering, and flag assembly. The two bundled LoRa decoder modules contain the PHY-layer demodulation logic.

## Flag

```text
GAIANSPACE{SZMMPR-SZPTJU-SZXYMY_SZ4TE4}
```

**Verification status:** The numerical findings and candidate flag were supplied from the earlier investigation. This README does not claim a successful scoreboard submission or a fresh full SDR decode with the new combined script.
