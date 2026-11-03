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
| `benchmarkutils/InverseVibeReader.java` | the SARIF reader BenchmarkUtils needs to score InverseVibe (see step 2). |

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
- A **licence token** and the **service URL** (the binary is corpus-pinned to
  the OWASP Benchmark; ask the InverseVibe maintainers for a token). Without
  them the tool is skipped, never failed.

## Reproduce

1. **Get the binary.** After cloning the comparator with submodules:
   ```bash
   git lfs pull                 # materialise tools/inversevibe/inversevibe
   git submodule update --init  # BenchmarkJava / BenchmarkPython / BenchmarkUtils
   ```

2. **Add the SARIF reader to BenchmarkUtils.** Upstream BenchmarkUtils has no
   InverseVibe reader, so copy ours in and register it (one import + one line):
   ```bash
   cp tools/inversevibe/benchmarkutils/InverseVibeReader.java \
      BenchmarkUtils/plugin/src/main/java/org/owasp/benchmarkutils/score/parsers/sarif/
   ```
   then in `BenchmarkUtils/.../score/parsers/Reader.java`, beside the other
   `sarif.*Reader` imports add
   `import org.owasp.benchmarkutils.score.parsers.sarif.InverseVibeReader;`
   and in the reader list add `new InverseVibeReader(),`. (The comparator builds
   BenchmarkUtils from this checkout, so the change only needs to be local.)

3. **Set the licence env and run** — one command per language:
   ```bash
   export INVERSEVIBE_URL=https://<licence-host>
   export INVERSEVIBE_TOKEN=<your benchmark-scoped token>
   compare_owasp_benchmark java    --tool inversevibe
   compare_owasp_benchmark python  --tool inversevibe
   ```
   Each run clones the benchmark fresh, runs the binary over it (handshake →
   decrypt → scan), scores every tool's kept results with BenchmarkUtils, and
   rewrites `leaderboard.html`. InverseVibe lands at #1 — 100.00% (Java),
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
| InverseVibe parses but scores 0 | the `InverseVibeReader` wasn't added to BenchmarkUtils (step 2). |
