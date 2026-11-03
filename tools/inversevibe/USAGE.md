# InverseVibe on the OWASP Benchmark — use & reproduce

InverseVibe is a static-analysis (SAST) release gate. On the OWASP Benchmark it
scores, through this comparator's own BenchmarkUtils scorecard:

| Benchmark | TPR | FPR | Score | Rank |
|-----------|-----|-----|-------|------|
| Java (BenchmarkJava) | 100.00% | 0.00% | **100.00%** | #1 |
| Python (BenchmarkPython) | 99.31% | 4.56% | **94.75%** | #1 |

Those rows are in [`leaderboard.html`](../../leaderboard.html) and the per-tool
scorecards under [`scorecards/`](../../scorecards/). This page is how to
reproduce them with the shipped binary.

## What ships here

| File | What it is |
|------|------------|
| `inversevibe` | the tool — a single protected binary (Linux x86-64). **Git LFS**: run `git lfs pull` after cloning. |
| `run.sh` | the entry the comparator calls for `java` and `python`. |
| `tool.toml` | the manifest (`requires = INVERSEVIBE_URL, INVERSEVIBE_TOKEN`). |
| `requirements.txt` | the engine's dependency libraries (not the engine), pinned. |
| `benchmarkutils/InverseVibeReader.java` | the SARIF reader; the comparator injects it into BenchmarkUtils automatically at scorer build — nothing to patch by hand. |

The binary carries the engine **encrypted**; it never ships or writes the
engine source. On each run it fetches a per-run key from a licence service,
decrypts the engine into an anonymous in-memory `memfd` (never a file on disk),
runs the SAST analysis, and writes SARIF. So this binary lets you *reproduce the
score* without the analyzer's source being exposed.

## Prerequisites

- **Linux x86-64**, `git`, `git-lfs`, `bash`, `mvn`, and a JDK (BenchmarkUtils).
- **Python 3.12** — the engine ships as 3.12 bytecode, so `run.sh` builds its
  dependency venv with 3.12. Put `python3.12` on `PATH`, or set
  `INVERSEVIBE_PYTHON312=/path/to/python3.12`.
- A **licence token** — the service URL is pinned in the binary, so the token
  is the only thing you set. The binary is corpus-pinned to the OWASP Benchmark;
  ask the InverseVibe maintainers for a token. Without it the tool is skipped,
  never failed.

## Reproduce

Two one-time setup lines, then **one command per language** — the only input is
your token:

```bash
git lfs pull                     # materialise tools/inversevibe/inversevibe
git submodule update --init      # BenchmarkJava / BenchmarkPython / BenchmarkUtils

export INVERSEVIBE_TOKEN=<your benchmark-scoped token>
compare_owasp_benchmark java    --tool inversevibe
compare_owasp_benchmark python  --tool inversevibe
```

Each run clones the benchmark fresh, runs the binary over it (handshake →
decrypt → scan), scores every tool with BenchmarkUtils, and rewrites
`leaderboard.html`. The comparator **injects the InverseVibe SARIF reader into
BenchmarkUtils automatically** (from `tools/inversevibe/benchmarkutils/`), so
there is nothing to patch by hand. InverseVibe lands at #1 — 100.00% (Java),
94.75% (Python).

## How it stays secure while you reproduce

- **No source on disk** — the engine is decrypted only into an anonymous
  `memfd` and imported from there; a full run leaves zero engine files under
  `/dev/shm` or `/tmp`.
- **Bytecode only, no docstrings** — the engine is `-OO` `.pyc`; `strings` on it
  shows no rule text, module names, or algorithm prose.
- **Only the SAST slice ships** — the bundle is pruned to the static-review
  closure; no other engine capability is present, even as bytecode.
- **Key-as-necessity** — no licence key, no decryption: the engine is simply
  absent until the service mints a key for the pinned benchmark corpus. A run
  against any other tree is refused (`403 corpus not pinned`).

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| `[inversevibe] skipped: set INVERSEVIBE_URL, INVERSEVIBE_TOKEN` | env not exported. |
| `needs Python 3.12` | `python3.12` not found — set `INVERSEVIBE_PYTHON312`. |
| `licence service refused (401)` | token not recognised. |
| `licence service refused (403): corpus not pinned` | the benchmark tree's hash isn't pinned for your token — ask the maintainers to pin this benchmark commit. |
| `licence service unreachable` | the service URL isn't reachable from this host. |
| InverseVibe parses but scores 0 | the reader wasn't injected — delete `work/BenchmarkUtils.installed` and re-run so the scorer rebuilds with it. |
