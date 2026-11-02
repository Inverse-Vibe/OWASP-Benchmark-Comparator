#!/usr/bin/env bash
# Snyk Code - BenchmarkJava's scripts/runSnykSAST.sh, unchanged, with the snyk CLI
# downloaded once into TOOL_CACHE. BenchmarkPython ships no Snyk script, so for
# Python this runs that script's own command. Authenticates with SNYK_TOKEN.

set -euo pipefail
: "${BENCHMARK_LANGUAGE:?}" "${BENCHMARK_RESULTS_PREFIX:?}" "${TOOL_CACHE:?}" "${SNYK_TOKEN:?}"

if [[ ! -x "$TOOL_CACHE/snyk" ]]; then
  echo "Downloading the Snyk CLI..."
  curl -sSfL -o "$TOOL_CACHE/snyk" https://downloads.snyk.io/cli/stable/snyk-linux
  chmod +x "$TOOL_CACHE/snyk"
fi
export PATH="$TOOL_CACHE:$PATH"
snyk -v

# `snyk code test` exits 1 when it finds anything; the SARIF file decides.
case "$BENCHMARK_LANGUAGE" in
  java) bash scripts/runSnykSAST.sh || true ;;
  python)
    snyk code test \
      "--sarif-file-output=results/${BENCHMARK_RESULTS_PREFIX}snykCodeCli-v$(snyk -v)-$SECONDS.sarif" || true
    ;;
  *)
    echo "no Snyk setup for $BENCHMARK_LANGUAGE" >&2
    exit 1
    ;;
esac
