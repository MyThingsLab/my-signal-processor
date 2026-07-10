from __future__ import annotations

import math
from pathlib import Path

import pytest

from mysignalprocessor.signal import MAX_SAMPLES, analyze, read_csv_column


def _write_sine_csv(path: Path, *, freq_hz: float, sample_rate: float, n: int) -> None:
    lines = [str(math.sin(2 * math.pi * freq_hz * i / sample_rate)) for i in range(n)]
    path.write_text("\n".join(lines))


def test_read_csv_column_parses_single_numeric_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    csv_path.write_text("1.0\n2.5\n-3.25\n")
    result = read_csv_column(csv_path)
    assert result.ok
    assert result.samples == (1.0, 2.5, -3.25)


def test_read_csv_column_rejects_non_numeric_value(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    csv_path.write_text("1.0\nnot-a-number\n3.0\n")
    result = read_csv_column(csv_path)
    assert not result.ok
    assert result.reason == "invalid_value"


def test_read_csv_column_rejects_empty_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    csv_path.write_text("")
    result = read_csv_column(csv_path)
    assert not result.ok
    assert result.reason == "empty"


def test_read_csv_column_rejects_over_sample_cap(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=1000.0, n=MAX_SAMPLES + 1)
    result = read_csv_column(csv_path)
    assert not result.ok
    assert result.reason == "sample_cap_exceeded"


def test_analyze_detects_known_dominant_frequency(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    sample_rate = 1000.0
    freq_hz = 50.0
    _write_sine_csv(csv_path, freq_hz=freq_hz, sample_rate=sample_rate, n=2000)

    result = read_csv_column(csv_path)
    assert result.ok
    stats = analyze(result.samples, sample_rate)

    assert stats.dominant_freq_hz == pytest.approx(freq_hz, abs=1.0)
    assert stats.n_samples == 2000
    assert stats.peak == pytest.approx(1.0, abs=0.01)


def test_analyze_computes_mean_std_peak_for_constant_signal() -> None:
    samples = tuple([3.0] * 100)
    stats = analyze(samples, sample_rate=1.0)
    assert stats.mean == pytest.approx(3.0)
    assert stats.std == pytest.approx(0.0)
    assert stats.peak == pytest.approx(3.0)
