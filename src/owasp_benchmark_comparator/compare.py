"""`compare_owasp_benchmark <java|python>`: run tools, then OWASP's scorecard.

    compare_owasp_benchmark java                     every tool that runs on Java
    compare_owasp_benchmark java --tool sonarqube    just these

For the chosen benchmark, in fresh clones of its pinned commit:

1. each tool's script - from its folder under tools/, or one the benchmark
   repository ships - in a clone of its own, leaving a results file in `results/`
2. that repository's `createScorecards.sh`, on a clone whose `results/` holds
   just those files - the results OWASP ships are taken out first

and the leaderboard from the scorecard it writes. Needs bash, git and Maven on
PATH (or --java-home / --maven-home), plus whatever each tool script needs.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from owasp_benchmark_comparator import __version__, leaderboard
from owasp_benchmark_comparator.benchmarks import (
    BENCHMARKS,
    ROOT,
    Environment,
    RunError,
    fresh_clone,
    install_scorer,
    load_tools,
    pinned,
)
from owasp_benchmark_comparator.scorecard import Row, read, render

#: The comparison page; its data block is rewritten after every run.
PAGE = ROOT / "leaderboard.html"
#: Not a results file: the benchmark keeps results/ in git with it.
KEEP = frozenset({".placeholder"})


def snapshot(results: Path) -> dict[str, tuple[int, int]]:
    """Each file's size and modification time."""
    return {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in results.iterdir()
        if path.is_file()
    }


def changed(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> list[str]:
    """Files added or rewritten since `before`."""
    return sorted(name for name, stamp in after.items() if before.get(name) != stamp)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compare_owasp_benchmark",
        description="Run tools on an OWASP Benchmark and print its own scorecard.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("language", choices=sorted(BENCHMARKS), help="the benchmark to run")
    parser.add_argument("--tool", action="append", help="only this tool (repeatable)")
    parser.add_argument("--java-home", help="the JDK for Maven (default: JAVA_HOME)")
    parser.add_argument("--maven-home", help="the Maven to use (default: mvn on PATH)")
    parser.add_argument("--work", type=Path, help="where clones and logs go (default: work/)")
    parser.add_argument(
        "--no-leaderboard", action="store_true", help="do not update leaderboard.html"
    )
    return parser


def scorecard(clone: Path, env: Environment, bash: str, log: Path) -> list[Row]:
    """Run the benchmark's own createScorecards.sh and read the leaderboard it writes."""
    env.run([bash, "createScorecards.sh"], clone, log)
    home = clone / "scorecard" / "Scorecard_Home.html"
    if not home.exists():
        raise RunError(f"createScorecards.sh wrote no {home}")
    return read(home)


def compare(args: argparse.Namespace) -> int:
    benchmark = BENCHMARKS[args.language]
    tools = [tool for tool in load_tools() if benchmark.id in tool.scripts]
    if args.tool:
        known = {tool.id for tool in tools}
        unknown = sorted(set(args.tool) - known)
        if unknown:
            there = ", ".join(sorted(known)) or "none"
            raise RunError(f"no {benchmark.id} tool called {', '.join(unknown)}; there is {there}")
        tools = [tool for tool in tools if tool.id in args.tool]

    env = Environment.build(args.java_home, args.maven_home)
    work: Path = (args.work or ROOT / "work").resolve()
    bash = env.which("bash")

    print(f"[scorer] installing {install_scorer(work, env)[:12]} ...", flush=True)
    clone = work / benchmark.id / benchmark.directory
    pin = pinned(ROOT / benchmark.directory, env)
    fresh_clone(ROOT / benchmark.directory, clone, env)
    # Only what is run here is scored: the results OWASP ships in the benchmark
    # come out of this working clone (never the submodule) before scoring.
    for path in (clone / "results").iterdir():
        if path.is_file() and path.name not in KEEP:
            path.unlink()

    store = work / benchmark.id / "results"
    store.mkdir(parents=True, exist_ok=True)
    failed = 0
    carried: list[str] = []
    for tool in tools:
        missing = [name for name in tool.requires if not env.variables.get(name)]
        if missing:
            # Not a failure: a tool that needs an account is optional until given one.
            print(f"[{tool.id}] skipped: set {', '.join(missing)}", flush=True)
            continue
        # Each tool in its own fresh clone: a tool that builds the project leaves
        # target/ behind - owned by root, from a container - and the next tool's
        # build cannot write there. Only its results file is carried over.
        own = work / benchmark.id / "runs" / tool.id / benchmark.directory
        try:
            fresh_clone(ROOT / benchmark.directory, own, env)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"[{tool.id}] FAILED: could not reset {own}: {error}", file=sys.stderr)
            failed += 1
            continue
        script = tool.script(benchmark.id, own)
        print(f"[{tool.id}] {script.relative_to(script.parents[1])} ...", flush=True)
        log = work / benchmark.id / "logs" / f"{tool.id}.log"
        before = snapshot(own / "results")
        cache = work / "cache" / tool.id
        cache.mkdir(parents=True, exist_ok=True)
        given = {
            "BENCHMARK_LANGUAGE": benchmark.id,
            "BENCHMARK_RESULTS_PREFIX": benchmark.results_prefix,
            "TOOL_DIR": str(tool.directory),
            # Kept between runs, for downloads too big to fetch every time.
            "TOOL_CACHE": str(cache),
        }
        try:
            env.run([bash, str(script)], own, log, given)
        except RunError as error:
            print(f"[{tool.id}] FAILED: {error}", file=sys.stderr)
            failed += 1
            continue
        # OWASP's scripts do not stop at the first error, so one can fail midway
        # and still exit 0. A tool that wrote nothing to results/ was not run.
        # Written, not added: Bandit's script rewrites the file OWASP ships.
        written = changed(before, snapshot(own / "results"))
        if not written:
            print(f"[{tool.id}] FAILED: wrote nothing to results/ - see {log}", file=sys.stderr)
            failed += 1
            continue
        # Kept per tool between runs, replacing that tool's previous results: a
        # run of one tool is scored beside the latest of every other.
        kept = store / tool.id
        if kept.exists():
            shutil.rmtree(kept)
        kept.mkdir(parents=True)
        for name in written:
            shutil.copy2(own / "results" / name, kept / name)
            carried.append(name)

    for kept in sorted(path for path in store.iterdir() if path.is_dir()):
        for result in kept.iterdir():
            shutil.copy2(result, clone / "results" / result.name)
    if not any(path.name not in KEEP for path in (clone / "results").iterdir()):
        raise RunError("no tool has written a results file - nothing to score")
    print("[scorecard] createScorecards.sh ...", flush=True)
    rows = scorecard(clone, env, bash, work / benchmark.id / "logs" / "scorecard.log")

    print()
    print(render(benchmark.title, rows))
    print(f"\n  results from this run: {', '.join(sorted(carried)) or 'none'}")
    print(f"  scorecard: {clone / 'scorecard' / 'Scorecard_Home.html'}")
    if not args.no_leaderboard:
        leaderboard.update(PAGE, benchmark, pin, rows, clone / "scorecard")
        print(f"  leaderboard: {PAGE}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return compare(args)
    except RunError as error:
        print(f"compare_owasp_benchmark: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
