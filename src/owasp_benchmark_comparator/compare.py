"""`compare_owasp_benchmark <java|python>`: run tools, then OWASP's scorecard.

    compare_owasp_benchmark java                     every tool that runs on Java
    compare_owasp_benchmark java --tool sonarqube    just these

For the chosen benchmark, in a fresh clone of its pinned commit:

1. each tool's script - from its folder under tools/, or one the benchmark
   repository ships - which leaves a results file in `results/`
2. that repository's `createScorecards.sh`, which scores everything in
   `results/` - the tools just run and the reference results OWASP ships

and the leaderboard from the scorecard it writes. Needs bash, git and Maven on
PATH (or --java-home / --maven-home), plus whatever each tool script needs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from owasp_benchmark_comparator import __version__, leaderboard
from owasp_benchmark_comparator.benchmarks import (
    BENCHMARKS,
    ROOT,
    Benchmark,
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


def reference_tools(
    benchmark: Benchmark, clone: Path, work: Path, env: Environment, bash: str, pin: str
) -> set[str]:
    """The rows OWASP's shipped results make on their own, scored once per pin -
    so the page can tell OWASP's reference results from tools run here."""
    cache = work / benchmark.id / f"reference-{pin[:12]}.json"
    if cache.exists():
        return set(json.loads(cache.read_text(encoding="utf-8")))
    print("[reference] scoring the results OWASP ships ...", flush=True)
    rows = scorecard(clone, env, bash, work / benchmark.id / "logs" / "reference.log")
    names = sorted(row.tool for row in rows)
    cache.write_text(json.dumps(names, indent=1), encoding="utf-8")
    return set(names)


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
    reference = reference_tools(benchmark, clone, work, env, bash, pin)
    shipped = snapshot(clone / "results")

    failed = 0
    for tool in tools:
        missing = [name for name in tool.requires if not env.variables.get(name)]
        if missing:
            # Not a failure: a tool that needs an account is optional until given one.
            print(f"[{tool.id}] skipped: set {', '.join(missing)}", flush=True)
            continue
        script = tool.script(benchmark.id, clone)
        print(f"[{tool.id}] {script.relative_to(script.parents[1])} ...", flush=True)
        log = work / benchmark.id / "logs" / f"{tool.id}.log"
        before = snapshot(clone / "results")
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
            env.run([bash, str(script)], clone, log, given)
        except RunError as error:
            print(f"[{tool.id}] FAILED: {error}", file=sys.stderr)
            failed += 1
            continue
        # OWASP's scripts do not stop at the first error, so one can fail midway
        # and still exit 0. A tool that wrote nothing to results/ was not run.
        # Written, not added: Bandit's script rewrites the file OWASP ships.
        if not changed(before, snapshot(clone / "results")):
            print(f"[{tool.id}] FAILED: wrote nothing to results/ - see {log}", file=sys.stderr)
            failed += 1

    print("[scorecard] createScorecards.sh ...", flush=True)
    rows = scorecard(clone, env, bash, work / benchmark.id / "logs" / "scorecard.log")

    print()
    print(render(benchmark.title, rows))
    written = changed(shipped, snapshot(clone / "results"))
    print(f"\n  results from this run: {', '.join(written) or 'none'}")
    print(f"  scorecard: {clone / 'scorecard' / 'Scorecard_Home.html'}")
    if not args.no_leaderboard:
        leaderboard.update(PAGE, benchmark, pin, rows, reference, clone / "scorecard")
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
