# OWASP Benchmark Comparator

Run security tools against the [OWASP Benchmark](https://owasp.org/www-project-benchmark/)
(Java & Python) with one command, and print the scorecard OWASP's own code
produces. Each tool only runs and hands over its own native results; mapping
them to CWEs and every score come from OWASP's BenchmarkUtils, unedited.

*Not affiliated with or endorsed by OWASP. "OWASP" and "OWASP Benchmark" are
names of OWASP Foundation projects.*

## Leaderboard

[`leaderboard.html`](leaderboard.html) ranks every tool run here on each
benchmark, and opens the full OWASP scorecard for a tool when you select it.
OWASP publishes no official leaderboard; this one only puts results side by
side. Open it straight from a clone, or through GitHub Pages (serve the root of
`main`; `index.html` opens it). The scorecards it links live in
[`scorecards/`](scorecards/), all by relative paths.

## Why you can trust the numbers

The three OWASP repositories are submodules at the root, pinned, and never edited:

| Submodule | What it is | Pinned |
|---|---|---|
| [`BenchmarkJava/`](https://github.com/OWASP-Benchmark/BenchmarkJava) | v1.2 - 2,740 cases, 1,415 vulnerable | `20cbf3d` |
| [`BenchmarkPython/`](https://github.com/OWASP-Benchmark/BenchmarkPython) | v0.1 - 1,230 cases, 452 vulnerable | `f129148` |
| [`BenchmarkUtils/`](https://github.com/OWASP-Benchmark/BenchmarkUtils) | the scorer | `beb6ef9` |

Outside them is only orchestration and each tool's runner - nothing maps or
scores. Check it yourself:
`git submodule status` shows the pins, and `git -C BenchmarkJava status` shows
nothing changed.

## Run

```bash
git clone --recurse-submodules --shallow-submodules https://github.com/Inverse-Vibe/OWASP-Benchmark-Comparator.git
cd OWASP-Benchmark-Comparator
pip install -e .
compare_owasp_benchmark java      # or: python
```

For the chosen benchmark, in a fresh clone of its pinned commit under `work/`:

1. BenchmarkUtils is installed from its submodule with `mvn install`, as its
   README says (once per pin).
2. Each tool's script runs and leaves its native results file in `results/`.
3. The benchmark's own `createScorecards.sh` scores the tools just run. Each
   tool runs in its own fresh clone; only its results file is carried into the
   one that is scored, from which the results OWASP ships are first removed.
4. The leaderboard is read off the `Scorecard_Home.html` it writes and printed.
5. `leaderboard.html`'s data block is updated and the scorecard copied to
   `scorecards/<language>/`. `--no-leaderboard` skips this.

`--tool <id>` runs only some tools. Logs go to `work/<language>/logs/`.

Needs bash, git, a JDK and Maven (on PATH, or `--java-home` / `--maven-home`),
plus whatever each tool needs - SonarQube needs Docker, curl and jq.

## Tools

| Tool | Java | Python | How it runs |
|---|---|---|---|
| SonarQube Community Build | ✓ | ✓ | `tools/sonarqube/` - Docker, pinned versions |
| CodeQL | ✓ | ✓ | the benchmark's `translateCodeQL.sh` + `runCodeQL.sh` |
| Semgrep CE | ✓ | ✓ | BenchmarkJava's `runSemgrep.sh`; the same command for Python |
| Bearer | ✓ | ✓ | the benchmark's `runBearer.sh` |
| Precaution | ✓ | ✓ | BenchmarkJava's `runPrecaution.sh`; the same command for Python |
| Bandit | | ✓ | BenchmarkPython's `runBandit.sh` |
| FindSecBugs, SpotBugs, PMD | ✓ | | BenchmarkJava's `runFindSecBugs.sh`, `runSpotBugs.sh`, `runPMD.sh` |
| OpenTaint, ShiftLeft Scan, Insider | ✓ | | BenchmarkJava's own scripts |
| Horusec | ✓ | | `tools/horusec/` - Docker |
| Snyk Code | ✓ | ✓ | BenchmarkJava's `runSnykSAST.sh`; needs `SNYK_TOKEN` |

One folder per tool under [`tools/`](tools/), holding everything it needs:

```
tools/sonarqube/
  tool.toml     its name, and the script it runs on each benchmark
  run.sh        SonarQube Community Build + scanner in Docker, pinned versions
  export.py     the project's issues and hotspots, as the API returns them
```

```toml
name = "Snyk Code"
requires = ["SNYK_TOKEN"]   # skipped, not failed, until it is set
java = "./run.sh"           # "./" = in this folder
python = "./run.sh"         # anything else = a script the benchmark ships
```

A script runs from the root of a fresh clone of the benchmark, with
`BENCHMARK_LANGUAGE`, `BENCHMARK_RESULTS_PREFIX`, `TOOL_DIR` and `TOOL_CACHE`
(kept between runs, for big downloads) set, and must leave a results file in
`results/` in a format a BenchmarkUtils reader accepts. A script that writes
nothing there counts as failed. Where a benchmark ships a script that works as
written, `tool.toml` points straight at it; where it does not, the tool's
`run.sh` says what it changes and why.

**SonarQube** follows `BenchmarkJava/scripts/runSonarQube.sh` with two changes,
both because the original does not work as written: Java is compiled first (the
original scans with no bytecode), and the export is `export.py` rather than
BenchmarkJava's `SonarReport`, which asks for hotspots with a parameter current
SonarQube rejects. The file it writes is the one `SonarReport` writes, read by
BenchmarkUtils' own `SonarQubeJsonReader`.

## How the score works

BenchmarkUtils' score is the Youden index - true-positive rate minus
false-positive rate - **averaged per category, not pooled**, so a category of 15
cases weighs what one of 272 does. Only the number on its scorecard is quoted.
