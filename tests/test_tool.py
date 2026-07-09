from __future__ import annotations

import json
import math
from pathlib import Path

from mythings.engine import EngineRequest, EngineResult, NoopEngine
from mythings.ledger import Ledger
from mythings.policy import Action, Decision, PolicyResult

from conftest import FakeRunner
from mysignalprocessor.tool import SignalProcessor


class ScriptedEngine:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.requests: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.requests.append(request)
        return EngineResult(text=self._reply)


class DenyPolicy:
    def evaluate(self, action: Action) -> PolicyResult:
        return PolicyResult(Decision.DENY, reason="no", rule="test")


def _write_sine_csv(path: Path, *, freq_hz: float, sample_rate: float, n: int) -> None:
    lines = [str(math.sin(2 * math.pi * freq_hz * i / sample_rate)) for i in range(n)]
    path.write_text("\n".join(lines))


def test_analyze_uses_engine_reply(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=50.0, sample_rate=1000.0, n=2000)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine(
        json.dumps(
            {
                "narrative": "The signal oscillates around 50Hz.",
                "suggested_action": "Inspect the source for a 50Hz interference component.",
            }
        )
    )
    processor = SignalProcessor(ledger=ledger, engine=engine)
    result = processor.analyze(str(csv_path), sample_rate=1000.0)

    assert result.outcome == "success"
    assert result.dominant_freq_hz == 50.0 or abs(result.dominant_freq_hz - 50.0) < 1.0
    assert result.narrative == "The signal oscillates around 50Hz."
    assert result.suggested_action == "Inspect the source for a 50Hz interference component."
    entries = list(ledger)
    assert entries[-1].kind == "signal_analysis"
    assert entries[-1].data["file"] == str(csv_path)


def test_analyze_degrades_to_empty_strings_against_noop_engine(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=10.0, sample_rate=100.0, n=500)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    processor = SignalProcessor(ledger=ledger, engine=NoopEngine())
    result = processor.analyze(str(csv_path), sample_rate=100.0)

    assert result.outcome == "success"
    assert result.narrative == ""
    assert result.suggested_action == ""
    assert result.n_samples == 500
    assert result.mean is not None
    assert result.std is not None
    assert result.peak > 0


def test_analyze_skips_engine_call_when_sample_cap_exceeded(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=1000.0, n=100_001)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine("should never be called")
    processor = SignalProcessor(ledger=ledger, engine=engine)
    result = processor.analyze(str(csv_path), sample_rate=1000.0)

    assert result.outcome == "skipped"
    assert "sample_cap_exceeded" in result.detail
    assert engine.requests == []
    entries = list(ledger)
    assert entries[-1].outcome == "skipped"


def test_analyze_skips_engine_call_on_empty_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    csv_path.write_text("")
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine("should never be called")
    processor = SignalProcessor(ledger=ledger, engine=engine)
    result = processor.analyze(str(csv_path))

    assert result.outcome == "skipped"
    assert "empty" in result.detail
    assert engine.requests == []


def test_comment_posts_analysis_when_requested(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=100.0, n=200)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    fake = FakeRunner()
    processor = SignalProcessor(ledger=ledger, repo="owner/name", runner=fake, engine=NoopEngine())
    result = processor.analyze(str(csv_path), sample_rate=100.0, issue=5, comment=True)

    assert result.comment_url is not None
    assert fake.calls[0][:2] == ["issue", "comment"]


def test_comment_skipped_without_issue(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=100.0, n=200)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    processor = SignalProcessor(ledger=ledger, repo="owner/name", engine=NoopEngine())
    result = processor.analyze(str(csv_path), sample_rate=100.0, comment=True)
    assert result.comment_url is None


def test_comment_skipped_without_repo(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=100.0, n=200)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    processor = SignalProcessor(ledger=ledger, engine=NoopEngine())
    result = processor.analyze(str(csv_path), sample_rate=100.0, issue=5, comment=True)
    assert result.comment_url is None


def test_comment_denied_by_policy_is_not_posted(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=100.0, n=200)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    fake = FakeRunner()
    processor = SignalProcessor(
        ledger=ledger, repo="owner/name", runner=fake, engine=NoopEngine(), policy=DenyPolicy()
    )
    result = processor.analyze(str(csv_path), sample_rate=100.0, issue=5, comment=True)
    assert result.comment_url is None
    assert fake.calls == []


def test_json_but_non_dict_engine_reply_degrades_to_empty_strings(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=100.0, n=200)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine(json.dumps(["not", "a", "dict"]))
    processor = SignalProcessor(ledger=ledger, engine=engine)
    result = processor.analyze(str(csv_path), sample_rate=100.0)
    assert result.narrative == ""
    assert result.suggested_action == ""


def test_non_json_engine_reply_degrades_to_empty_strings(tmp_path: Path) -> None:
    csv_path = tmp_path / "signal.csv"
    _write_sine_csv(csv_path, freq_hz=5.0, sample_rate=100.0, n=200)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    processor = SignalProcessor(ledger=ledger, engine=ScriptedEngine("not json"))
    result = processor.analyze(str(csv_path), sample_rate=100.0)
    assert result.narrative == ""
    assert result.suggested_action == ""
