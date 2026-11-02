"""Compare security tools on the OWASP Benchmark, scored only by OWASP's own code.

The benchmarks and their scorer are submodules, pinned and never edited. Each
tool is a folder under tools/ whose script runs it and leaves its native results
file in `results/`; the scorecard is made by the benchmark's own
`createScorecards.sh`, so BenchmarkUtils' readers do every mapping and all the
scoring. Nothing here maps or scores.
"""

__version__ = "0.0.1"
