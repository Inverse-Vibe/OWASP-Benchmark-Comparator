#!/usr/bin/env bash
# Horusec CLI on BenchmarkJava, writing the JSON report BenchmarkUtils'
# HorusecReader reads. Its own engine only (-D): otherwise Horusec starts further
# containers from inside its own. Its engine opens every file at once, so the
# container's open-file limit is raised - at the default it stops partway with
# "too many open files" and reports a handful of findings.

set -euo pipefail
: "${BENCHMARK_RESULTS_PREFIX:?}"

image="horuszup/horusec-cli:v2.8.0"
docker pull -q "$image" > /dev/null
result="results/${BENCHMARK_RESULTS_PREFIX}horusec-v2.8.0.json"
docker run --rm --ulimit nofile=65536:65536 --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "${PWD}:/src" -w /src "$image" \
  horusec start -p /src -D -o json -O "/src/$result" \
  -i "**/results/**,**/scorecard/**,**/scripts/**,**/tools/**,**/VMs/**" \
  --information-severity=true --analysis-timeout 3600
test -s "$result"
