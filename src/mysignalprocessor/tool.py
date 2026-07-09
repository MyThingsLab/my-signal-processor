from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mythings.engine import Engine, EngineRequest, NoopEngine
from mythings.github import Runner, _gh
from mythings.isolation import in_github_actions
from mythings.ledger import Ledger
from mythings.policy import ALLOW, Action, Decision, Policy, PolicyResult

from mysignalprocessor.signal import Stats, analyze, read_csv_column

TOOL = "mysignalprocessor"
LEDGER_KIND = "signal_analysis"
BACKLOG_LABEL = "my-signal-processor"

_ENGINE_SYSTEM = (
    "You narrate deterministic FFT/statistics results for a numeric signal. "
    'Reply with only a JSON object: {"narrative": str, "suggested_action": str}. '
    "narrative is 2-3 sentences describing what the stats show. suggested_action "
    "is exactly one concrete follow-up action, phrased tool-agnostically -- "
    "never name a specific software tool by name."
)


class _AllowPolicy:
    def evaluate(self, action: Action) -> PolicyResult:
        return ALLOW


@dataclass(frozen=True)
class Result:
    outcome: str  # success | skipped
    file: str
    n_samples: int = 0
    sample_rate: float = 0.0
    dominant_freq_hz: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    peak: float = 0.0
    narrative: str = ""
    suggested_action: str = ""
    detail: str = ""
    comment_url: str | None = None


class SignalProcessor:
    def __init__(
        self,
        *,
        ledger: Ledger,
        repo: str | None = None,
        runner: Runner = _gh,
        engine: Engine | None = None,
        policy: Policy | None = None,
    ) -> None:
        self.ledger = ledger
        self.repo = repo
        self.runner = runner
        self.engine: Engine = engine or NoopEngine()
        self.policy: Policy = policy or _AllowPolicy()

    def analyze(
        self,
        file: str,
        *,
        sample_rate: float = 1.0,
        issue: int | None = None,
        comment: bool = False,
    ) -> Result:
        read = read_csv_column(Path(file))
        if not read.ok:
            result = Result(
                outcome="skipped",
                file=file,
                detail=f"skipped: {read.reason}",
            )
            self._record(result)
            return result

        stats = analyze(read.samples, sample_rate)
        reply = self._narrate(stats, file)
        comment_url = self._comment(issue, file, stats, reply) if comment else None

        result = Result(
            outcome="success",
            file=file,
            n_samples=stats.n_samples,
            sample_rate=stats.sample_rate,
            dominant_freq_hz=stats.dominant_freq_hz,
            mean=stats.mean,
            std=stats.std,
            peak=stats.peak,
            narrative=reply["narrative"],
            suggested_action=reply["suggested_action"],
            detail=f"analyzed {file}, dominant freq {stats.dominant_freq_hz}Hz",
            comment_url=comment_url,
        )
        self._record(result)
        return result

    def _narrate(self, stats: Stats, file: str) -> dict[str, str]:
        context = {
            "file": file,
            "n_samples": stats.n_samples,
            "sample_rate": stats.sample_rate,
            "dominant_freq_hz": stats.dominant_freq_hz,
            "mean": stats.mean,
            "std": stats.std,
            "peak": stats.peak,
        }
        reply = self.engine.run(
            EngineRequest(
                prompt=json.dumps(context),
                system=_ENGINE_SYSTEM,
                context=context,
            )
        )
        parsed = _parse_reply(reply.text)
        if parsed is not None:
            return parsed
        return {"narrative": "", "suggested_action": ""}

    def _comment(
        self, issue: int | None, file: str, stats: Stats, reply: dict[str, str]
    ) -> str | None:
        if self.repo is None or issue is None:
            return None
        body = (
            f"Analyzed `{file}`:\n\n```json\n"
            + json.dumps({**stats.__dict__, **reply}, indent=2)
            + "\n```"
        )
        argv = ["issue", "comment", str(issue), "--repo", self.repo, "--body", body]
        action = Action(kind="bash", payload={"command": "gh " + " ".join(argv[:3])})
        decision = self.policy.evaluate(action).under(unattended=in_github_actions())
        if decision is not Decision.ALLOW:
            return None
        return self.runner(argv).strip() or None

    def _record(self, result: Result) -> None:
        self.ledger.record(
            tool=TOOL,
            kind=LEDGER_KIND,
            outcome=result.outcome,
            detail=result.detail,
            file=result.file,
            n_samples=result.n_samples,
            sample_rate=result.sample_rate,
            dominant_freq_hz=result.dominant_freq_hz,
            comment_url=result.comment_url,
        )


def _parse_reply(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    narrative = obj.get("narrative")
    narrative = narrative if isinstance(narrative, str) else ""
    suggested_action = obj.get("suggested_action")
    suggested_action = suggested_action if isinstance(suggested_action, str) else ""
    return {"narrative": narrative, "suggested_action": suggested_action}
