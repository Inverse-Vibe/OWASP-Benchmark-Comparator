#!/usr/bin/env bash
# Bandit through BenchmarkPython's scripts/runBandit.sh, unchanged. Bandit exits 1
# whenever it finds anything, and that script runs under `set -e`, so it reports
# failure after writing its SARIF. Its exit status is ignored here; whether a
# results file was written decides.

bash scripts/runBandit.sh || true
