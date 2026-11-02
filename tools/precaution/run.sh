#!/usr/bin/env bash
# Precaution (precli) - BenchmarkJava's scripts/runPrecaution.sh, unchanged, with
# precli installed once into a virtualenv in TOOL_CACHE. BenchmarkPython ships no
# Precaution script, so for Python this runs that script's own command.

set -euo pipefail
: "${BENCHMARK_LANGUAGE:?}" "${BENCHMARK_RESULTS_PREFIX:?}" "${TOOL_CACHE:?}"

if [[ ! -x "$TOOL_CACHE/venv/bin/precli" ]]; then
  echo "Installing precli..."
  python3 -m venv "$TOOL_CACHE/venv"
  "$TOOL_CACHE/venv/bin/pip" install -q precli
fi
export PATH="$TOOL_CACHE/venv/bin:$PATH"
precli --version

# precli exits 1 whenever it finds anything; whether a results file was written
# decides.
case "$BENCHMARK_LANGUAGE" in
  java) bash scripts/runPrecaution.sh || true ;;
  python) precli -r . --json -o "results/${BENCHMARK_RESULTS_PREFIX}Precaution.json" || true ;;
  *)
    echo "no Precaution setup for $BENCHMARK_LANGUAGE" >&2
    exit 1
    ;;
esac
