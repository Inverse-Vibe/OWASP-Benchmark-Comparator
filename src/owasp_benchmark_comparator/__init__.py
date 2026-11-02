"""Compare security tools on the OWASP Benchmark, using only OWASP's own code.

The benchmarks and their scorer are submodules, pinned and never edited. A tool
runs through the script its benchmark repository ships; the scorecard is made by
that repository's own `createScorecards.sh`. What lives here only clones, runs
and prints - nothing here scans, maps or scores.
"""

__version__ = "0.0.1"
