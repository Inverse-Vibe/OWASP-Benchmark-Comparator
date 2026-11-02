#!/usr/bin/env bash
# Semgrep (Community Edition) on BenchmarkPython - BenchmarkJava/scripts/runSemgrep.sh
# with the Python results-file name: the same image and the same `p/security-audit`
# ruleset, writing the SARIF that BenchmarkUtils' SemgrepSarifReader reads.

set -euo pipefail
: "${BENCHMARK_RESULTS_PREFIX:?}"

docker pull -q semgrep/semgrep > /dev/null
semgrep_version=$(docker run --rm semgrep/semgrep semgrep --version)
result_file="/src/results/${BENCHMARK_RESULTS_PREFIX}Semgrep-v$semgrep_version.sarif"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "${PWD}:/src" semgrep/semgrep \
  semgrep --config p/security-audit -q --sarif -o "$result_file" . > /dev/null
