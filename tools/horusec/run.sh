#!/usr/bin/env bash
# Horusec CLI on the benchmark in the current directory, writing the JSON report
# that BenchmarkUtils' HorusecReader reads. Its own engine only (-D): the
# alternative is Horusec starting further containers from inside its own.

set -euo pipefail
: "${BENCHMARK_RESULTS_PREFIX:?}"

image="horuszup/horusec-cli:latest"
docker pull -q "$image" > /dev/null
version=$(docker run --rm "$image" horusec version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "${PWD}:/src" -w /src "$image" \
  horusec start -p /src -D -o json \
  -O "/src/results/${BENCHMARK_RESULTS_PREFIX}horusec-v${version:-unknown}.json" \
  -i "**/results/**,**/scorecard/**,**/scripts/**,**/tools/**,**/VMs/**" \
  --information-severity=true || true
# Horusec exits non-zero whenever it finds anything; the report decides.
test -s "results/${BENCHMARK_RESULTS_PREFIX}horusec-v${version:-unknown}.json"
