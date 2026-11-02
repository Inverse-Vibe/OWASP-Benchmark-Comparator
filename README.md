# OWASP Benchmark Comparator

Run security tools against the [OWASP Benchmark](https://owasp.org/www-project-benchmark/)
(Java & Python) with one command, and print the scorecard OWASP's own code
produces. Each tool only runs and hands over its own native results; mapping
them to CWEs and every score come from OWASP's BenchmarkUtils, unedited.

*Not affiliated with or endorsed by OWASP. "OWASP" and "OWASP Benchmark" are
names of OWASP Foundation projects.*

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
3. The benchmark's own `createScorecards.sh` scores everything in `results/` -
   the tools just run, beside the reference results OWASP ships.
4. The leaderboard is read off the `Scorecard_Home.html` it writes and printed.

`--tool <id>` runs only some tools. Logs go to `work/<language>/logs/`.

Needs bash, git, a JDK and Maven (on PATH, or `--java-home` / `--maven-home`),
plus whatever each tool needs - SonarQube needs Docker, curl and jq.

## Tools

One folder per tool under [`tools/`](tools/), holding everything it needs:

```
tools/sonarqube/
  tool.toml     its name, and the script it runs on each benchmark
  run.sh        SonarQube Community Build + scanner in Docker, pinned versions
  export.py     the project's issues and hotspots, as the API returns them
```

```toml
name = "SonarQube"
java = "./run.sh"       # "./" = in this folder
python = "./run.sh"     # anything else = a script the benchmark ships
```

A script runs from the root of a fresh clone of the benchmark, with
`BENCHMARK_LANGUAGE`, `BENCHMARK_RESULTS_PREFIX` and `TOOL_DIR` set, and must
leave one results file in `results/` in a format a BenchmarkUtils reader
accepts. A script that leaves nothing there counts as failed. Where a benchmark
already ships a working script for a tool, `tool.toml` points at it instead.

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
