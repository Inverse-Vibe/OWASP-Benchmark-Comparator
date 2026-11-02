# OWASP Benchmark Comparator

Run security tools against the [OWASP Benchmark](https://owasp.org/www-project-benchmark/)
(Java & Python) with one command, and print the scorecard OWASP's own code
produces. Nothing here scans, maps or scores: every tool runs through the script
its benchmark repository ships, and every score comes from OWASP's BenchmarkUtils.

*Not affiliated with or endorsed by OWASP. "OWASP" and "OWASP Benchmark" are
names of OWASP Foundation projects.*

## Why you can trust the numbers

The three OWASP repositories are submodules at the root, pinned, and never edited:

| Submodule | What it is | Pinned |
|---|---|---|
| [`BenchmarkJava/`](https://github.com/OWASP-Benchmark/BenchmarkJava) | v1.2 - 2,740 cases, 1,415 vulnerable | `20cbf3d` |
| [`BenchmarkPython/`](https://github.com/OWASP-Benchmark/BenchmarkPython) | v0.1 - 1,230 cases, 452 vulnerable | `f129148` |
| [`BenchmarkUtils/`](https://github.com/OWASP-Benchmark/BenchmarkUtils) | the scorer | `beb6ef9` |

Everything outside them only clones, runs and prints. Check it yourself:
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
2. Each tool runs through its benchmark's own script, e.g.
   `BenchmarkJava/scripts/runSonarQube.sh`, which writes into `results/`.
3. The benchmark's own `createScorecards.sh` scores everything in `results/` -
   the tools just run, beside the reference results OWASP ships.
4. The leaderboard is read off the `Scorecard_Home.html` it writes and printed.

`--tool <id>` runs only some tools. Logs go to `work/<language>/logs/`.

Needs bash, git, a JDK and Maven (on PATH, or `--java-home` / `--maven-home`),
plus whatever each tool's script needs - `runSonarQube.sh` uses Docker.

## Tools

[`tools.toml`](src/owasp_benchmark_comparator/tools.toml) lists them, one entry
per tool naming the script each benchmark ships for it:

```toml
[sonarqube]
name = "SonarQube"
java = "scripts/runSonarQube.sh"
```

A tool is added by adding its entry. A tool with no script in a benchmark
repository is not run on that benchmark. Running a new tool, or scoring one
BenchmarkUtils has no reader for, belongs upstream in OWASP's repositories, so
that it is OWASP's code that runs and scores it.

## How the score works

BenchmarkUtils' score is the Youden index - true-positive rate minus
false-positive rate - **averaged per category, not pooled**, so a category of 15
cases weighs what one of 272 does. Only the number on its scorecard is quoted.
