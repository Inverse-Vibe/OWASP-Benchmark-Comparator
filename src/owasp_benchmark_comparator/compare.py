"""`compare_owasp_benchmark <java|python>`: run tools, then OWASP's scorecard.

    compare_owasp_benchmark java                     every tool with a Java script
    compare_owasp_benchmark java --tool sonarqube    just these

For the chosen benchmark, in a fresh clone of its pinned commit:

1. each tool's own script from that repository (`scripts/run<Tool>.sh`)
2. that repository's `createScorecards.sh`, which scores everything in
   `results/` - the tools just run and the reference results OWASP ships

and the leaderboard from the scorecard it writes. Needs bash, git and Maven on
PATH (or --java-home / --maven-home), plus whatever each tool script needs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from owasp_benchmark_comparator import __version__
from owasp_benchmark_comparator.benchmarks import (
    BENCHMARKS,
    ROOT,
    Environment,
    RunError,
    fresh_clone,
    install_scorer,
    load_tools,
)
from owasp_benchmark_comparator.scorecard import leaderboard, render


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
    return parser


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
    fresh_clone(ROOT / benchmark.directory, clone, env)
    shipped = {path.name for path in (clone / "results").iterdir()}

    failed = 0
    for tool in tools:
        print(f"[{tool.id}] {tool.scripts[benchmark.id]} ...", flush=True)
        log = work / benchmark.id / "logs" / f"{tool.id}.log"
        before = {path.name for path in (clone / "results").iterdir()}
        try:
            env.run([bash, tool.scripts[benchmark.id]], clone, log)
        except RunError as error:
            print(f"[{tool.id}] FAILED: {error}", file=sys.stderr)
            failed += 1
            continue
        # OWASP's scripts do not stop at the first error, so one can fail midway
        # and still exit 0. A tool that left nothing in results/ was not run.
        if {path.name for path in (clone / "results").iterdir()} <= before:
            print(f"[{tool.id}] FAILED: wrote nothing to results/ - see {log}", file=sys.stderr)
            failed += 1

    print("[scorecard] createScorecards.sh ...", flush=True)
    env.run([bash, "createScorecards.sh"], clone, work / benchmark.id / "logs" / "scorecard.log")
    home = clone / "scorecard" / "Scorecard_Home.html"
    if not home.exists():
        raise RunError(f"createScorecards.sh wrote no {home}")

    print()
    print(render(benchmark.title, leaderboard(home.read_text(encoding="utf-8"))))
    added = sorted(path.name for path in (clone / "results").iterdir() if path.name not in shipped)
    print(f"\n  results from this run: {', '.join(added) or 'none'}")
    print(f"  scorecard: {home}")
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
