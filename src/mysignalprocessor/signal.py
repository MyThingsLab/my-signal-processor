from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MAX_SAMPLES = 100_000


@dataclass(frozen=True)
class ReadResult:
    ok: bool
    # set when ok is False: "sample_cap_exceeded" | "empty" | "invalid_value"
    reason: str = ""
    samples: tuple[float, ...] = ()


def read_csv_column(path: Path) -> ReadResult:
    values: list[float] = []
    with path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if not row:
                continue
            cell = row[0].strip()
            if not cell:
                continue
            try:
                values.append(float(cell))
            except ValueError:
                return ReadResult(ok=False, reason="invalid_value")
            if len(values) > MAX_SAMPLES:
                return ReadResult(ok=False, reason="sample_cap_exceeded")
    if not values:
        return ReadResult(ok=False, reason="empty")
    return ReadResult(ok=True, samples=tuple(values))


@dataclass(frozen=True)
class Stats:
    n_samples: int
    sample_rate: float
    dominant_freq_hz: float
    mean: float
    std: float
    peak: float


def analyze(samples: tuple[float, ...], sample_rate: float) -> Stats:
    array = np.asarray(samples, dtype=np.float64)
    spectrum = np.fft.rfft(array)
    freqs = np.fft.rfftfreq(array.size, d=1.0 / sample_rate)
    magnitudes = np.abs(spectrum)
    # Bin 0 is the DC component -- excluded so a nonzero-mean signal doesn't
    # always "win" the dominant-frequency search trivially.
    if magnitudes.size > 1:
        dominant_bin = int(np.argmax(magnitudes[1:])) + 1
    else:
        dominant_bin = 0
    return Stats(
        n_samples=array.size,
        sample_rate=sample_rate,
        dominant_freq_hz=float(freqs[dominant_bin]),
        mean=float(np.mean(array)),
        std=float(np.std(array)),
        peak=float(np.max(np.abs(array))),
    )
