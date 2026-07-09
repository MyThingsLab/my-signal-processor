from __future__ import annotations

import json
import math
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, NoopEngine

from mysignalprocessor import cli
from mysignalprocessor.tool import Result


def _write_sine_csv(path: Path, *, freq_hz: float, sample_rate: float, n: int) -> None:
    lines = [str(math.sin(2 * math.pi * freq_hz * i / sample_rate)) for i in range(n)]
    path.write_text("\n".join(lines))


def test_build_engine_noop_by_default() -> None:
    assert isinstance(cli.build_engine("noop"), NoopEngine)


def test_build_engine_claude_cli() -> None:
    assert isinstance(cli.build_engine("claude-cli"), ClaudeCLIEngine)


def test_analyze_prints_json(monkeypatch, tmp_path: Path, capsys) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=100.0, n=200)
    result = Result(
        outcome="success",
        file=str(csv_path),
        n_samples=200,
        sample_rate=100.0,
        dominant_freq_hz=5.0,
        mean=0.0,
        std=0.7,
        peak=1.0,
        narrative="narrated",
        suggested_action="do something",
        detail=f"analyzed {csv_path}, dominant freq 5.0Hz",
    )

    class _StubSignalProcessor:
        def __init__(self, **kwargs: object) -> None:
            pass

        def analyze(self, file: str, *, sample_rate=1.0, issue=None, comment=False) -> Result:
            return result

    monkeypatch.setattr(cli, "SignalProcessor", _StubSignalProcessor)
    code = cli.main(
        [
            "analyze",
            "--file",
            str(csv_path),
            "--ledger",
            str(tmp_path / "ledger.jsonl"),
            "--json",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dominant_freq_hz"] == 5.0
    assert out["narrative"] == "narrated"


def test_analyze_prints_narrative_without_json_flag(monkeypatch, tmp_path: Path, capsys) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=100.0, n=200)
    result = Result(
        outcome="success",
        file=str(csv_path),
        n_samples=200,
        sample_rate=100.0,
        narrative="the narrated text",
        detail="d",
    )

    class _StubSignalProcessor:
        def __init__(self, **kwargs: object) -> None:
            pass

        def analyze(self, file: str, *, sample_rate=1.0, issue=None, comment=False) -> Result:
            return result

    monkeypatch.setattr(cli, "SignalProcessor", _StubSignalProcessor)
    cli.main(
        [
            "analyze",
            "--file",
            str(csv_path),
            "--ledger",
            str(tmp_path / "ledger.jsonl"),
        ]
    )
    assert capsys.readouterr().out.strip() == "the narrated text"


def test_analyze_prints_detail_when_narrative_empty(monkeypatch, tmp_path: Path, capsys) -> None:
    csv_path = tmp_path / "signal.csv"
    result = Result(
        outcome="skipped",
        file=str(csv_path),
        detail="skipped: empty",
    )

    class _StubSignalProcessor:
        def __init__(self, **kwargs: object) -> None:
            pass

        def analyze(self, file: str, *, sample_rate=1.0, issue=None, comment=False) -> Result:
            return result

    monkeypatch.setattr(cli, "SignalProcessor", _StubSignalProcessor)
    cli.main(
        [
            "analyze",
            "--file",
            str(csv_path),
            "--ledger",
            str(tmp_path / "ledger.jsonl"),
        ]
    )
    assert capsys.readouterr().out.strip() == "skipped: empty"
