# my-signal-processor — agent instructions

You are developing **my-signal-processor**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** given a local CSV time-series file, compute an FFT power
  spectrum and basic statistics deterministically, then narrate the findings
  (`mysignalprocessor analyze`). One CSV in, one narrated record out — no
  attachments, no URLs, no timestamp-column inference.
- **The single Engine call:** "given these deterministic FFT/statistics
  results, narrate the findings and suggest one concrete follow-up action" —
  replies with `{narrative, suggested_action}`. `narrative` is 2-3 sentences;
  `suggested_action` is exactly one tool-agnostic follow-up (never names
  another My[X] tool). Against `NoopEngine`: no narration — both fields are
  empty strings, the raw deterministic stats are still returned in full.
- **Invariants / rules:**
  - Deterministic pre-work reads a single numeric CSV column via stdlib
    `csv` — no pandas. FFT via `numpy.fft.rfft` — the fleet's second
    precedent (after my-raytracer) for a compute-library dependency, not an
    API SDK.
  - Cap at 100,000 samples: over the cap, the FFT and the Engine call are
    skipped (`outcome=skipped`) — never silently truncated.
  - No network in the deterministic pre-work — the CSV is read from a local
    path only.
  - **No `Workspace`, no PR.** Read-only utility: output to stdout (`--json`)
    and, if `--issue`/`--repo`/`--comment` are given, an optional issue
    comment via `Action(kind="bash", ...)` routed through `Policy.evaluate()`.
    Never commits to a repo.
  - Stateless: each run is independent, writes exactly one
    `kind=signal_analysis` ledger entry per run.
- **Backlog label:** `my-signal-processor`.
