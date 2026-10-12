#!/usr/bin/env python3
"""Recover HALCYON-7's QPSK last carrier from raw CS16 IQ."""

import re
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

SAMPLE_RATE = 2_000_000.0
SYMBOL_RATE = 250_000.0
SPS = 8
RRC_ALPHA = 0.35
SYNC = 0x1ACFFC1D
CONSTELLATION = np.array([1+1j, -1+1j, -1-1j, 1-1j]) / np.sqrt(2)
DIBITS = ("00", "01", "11", "10")


def rrc_taps(alpha: float, sps: int, span: int) -> np.ndarray:
    times = np.arange(-span * sps // 2, span * sps // 2 + 1) / float(sps)
    taps = np.zeros(times.size, dtype=np.float64)
    for index, time in enumerate(times):
        if abs(time) < 1e-12:
            taps[index] = 1.0 + alpha * (4.0 / np.pi - 1.0)
        elif abs(abs(time) - 1.0 / (4.0 * alpha)) < 1e-12:
            taps[index] = alpha / np.sqrt(2.0) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * alpha))
                + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * alpha))
            )
        else:
            taps[index] = (
                np.sin(np.pi * time * (1.0 - alpha))
                + 4.0 * alpha * time * np.cos(np.pi * time * (1.0 + alpha))
            ) / (np.pi * time * (1.0 - (4.0 * alpha * time) ** 2))
    return taps / np.sqrt(np.sum(taps * taps))


def main() -> None:
    raw = np.fromfile(Path(__file__).with_name("halcyon_iq.cs16"), dtype="<i2")
    if raw.size % 2:
        raise ValueError("Uneven I/Q sample count")
    iq = raw.reshape(-1, 2)
    signal = (iq[:, 0].astype(np.float64) + 1j * iq[:, 1].astype(np.float64)) / 32768.0

    # Estimate the dominant fourth-power tone (QPSK removes data phase under x^4).
    nfft = 131072
    fft = np.fft.fft(signal**4, n=nfft)
    frequencies = np.fft.fftfreq(nfft, d=1.0 / SAMPLE_RATE)
    coarse_cfo = float(frequencies[np.argmax(np.abs(fft))] / 4.0)
    print(f"Estimated CFO: {coarse_cfo:.2f} Hz")

    sample_index = np.arange(signal.size, dtype=np.float64)
    corrected = signal * np.exp(-2j * np.pi * coarse_cfo * sample_index / SAMPLE_RATE)
    filtered = fftconvolve(corrected, rrc_taps(RRC_ALPHA, SPS, 10), mode="same")

    preamble = f"{SYNC:032b}" * 2
    ideal_preamble = np.array([
        CONSTELLATION[DIBITS.index(preamble[index:index + 2])]
        for index in range(0, len(preamble), 2)
    ])

    best = None
    for offset in range(SPS):
        symbols = filtered[offset::SPS]
        for start in range(12, min(50, symbols.size - len(ideal_preamble))):
            ratio = symbols[start:start + 32] / ideal_preamble
            residual_hz = (np.angle(np.sum(ratio[1:] * np.conj(ratio[:-1])))
                           * SYMBOL_RATE / (2.0 * np.pi))
            relative_index = np.arange(32, dtype=np.float64)
            derotated = ratio * np.exp(-2j * np.pi * residual_hz * relative_index / SYMBOL_RATE)
            quality = float(abs(np.mean(derotated)) / np.mean(abs(derotated)))
            if best is None or quality > best[0]:
                phase = float(np.angle(np.mean(derotated)))
                best = (quality, offset, start, residual_hz, phase)

    if best is None:
        raise RuntimeError("No QPSK synchronization candidate")

    quality, offset, start, residual_hz, phase = best
    symbols = filtered[offset::SPS]
    symbol_index = np.arange(symbols.size, dtype=np.float64) - float(start)
    symbols *= np.exp(-1j * (phase + 2.0 * np.pi * residual_hz * symbol_index / SYMBOL_RATE))
    point_indices = np.argmin(np.abs(symbols[:, None] - CONSTELLATION[None, :]), axis=1)
    bits = "".join(DIBITS[int(index)] for index in point_indices)

    found = bits[2 * start:2 * start + 64]
    if found != preamble:
        raise RuntimeError(f"Invalid preamble: {found}")
    message_bits = bits[2 * start + 64:]
    message_bits = message_bits[:len(message_bits) // 8 * 8]
    message = bytes(int(message_bits[index:index+8], 2)
                    for index in range(0, len(message_bits), 8))
    matched = re.search(rb"GAIANSPACE\{[^}]+\}", message)
    if matched is None:
        raise RuntimeError(f"Flag not found. Payload: {message!r}")
    print(f"Preamble alignment: sample offset={offset}, starting symbol={start}")
    print(f"Residual CFO: {residual_hz:.2f} Hz; sync quality={quality:.5f}")
    print(f"Recovered payload: {message!r}")
    print(f"FLAG: {matched.group().decode('ascii')}")


if __name__ == "__main__":
    main()

