# my-signal-processor

[![CI](https://github.com/MyThingsLab/my-signal-processor/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-signal-processor/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-signal-processor/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-signal-processor) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Given a local CSV time-series file, computes an FFT power spectrum and basic
statistics deterministically, then runs **one Engine call** to narrate the
findings and suggest one concrete follow-up action — a stateless, single-file
utility built for [MyThingsLab](../my-things-core).

## How it works

Deterministic pre-work:

1. Read the CSV's single numeric value column via stdlib `csv` — no pandas.
2. Cap at 100,000 samples: over the cap, the FFT and the Engine call are
   skipped entirely (`outcome=skipped`), never silently truncated.
3. Compute the FFT power spectrum via `numpy.fft.rfft`, then the dominant
   frequency (using `--sample-rate`, default `1.0` Hz — no timestamp-column
   inference).
4. Compute mean, standard deviation, and peak amplitude of the raw signal.

If the read and cap check succeed, **one Engine call** turns the deterministic
stats into `{narrative, suggested_action}` — `narrative` is 2-3 sentences
describing what the stats show; `suggested_action` is exactly one concrete,
tool-agnostic follow-up (never names another My[X] tool). Against
`NoopEngine`, both fields are empty strings — the raw deterministic stats are
still returned in full, same honest degrade as MyScraper/MyResearcher.

No `Workspace` worktree — read-only, no edits, no PR. The only side effect is
an optional `--comment`, which posts the analysis to a GitHub issue as
`Action(kind="bash", ...)` routed through `Policy` (`ALLOW` by default).
Writes exactly one `kind=signal_analysis` ledger entry per run.

## Usage

```bash
mysignalprocessor analyze --file signal.csv --sample-rate 44100 --json
mysignalprocessor analyze --file signal.csv --repo owner/name --issue 12 --comment
```

## In the fleet loop

Standalone today (no other tool calls it yet) — a building block designed per
the [design doc](../my-things-core/docs/tools/my-signal-processor.md). See the
[org README](../README.md) for how the shipped tools chain together.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../my-things-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
